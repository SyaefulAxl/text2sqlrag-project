"""
Qdrant Vector Service - Hybrid Search (Dense + Sparse)

Replaces Pinecone with Qdrant for vector storage and retrieval.
Supports hybrid search using OpenAI embeddings (dense) + SPLADE (sparse).
"""

import logging
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    PointStruct,
    SparseVector,
    SearchRequest,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import settings

logger = logging.getLogger(__name__)


class QdrantVectorService:
    """
    Qdrant-based vector service with hybrid search support.
    
    Features:
    - Dense vectors (OpenAI embeddings)
    - Sparse vectors (SPLADE)
    - Hybrid search with RRF (Reciprocal Rank Fusion)
    - Metadata filtering
    """

    DENSE_VECTOR_NAME = "dense"
    SPARSE_VECTOR_NAME = "sparse"
    DENSE_DIMENSION = 1536  # OpenAI text-embedding-3-small

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """Initialize Qdrant client."""
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_DOCUMENTS

        # Initialize client
        if self.api_key:
            # Suppress warning for insecure connection (VPS is behind firewall)
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
                self.client = QdrantClient(url=self.url, api_key=self.api_key)
        else:
            self.client = QdrantClient(url=self.url)

        logger.info(f"Qdrant client initialized: {self.url}")

    def create_collection(self, recreate: bool = False) -> bool:
        """
        Create collection with dense + sparse vector configuration.
        
        Args:
            recreate: If True, delete existing collection and recreate
            
        Returns:
            True if collection was created/exists
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if exists and not recreate:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return True

            if exists and recreate:
                logger.warning(f"Deleting existing collection '{self.collection_name}'")
                self.client.delete_collection(self.collection_name)

            # Create collection with hybrid vectors
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    self.DENSE_VECTOR_NAME: VectorParams(
                        size=self.DENSE_DIMENSION,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    self.SPARSE_VECTOR_NAME: SparseVectorParams()
                },
            )

            logger.info(f"Created collection '{self.collection_name}' with hybrid vectors")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def upsert_documents(
        self,
        ids: List[str],
        dense_vectors: List[List[float]],
        sparse_vectors: Optional[List[Dict[str, Any]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Upsert documents with dense and optionally sparse vectors.
        
        Args:
            ids: Document IDs
            dense_vectors: Dense embedding vectors (from OpenAI)
            sparse_vectors: Optional sparse vectors (from SPLADE) 
                           Format: [{"indices": [1, 5, 10], "values": [0.5, 0.3, 0.8]}, ...]
            metadatas: Optional metadata for each document
            
        Returns:
            Number of documents upserted
        """
        try:
            points = []
            for i, doc_id in enumerate(ids):
                # Build vector dict
                vectors = {
                    self.DENSE_VECTOR_NAME: dense_vectors[i]
                }

                # Add sparse vector if provided
                if sparse_vectors and i < len(sparse_vectors):
                    sv = sparse_vectors[i]
                    if sv and sv.get("indices") and sv.get("values"):
                        vectors[self.SPARSE_VECTOR_NAME] = SparseVector(
                            indices=sv["indices"],
                            values=sv["values"],
                        )

                # Build payload
                payload = metadatas[i] if metadatas and i < len(metadatas) else {}

                points.append(
                    PointStruct(
                        id=doc_id,
                        vector=vectors,
                        payload=payload,
                    )
                )

            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )

            logger.info(f"Upserted {len(points)} documents to '{self.collection_name}'")
            return len(points)

        except Exception as e:
            logger.error(f"Failed to upsert documents: {e}")
            raise

    def hybrid_search(
        self,
        query_dense: List[float],
        query_sparse: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using dense + sparse vectors.
        Uses RRF (Reciprocal Rank Fusion) to combine results.
        
        Args:
            query_dense: Dense query vector (from OpenAI)
            query_sparse: Optional sparse query vector (from SPLADE)
            top_k: Number of results to return
            filter_conditions: Optional metadata filters
                              Format: {"field": "value"} or {"field": {"$gte": 1}}
            
        Returns:
            List of search results with scores and metadata
        """
        try:
            # Build filter if provided
            qdrant_filter = None
            if filter_conditions:
                conditions = []
                for field, value in filter_conditions.items():
                    if isinstance(value, dict):
                        # Range filter
                        conditions.append(
                            FieldCondition(
                                key=field,
                                range=models.Range(**value),
                            )
                        )
                    else:
                        # Exact match
                        conditions.append(
                            FieldCondition(
                                key=field,
                                match=MatchValue(value=value),
                            )
                        )
                qdrant_filter = Filter(must=conditions)

            # Prepare search requests for hybrid search
            prefetch = []

            # Dense search prefetch
            prefetch.append(
                models.Prefetch(
                    query=query_dense,
                    using=self.DENSE_VECTOR_NAME,
                    limit=top_k * 2,  # Get more for RRF fusion
                    filter=qdrant_filter,
                )
            )

            # Sparse search prefetch (if sparse vector provided)
            if query_sparse and query_sparse.get("indices") and query_sparse.get("values"):
                prefetch.append(
                    models.Prefetch(
                        query=SparseVector(
                            indices=query_sparse["indices"],
                            values=query_sparse["values"],
                        ),
                        using=self.SPARSE_VECTOR_NAME,
                        limit=top_k * 2,
                        filter=qdrant_filter,
                    )
                )

            # Execute hybrid search with RRF fusion
            if len(prefetch) > 1:
                # Hybrid search
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=prefetch,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=top_k,
                )
            else:
                # Dense-only search
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_dense,
                    using=self.DENSE_VECTOR_NAME,
                    limit=top_k,
                    query_filter=qdrant_filter,
                )

            # Format results
            formatted = []
            for point in results.points:
                formatted.append({
                    "id": str(point.id),
                    "score": point.score,
                    "metadata": point.payload or {},
                })

            logger.debug(f"Hybrid search returned {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise

    def dense_search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform dense-only search (fallback when SPLADE is unavailable).
        
        Args:
            query_vector: Dense query vector
            top_k: Number of results
            filter_conditions: Optional filters
            
        Returns:
            List of search results
        """
        return self.hybrid_search(
            query_dense=query_vector,
            query_sparse=None,
            top_k=top_k,
            filter_conditions=filter_conditions,
        )

    def delete_by_filter(self, filter_conditions: Dict[str, Any]) -> int:
        """
        Delete documents matching filter conditions.
        
        Args:
            filter_conditions: Metadata filters
            
        Returns:
            Number of deleted documents (approximate)
        """
        try:
            conditions = []
            for field, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value),
                    )
                )

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=Filter(must=conditions)
                ),
            )

            logger.info(f"Deleted documents matching filter: {filter_conditions}")
            return 1  # Qdrant doesn't return count

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": getattr(info, 'points_count', 0),
                "indexed_vectors_count": getattr(info, 'indexed_vectors_count', None),
                "status": str(getattr(info, 'status', 'unknown')),
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}


    def get_all_embeddings(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Retrieve all embeddings from the collection (with limit).
        Useful for batch analysis (clustering, PCA).
        """
        try:
            # Scroll through points
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_vectors=[self.DENSE_VECTOR_NAME],
                with_payload=True,
            )
            
            results = []
            for point in points:
                vector = None
                # Handle vector response structure (can be dict or direct)
                if point.vector:
                    if isinstance(point.vector, dict):
                        vector = point.vector.get(self.DENSE_VECTOR_NAME)
                    else:
                        # Fallback if just one vector returned without name (unlikely with named vectors)
                        vector = point.vector
                
                if vector:
                    results.append({
                        "id": str(point.id),
                        "vector": vector,
                        "metadata": point.payload or {}
                    })
            
            logger.info(f"Retrieved {len(results)} embeddings for analysis")
            return results
            
        except Exception as e:
            logger.error(f"Failed to fetch all embeddings: {e}")
            return []


# Convenience function for backward compatibility
def get_qdrant_service(collection_name: Optional[str] = None) -> QdrantVectorService:
    """Get a QdrantVectorService instance."""
    return QdrantVectorService(collection_name=collection_name)
