"""OCR router -- photo upload + poll (M2).

POST /ocr/upload: upload image, call OCR service (mock for now), structured preview
GET  /ocr/upload/{upload_id}: poll OCR status
"""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import KnowledgePoint, OcrUpload, User
from app.schemas.ocr import OcrUploadResponse, OcrPollResponse, OcrStructuredResult

router = APIRouter(prefix="/ocr", tags=["ocr"])

FREE_DAILY_LIMIT = 5


@router.post("/upload", response_model=OcrUploadResponse)
async def ocr_upload(
    file: UploadFile = File(...),
    subject_id: str = Form(...),
    source: str = Form("photo"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Rate limiting: free users max 5/day
    if not user.is_member:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date()
        count_result = await db.execute(
            select(OcrUpload).where(
                OcrUpload.user_id == user.id,
                OcrUpload.created_at >= today,
            )
        )
        today_count = len(count_result.scalars().all())
        if today_count >= FREE_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": f"Free users limited to {FREE_DAILY_LIMIT} OCR uploads per day. Upgrade to membership.",
                },
            )

    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Only jpg/png/webp images accepted")

    # Save upload record
    upload = OcrUpload(
        user_id=user.id,
        subject_id=uuid.UUID(subject_id),
        image_path=file.filename,
        status="pending",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    # --- OCR processing (mock: ep-ai will replace with Pix2Text) ---
    # In production, call ocr_service.recognize() here
    try:
        contents = await file.read()
        # Mock: generate a plausible structured result based on image presence
        import re
        text_preview = ""
        try:
            # Try to extract any readable text from the image bytes (placeholder)
            text_preview = f"OCR mock recognition for {file.filename}"

            # Mock structured result
            structured = OcrStructuredResult(
                type="single",
                content="Mock question content (OCR placeholder). Real OCR via Pix2Text ONNX not yet integrated.",
                options=[
                    {"key": "A", "text": "Option A"},
                    {"key": "B", "text": "Option B"},
                    {"key": "C", "text": "Option C"},
                    {"key": "D", "text": "Option D"},
                ],
                answer="C",
                analysis="Mock analysis.",
                confidence=0.82,
            )

            # Get top-3 suggested KPs (keyword match)
            kp_result = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.subject_id == uuid.UUID(subject_id),
                    KnowledgePoint.level == 3,
                ).limit(3)
            )
            kps = kp_result.scalars().all()
            suggested_kps = [
                {"id": str(kp.id), "name": kp.name, "score": 0.9 - i * 0.05}
                for i, kp in enumerate(kps)
            ]

            upload.status = "parsed"
            upload.raw_text = text_preview
            upload.structured = structured.model_dump()
            upload.suggested_kps = suggested_kps
            await db.commit()

            return OcrUploadResponse(
                upload_id=str(upload.id),
                status="parsed",
                raw_text=text_preview,
                structured=structured,
                suggested_kps=suggested_kps,
            )
        except Exception:
            raise
    except Exception:
        upload.status = "failed"
        upload.error = "OCR_EMPTY"
        await db.commit()

        return OcrUploadResponse(
            upload_id=str(upload.id),
            status="failed",
            error="OCR_EMPTY",
            message="No valid question detected. Please retake or enter manually.",
        )


@router.get("/upload/{upload_id}", response_model=OcrPollResponse)
async def ocr_poll(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OcrUpload).where(
            OcrUpload.id == upload_id,
            OcrUpload.user_id == user.id,
        )
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="OCR upload not found")

    structured = None
    if upload.structured:
        structured = OcrStructuredResult(**upload.structured)

    return OcrPollResponse(
        upload_id=str(upload.id),
        status=upload.status,
        raw_text=upload.raw_text,
        structured=structured,
        suggested_kps=upload.suggested_kps,
        error=upload.error,
    )
