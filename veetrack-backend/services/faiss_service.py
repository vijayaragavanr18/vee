import os
import json
import logging
from datetime import datetime
import faiss
import numpy as np
from glob import glob

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "/tmp/veetrack_checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

class FaissService:
    def __init__(self, vector_dim: int = 384):
        self.vector_dim = vector_dim
        self.index = faiss.IndexFlatL2(vector_dim)
        
        # Move to GPU if available and allowed by ModelManager
        from services.model_manager import model_manager
        res = model_manager.get_faiss_resource()
        if res:
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
            
        self.article_ids = []
        self.last_checkpoint_time = None

    def add_article(self, article_id: str, embedding: np.ndarray):
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)
        self.index.add(embedding.astype("float32"))
        self.article_ids.append(article_id)

    def search(self, query_embedding: np.ndarray, k: int = 5):
        if self.index.ntotal == 0:
            return []
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        distances, indices = self.index.search(query_embedding.astype("float32"), k)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.article_ids):
                results.append({
                    "article_id": self.article_ids[idx],
                    "distance": float(distances[0][i])
                })
        return results

    def checkpoint(self):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        index_path = os.path.join(CHECKPOINT_DIR, f"faiss_index_{timestamp}.bin")
        meta_path = os.path.join(CHECKPOINT_DIR, f"faiss_meta_{timestamp}.json")
        
        # Must move to CPU to write to disk
        if isinstance(self.index, faiss.GpuIndex):
            cpu_index = faiss.index_gpu_to_cpu(self.index)
            faiss.write_index(cpu_index, index_path)
        else:
            faiss.write_index(self.index, index_path)
            
        with open(meta_path, "w") as f:
            json.dump({
                "article_count": len(self.article_ids),
                "last_indexed_article_id": self.article_ids[-1] if self.article_ids else None,
                "timestamp": timestamp,
                "article_ids": self.article_ids
            }, f)
            
        self.last_checkpoint_time = timestamp
        logger.info(f"FAISS checkpointed to {index_path} with {len(self.article_ids)} articles.")
        self._cleanup_old_checkpoints()

    def load_from_checkpoint(self):
        checkpoints = sorted(glob(os.path.join(CHECKPOINT_DIR, "faiss_meta_*.json")))
        if not checkpoints:
            logger.info("No FAISS checkpoints found. Starting fresh.")
            return False
            
        latest_meta_path = checkpoints[-1]
        timestamp = latest_meta_path.split("_meta_")[1].replace(".json", "")
        index_path = os.path.join(CHECKPOINT_DIR, f"faiss_index_{timestamp}.bin")
        
        if os.path.exists(index_path):
            cpu_index = faiss.read_index(index_path)
            
            from services.model_manager import model_manager
            res = model_manager.get_faiss_resource()
            if res:
                self.index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
            else:
                self.index = cpu_index
                
            with open(latest_meta_path, "r") as f:
                meta = json.load(f)
                self.article_ids = meta.get("article_ids", [])
                
            self.last_checkpoint_time = timestamp
            logger.info(f"Loaded FAISS checkpoint from {timestamp} with {len(self.article_ids)} articles.")
            return True
        return False

    def _cleanup_old_checkpoints(self):
        metas = sorted(glob(os.path.join(CHECKPOINT_DIR, "faiss_meta_*.json")))
        if len(metas) > 3:
            for old_meta in metas[:-3]:
                ts = old_meta.split("_meta_")[1].replace(".json", "")
                old_index = os.path.join(CHECKPOINT_DIR, f"faiss_index_{ts}.bin")
                try:
                    os.remove(old_meta)
                    if os.path.exists(old_index):
                        os.remove(old_index)
                except Exception as e:
                    logger.error(f"Failed to delete old checkpoint {ts}: {e}")

faiss_service = FaissService()
