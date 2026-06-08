"""
Centralized Machine Learning Model Registry.

This file loads all the AI/ML models used in the VeeTrack platform.
It provides a single place to see what models are being used and ensures
they are only loaded into memory once.
"""

import logging

logger = logging.getLogger(__name__)

# Model state globals
_sentiment_model = None
_embed_model = None
_summarizer = None


def init_models():
    """Load all primary ML models into memory. Safe to call multiple times."""
    global _sentiment_model, _nlp, _embed_model, _summarizer
    
    # 1. Sentiment Model (Cardiff RoBERTa)
    if _sentiment_model is None:
        try:
            from transformers import pipeline as hf_pipeline
            _sentiment_model = hf_pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                top_k=1,
            )
            print("[Models] Cardiff RoBERTa loaded [OK]")
        except Exception as e:
            print(f"[Models] RoBERTa failed to load: {e}")
            raise e



    # 3. Embeddings Model (fastembed)
    if _embed_model is None:
        try:
            from fastembed import TextEmbedding
            from backend.device import DEVICE
            providers = ["CUDAExecutionProvider"] if DEVICE == "cuda" else ["CPUExecutionProvider"]
            try:
                _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=providers)
                print(f"[Models] BAAI/bge-small-en-v1.5 loaded ({providers[0]}) [OK]")
            except ValueError as e:
                if "CUDAExecutionProvider" in str(e):
                    print("[Models] ONNX CUDA not found, falling back to CPU for FastEmbed...")
                    _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=["CPUExecutionProvider"])
                    print("[Models] BAAI/bge-small-en-v1.5 loaded (CPUExecutionProvider) [OK]")
                else:
                    raise e
        except Exception as e:
            print(f"[Models] TextEmbedding failed to load: {e}")
            raise e

    # 4. Summarization (sumy TextRank)
    if _summarizer is None:
        try:
            from sumy.summarizers.text_rank import TextRankSummarizer
            _summarizer = TextRankSummarizer()
            print("[Models] sumy TextRank loaded [OK]")
        except Exception as e:
            print(f"[Models] sumy TextRank failed to load: {e}")
            raise e


def get_sentiment_model():
    return _sentiment_model

def get_embed_model():
    return _embed_model

def get_summarizer():
    return _summarizer

# Models will be loaded asynchronously during data ingestion to save time
# init_models()
