"""
Resume API Router

Endpoints for resume upload, processing, and search.
Includes LLM-powered intent parsing and request queue.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import Optional
from datetime import datetime
import logging

from app.services.resume_service import get_resume_service
from app.services.resume_query_service import get_query_service
from app.services.queue_service import get_processing_queue
from app.utils import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["Resumes"])


# ═══════════════════════════════════════════════════════════════════
# Health & Queue Status
# ═══════════════════════════════════════════════════════════════════

@router.get("/health", status_code=status.HTTP_200_OK)
async def resume_service_health():
    """Health check for resume service and its dependencies."""
    from app.services.sparse_embedding_service import get_splade_service
    from app.services.reranker_service import get_reranker_service
    from app.services.qdrant_vector_service import QdrantVectorService
    from app.config import settings

    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
    }

    # Check SPLADE
    try:
        splade = get_splade_service()
        health["services"]["splade"] = splade.health_check()
    except Exception as e:
        health["services"]["splade"] = {"status": "error", "message": str(e)}

    # Check Reranker
    try:
        reranker = get_reranker_service()
        health["services"]["reranker"] = reranker.health_check()
    except Exception as e:
        health["services"]["reranker"] = {"status": "error", "message": str(e)}

    # Check Qdrant
    try:
        qdrant = QdrantVectorService(collection_name=settings.QDRANT_COLLECTION_RESUMES)
        health["services"]["qdrant"] = qdrant.get_collection_stats()
    except Exception as e:
        health["services"]["qdrant"] = {"status": "error", "message": str(e)}

    # Check PostgreSQL
    try:
        resume_service = get_resume_service()
        health["services"]["database"] = resume_service.check_database_health()
    except Exception as e:
        health["services"]["database"] = {"status": "error", "message": str(e)}

    # Check queue
    queue = get_processing_queue()
    health["queue"] = queue.get_queue_info()

    errors = [s for s in health["services"].values() if s.get("status") == "error"]
    if errors:
        health["status"] = "degraded"

    return health


@router.get("/queue", status_code=status.HTTP_200_OK)
async def get_queue_status():
    """Get current queue status."""
    queue = get_processing_queue()
    return queue.get_queue_info()


# ═══════════════════════════════════════════════════════════════════
# Upload with Queue
# ═══════════════════════════════════════════════════════════════════

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload and process a resume file.
    
    Pipeline: Queue → Save → OCR/Extract → AI Analysis → Vector Index → Database
    
    If queue is full (>3 concurrent), request is queued.
    
    Returns: Resume processing results with OCR/Analysis metrics.
    """
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain", "image/png", "image/jpeg"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.validation_error(
                f"Unsupported file type: {file.content_type}",
                field="file"
            )
        )

    try:
        resume_service = get_resume_service()
        
        # Read file content (needed for sync processing)
        content = await file.read()
        
        # Process directly (queue handles concurrency internally via semaphore)
        import io
        result = resume_service.process_resume(
            file=io.BytesIO(content),
            filename=file.filename,
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Resume processing failed",
                    "message": result.get("error", "Unknown error"),
                    "filename": file.filename,
                }
            )

        # Build response with detailed metrics
        ocr_stats = result.get("ocr_stats", {})
        analysis_stats = result.get("analysis_stats", {})
        
        return {
            "status": "success",
            "resume_id": result["id"],
            "filename": result["filename"],
            
            # Storage locations
            "storage": {
                "file_path": result.get("file_path"),
                "txt_path": result.get("txt_path"),
                "vector_indexed": result.get("indexed", False),
                "database_stored": result.get("stored_in_db", False),
            },
            
            # Candidate info
            "candidate": {
                "name": result["data"].get("name"),
                "email": result["data"].get("email_id"),
                "phone": result["data"].get("contact_number"),
                "experience": result["data"].get("experience"),
                "current_org": result["data"].get("current_organisation"),
                "designation": result["data"].get("current_designation"),
                "candidate_type": result["data"].get("candidate_type"),
            },
            
            # AI analysis results
            "analysis": {
                "category": result["data"].get("category"),
                "vote": result["data"].get("vote"),
                "summary": result["data"].get("summarize"),
                "consideration": result["data"].get("consideration"),
            },
            
            # OCR Metrics
            "ocr_metrics": {
                "method": ocr_stats.get("method"),
                "duration_seconds": ocr_stats.get("duration_seconds", 0),
                "input_tokens": ocr_stats.get("input_tokens", 0),
                "output_tokens": ocr_stats.get("output_tokens", 0),
                "cost_usd": ocr_stats.get("cost_usd", 0),
            },
            
            # Analysis Metrics
            "analysis_metrics": {
                "duration_seconds": analysis_stats.get("duration_seconds", 0),
                "prompt_tokens": analysis_stats.get("prompt_tokens", 0),
                "completion_tokens": analysis_stats.get("completion_tokens", 0),
                "total_tokens": analysis_stats.get("total_tokens", 0),
                "cost_usd": analysis_stats.get("cost_usd", 0),
            },
            
            # Total Processing Time
            "total_processing_seconds": result.get("processing_time_seconds"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.internal_error("upload resume", e)
        )


# ═══════════════════════════════════════════════════════════════════
# Smart Search with Intent Parsing
# ═══════════════════════════════════════════════════════════════════

@router.post("/search", status_code=status.HTTP_200_OK)
async def search_resumes(
    query: str,
    top_k: int = 10,
    department: Optional[str] = None,
    min_experience: Optional[int] = None,
):
    """
    Smart search across resumes with LLM intent detection.
    
    Query is analyzed to determine intent:
    - "resume_search": Vector similarity search for candidates
    - "sql_query": SQL analytics query (counts, aggregations)
    - "chat": Conversational response
    
    Args:
        query: Natural language search query
        top_k: Number of results for resume search
        
    Returns:
        Appropriate response based on query intent
    """
    if len(query) < 2:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse.validation_error("Query too short", field="query")
        )

    try:
        # Step 1: Parse intent
        query_service = get_query_service()
        parsed = query_service.parse_query(query)
        
        intent = parsed.get("intent")
        confidence = parsed.get("confidence", 0)

        # Step 2: Route based on intent
        if intent == "resume_search":
            # Vector search
            resume_service = get_resume_service()
            
            # Merge parsed filters with explicit filters
            filters = query_service.get_search_filters(parsed)
            if department:
                filters["department"] = department
                
            results = resume_service.search_resumes(
                query=query,
                top_k=top_k,
                filters=filters if filters else None,
            )

            return {
                "status": "success",
                "intent": intent,
                "confidence": confidence,
                "query": query,
                "filters_applied": filters,
                "total_results": len(results),
                "results": results,
            }

        elif intent == "sql_query":
            # SQL analytics (via Vanna or direct)
            sql_description = query_service.get_sql_description(parsed)
            
            # TODO: Integrate with Vanna AI for SQL generation
            return {
                "status": "success",
                "intent": intent,
                "confidence": confidence,
                "query": query,
                "sql_description": sql_description,
                "message": "SQL analytics coming soon. Use resume_search for now.",
            }

        else:  # chat or null
            chat_response = query_service.get_chat_response(parsed)
            return {
                "status": "success",
                "intent": intent,
                "confidence": confidence,
                "query": query,
                "message": chat_response,
            }

    except Exception as e:
        logger.error(f"Resume search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.internal_error("search resumes", e)
        )


# ═══════════════════════════════════════════════════════════════════
# List & Get
# ═══════════════════════════════════════════════════════════════════

@router.get("", status_code=status.HTTP_200_OK)
async def list_resumes(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
):
    """List all processed resumes with pagination."""
    if limit > 100:
        limit = 100

    try:
        resume_service = get_resume_service()
        result = resume_service.list_resumes(
            skip=skip,
            limit=limit,
            status=status_filter,
        )
        return {"status": "success", **result}

    except Exception as e:
        logger.error(f"List resumes failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.internal_error("list resumes", e)
        )


@router.get("/{resume_id}", status_code=status.HTTP_200_OK)
async def get_resume(resume_id: str):
    """Get a specific resume by ID."""
    try:
        resume_service = get_resume_service()
        result = resume_service.get_resume(resume_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Resume not found: {resume_id}"
            )

        return {"status": "success", "resume": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get resume failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse.internal_error("get resume", e)
        )
