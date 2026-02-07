"""
Resume Service - Main Orchestrator

Coordinates resume upload, OCR extraction, AI analysis,
storage, and vector indexing.
"""

import logging
import hashlib
import uuid
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO

import psycopg2
from psycopg2.extras import RealDictCursor

# Fix for "This event loop is already running" error in FastAPI
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # nest_asyncio not required if not in async context

from app.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_vector_service import QdrantVectorService
from app.services.sparse_embedding_service import get_splade_service

logger = logging.getLogger(__name__)


class ResumeService:
    """
    Main service for resume processing pipeline.
    
    Pipeline: Upload → OCR → AI Analysis → Store Metadata → Vector Index
    """

    def __init__(self):
        """Initialize resume service with dependencies."""
        self.storage_path = Path(settings.RESUME_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize services
        self.embedding_service = EmbeddingService()
        self.vector_service = QdrantVectorService(
            collection_name=settings.QDRANT_COLLECTION_RESUMES
        )
        self.splade_service = get_splade_service()
        
        # Database connection string
        self.db_url = settings.RESUME_DATABASE_URL
        self._db_available = self._check_db_connection()
        
        if self._db_available:
            logger.info("ResumeService initialized with PostgreSQL")
        else:
            logger.warning("ResumeService initialized WITHOUT database (in-memory only)")

    def process_resume(
        self,
        file: BinaryIO,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a resume through the full pipeline.
        
        Args:
            file: File-like object containing resume
            filename: Original filename
            metadata: Optional additional metadata
            
        Returns:
            Dict with processing results including extracted data
        """
        start_time = datetime.now()
        result = {
            "id": str(uuid.uuid4()),
            "filename": filename,
            "status": "pending",
            "error": None,
            "data": {},
        }

        try:
            # Step 1: Save file
            file_path = self._save_file(file, filename, result["id"])
            result["file_path"] = str(file_path)
            result["file_hash"] = self._compute_hash(file_path)

            # Step 1b: Check for duplicates (same file uploaded before)
            existing = self._check_duplicate(result["file_hash"])
            if existing:
                logger.info(f"Duplicate detected: {filename} matches existing resume {existing['id']}")
                # Clean up the newly saved file
                file_path.unlink(missing_ok=True)
                return {
                    "id": existing["id"],
                    "filename": filename,
                    "status": "duplicate",
                    "duplicate_of": existing["id"],
                    "data": existing.get("data", {}),
                    "message": "File already processed - returning existing data",
                }

            # Step 2: Extract text (OCR if needed)
            from app.services.resume_ocr_service import ResumeOCRService
            ocr_service = ResumeOCRService()
            text, ocr_stats = ocr_service.extract_text(file_path)
            
            if not text or len(text) < 50:
                result["status"] = "failed"
                result["error"] = "Could not extract text from resume"
                return result

            result["extracted_text_length"] = len(text)
            result["ocr_stats"] = ocr_stats

            # Step 3: AI Analysis
            from app.services.resume_analyzer_service import ResumeAnalyzerService
            analyzer = ResumeAnalyzerService()
            analysis_data, analysis_stats = analyzer.analyze(text, filename)
            
            if not analysis_data:
                result["status"] = "failed"
                result["error"] = "AI analysis failed"
                return result

            result["data"] = analysis_data
            result["analysis_stats"] = analysis_stats

            # Step 4: Generate embeddings and index
            indexing_result = self._index_resume(
                resume_id=result["id"],
                text=text,
                metadata={
                    **result["data"],
                    "filename": filename,
                    "file_hash": result["file_hash"],
                },
            )
            result["indexed"] = indexing_result

            # Step 5: Save extracted text as .txt file
            txt_path = self._save_extracted_text(text, result["id"])
            result["txt_path"] = str(txt_path) if txt_path else None

            # Step 6: Store in database (if available)
            db_stored = self._store_in_database(result, text)
            result["stored_in_db"] = db_stored

            result["status"] = "processed"
            result["processing_time_seconds"] = (datetime.now() - start_time).total_seconds()

            # Step 7: Register hash for deduplication
            self._register_hash(result["file_hash"], {
                "id": result["id"],
                "data": result["data"],
                "filename": filename,
            })

            logger.info(f"Resume processed: {filename} in {result['processing_time_seconds']:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Resume processing failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            
            # Store failed result in DB for tracking
            try:
                self._store_failed_resume(result, str(e))
            except:
                pass
                
            return result

    def _save_file(
        self,
        file: BinaryIO,
        filename: str,
        resume_id: str,
    ) -> Path:
        """Save uploaded file to storage."""
        # Create subdirectory by date
        date_dir = self.storage_path / datetime.now().strftime("%Y-%m")
        date_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        ext = Path(filename).suffix
        safe_filename = f"{resume_id}{ext}"
        file_path = date_dir / safe_filename

        # Write file
        content = file.read()
        file_path.write_bytes(content)
        
        logger.debug(f"Saved resume to {file_path}")
        return file_path

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file for deduplication."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _check_duplicate(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Check if a resume with this hash was already processed.
        
        Uses in-memory registry for now.
        TODO: Replace with database lookup when RESUME_DATABASE_URL is configured.
        """
        if not hasattr(self, '_hash_registry'):
            self._hash_registry = {}
        
        return self._hash_registry.get(file_hash)

    def _register_hash(self, file_hash: str, resume_data: Dict[str, Any]):
        """Register a processed resume hash."""
        if not hasattr(self, '_hash_registry'):
            self._hash_registry = {}
        
        self._hash_registry[file_hash] = resume_data

    def _index_resume(
        self,
        resume_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate embeddings and index in Qdrant."""
        try:
            # Ensure collection exists
            self.vector_service.create_collection()

            # Generate dense embedding (async method - use nest_asyncio compatible approach)
            loop = asyncio.get_event_loop()
            embeddings, _ = loop.run_until_complete(
                self.embedding_service.generate_embeddings([text])
            )
            dense_vector = embeddings[0] if embeddings else None
            
            if not dense_vector:
                raise ValueError("Failed to generate embedding")

            # Generate sparse embedding (if SPLADE available)
            sparse_vector = self.splade_service.encode(text)

            # Index in Qdrant
            self.vector_service.upsert_documents(
                ids=[resume_id],
                dense_vectors=[dense_vector],
                sparse_vectors=[sparse_vector] if sparse_vector else None,
                metadatas=[metadata],
            )

            return {"success": True, "has_sparse": sparse_vector is not None}

        except Exception as e:
            logger.error(f"Resume indexing failed: {e}")
            return {"success": False, "error": str(e)}

    def search_resumes(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across resumes.
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Optional metadata filters
            
        Returns:
            List of matching resumes with scores
        """
        try:
            # Generate query embeddings (async method - use nest_asyncio compatible approach)
            loop = asyncio.get_event_loop()
            embeddings, _ = loop.run_until_complete(
                self.embedding_service.generate_embeddings([query])
            )
            query_dense = embeddings[0] if embeddings else None
            
            if not query_dense:
                raise ValueError("Failed to generate query embedding")
            
            query_sparse = self.splade_service.encode(query)

            # Search
            results = self.vector_service.hybrid_search(
                query_dense=query_dense,
                query_sparse=query_sparse,
                top_k=top_k,
                filter_conditions=filters,
            )

            return results

        except Exception as e:
            logger.error(f"Resume search failed: {e}")
            return []

    def get_resume(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """Get resume by ID from database with all 53 columns."""
        if not self._db_available:
            # Check in-memory registry
            for data in getattr(self, '_hash_registry', {}).values():
                if data.get('id') == resume_id:
                    return data
            return None
            
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    id, filename, file_hash, file_path, status, created_at, updated_at,
                    extracted_text_length, processing_time_seconds, error_message,
                    name, country_code, contact_number, email_id, age, current_location, languages_known,
                    education_qualification, specialization, certifications,
                    experience, experience_years, experience_months, current_organisation, current_designation,
                    category, department, division, functions,
                    machines_brands, machines_model, skills, raw_material_expertise, plant_scale_capacity,
                    summarize, vote, consideration, raw_ai_response,
                    roles, preferred_location_1, preferred_location_2, primary_expertise, secondary_expertise,
                    currency, current_ctc, expected_ctc, notice_period, referred_by, source,
                    remarks, lead_status, date_of_calling
                FROM resumes WHERE id::text = %s
            """, (resume_id,))
            
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row:
                result = dict(row)
                # Convert UUID to string
                result['id'] = str(result['id'])
                return result
            return None
            
        except Exception as e:
            logger.error(f"Database lookup failed: {e}")
            return None

    def list_resumes(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List resumes with pagination."""
        if not self._db_available:
            return {
                "items": list(getattr(self, '_hash_registry', {}).values()),
                "total": len(getattr(self, '_hash_registry', {})),
                "skip": skip,
                "limit": limit,
            }
            
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query
            where_clause = ""
            params = []
            if status:
                where_clause = "WHERE status = %s"
                params.append(status)
            
            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM resumes {where_clause}", params)
            total = cursor.fetchone()['count']
            
            # Get paginated results
            cursor.execute(f"""
                SELECT id, filename, name, email_id, contact_number,
                       experience_years, current_organisation, current_designation,
                       category, vote, lead_status, status, created_at
                FROM resumes {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, skip])
            
            items = []
            for row in cursor.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])  # Convert UUID
                items.append(item)
            cursor.close()
            conn.close()
            
            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
            
        except Exception as e:
            logger.error(f"Database list failed: {e}")
            return {
                "items": [],
                "total": 0,
                "skip": skip,
                "limit": limit,
                "error": str(e),
            }
    
    def _check_db_connection(self) -> bool:
        """Check if database is available."""
        if not self.db_url:
            return False
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=5)
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Database not available: {e}")
            return False
    
    def _store_in_database(self, result: Dict[str, Any], text: str) -> bool:
        """Store resume data in PostgreSQL with full metrics."""
        if not self._db_available:
            return False
            
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            data = result.get('data', {})
            ocr_stats = result.get('ocr_stats', {})
            analysis_stats = result.get('analysis_stats', {})
            
            # Parse experience to years and months
            exp_years, exp_months = self._parse_experience(data.get('experience', ''))
            
            # Helper to safely convert to JSON
            def to_json(val):
                if val is None:
                    return None
                if isinstance(val, (dict, list)):
                    return json.dumps(val, ensure_ascii=False)
                return str(val) if val else None
            
            cursor.execute("""
                INSERT INTO resumes (
                    -- System fields
                    id, filename, file_hash, file_path, status,
                    extracted_text_length, total_processing_seconds, extracted_text,
                    
                    -- OCR Metrics
                    ocr_method, ocr_duration_seconds, ocr_input_tokens, ocr_output_tokens, ocr_cost_usd,
                    
                    -- Analysis Metrics
                    analysis_duration_seconds, analysis_input_tokens, analysis_output_tokens, analysis_cost_usd,
                    
                    -- AI: Personal
                    name, country_code, contact_number, email_id, age, current_location, languages_known,
                    
                    -- AI: Education (JSON fields)
                    education_qualification, specialization, certifications,
                    
                    -- AI: Experience
                    experience, experience_years, experience_months, current_organisation, current_designation,
                    
                    -- AI: Textile Classification (JSON fields)
                    category, candidate_type, department, division, functions,
                    
                    -- AI: Technical (JSON fields)
                    machines_brands, machines_model, skills, raw_material_expertise, plant_scale_capacity,
                    
                    -- AI: Assessment
                    summarize, vote, consideration, raw_ai_response
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    updated_at = NOW(),
                    status = EXCLUDED.status,
                    raw_ai_response = EXCLUDED.raw_ai_response
            """, (
                # System fields
                result['id'],
                result['filename'],
                result.get('file_hash'),
                result.get('file_path'),
                result.get('status', 'processed'),
                result.get('extracted_text_length'),
                result.get('processing_time_seconds'),
                text[:100000] if text else None,
                
                # OCR Metrics
                ocr_stats.get('method'),
                ocr_stats.get('duration_seconds'),
                ocr_stats.get('input_tokens', 0),
                ocr_stats.get('output_tokens', 0),
                ocr_stats.get('cost_usd', 0.0),
                
                # Analysis Metrics
                analysis_stats.get('duration_seconds'),
                analysis_stats.get('prompt_tokens', 0),
                analysis_stats.get('completion_tokens', 0),
                analysis_stats.get('cost_usd', 0.0),
                
                # AI: Personal
                data.get('name'),
                data.get('country_code'),
                data.get('contact_number'),
                data.get('email_id'),
                data.get('age'),
                data.get('current_location'),
                to_json(data.get('languages_known', [])),
                
                # AI: Education (FIXED: use json.dumps)
                to_json(data.get('education_qualification')),
                data.get('specialization'),
                to_json(data.get('certifications', [])),
                
                # AI: Experience
                data.get('experience'),
                exp_years,
                exp_months,
                data.get('current_organisation'),
                data.get('current_designation'),
                
                # AI: Textile Classification
                data.get('category'),
                self._determine_candidate_type(data),  # NEW: AI-determined candidate type
                to_json(data.get('department', [])),
                to_json(data.get('division', [])),
                to_json(data.get('functions', [])),
                
                # AI: Technical
                to_json(data.get('machines_brands', [])),
                to_json(data.get('machines_model', [])),
                to_json(data.get('skills', [])),
                to_json(data.get('raw_material_expertise', [])),
                data.get('plant_scale_capacity'),
                
                # AI: Assessment
                data.get('summarize'),
                min(data.get('vote', 3), 5) if data.get('vote') else None,
                data.get('consideration'),
                json.dumps(data, ensure_ascii=False),
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Resume stored in database: {result['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
            return False
    
    def _determine_candidate_type(self, data: Dict[str, Any]) -> str:
        """Determine candidate type based on extracted data."""
        # Check for textile-specific indicators
        textile_departments = {'spinning', 'weaving', 'knitting', 'dyeing', 'processing', 'garment'}
        textile_machines = {'rieter', 'toyota', 'picanol', 'truetzschler', 'marzoli', 'saurer'}
        
        departments = [d.lower() for d in data.get('department', [])]
        machines = [m.lower() for m in data.get('machines_brands', [])]
        category = (data.get('category') or '').lower()
        
        # Check for textile
        is_textile = (
            any(d in textile_departments for d in departments) or
            any(m in textile_machines for m in machines) or
            'textile' in str(data.get('education_qualification', '')).lower()
        )
        
        # Check for technical vs non-technical
        is_technical = category != 'commercial' and (
            departments or machines or
            any(f in str(data.get('functions', [])).lower() for f in ['production', 'quality', 'maintenance'])
        )
        
        if is_textile and is_technical:
            return 'textile'
        elif is_textile and not is_technical:
            return 'non-technical'
        elif is_technical:
            return 'technical'
        else:
            return 'non-textile'
    
    def _store_failed_resume(self, result: Dict[str, Any], error: str) -> bool:
        """Store failed resume attempt for tracking."""
        if not self._db_available:
            return False
            
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO resumes (id, filename, file_hash, file_path, status, error_message)
                VALUES (%s, %s, %s, %s, 'failed', %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = 'failed',
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
            """, (
                result['id'],
                result['filename'],
                result.get('file_hash'),
                result.get('file_path'),
                error[:1000],
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except:
            return False
    
    def _parse_experience(self, exp_str: str) -> tuple:
        """Parse experience string to (years, months) tuple."""
        if not exp_str:
            return (None, 0)
        try:
            import re
            years_match = re.search(r'(\d+)\s*years?', exp_str, re.IGNORECASE)
            months_match = re.search(r'(\d+)\s*months?', exp_str, re.IGNORECASE)
            
            years = int(years_match.group(1)) if years_match else None
            months = int(months_match.group(1)) if months_match else 0
            
            return (years, months)
        except:
            return (None, 0)
    
    def _parse_experience_years(self, exp_str: str) -> Optional[int]:
        """Parse experience string to years integer (legacy compat)."""
        years, _ = self._parse_experience(exp_str)
        return years
    
    def _save_extracted_text(self, text: str, resume_id: str) -> Optional[Path]:
        """Save extracted text as .txt file."""
        try:
            date_dir = self.storage_path / datetime.now().strftime("%Y-%m")
            date_dir.mkdir(parents=True, exist_ok=True)
            
            txt_path = date_dir / f"{resume_id}_extracted.txt"
            txt_path.write_text(text, encoding='utf-8')
            
            logger.debug(f"Saved extracted text to {txt_path}")
            return txt_path
        except Exception as e:
            logger.error(f"Failed to save extracted text: {e}")
            return None
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database health status."""
        if not self.db_url:
            return {"status": "disabled", "message": "RESUME_DATABASE_URL not configured"}
            
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM resumes")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return {
                "status": "healthy",
                "resume_count": count,
                "database": "texcoms_rag",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global instance
_resume_service: Optional[ResumeService] = None


def get_resume_service() -> ResumeService:
    """Get or create the global resume service instance."""
    global _resume_service
    if _resume_service is None:
        _resume_service = ResumeService()
    return _resume_service
