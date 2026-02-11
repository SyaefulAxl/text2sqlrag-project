"""
Configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra environment variables not defined
    )

    # ═══════════════════════════════════════════════════════════════════
    # Application
    # ═══════════════════════════════════════════════════════════════════
    APP_NAME: str = "Texcoms RAG and SQL Services"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    ROOT_PATH: str = ""
    API_SECURITY_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # OpenAI Configuration
    # ═══════════════════════════════════════════════════════════════════
    OPENAI_API_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # Pinecone Configuration (Legacy/Fallback)
    # ═══════════════════════════════════════════════════════════════════
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENV: str = "us-west-2"  # Default
    PINECONE_ENVIRONMENT: Optional[str] = None  # For vector_service.py compatibility
    PINECONE_INDEX_NAME: str = "rag-documents"  # Default index name

    # ═══════════════════════════════════════════════════════════════════
    # Upstash Redis Configuration (Cloud Cache)
    # ═══════════════════════════════════════════════════════════════════
    UPSTASH_REDIS_URL: Optional[str] = None
    UPSTASH_REDIS_TOKEN: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # OPIK Observability
    # ═══════════════════════════════════════════════════════════════════
    OPIK_API_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # Qdrant Vector Database (VPS)
    # ═══════════════════════════════════════════════════════════════════
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_DOCUMENTS: str = "texcoms_documents"  # Renamed
    QDRANT_COLLECTION_RESUMES: str = "texcoms_resumes"  # Renamed

    # ═══════════════════════════════════════════════════════════════════
    # SPLADE Sparse Embedding Service (VPS)
    # ═══════════════════════════════════════════════════════════════════
    SPLADE_SERVICE_URL: str = "http://localhost:8080"
    SPLADE_ENABLED: bool = True

    # ═══════════════════════════════════════════════════════════════════
    # Cross-Encoder Reranker Service (VPS)
    # ═══════════════════════════════════════════════════════════════════
    RERANKER_SERVICE_URL: str = "http://localhost:8081"
    RERANKER_ENABLED: bool = True
    RERANKER_TOP_K: int = 5

    # ═══════════════════════════════════════════════════════════════════
    # PostgreSQL Database (VPS)
    # ═══════════════════════════════════════════════════════════════════
    TEXCOMS_DB_URL: Optional[str] = None  # Renamed from RESUME_DATABASE_URL
    RESUME_DATABASE_URL: Optional[str] = (
        None  # Keeping for backward compat if needed, but pref is TEXCOMS_DB_URL
    )

    @property
    def DATABASE_URL(self) -> Optional[str]:
        return self.TEXCOMS_DB_URL or self.RESUME_DATABASE_URL

    # ═══════════════════════════════════════════════════════════════════
    # Redis/DragonflyDB Cache (VPS)
    # ═══════════════════════════════════════════════════════════════════
    TEXCOMS_REDIS_URL: Optional[str] = None  # Primary cache (Renamed)
    REDIS_URL: Optional[str] = None  # Legacy support (keeping to avoid Pydantic error)
    DRAGONFLY_URL: str = "redis://localhost:6379"

    @property
    def FINAL_REDIS_URL(self) -> str:
        return self.TEXCOMS_REDIS_URL or self.REDIS_URL or self.DRAGONFLY_URL

    # ═══════════════════════════════════════════════════════════════════
    # Langfuse Monitoring (VPS)
    # ═══════════════════════════════════════════════════════════════════
    LANGFUSE_HOST: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # Vanna Text-to-SQL Configuration
    # ═══════════════════════════════════════════════════════════════════
    VANNA_MODEL: str = "gpt-4o"
    VANNA_TEMPERATURE: float = 0.0
    VANNA_TOP_P: float = 0.1
    VANNA_SEED: int = 42
    VANNA_MAX_TOKENS: int = 2000

    # ═══════════════════════════════════════════════════════════════════
    # Text Chunking Configuration
    # ═══════════════════════════════════════════════════════════════════
    CHUNK_SIZE: int = 512
    MIN_CHUNK_SIZE: int = 256
    CHUNK_OVERLAP: int = 50
    EMBEDDING_DIMENSION: int = 1536  # OpenAI text-embedding-3-small

    # ═══════════════════════════════════════════════════════════════════
    # Cache TTL Configuration (seconds)
    # ═══════════════════════════════════════════════════════════════════
    CACHE_TTL_EMBEDDINGS: int = 604800  # 7 days
    CACHE_TTL_RAG: int = 3600  # 1 hour
    CACHE_TTL_SQL_GEN: int = 86400  # 24 hours
    CACHE_TTL_SQL_RESULT: int = 900  # 15 minutes

    # ═══════════════════════════════════════════════════════════════════
    # Resume Service Configuration
    # ═══════════════════════════════════════════════════════════════════
    RESUME_OCR_MODEL: str = "gpt-4o-mini"
    RESUME_ANALYSIS_MODEL: str = "gpt-4o-mini"
    RESUME_STORAGE_PATH: str = "data/resumes"
    RESUME_MAX_CONCURRENT: int = 3  # Max concurrent resume processing

    # ═══════════════════════════════════════════════════════════════════
    # Storage Configuration
    # ═══════════════════════════════════════════════════════════════════
    STORAGE_BACKEND: str = "local"

    @property
    def UPLOAD_DIR(self) -> str:
        if self.ENVIRONMENT == "production" or self.STORAGE_BACKEND == "s3":
            return "/tmp/uploads"
        return "data/uploads"

    @property
    def CACHE_DIR(self) -> str:
        if self.ENVIRONMENT == "production" or self.STORAGE_BACKEND == "s3":
            return "/tmp/cached_chunks"
        return "data/cached_chunks"

    @property
    def is_lambda(self) -> bool:
        """Check if running in AWS Lambda environment."""
        return os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None


# Global settings instance
settings = Settings()
