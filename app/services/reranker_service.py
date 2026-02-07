"""
Cross-Encoder Reranker Service Client

Calls the remote reranker microservice running on Hostinger VPS
to re-score search results for improved relevance.
"""

import logging
import httpx
from typing import Optional, Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Client for the remote cross-encoder reranker service.
    
    The actual cross-encoder model runs on Hostinger VPS to avoid
    loading heavy models in Lambda. Uses ms-marco-MiniLM for reranking.
    """

    def __init__(
        self,
        service_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize reranker service client.
        
        Args:
            service_url: URL of the reranker service (default: from config)
            timeout: Request timeout in seconds
        """
        self.service_url = service_url or settings.RERANKER_SERVICE_URL
        self.timeout = timeout
        self.enabled = settings.RERANKER_ENABLED
        self.default_top_k = settings.RERANKER_TOP_K

        if not self.enabled:
            logger.warning("Reranker service is disabled in config")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Rerank documents based on relevance to query.
        
        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (default: from config)
            
        Returns:
            Dict with 'scores' and 'rankings' (indices of top-K documents)
        """
        if not self.enabled:
            # Return original order with dummy scores
            return {
                "scores": [1.0] * min(len(documents), top_k or self.default_top_k),
                "rankings": list(range(min(len(documents), top_k or self.default_top_k))),
            }

        if not documents:
            return {"scores": [], "rankings": []}

        top_k = top_k or self.default_top_k

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.service_url}/rerank",
                    json={
                        "query": query,
                        "documents": documents,
                        "top_k": top_k,
                    },
                )
                response.raise_for_status()
                result = response.json()
                
                logger.debug(f"Reranked {len(documents)} documents → top {top_k}")
                return result

        except httpx.TimeoutException:
            logger.warning("Reranker service timeout, returning original order")
            return {
                "scores": [1.0] * min(len(documents), top_k),
                "rankings": list(range(min(len(documents), top_k))),
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Reranker service error: {e.response.status_code}")
            return {
                "scores": [1.0] * min(len(documents), top_k),
                "rankings": list(range(min(len(documents), top_k))),
            }
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return {
                "scores": [1.0] * min(len(documents), top_k),
                "rankings": list(range(min(len(documents), top_k))),
            }

    def rerank_with_metadata(
        self,
        query: str,
        results: List[Dict[str, Any]],
        text_key: str = "text",
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results and preserve metadata.
        
        Args:
            query: The search query
            results: List of result dicts with text and metadata
            text_key: Key for the text field in results
            top_k: Number of top results to return
            
        Returns:
            Reranked list of result dicts with added 'rerank_score'
        """
        if not results:
            return []

        # Extract texts for reranking
        documents = [r.get(text_key, "") for r in results]

        # Get reranking
        rerank_result = self.rerank(query, documents, top_k)

        # Rebuild results in new order
        reranked = []
        for i, idx in enumerate(rerank_result["rankings"]):
            if idx < len(results):
                result = results[idx].copy()
                result["rerank_score"] = rerank_result["scores"][i]
                result["original_rank"] = idx
                reranked.append(result)

        return reranked

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the reranker service is healthy.
        
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
_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    """Get or create the global reranker service instance."""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service
