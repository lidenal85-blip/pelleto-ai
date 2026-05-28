"""
app/services/content/service.py — ContentStore и ProductStore.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from app.core.database import get_db
from app.core.logger import get_logger

log = get_logger("content")

_cache_version = 0

def get_cache_version() -> int:
    return _cache_version

def invalidate_cache() -> None:
    global _cache_version
    _cache_version += 1
    log.info(f"Landing cache invalidated | version={_cache_version}")


# ── ContentBlocks ────────────────────────────────────────────────────────────

async def get_published_blocks(block_type: str | None = None) -> list[dict]:
    async with get_db() as db:
        if block_type:
            sql = "SELECT * FROM content_blocks WHERE status='published' AND type=? ORDER BY sort_order, published_at DESC"
            params = (block_type,)
        else:
            sql = "SELECT * FROM content_blocks WHERE status='published' ORDER BY sort_order, published_at DESC"
            params = ()
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def list_blocks(status: str | None = None) -> list[dict]:
    async with get_db() as db:
        if status:
            sql = "SELECT * FROM content_blocks WHERE status=? ORDER BY created_at DESC"
            params = (status,)
        else:
            sql = "SELECT * FROM content_blocks ORDER BY created_at DESC"
            params = ()
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_block(block_id: str) -> Optional[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM content_blocks WHERE id=?", (block_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def save_block(data: dict) -> str:
    block_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO content_blocks(id,type,title,body,image_hint,status,sort_order,created_at,source_task_id)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                block_id, data.get("type", "advice"),
                data["title"], data["body"],
                data.get("image_hint"),
                data.get("status", "draft"),
                data.get("sort_order", 0),
                now, data.get("source_task_id")
            )
        )
        await db.commit()
    return block_id


async def publish_block(block_id: str) -> bool:
    """draft → published. Атомарно."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "UPDATE content_blocks SET status='published', published_at=? WHERE id=? AND status='draft'",
            (now, block_id)
        )
        await db.commit()
    invalidate_cache()
    return True


async def reject_block(block_id: str) -> bool:
    async with get_db() as db:
        await db.execute(
            "UPDATE content_blocks SET status='archived' WHERE id=?", (block_id,)
        )
        await db.commit()
    return True


async def delete_block(block_id: str) -> bool:
    async with get_db() as db:
        await db.execute("DELETE FROM content_blocks WHERE id=?", (block_id,))
        await db.commit()
    return True


# ── PublicationQueue ─────────────────────────────────────────────────────────

async def queue_content(content_data: dict, task_settings: dict | None = None) -> str:
    q_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO publication_queue(id,content_data,status,task_settings,created_at)
               VALUES(?,?,?,?,?)""",
            (q_id, json.dumps(content_data, ensure_ascii=False),
             "pending", json.dumps(task_settings or {}, ensure_ascii=False), now)
        )
        await db.commit()
    return q_id


async def list_queue(status: str | None = None) -> list[dict]:
    async with get_db() as db:
        if status:
            sql = "SELECT * FROM publication_queue WHERE status=? ORDER BY created_at DESC"
            params = (status,)
        else:
            sql = "SELECT * FROM publication_queue ORDER BY created_at DESC"
            params = ()
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["content_data"] = json.loads(d["content_data"])
        d["task_settings"] = json.loads(d.get("task_settings") or "{}")
        result.append(d)
    return result


async def approve_queue_item(q_id: str, reviewer_ip: str) -> Optional[str]:
    """Утверждает черновик, публикует в ContentStore. Атомарно."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM publication_queue WHERE id=? AND status='pending'", (q_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None

        content_data = json.loads(row["content_data"])
        block_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        try:
            await db.execute(
                """INSERT INTO content_blocks(id,type,title,body,image_hint,status,sort_order,created_at,published_at,source_task_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (block_id, content_data.get("type", "advice"),
                 content_data["title"], content_data["body"],
                 content_data.get("image_hint"),
                 "published", 0, now, now, q_id)
            )
            await db.execute(
                "UPDATE publication_queue SET status='approved', reviewed_at=?, reviewed_by_ip=? WHERE id=?",
                (now, reviewer_ip, q_id)
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            log.error(f"Approve failed, rolled back | error={str(e)}")
            raise

    invalidate_cache()
    log.info(f"Queue item approved | q_id={q_id} block_id={block_id}")
    return block_id


async def reject_queue_item(q_id: str, reviewer_ip: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            "UPDATE publication_queue SET status='rejected', reviewed_at=?, reviewed_by_ip=? WHERE id=? AND status='pending'",
            (now, reviewer_ip, q_id)
        )
        await db.commit()
    return True


# ── Products ─────────────────────────────────────────────────────────────────

async def list_products(active_only: bool = False) -> list[dict]:
    async with get_db() as db:
        sql = "SELECT * FROM products"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY sort_order, name"
        async with db.execute(sql) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_product(product_id: str) -> Optional[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM products WHERE id=?", (product_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def upsert_product(data: dict) -> str:
    now = datetime.now(timezone.utc).isoformat()
    product_id = data.get("id") or str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO products(id,name,description,price_min,price_max,unit,photo_url,active,sort_order,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, description=excluded.description,
                 price_min=excluded.price_min, price_max=excluded.price_max,
                 unit=excluded.unit, photo_url=excluded.photo_url,
                 active=excluded.active, sort_order=excluded.sort_order,
                 updated_at=excluded.updated_at""",
            (product_id, data["name"], data.get("description", ""),
             data.get("price_min"), data.get("price_max"),
             data.get("unit", "т"), data.get("photo_url"),
             1 if data.get("active", True) else 0,
             data.get("sort_order", 0), now)
        )
        await db.commit()
    return product_id


async def delete_product(product_id: str) -> bool:
    async with get_db() as db:
        await db.execute("DELETE FROM products WHERE id=?", (product_id,))
        await db.commit()
    return True