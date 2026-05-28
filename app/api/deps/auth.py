"""
app/api/deps/auth.py — FastAPI dependency: проверка админ-сессии.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse
from app.services.auth import validate_session


class RequireAdmin:
    async def __call__(self, request: Request):
        token = request.cookies.get("admin_token", "")
        if not await validate_session(token):
            return RedirectResponse(url="/admin/login", status_code=303)
        return token


require_admin = RequireAdmin()