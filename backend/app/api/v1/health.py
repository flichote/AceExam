"""Health check router."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "AceExam"}
