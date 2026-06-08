from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class SentimentEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"

class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ExtractedEntity(BaseModel):
    name: str = Field(..., description="The name of the entity.")
    type: str = Field(..., description="The type of the entity (e.g., PERSON, ORG, GPE).")
    context: Optional[str] = Field(None, description="Brief context of how the entity is involved.")

class IntelligenceCardSchema(BaseModel):
    executive_summary: str = Field(
        ..., 
        description="A comprehensive, full-page executive summary of the article.",
        min_length=50
    )
    key_takeaways: List[str] = Field(
        ..., 
        description="3-5 bullet points outlining the most critical information.",
        min_items=1,
        max_items=10
    )
    sentiment: SentimentEnum = Field(..., description="The overall PR sentiment of the article.")
    risk_level: RiskLevelEnum = Field(..., description="The assessed PR risk level.")
    recommended_actions: List[str] = Field(
        ..., 
        description="Actionable PR steps to take in response to this article.",
        min_items=1
    )
    entities_involved: List[ExtractedEntity] = Field(
        ..., 
        description="List of key entities extracted from the text."
    )
