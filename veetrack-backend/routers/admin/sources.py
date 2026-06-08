from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from database import get_db
from models import NewsSource, User
from auth.dependencies import require_role

router = APIRouter(prefix="/admin/sources", tags=["admin", "sources"])

class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: str
    fetch_interval_minutes: int = 15

@router.post("/")
async def create_source(
    source: SourceCreate, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"]))
):
    db_source = NewsSource(**source.model_dump())
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    return db_source

@router.get("/")
async def list_sources(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin", "analyst"]))
):
    result = await db.execute(select(NewsSource))
    return result.scalars().all()

@router.post("/{source_id}/trigger")
async def trigger_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"]))
):
    result = await db.execute(select(NewsSource).where(NewsSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    from tasks.ingestion import fetch_source_task
    fetch_source_task.delay(source_id)
    return {"msg": f"Ingestion triggered for {source.name}"}
