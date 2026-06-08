import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Singleton Manager to enforce strict VRAM constraints.
    Pins all small models to CPU to reserve 100% of available GPU VRAM for vLLM and FAISS.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._gliner_model = None
        self._embed_model = None
        self._sentiment_model = None
        self._faiss_resource = None
        self._initialized = True
        logger.info("ModelManager initialized.")

    def get_gliner(self):
        """Loads GLiNER pinned entirely to CPU."""
        if self._gliner_model is None:
            from gliner import GLiNER
            logger.info("Loading GLiNER to CPU...")
            # Enforce map_location="cpu" to prevent CUDA memory grab
            self._gliner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1", map_location="cpu")
        return self._gliner_model

    def get_embed_model(self):
        """Loads FastEmbed pinned entirely to CPU via ONNX."""
        if self._embed_model is None:
            from fastembed import TextEmbedding
            logger.info("Loading FastEmbed to CPU...")
            # Use default CPU execution provider, do not pass providers=['CUDAExecutionProvider']
            self._embed_model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                providers=["CPUExecutionProvider"]
            )
        return self._embed_model

    def get_sentiment_model(self):
        """Loads Cardiff RoBERTa sentiment model pinned to CPU."""
        if self._sentiment_model is None:
            from transformers import pipeline
            logger.info("Loading Sentiment Model to CPU...")
            # device=-1 explicitly forces CPU inference
            self._sentiment_model = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1
            )
        return self._sentiment_model

    def get_faiss_resource(self):
        """Configures FAISS GPU resource to strictly cap at 512MB Temp Memory."""
        if self._faiss_resource is None:
            try:
                import faiss
                logger.info("Configuring FAISS GPU Standard Resource (512MB cap)...")
                res = faiss.StandardGpuResources()
                # 512MB = 512 * 1024 * 1024 bytes
                res.setTempMemory(512 * 1024 * 1024)
                self._faiss_resource = res
            except (ImportError, AttributeError):
                logger.warning("faiss-gpu not found or GPU resources missing. Falling back to CPU mode.")
                self._faiss_resource = None
        return self._faiss_resource

# Export singleton instance
model_manager = ModelManager()
