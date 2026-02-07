"""
DragonflyDB Cache Service

Redis-compatible caching using DragonflyDB on Hostinger VPS.
Replaces Upstash Redis for query-level caching.
"""

import logging
import json
import hashlib
from typing import Optional, Any
import redis

from app.config import settings

logger = logging.getLogger(__name__)


class DragonflyCache:
    """
    Redis-compatible cache using DragonflyDB.
    
    DragonflyDB is a drop-in Redis replacement with better performance
    and memory efficiency. Runs on Hostinger VPS.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        default_ttl: int = 3600,
    ):
        """
        Initialize DragonflyDB client.
        
        Args:
            url: Redis URL (default: from config)
            default_ttl: Default TTL in seconds
        """
        self.url = url or settings.DRAGONFLY_URL
        self.default_ttl = default_ttl
        self.client: Optional[redis.Redis] = None

        try:
            self.client = redis.from_url(
                self.url,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # Test connection
            self.client.ping()
            logger.info(f"DragonflyDB connected: {self.url}")
        except Exception as e:
            logger.warning(f"DragonflyDB connection failed: {e}")
            self.client = None

    @property
    def is_available(self) -> bool:
        """Check if cache is available."""
        return self.client is not None

    def _make_key(self, prefix: str, *args) -> str:
        """Generate a cache key from prefix and arguments."""
        key_data = json.dumps(args, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"{prefix}:{key_hash}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.client:
            return None

        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: TTL in seconds (default: default_ttl)
            
        Returns:
            True if successful
        """
        if not self.client:
            return False

        try:
            serialized = json.dumps(value, default=str)
            self.client.setex(key, ttl or self.default_ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.client:
            return False

        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern.
        
        Args:
            pattern: Redis pattern (e.g., "embedding:*")
            
        Returns:
            Number of deleted keys
        """
        if not self.client:
            return 0

        try:
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern failed: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════
    # Convenience methods for specific cache types
    # ═══════════════════════════════════════════════════════════════════

    def cache_embedding(self, text: str, embedding: list) -> bool:
        """Cache an embedding."""
        key = self._make_key("emb", text)
        return self.set(key, embedding, ttl=settings.CACHE_TTL_EMBEDDINGS)

    def get_embedding(self, text: str) -> Optional[list]:
        """Get cached embedding."""
        key = self._make_key("emb", text)
        return self.get(key)

    def cache_rag_result(self, query: str, result: dict) -> bool:
        """Cache a RAG query result."""
        key = self._make_key("rag", query)
        return self.set(key, result, ttl=settings.CACHE_TTL_RAG)

    def get_rag_result(self, query: str) -> Optional[dict]:
        """Get cached RAG result."""
        key = self._make_key("rag", query)
        return self.get(key)

    def cache_sql_query(self, question: str, sql: str) -> bool:
        """Cache generated SQL."""
        key = self._make_key("sql", question)
        return self.set(key, {"sql": sql}, ttl=settings.CACHE_TTL_SQL_GEN)

    def get_sql_query(self, question: str) -> Optional[str]:
        """Get cached SQL query."""
        key = self._make_key("sql", question)
        result = self.get(key)
        return result["sql"] if result else None

    def health_check(self) -> dict:
        """Check cache health."""
        if not self.client:
            return {"status": "disconnected"}

        try:
            info = self.client.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "keys": self.client.dbsize(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global instance
_cache: Optional[DragonflyCache] = None


def get_cache() -> DragonflyCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = DragonflyCache()
    return _cache
