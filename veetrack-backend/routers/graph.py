from fastapi import APIRouter, Depends, HTTPException
from auth.dependencies import require_role
from models import User

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("/entity/{name}")
async def get_entity_neighbors(
    name: str,
    user: User = Depends(require_role(["admin", "analyst"]))
):
    from services.graph_service import graph_service
    neighbors = graph_service.get_neighbors(name)
    if not neighbors:
        raise HTTPException(status_code=404, detail="Entity not found or has no connections")
    return {"entity": name, "neighbors": neighbors}

@router.get("/path/{entity_a}/{entity_b}")
async def get_entity_path(
    entity_a: str, 
    entity_b: str,
    user: User = Depends(require_role(["admin", "analyst"]))
):
    from services.graph_service import graph_service
    result = graph_service.get_path(entity_a, entity_b)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
