"""
SPLADE Sparse Embedding Service Client

Calls the remote SPLADE microservice running on Hostinger VPS
to generate sparse vectors for hybrid search.
"""

import logging
import httpx
from typing import Optional, Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)


class SpladeEmbeddingService:
    """
    Client for the remote SPLADE sparse embedding service.
    
    The actual SPLADE model runs on Hostinger VPS to avoid
    loading heavy PyTorch models in Lambda.
    """

    def __init__(
        self,
        service_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize SPLADE service client.
        
        Args:
            service_url: URL of the SPLADE service (default: from config)
            timeout: Request timeout in seconds
        """
        self.service_url = service_url or settings.SPLADE_SERVICE_URL
        self.timeout = timeout
        self.enabled = settings.SPLADE_ENABLED

        if not self.enabled:
            logger.warning("SPLADE service is disabled in config")

    def encode(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Generate sparse vector for a single text.
        
        Args:
            text: Input text to encode
            
        Returns:
            Sparse vector dict: {"indices": [...], "values": [...]}
            None if service is disabled or fails
        """
        if not self.enabled:
            return None

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.service_url}/encode",
                    json={"text": text},
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.warning(f"SPLADE service timeout for text: {text[:50]}...")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"SPLADE service error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"SPLADE encoding failed: {e}")
            return None

    def encode_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Generate sparse vectors for multiple texts.
        
        Args:
            texts: List of input texts
            batch_size: Number of texts per batch request
            
        Returns:
            List of sparse vectors (None for failed encodings)
        """
        if not self.enabled:
            return [None] * len(texts)

        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = []
            
            for text in batch:
                sparse_vec = self.encode(text)
                batch_results.append(sparse_vec)
            
            results.extend(batch_results)

        logger.info(f"Encoded {len(texts)} texts with SPLADE")
        return results

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the SPLADE service is healthy.
        
        Returns:
            Health status dict
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.service_url}/health")
                response.raise_for_status()
                return response.json()

        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global instance for convenience
_splade_service: Optional[SpladeEmbeddingService] = None


def get_splade_service() -> SpladeEmbeddingService:
    """Get or create the global SPLADE service instance."""
    global _splade_service
    if _splade_service is None:
        _splade_service = SpladeEmbeddingService()
    return _splade_service
