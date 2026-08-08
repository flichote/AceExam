"""Chat router -- AI explain / followup with SSE + RAG (M2 enhanced).

M2 changes vs M1:
- SSE uses structured events (delta/step/citations/done) per api.md section 0.4
- 'model' field in non-streaming response
- Proper step/citation structure

M3.5: TTS endpoint (§12.1) — voice synthesis from chat explanation
"""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_member
from app.db import get_db
from app.db.models import ChatSession, Question, User
from app.schemas.chat import ChatExplainRequest, ChatFollowupRequest, ChatResponse
from app.schemas.tts import TTSRequest, TTSResponse
from app.services.llm_gateway import llm_gateway

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/explain")
async def explain(
    body: ChatExplainRequest,
    stream: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    result = await db.execute(select(Question).where(Question.id == body.question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": (
            "You are AceExam's AI tutor. Provide step-by-step explanations based on the question content. "
            "Output JSON with steps, conclusion, and citations."
        )},
        {"role": "user", "content": (
            f"Explain this question step by step:\n"
            f"Question: {question.content}\n"
            f"Options: {question.options}\n"
            f"Answer: {question.answer}\n"
            f"Analysis: {question.analysis}\n\n"
            f"Respond in JSON format: {{'steps': [{{'title': '...', 'content': '...'}}], "
            f"'conclusion': '...', 'citations': [], 'uncovered': false}}"
        )},
    ]

    tier = llm_gateway.route_tier(
        require_depth=question.difficulty >= 4 or question.type in ("essay", "proof", "writing"),
        difficulty=question.difficulty,
        question_type=question.type,
    )

    if stream:
        import json as _json

        async def generate():
            yield "data: {\"type\":\"step\",\"step_index\":0,\"title\":\"Understanding the question\"}\n\n"
            full_content = ""
            async for chunk in llm_gateway.chat_stream(tier, messages):
                full_content += chunk
                event = _json.dumps({"type": "delta", "content": chunk})
                yield f"data: {event}\n\n"

            session_id = str(uuid.uuid4())
            yield _json.dumps({"type": "citations", "citations": []})
            yield "\n\n"
            done_event = _json.dumps({
                "type": "done",
                "session_id": session_id,
                "uncovered": False,
                "model": "pro" if tier == "pro" else "flash",
            })
            yield f"data: {done_event}\n\n"

            # Save chat session
            session = ChatSession(
                user_id=user.id,
                question_id=uuid.UUID(body.question_id),
                session_key=secrets.token_urlsafe(32),
                messages=messages + [{"role": "assistant", "content": full_content}],
            )
            db.add(session)
            await db.commit()

        return StreamingResponse(generate(), media_type="text/event-stream")

    resp = await llm_gateway.chat(tier, messages)

    # Try to parse JSON from response
    import json as _json
    content = resp["content"]
    try:
        parsed = _json.loads(content)
        steps = parsed.get("steps", [{"title": "Explanation", "content": content}])
        conclusion = parsed.get("conclusion")
        citations = parsed.get("citations", [])
        uncovered = parsed.get("uncovered", False)
    except _json.JSONDecodeError:
        steps = [{"title": "Explanation", "content": content}]
        conclusion = None
        citations = []
        uncovered = False

    # Chat session
    session_id = body.followup_session_id
    if session_id:
        sess_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = sess_result.scalar_one_or_none()
    else:
        session = None

    if session is None:
        session = ChatSession(
            user_id=user.id,
            question_id=uuid.UUID(body.question_id),
            session_key=secrets.token_urlsafe(32),
            messages=messages + [{"role": "assistant", "content": content}],
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return ChatResponse(
        session_id=str(session.id),
        steps=steps,
        conclusion=conclusion,
        citations=citations,
        uncovered=uncovered,
        model="pro" if tier == "pro" else "flash",
    )


@router.post("/followup")
async def followup(
    body: ChatFollowupRequest,
    stream: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    sess_result = await db.execute(
        select(ChatSession).where(ChatSession.id == body.session_id, ChatSession.user_id == user.id)
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = session.messages[-10:] + [{"role": "user", "content": body.message}]

    if stream:
        import json as _json

        async def generate():
            full_content = ""
            async for chunk in llm_gateway.chat_stream("flash", messages):
                full_content += chunk
                event = _json.dumps({"type": "delta", "content": chunk})
                yield f"data: {event}\n\n"
            done_event = _json.dumps({
                "type": "done",
                "session_id": str(session.id),
                "uncovered": False,
                "model": "flash",
            })
            yield f"data: {done_event}\n\n"
            session.messages = messages + [{"role": "assistant", "content": full_content}]
            await db.commit()

        return StreamingResponse(generate(), media_type="text/event-stream")

    resp = await llm_gateway.chat("flash", messages)
    content = resp["content"]
    messages.append({"role": "assistant", "content": content})
    session.messages = messages
    await db.commit()

    return ChatResponse(
        session_id=str(session.id),
        steps=[{"title": "Follow-up answer", "content": content}],
        conclusion=None,
        citations=[],
        uncovered=False,
        model="flash",
    )


# ── M3.5 TTS ──

_VALID_VOICES = {"zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"}
_TTS_CACHE_DIR = Path("backend/media/tts")


def _clean_text_for_tts(messages: list[dict]) -> str:
    """从 chat_sessions.messages 中提取最后一条 assistant 消息的讲解文本。"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # 简单清洗：去 LaTeX 标记（$...$ 替换为空格）
            import re
            content = re.sub(r'\$[^$]*\$', '', content)
            return content.strip()
    return ""


@router.post("/explain/{session_id}/tts", response_model=TTSResponse)
async def generate_tts(
    session_id: str,
    body: TTSRequest = TTSRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    if body.voice not in _VALID_VOICES:
        raise HTTPException(status_code=422, detail=f"Invalid voice. Choose from: {_VALID_VOICES}")

    # Validate session
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Extract explanation text
    text = _clean_text_for_tts(session.messages)
    if not text:
        raise HTTPException(status_code=404, detail="No explanation content found")

    # Cache key
    cache_key = hashlib.sha256((text + body.voice).encode()).hexdigest()
    cache_file = _TTS_CACHE_DIR / f"{cache_key}.mp3"
    audio_url = f"/api/v1/tts/audio/{cache_key}.mp3"

    cache_hit = cache_file.exists()
    text_preview = text[:100] + "……" if len(text) > 100 else text

    try:
        if not cache_hit:
            import edge_tts
            import asyncio as _asyncio

            _TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            communicate = edge_tts.Communicate(text, body.voice)
            # Write to temp file then rename atomically
            tmp_file = cache_file.with_suffix(".tmp")
            with open(tmp_file, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
            tmp_file.rename(cache_file)

        return TTSResponse(
            session_id=session_id,
            audio_url=audio_url,
            voice=body.voice,
            text_preview=text_preview,
            cache_hit=cache_hit,
            created_at=datetime.now(timezone.utc),  # type: ignore[arg-type]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS service unavailable: {e}")


@router.get("/tts/audio/{file_hash}.mp3")
async def get_tts_audio(
    file_hash: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    cache_file = _TTS_CACHE_DIR / f"{file_hash}.mp3"
    if not cache_file.exists():
        raise HTTPException(status_code=404, detail="Audio file not found — regenerate TTS")
    return FileResponse(
        path=str(cache_file),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )
