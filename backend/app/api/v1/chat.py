"""Chat router -- AI explain / followup with SSE + RAG (M2 enhanced).

M2 changes vs M1:
- SSE uses structured events (delta/step/citations/done) per api.md section 0.4
- 'model' field in non-streaming response
- Proper step/citation structure
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_member
from app.db import get_db
from app.db.models import ChatSession, Question, User
from app.schemas.chat import ChatExplainRequest, ChatFollowupRequest, ChatResponse
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
