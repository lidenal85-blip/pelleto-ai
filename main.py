"""
main.py — точка входа FastAPI приложения Pelleto AI.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.core.config import PORT, DEBUG, SITE_VERSION, STATIC_DIR, DATA_DIR
from app.core.database import init_db
from app.core.logger import get_logger
from app.api.routes.landing import router as landing_router
from app.api.routes.agent import router as agent_router
from app.api.routes.admin import router as admin_router
from app.api.deps.auth import AdminNotAuthenticated

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting Pelleto AI v{SITE_VERSION}")
    await init_db()
    await seed_kb_if_empty()
    log.info(f"Pelleto AI ready on port {PORT}")
    yield
    log.info("Pelleto AI shutdown")


async def seed_kb_if_empty():
    import json
    from app.core.database import get_db
    seed_path = os.path.join(DATA_DIR, "knowledge_base_seed.json")
    if not os.path.exists(seed_path):
        return
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM knowledge_facts") as cur:
            (count,) = await cur.fetchone()
    if count > 0:
        log.info(f"KB already seeded: {count} facts")
        return
    try:
        with open(seed_path, encoding="utf-8") as f:
            facts = json.load(f)
        from app.services.knowledge import add_fact
        added = 0
        for fact in facts:
            try:
                await add_fact(fact)
                added += 1
            except Exception as e:
                log.warning(f"Seed fact skip: {e}")
        log.info(f"KB seeded: {added} facts")
    except Exception as e:
        log.error(f"KB seed failed: {e}")


app = FastAPI(
    title="Pelleto AI",
    version=SITE_VERSION,
    debug=DEBUG,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(landing_router)
app.include_router(agent_router)
app.include_router(admin_router)


@app.exception_handler(AdminNotAuthenticated)
async def admin_auth_redirect(request: Request, exc: AdminNotAuthenticated):
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/health")
async def health():
    from app.services.ai.gemini_client import circuit_status
    from app.core.config import AGENT_ENABLED
    return {
        "status": "ok",
        "version": SITE_VERSION,
        "agent_enabled": AGENT_ENABLED,
        "llm_circuit": circuit_status(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=DEBUG)