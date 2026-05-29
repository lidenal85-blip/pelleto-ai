"""
app/api/deps/auth.py — проверка админ-сессии.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse
from app.services.auth import validate_session


class AdminNotAuthenticated(Exception):
    pass


async def require_admin(request: Request) -> str:
    token = request.cookies.get("admin_token", "")
    if not await validate_session(token):
        raise AdminNotAuthenticated()
    return token