"""Chat router — AI explain / followup via LLM gateway (streaming supported)."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_member, get_current_user
from app.db import get_db
from app.db.models import ChatSession, Question, User
from app.schemas.chat import ChatExplainRequest, ChatFollowupRequest
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
        {"role": "system", "content": "你是AceExam的AI助教。请基于题目内容进行分步讲解。"},
        {"role": "user", "content": f"请讲解这道题目：\n{question.content}\n选项：{question.options}\n答案：{question.answer}\n解析：{question.analysis}"},
    ]

    tier = llm_gateway.route_tier(
        require_depth=question.difficulty >= 4 or question.type in ("essay", "proof", "writing"),
        difficulty=question.difficulty,
        question_type=question.type,
    )

    if stream:
        async def generate():
            async for chunk in llm_gateway.chat_stream(tier, messages):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    resp = await llm_gateway.chat(tier, messages)

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
            messages=messages + [{"role": "assistant", "content": resp["content"]}],
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return {
        "session_id": str(session.id),
        "steps": [{"title": "讲解", "content": resp["content"]}],
        "conclusion": None,
        "citations": [],
        "uncovered": False,
    }


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

    messages = session.messages + [{"role": "user", "content": body.message}]

    if stream:
        async def generate():
            async for chunk in llm_gateway.chat_stream("flash", messages):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    resp = await llm_gateway.chat("flash", messages)
    messages.append({"role": "assistant", "content": resp["content"]})
    session.messages = messages
    await db.commit()

    return {
        "session_id": str(session.id),
        "steps": [{"title": "追问回答", "content": resp["content"]}],
        "conclusion": None,
        "citations": [],
        "uncovered": False,
    }
