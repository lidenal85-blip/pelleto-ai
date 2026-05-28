"""
app/api/routes/agent.py — M2: POST /api/agent/chat
"""
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.services.ai import ask_agent
from app.services.content import list_products
from app.core.config import AGENT_ENABLED, AGENT_MAX_QUESTION_LEN, ORDER_URL, SITE_PHONE
from app.core.database import get_db
from app.core.logger import get_logger
from datetime import datetime, timezone

router = APIRouter()
log = get_logger("agent_route")


class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=500)


class ChatRequest(BaseModel):
    question: str = Field(max_length=500)
    session_id: str = Field(default="")
    history: list[ChatMessage] = Field(default=[])


@router.post("/api/agent/chat")
async def agent_chat(req: Request, body: ChatRequest):
    if not AGENT_ENABLED:
        return JSONResponse({"error": "service_unavailable",
                            "fallback_message": f"Консультант временно Cтключён. Позвоните: {SITE_PHONE}"}, status_code=503)

    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "empty_question"}, status_code=400)

    request_id = req.headers.get("X-Request-ID", str(uuid.uuid4()))
    session_id = body.session_id or str(uuid.uuid4())
    history = [{"role": m.role, "content": m.content} for m in body.history]

    result = await ask_agent(
        question=question,
        session_id=session_id,
        history=history,
        request_id=request_id
    )

    # Логирование
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO dialogue_logs(id,session_id,request_id,question,answer,phase,confidence,has_error,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, request_id,
             question[:2000], result["answer"][:2000],
             result.get("phase"), result.get("confidence"),
             1 if result.get("confidence") == "low" else 0,
             now)
        )
        await db.commit()

    response = {
        "answer": result["answer"],
        "cta": {
            "show": result.get("cta_show", False),
            "text": result.get("cta_text", "Оформить заказ"),
            "url": ORDER_URL
        },
        "phase": result.get("phase", "initial"),
        "request_id": request_id
    }
    return JSONResponse(response)