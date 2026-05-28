"""
app/services/auth/service.py — bcrypt аутентификация, сессии, rate limiting.
"""
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.config import (
    MASTER_KEY_HASH, SESSION_LIFETIME_HOURS,
    MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES
)

log = get_logger("auth")


def verify_master_key(attempt: str) -> bool:
    if not MASTER_KEY_HASH:
        log.error("MASTER_KEY_HASH not set in env")
        return False
    return bcrypt.checkpw(attempt.encode(), MASTER_KEY_HASH.encode())


async def check_rate_limit(ip: str) -> dict:
    """Возвращает {blocked, attempts_left}."""
    async with get_db() as db:
        async with db.execute(
            "SELECT count, blocked_until FROM login_attempts WHERE ip=?", (ip,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return {"blocked": False, "attempts_left": MAX_LOGIN_ATTEMPTS}

    if row["blocked_until"]:
        blocked_until = datetime.fromisoformat(row["blocked_until"])
        if datetime.now(timezone.utc) < blocked_until:
            return {"blocked": True, "attempts_left": 0}

    attempts_left = max(0, MAX_LOGIN_ATTEMPTS - row["count"])
    return {"blocked": False, "attempts_left": attempts_left}


async def record_failed_attempt(ip: str) -> int:
    """Записывает неудачную попытку, возвращает кол-во попыток."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        async with db.execute(
            "SELECT count FROM login_attempts WHERE ip=?", (ip,)
        ) as cur:
            row = await cur.fetchone()

        new_count = (row["count"] + 1) if row else 1
        blocked_until = None
        if new_count >= MAX_LOGIN_ATTEMPTS:
            blocked_until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            log.warning(f"IP blocked | ip={ip} blocked_until={blocked_until}")

        await db.execute(
            """INSERT INTO login_attempts(ip, count, blocked_until, last_attempt)
               VALUES(?,?,?,?)
               ON CONFLICT(ip) DO UPDATE SET
                 count=excluded.count,
                 blocked_until=excluded.blocked_until,
                 last_attempt=excluded.last_attempt""",
            (ip, new_count, blocked_until, now)
        )
        await db.commit()
    return new_count


async def clear_attempts(ip: str) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM login_attempts WHERE ip=?", (ip,))
        await db.commit()


async def create_session(ip: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(hours=SESSION_LIFETIME_HOURS)).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO admin_sessions(token, ip, created_at, expires_at) VALUES(?,?,?,?)",
            (token, ip, now.isoformat(), expires)
        )
        await db.commit()
    log.info(f"Session created | ip={ip}")
    return token


async def validate_session(token: str) -> bool:
    if not token:
        return False
    async with get_db() as db:
        async with db.execute(
            "SELECT expires_at FROM admin_sessions WHERE token=?", (token,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return False
    expires = datetime.fromisoformat(row["expires_at"])
    return datetime.now(timezone.utc) < expires


async def delete_session(token: str) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM admin_sessions WHERE token=?", (token,))
        await db.commit()