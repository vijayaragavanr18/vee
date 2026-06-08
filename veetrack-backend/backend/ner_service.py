from gliner import GLiNER
import threading
import torch
from backend.device import DEVICE

_model = None
_lock = threading.Lock()

ENTITY_LABELS = [
    "company", "person", "location", "country", "city",
    "product", "technology", "currency", "stock ticker",
    "government body", "law or regulation", "event"
]

def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
                if DEVICE == "cuda":
                    _model = _model.to("cuda")
    return _model

def extract_entities(text: str, threshold: float = 0.4) -> list[dict]:
    model = get_model()
    # GLiNER has a 512 token limit — chunk long articles
    words = text.split()
    chunks = [" ".join(words[i:i+300]) for i in range(0, len(words), 280)]
    
    all_entities = []
    seen = set()
    for chunk in chunks:
        entities = model.predict_entities(chunk, ENTITY_LABELS, threshold=threshold)
        for e in entities:
            key = (e["text"].lower().strip(), e["label"])
            if key not in seen:
                seen.add(key)
                all_entities.append({
                    "text": e["text"],
                    "label": e["label"],
                    "score": round(e["score"], 3)
                })
    return all_entities

def batch_extract_entities(texts: list[str], threshold: float = 0.4) -> list[list[dict]]:
    model = get_model()
    # Truncate texts to 400 words to avoid chunking complexities across batches
    trunc_texts = [" ".join(text.split()[:400]) for text in texts]
    
    batch_results = model.batch_predict_entities(trunc_texts, ENTITY_LABELS, threshold=threshold)
    final_results = []
    
    for entities in batch_results:
        seen = set()
        filtered = []
        for e in entities:
            key = (e["text"].lower().strip(), e["label"])
            if key not in seen:
                seen.add(key)
                filtered.append({
                    "text": e["text"],
                    "label": e["label"],
                    "score": round(e["score"], 3)
                })
        final_results.append(filtered)
        
    return final_results
