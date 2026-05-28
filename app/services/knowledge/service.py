"""
app/services/knowledge/service.py — CRUD + FTS5-поиск Базы знаний.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from app.core.database import get_db
from app.core.logger import get_logger

log = get_logger("knowledge")


async def search_facts(
    query: str,
    topics: list[str] | None = None,
    min_confidence: str = "medium",
    limit: int = 5
) -> list[dict]:
    """
    FTS5-поиск по fact + topics_text.
    min_confidence: high > medium > low
    """
    conf_order = {"high": 3, "medium": 2, "low": 1}
    min_val = conf_order.get(min_confidence, 2)

    async with get_db() as db:
        if query.strip():
            fts_query = " OR ".join(query.split())
            sql = """
                SELECT kf.*
                FROM knowledge_fts
                JOIN knowledge_facts kf ON kf.id = knowledge_fts.id
                WHERE knowledge_fts MATCH ?
                  AND (CASE kf.confidence WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) >= ?
                ORDER BY rank
                LIMIT ?
            """
            params = (fts_query, min_val, limit)
        else:
            sql = """
                SELECT * FROM knowledge_facts
                WHERE (CASE confidence WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) >= ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (min_val, limit)

        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["topics"] = json.loads(d.get("topics", "[]"))
        d["countries"] = json.loads(d.get("countries", '["ru"]'))
        result.append(d)

    log.info(f"KB search | query={query[:50]} found={len(result)}")
    return result


async def get_fact(fact_id: str) -> Optional[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM knowledge_facts WHERE id=?", (fact_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["topics"] = json.loads(d.get("topics", "[]"))
    d["countries"] = json.loads(d.get("countries", '["ru"]'))
    return d


async def list_facts(limit: int = 100, offset: int = 0) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM knowledge_facts ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["topics"] = json.loads(d.get("topics", "[]"))
        d["countries"] = json.loads(d.get("countries", '["ru"]'))
        result.append(d)
    return result


async def count_facts() -> int:
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM knowledge_facts") as cur:
            (n,) = await cur.fetchone()
    return n


async def add_fact(data: dict) -> str:
    fact_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    topics = json.dumps(data.get("topics", []), ensure_ascii=False)
    countries = json.dumps(data.get("countries", ["ru"]), ensure_ascii=False)
    async with get_db() as db:
        await db.execute(
            """INSERT INTO knowledge_facts
               (id,type,topics,fact,source,confidence,countries,sales_hook,agent_trigger,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fact_id,
                data.get("type", "expert_case"),
                topics,
                data["fact"],
                data.get("source", ""),
                data.get("confidence", "medium"),
                countries,
                data.get("sales_hook"),
                1 if data.get("agent_trigger", True) else 0,
                now, now
            )
        )
        await db.commit()
    log.info(f"Fact added | id={fact_id}")
    return fact_id


async def delete_fact(fact_id: str) -> bool:
    async with get_db() as db:
        await db.execute("DELETE FROM knowledge_facts WHERE id=?", (fact_id,))
        await db.commit()
    log.info(f"Fact deleted | id={fact_id}")
    return True


async def seed_from_file(json_path: str) -> int:
    """Load seed facts from JSON file if KB is empty."""
    n = await count_facts()
    if n > 0:
        log.info(f"KB already has facts, skip seed | count={n}")
        return 0
    import aiofiles
    async with aiofiles.open(json_path, encoding="utf-8") as f:
        content = await f.read()
    facts = json.loads(content)
    added = 0
    for fact in facts:
        try:
            await add_fact(fact)
            added += 1
        except Exception as e:
            log.error(f"Seed fact error | error={str(e)}")
    log.info(f"KB seeded | added={added}")
    return added