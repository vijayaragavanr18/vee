import os
from glob import glob
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth.dependencies import require_role
from models import User
from services.report_service import REPORTS_DIR

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/daily")
async def download_latest_daily_report(
    user: User = Depends(require_role(["admin", "analyst", "viewer"]))
):
    pdfs = sorted(glob(os.path.join(REPORTS_DIR, "daily_brief_*.pdf")))
    if not pdfs:
        raise HTTPException(status_code=404, detail="No daily reports available yet.")
        
    latest_pdf = pdfs[-1]
    filename = os.path.basename(latest_pdf)
    return FileResponse(
        path=latest_pdf, 
        filename=filename, 
        media_type='application/pdf'
    )
