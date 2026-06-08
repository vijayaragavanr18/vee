from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/dedup")
async def get_dedup_stats():
    """Returns 24h dedup exact_dupes, semantic_dupes, passed_to_llm counts."""
    from services.dedup_service import dedup_service
    return {
        "exact_dupes": dedup_service.exact_dupes,
        "semantic_dupes": dedup_service.semantic_dupes,
        "passed_to_llm": dedup_service.passed_to_llm
    }
