import os
import json
import logging
import httpx
from typing import Optional, Dict, Any

from schemas.intelligence_card import IntelligenceCardSchema

logger = logging.getLogger(__name__)

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1/chat/completions")
MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct-AWQ")

async def analyze_article(text: str, schema_appended: bool = False) -> Optional[Dict[str, Any]]:
    """
    Calls vLLM with guided structured decoding using the IntelligenceCard schema.
    """
    prompt = "Analyze the following article and extract intelligence."
    if schema_appended:
        prompt += f"\n\nYou MUST return a JSON object exactly matching this schema:\n{json.dumps(IntelligenceCardSchema.model_json_schema())}"
        
    messages = [
        {"role": "system", "content": "You are a Senior Corporate Intelligence Analyst. Respond only in valid JSON."},
        {"role": "user", "content": f"{prompt}\n\nArticle: {text}"}
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.1,
        "guided_json": IntelligenceCardSchema.model_json_schema(),
        "guided_decoding_backend": "outlines"
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(VLLM_URL, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # vLLM/Outlines guarantees output matches schema, but we double-verify
            parsed_data = json.loads(content)
            # Validate with Pydantic
            valid_card = IntelligenceCardSchema(**parsed_data)
            return valid_card.model_dump()
            
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return None

async def analyze_article_with_retry(text: str) -> Optional[Dict[str, Any]]:
    """
    Two-attempt retry logic. Second attempt appends schema explicitly.
    """
    # Attempt 1
    result = await analyze_article(text, schema_appended=False)
    if result is not None:
        return result
        
    logger.warning("Attempt 1 failed. Retrying with explicit schema appendage...")
    
    # Attempt 2
    result = await analyze_article(text, schema_appended=True)
    if result is not None:
        return result
        
    logger.error("Attempt 2 failed. Returning None.")
    return None
