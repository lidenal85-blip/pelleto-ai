"""
app/api/routes/agent.py — M2: POST /api/agent/chat
"""
import uuid
import time
from collections import defaultdict
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

# --- Simple in-memory rate limiter ---
# Max 20 requests per IP per minute
_RATE_WINDOW = 60      # seconds
_RATE_MAX    = 20      # requests per window
_rate_store: dict[str, list] = defaultdict(list)

def _check_rate(ip: str) -> bool:
    """Returns True if allowed, False if rate-limited."""
    now = time.time()
    timestamps = _rate_store[ip]
    # Drop old entries
    _rate_store[ip] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_MAX:
        return False
    _rate_store[ip].append(now)
    return True


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
        return JSONResponse(
            {"error": "service_unavailable",
             "fallback_message": f"Консультант временно недоступен. Позвоните: {SITE_PHONE}"},
            status_code=503
        )

    # Rate limit
    client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()
    if not _check_rate(client_ip):
        log.warning(f"Rate limit exceeded: ip={client_ip}")
        return JSONResponse(
            {"error": "rate_limit",
             "fallback_message": "Слишком много запросов. Подождите минуту."},
            status_code=429
        )

    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "empty_question"}, status_code=400)

    request_id = req.headers.get("X-Request-ID", str(uuid.uuid4()))
    session_id = body.session_id or str(uuid.uuid4())
    # Sanitize history: only user/assistant roles
    history = [
        {"role": m.role, "content": m.content}
        for m in body.history
        if m.role in ("user", "assistant")
    ]

    result = await ask_agent(
        question=question,
        session_id=session_id,
        history=history,
        request_id=request_id
    )

    # Log dialogue
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

    return JSONResponse({
        "answer": result["answer"],
        "cta": {
            "show": result.get("cta_show", False),
            "text": result.get("cta_text", "Оформить заказ"),
            "url": ORDER_URL
        },
        "phase": result.get("phase", "initial"),
        "request_id": request_id
    })


class OrderRequest(BaseModel):
    name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    address: str = Field(default="", max_length=200)
    comment: str = Field(default="", max_length=500)


@router.post("/api/order")
async def submit_order(req: OrderRequest):
    import httpx
    from app.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID
    msg = (
        f"✅ Новый заказ — {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}\n"
        f"Имя: {req.name}\nТел: {req.phone}\n"
        f"Адрес: {req.address or 'не указан'}\nПожелания: {req.comment or 'нет'}"
    )
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_ADMIN_CHAT_ID, "text": msg}
            )
    except Exception:
        pass
    return {"ok": True}