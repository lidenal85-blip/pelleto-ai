"""
app/core/database.py — aiosqlite пул + инициализация схемы + seed.
WAL mode + busy_timeout для параллельных чтений из AI модулей.
"""
import os
import json
import uuid
import aiosqlite
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from app.core.config import DB_PATH, DB_BUSY_TIMEOUT_MS, DATA_DIR
from app.core.logger import get_logger

log = get_logger("database")


@asynccontextmanager
async def get_db():
    """Async context manager for DB connection."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_facts (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL DEFAULT 'expert_case',
    topics        TEXT NOT NULL DEFAULT '[]',
    fact          TEXT NOT NULL,
    source        TEXT DEFAULT '',
    confidence    TEXT NOT NULL DEFAULT 'medium',
    countries     TEXT NOT NULL DEFAULT '["ru"]',
    sales_hook    TEXT DEFAULT NULL,
    agent_trigger INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
USING fts5(id UNINDEXED, fact, topics_text,
           content='knowledge_facts', content_rowid='rowid');

CREATE TRIGGER IF NOT EXISTS kf_ai AFTER INSERT ON knowledge_facts BEGIN
  INSERT INTO knowledge_fts(rowid,id,fact,topics_text)
  VALUES(new.rowid,new.id,new.fact,new.topics);
END;
CREATE TRIGGER IF NOT EXISTS kf_ad AFTER DELETE ON knowledge_facts BEGIN
  INSERT INTO knowledge_fts(knowledge_fts,rowid,id,fact,topics_text)
  VALUES('delete',old.rowid,old.id,old.fact,old.topics);
END;
CREATE TRIGGER IF NOT EXISTS kf_au AFTER UPDATE ON knowledge_facts BEGIN
  INSERT INTO knowledge_fts(knowledge_fts,rowid,id,fact,topics_text)
  VALUES('delete',old.rowid,old.id,old.fact,old.topics);
  INSERT INTO knowledge_fts(rowid,id,fact,topics_text)
  VALUES(new.rowid,new.id,new.fact,new.topics);
END;

CREATE TABLE IF NOT EXISTS content_blocks (
    id             TEXT PRIMARY KEY,
    type           TEXT NOT NULL DEFAULT 'advice',
    title          TEXT NOT NULL,
    body           TEXT NOT NULL,
    image_hint     TEXT DEFAULT NULL,
    status         TEXT NOT NULL DEFAULT 'draft',
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    published_at   TEXT DEFAULT NULL,
    source_task_id TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    price_min   REAL DEFAULT NULL,
    price_max   REAL DEFAULT NULL,
    unit        TEXT NOT NULL DEFAULT 'т',
    photo_url   TEXT DEFAULT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token      TEXT PRIMARY KEY,
    ip         TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    ip            TEXT PRIMARY KEY,
    count         INTEGER NOT NULL DEFAULT 0,
    blocked_until TEXT DEFAULT NULL,
    last_attempt  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dialogue_logs (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    request_id TEXT DEFAULT NULL,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    phase      TEXT DEFAULT NULL,
    confidence TEXT DEFAULT NULL,
    has_error  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dl_session ON dialogue_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_dl_error   ON dialogue_logs(has_error);

CREATE TABLE IF NOT EXISTS publication_queue (
    id             TEXT PRIMARY KEY,
    content_data   TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    task_settings  TEXT DEFAULT NULL,
    created_at     TEXT NOT NULL,
    reviewed_at    TEXT DEFAULT NULL,
    reviewed_by_ip TEXT DEFAULT NULL
);
"""


async def init_db() -> None:
    """Create schema. Idempotent. Uses executescript to handle triggers."""
    log.info(f"Initializing DB schema: {DB_PATH}")
    # executescript runs outside transaction context, so we open raw connection
    import sqlite3
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.close()
    log.info("DB schema OK")
    await seed_products()


async def seed_products() -> None:
    """Insert default products if table is empty."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            (count,) = await cur.fetchone()
        if count > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        products = [
            (str(uuid.uuid4()), "Пеллеты Светлые (Премиум)",
             "Древесные гранулы высшего качества из хвойных пород. "
             "Для автоматических бытовых котлов. Минимальная зольность.",
             13500.0, 15000.0, "т", None, 1, 1, now),
            (str(uuid.uuid4()), "Пеллеты Индустриальные",
             "Прочные серые гранулы для крупных котлов и промышленных мощностей. "
             "Высокая теплоотдача при доступной цене.",
             10500.0, 12000.0, "т", None, 1, 2, now),
            (str(uuid.uuid4()), "Пеллеты в мешках 15 кг",
             "Удобная фасовка для самостоятельной загрузки и хранения. "
             "Подходит для дачников с небольшим котлом.",
             220.0, 280.0, "мешок", None, 1, 3, now),
            (str(uuid.uuid4()), "Биг-бэг  700 кг",
             "Оптовая покупка с доставкой. Оптимально для всего сезона нагрева. "
             "Доставим и разгрузим на место.",
             9200.0, 10500.0, "биг-бэг", None, 1, 4, now),
        ]
        await db.executemany(
            "INSERT INTO products(id,name,description,price_min,price_max,unit,photo_url,active,sort_order,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            products
        )
        await db.commit()
        log.info(f"Seeded default products: {len(products)}")