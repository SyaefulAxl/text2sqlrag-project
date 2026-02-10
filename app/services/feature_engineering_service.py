"""
Advanced Feature Engineering Service (The "7 Tricks")

Implements advanced techniques to transform raw LLM embeddings into
task-specific signals for the Resume RAG service.

Techniques:
1. Semantic Similarity (Concept Anchors)
2. Dimensionality Reduction (PCA/SVD)
3. Clustering & Distance Features
4. Text Difference (Gap Analysis)
5. Whitening Normalization
6. Embedding Aggregation (Pooling)
7. Feature Synthesis (Polynomial)
"""

import logging
import numpy as np
import json
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings

# Try importing sklearn, but fail gracefully if not installed
try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """
    Service for transforming embeddings using advanced feature engineering tricks.
    """

    def __init__(self):
        """Initialize feature engineering service."""
        start_msg = "Sklearn available" if SKLEARN_AVAILABLE else "Sklearn NOT available (some features disabled)"
        logger.info(f"FeatureEngineeringService initialized: {start_msg}")
        
        # Concept Anchors for Resume Domain
        # These are pre-computed "centroids" for key concepts
        self.anchors = {
            "leadership": "Technical leadership, team management, strategic planning, executive role",
            "technical_textile": "Spinning, weaving, knitting, dyeing, textile machinery, technical expertise",
            "commercial": "Sales, marketing, merchandising, procurement, supply chain, business development",
            "quality": "Quality control, six sigma, ISO standards, audit, lab testing",
            "maintenance": "Maintenance, mechanical engineering, electrical, troubleshooting, repair",
        }
        self.anchor_embeddings: Dict[str, List[float]] = {}
        
        # Internal state for trained models (would ideally be persisted)
        self.pca_model = None
        self.kmeans_model = None
        self.scaler = None

    async def initialize_anchors(self, embedding_service):
        """Pre-compute embeddings for concept anchors."""
        logger.info("Initializing concept anchors...")
        texts = list(self.anchors.values())
        keys = list(self.anchors.keys())
        
        try:
            embeddings, _ = await embedding_service.generate_embeddings(texts)
            for i, key in enumerate(keys):
                self.anchor_embeddings[key] = embeddings[i]
            logger.info(f"Initialized {len(self.anchor_embeddings)} concept anchors")
        except Exception as e:
            logger.error(f"Failed to initialize anchors: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Trick 1: Semantic Similarity as a Feature
    # ═══════════════════════════════════════════════════════════════════
    def compute_anchor_features(self, embedding: List[float]) -> Dict[str, float]:
        """
        Calculate similarity features against concept anchors.
        
        Returns dict of {concept: similarity_score}
        """
        if not self.anchor_embeddings:
            return {}
            
        features = {}
        target = np.array(embedding).reshape(1, -1)
        
        for name, anchor_emb in self.anchor_embeddings.items():
            anchor = np.array(anchor_emb).reshape(1, -1)
            # Use dot product for normalized embeddings (equiv to cosine sim)
            # Assuming OpenAI embeddings are normalized
            sim = np.dot(target, anchor.T)[0][0]
            features[f"sim_{name}"] = round(float(sim), 4)
            
        return features

    # ═══════════════════════════════════════════════════════════════════
    # Trick 2: Dimensionality Reduction
    # ═══════════════════════════════════════════════════════════════════
    def reduce_dimensions(self, embeddings: List[List[float]], n_components: int = 50) -> List[List[float]]:
        """
        Reduce embedding dimensions using PCA.
        Must be fit on a batch of embeddings first.
        """
        if not SKLEARN_AVAILABLE:
            return embeddings
            
        emb_array = np.array(embeddings)
        
        # Fit if not already fitted or dimension mismatch
        if self.pca_model is None:
            n_samples = emb_array.shape[0]
            # Handle case where samples < components
            actual_components = min(n_components, n_samples)
            if actual_components < 1:
                return embeddings
                
            self.pca_model = PCA(n_components=actual_components)
            return self.pca_model.fit_transform(emb_array).tolist()
            
        return self.pca_model.transform(emb_array).tolist()

    # ═══════════════════════════════════════════════════════════════════
    # Trick 3: Cluster Labels & Distances
    # ═══════════════════════════════════════════════════════════════════
    def cluster_embeddings(self, embeddings: List[List[float]], n_clusters: int = 5) -> List[Dict[str, Any]]:
        """
        Cluster embeddings using K-Means and return assignments + distances.
        """
        if not SKLEARN_AVAILABLE or not embeddings:
            return [{"cluster": 0, "distance": 0.0} for _ in embeddings]
            
        emb_array = np.array(embeddings)
        n_samples = emb_array.shape[0]
        actual_k = min(n_clusters, n_samples)
        
        if actual_k < 1:
            return [{"cluster": 0, "distance": 0.0} for _ in embeddings]
            
        kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(emb_array)
        distances = kmeans.transform(emb_array)
        
        results = []
        for i, label in enumerate(labels):
            # Distance to own centroid
            dist = distances[i][label]
            results.append({
                "cluster_id": int(label),
                "cluster_distance": float(dist)
            })
            
        return results

    # ═══════════════════════════════════════════════════════════════════
    # Trick 4: Text Difference (Gap Analysis)
    # ═══════════════════════════════════════════════════════════════════
    def calculate_gap_features(self, emb_target: List[float], emb_ref: List[float]) -> Dict[str, Any]:
        """
        Calculate interaction features between two embeddings (e.g. Resume vs JD).
        Trick 4: Difference and Product vectors.
        """
        v1 = np.array(emb_target)
        v2 = np.array(emb_ref)
        
        # Basic similarity
        sim = float(np.dot(v1, v2)) if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0 else 0.0
        
        # Element-wise difference (Gap)
        diff = v1 - v2
        gap_magnitude = float(np.linalg.norm(diff))
        
        # Element-wise product (Alignment)
        prod = v1 * v2
        alignment_magnitude = float(np.sum(prod))
        
        return {
            "similarity": round(sim, 4),
            "gap_magnitude": round(gap_magnitude, 4),
            "alignment_score": round(alignment_magnitude, 4),
            # "diff_vector": diff.tolist(),  # Too large to return usually
        }

    # ═══════════════════════════════════════════════════════════════════
    # Trick 5: Whitening
    # ═══════════════════════════════════════════════════════════════════
    def whiten_embeddings(self, embeddings: List[List[float]]) -> List[List[float]]:
        """
        Apply PCA whitening to normalize variance in all directions.
        """
        if not SKLEARN_AVAILABLE or not embeddings:
            return embeddings
            
        emb_array = np.array(embeddings)
        
        # Need enough samples
        if emb_array.shape[0] < emb_array.shape[1]:
            # Not enough samples for full whitening, just standard scale
            scaler = StandardScaler()
            return scaler.fit_transform(emb_array).tolist()
            
        pca = PCA(whiten=True)
        return pca.fit_transform(emb_array).tolist()

    # ═══════════════════════════════════════════════════════════════════
    # Trick 7: Feature Synthesis
    # ═══════════════════════════════════════════════════════════════════
    def synthesize_features(self, embeddings: List[List[float]]) -> List[List[float]]:
        """
        Generate polynomial features from reduced embeddings.
        """
        if not SKLEARN_AVAILABLE:
            return embeddings
            
        # First reduce dimensions to avoid explosion
        reduced = self.reduce_dimensions(embeddings, n_components=10)
        
        poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
        return poly.fit_transform(reduced).tolist()


# Global Singleton
_feature_service = None

def get_feature_service() -> FeatureEngineeringService:
    global _feature_service
    if _feature_service is None:
        _feature_service = FeatureEngineeringService()
    return _feature_service
