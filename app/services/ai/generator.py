"""
app/services/ai/generator.py
Генерация контента (advice / faq) из KB.
"""
import os
from app.core.config import PROMPTS_DIR
from app.services.knowledge import search_facts
from app.services.ai.gemini_client import call_gemini, parse_json_response
from app.core.logger import get_logger

log = get_logger("generator")


async def generate_content(
    topic: str,
    task_type: str = "advice",
    settings: dict | None = None,
    request_id: str = ""
) -> dict:
    """
    Генерирует статью/FAQ.
    Возвращает {status, title, body, image_hint}.
    """
    settings = settings or {}
    min_vol = settings.get("volume", 400)
    max_vol = int(min_vol * 1.5)
    tone = settings.get("tone", "expert")
    tone_map = {"expert": "экспертный", "formal": "деловой", "friendly": "дружелюбный"}
    tone_ru = tone_map.get(tone, "экспертный")

    # Ищем факты
    facts = await search_facts(topic, min_confidence="medium", limit=8)
    if not facts:
        log.warning(f"Generator: no facts for topic | topic={topic}")
        return {"status": "insufficient_data", "title": None, "body": None, "image_hint": None}

    facts_text = "\n".join(f"- {f['fact']}" for f in facts)

    prompt_path = os.path.join(PROMPTS_DIR, "generator_system.txt")
    try:
        with open(prompt_path, encoding="utf-8") as f:
            system_prompt = (
                f.read()
                .replace("{MIN_CHARS}", str(min_vol))
                .replace("{MAX_CHARS}", str(max_vol))
                .replace("{TONE}", tone_ru)
            )
    except FileNotFoundError:
        system_prompt = f"Generate a {task_type} article in Russian about pellets. {min_vol}-{max_vol} chars. JSON only."

    user_prompt = (
        f"Тип: {task_type}\n"
        f"Тема: {topic}\n\n"
        f"=== ФАКТЫ ИЗ БАЗЫ ЗНАНИЙ ===\n{facts_text}"
    )

    try:
        raw = await call_gemini(system_prompt, user_prompt, request_id=request_id)
        parsed = parse_json_response(raw)
    except Exception as e:
        log.error(f"Generator: gemini error | error={str(e)}")
        return {"status": "insufficient_data", "title": None, "body": None, "image_hint": None}

    if parsed.get("status") == "insufficient_data":
        return {"status": "insufficient_data", "title": None, "body": None, "image_hint": None}

    return {
        "status": "success",
        "title": parsed.get("title", ""),
        "body": parsed.get("body", ""),
        "image_hint": parsed.get("image_hint"),
        "type": task_type
    }