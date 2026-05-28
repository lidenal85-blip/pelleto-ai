"""
app/api/routes/landing.py — M1: публичная страница.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.content import get_published_blocks, list_products
from app.core.config import TEMPLATES_DIR, SITE_NAME, SITE_PHONE, SITE_ADDRESS, SITE_VERSION, AGENT_ENABLED

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    advice_blocks = await get_published_blocks("advice")
    faq_blocks = await get_published_blocks("faq")
    products = await list_products(active_only=True)
    return templates.TemplateResponse(
        "landing/index.html",
        {
            "request": request,
            "advice_blocks": advice_blocks,
            "faq_blocks": faq_blocks,
            "products": products,
            "site_name": SITE_NAME,
            "site_phone": SITE_PHONE,
            "site_address": SITE_ADDRESS,
            "site_version": SITE_VERSION,
            "agent_enabled": AGENT_ENABLED,
        }
    )


@router.get("/order", response_class=HTMLResponse)
async def order_page(request: Request):
    return templates.TemplateResponse(
        "landing/order.html",
        {"request": request, "site_phone": SITE_PHONE, "site_name": SITE_NAME}
    )