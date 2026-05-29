"""
app/api/routes/admin.py — M3: админ-панель + M4: автентификация.
"""
import uuid
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.core.templates import templates
from app.api.deps.auth import require_admin
from app.services.auth import (
    verify_master_key, check_rate_limit, record_failed_attempt,
    clear_attempts, create_session, delete_session
)
from app.services.content import (
    list_blocks, list_queue, list_products,
    approve_queue_item, reject_queue_item, upsert_product, delete_product
)
from app.services.knowledge import list_facts, add_fact, delete_fact, count_facts
from app.services.ai import generate_content, circuit_status
from app.services.content import queue_content
from app.core.config import TEMPLATES_DIR, SITE_VERSION
from app.core.database import get_db

router = APIRouter(prefix="/admin")


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(request: Request, master_key: str = Form(...)):
    ip = request.client.host
    rate = await check_rate_limit(ip)
    if rate["blocked"]:
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": "Слишком много попыток. Подождите 30 минут."}
        )
    if not verify_master_key(master_key):
        await record_failed_attempt(ip)
        left = max(0, 3 - (3 - rate["attempts_left"] + 1))
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": f"Неверный ключ. Осталось попыток: {left}."}
        )
    await clear_attempts(ip)
    token = await create_session(ip)
    resp = RedirectResponse(url="/admin/dashboard", status_code=303)
    resp.set_cookie("admin_token", token, httponly=True, samesite="strict", max_age=86400)
    return resp


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("admin_token", "")
    if token:
        await delete_session(token)
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie("admin_token")
    return resp


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, token=Depends(require_admin)):
    kb_count = await count_facts()
    queue = await list_queue("pending")
    products = await list_products()
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "kb_count": kb_count,
            "pending_count": len(queue),
            "products_count": len(products),
            "llm_circuit": circuit_status(),
            "version": SITE_VERSION,
        }
    )


# ── Queue ──────────────────────────────────────────────────────────────────────

@router.get("/queue", response_class=HTMLResponse)
async def queue_view(request: Request, token=Depends(require_admin)):
    items = await list_queue()
    return templates.TemplateResponse("admin/queue.html", {"request": request, "items": items})


@router.post("/queue/{q_id}/approve")
async def queue_approve(q_id: str, request: Request, token=Depends(require_admin)):
    await approve_queue_item(q_id, request.client.host)
    return RedirectResponse(url="/admin/queue", status_code=303)


@router.post("/queue/{q_id}/reject")
async def queue_reject(q_id: str, request: Request, token=Depends(require_admin)):
    await reject_queue_item(q_id, request.client.host)
    return RedirectResponse(url="/admin/queue", status_code=303)


# ── Generator ─────────────────────────────────────────────────────────────────

@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request, token=Depends(require_admin)):
    return templates.TemplateResponse("admin/generate.html", {"request": request, "result": None})


@router.post("/generate")
async def generate_submit(
    request: Request,
    topic: str = Form(...),
    task_type: str = Form("advice"),
    tone: str = Form("expert"),
    volume: int = Form(400),
    token=Depends(require_admin)
):
    req_id = str(uuid.uuid4())
    settings = {"tone": tone, "volume": volume}
    result = await generate_content(topic, task_type=task_type, settings=settings, request_id=req_id)
    if result["status"] == "success":
        q_id = await queue_content(
            {"type": task_type, "title": result["title"], "body": result["body"], "image_hint": result.get("image_hint")},
            task_settings=settings
        )
        result["queued_id"] = q_id
    return templates.TemplateResponse("admin/generate.html", {"request": request, "result": result})


# ── Knowledge Base ─────────────────────────────────────────────────────────────

@router.get("/kb", response_class=HTMLResponse)
async def kb_view(request: Request, token=Depends(require_admin)):
    facts = await list_facts(limit=200)
    return templates.TemplateResponse("admin/kb.html", {"request": request, "facts": facts})


@router.post("/kb/add")
async def kb_add(
    request: Request,
    fact: str = Form(...),
    topics: str = Form(""),
    fact_type: str = Form("expert_case"),
    confidence: str = Form("medium"),
    sales_hook: str = Form(""),
    token=Depends(require_admin)
):
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    await add_fact({
        "fact": fact, "topics": topics_list,
        "type": fact_type, "confidence": confidence,
        "sales_hook": sales_hook or None
    })
    return RedirectResponse(url="/admin/kb", status_code=303)


@router.post("/kb/{fact_id}/delete")
async def kb_delete(fact_id: str, token=Depends(require_admin)):
    await delete_fact(fact_id)
    return RedirectResponse(url="/admin/kb", status_code=303)


# ── Products ────────────────────────────────────────────────────────────────────

@router.get("/products", response_class=HTMLResponse)
async def products_view(request: Request, token=Depends(require_admin)):
    products = await list_products()
    return templates.TemplateResponse("admin/products.html", {"request": request, "products": products})


@router.post("/products/save")
async def product_save(
    request: Request,
    product_id: str = Form(""),
    name: str = Form(...),
    description: str = Form(""),
    price_min: float = Form(None),
    price_max: float = Form(None),
    unit: str = Form("т"),
    active: str = Form("on"),
    sort_order: int = Form(0),
    token=Depends(require_admin)
):
    await upsert_product({
        "id": product_id or None,
        "name": name, "description": description,
        "price_min": price_min, "price_max": price_max,
        "unit": unit, "active": active == "on",
        "sort_order": sort_order
    })
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/products/{product_id}/delete")
async def product_delete(product_id: str, token=Depends(require_admin)):
    await delete_product(product_id)
    return RedirectResponse(url="/admin/products", status_code=303)


# ── Dialogue Logs ─────────────────────────────────────────────────────────────

@router.get("/dialogues", response_class=HTMLResponse)
async def dialogues_view(request: Request, token=Depends(require_admin)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM dialogue_logs ORDER BY created_at DESC LIMIT 200"
        ) as cur:
            logs = [dict(r) for r in await cur.fetchall()]
    return templates.TemplateResponse("admin/dialogues.html", {"request": request, "logs": logs})


@router.post("/dialogues/{log_id}/flag")
async def dialogue_flag(log_id: str, token=Depends(require_admin)):
    async with get_db() as db:
        await db.execute("UPDATE dialogue_logs SET has_error=1 WHERE id=?", (log_id,))
        await db.commit()
    return JSONResponse({"ok": True})


# ── Admin root redirect
@router.get("", response_class=HTMLResponse)
async def admin_root():
    return RedirectResponse(url="/admin/dashboard", status_code=303)