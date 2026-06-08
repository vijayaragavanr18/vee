import logging
from typing import Optional, Dict, Any, Tuple
from datasketch import MinHash, MinHashLSH
import numpy as np

logger = logging.getLogger(__name__)

class DedupService:
    def __init__(self):
        self.lsh = MinHashLSH(threshold=0.85, num_perm=64)
        
        # Stats tracking for endpoint
        self.exact_dupes = 0
        self.semantic_dupes = 0
        self.passed_to_llm = 0

    def minhash_check(self, text: str, article_id: str) -> Optional[str]:
        """Stage 1: Byte-level near-duplicate detection."""
        m = MinHash(num_perm=64)
        for word in text.lower().split()[:300]:
            m.update(word.encode('utf-8'))
            
        result = self.lsh.query(m)
        if result:
            return result[0] # Return the canonical ID
            
        self.lsh.insert(article_id, m)
        return None

    def semantic_check(self, embedding: np.ndarray, article_id: str) -> Optional[str]:
        """Stage 2: Semantic duplicate detection via FAISS cosine similarity."""
        from services.faiss_service import faiss_service
        
        # Ensure we have some vectors
        if faiss_service.index.ntotal == 0:
            return None
            
        results = faiss_service.search(embedding, k=1)
        if results and results[0]["distance"] < 0.03: # Since L2 distance of normalized vectors relates to cosine
            return results[0]["article_id"]
        return None

    async def check(self, article: Dict[str, Any], embedding: np.ndarray) -> Tuple[str, str]:
        """
        Full 2-stage pipeline check.
        Returns: (dedup_type, canonical_id)
        dedup_type is one of: "unique", "minhash", "semantic"
        """
        article_id = article.get("id")
        text = (article.get("title", "") + " " + article.get("body_text", ""))
        
        # Stage 1
        canonical_id = self.minhash_check(text, article_id)
        if canonical_id:
            self.exact_dupes += 1
            return "minhash", canonical_id
            
        # Stage 2
        canonical_id = self.semantic_check(embedding, article_id)
        if canonical_id:
            self.semantic_dupes += 1
            return "semantic", canonical_id
            
        self.passed_to_llm += 1
        return "unique", article_id

dedup_service = DedupService()
