"""
app/services/ai/agent.py
AI-агент: HistorySanitizer, DialoguePhaseTracker, HallucinationGuard, ответ.
"""
import re
from app.core.config import (
    AGENT_MAX_QUESTION_LEN, AGENT_MAX_HISTORY,
    PHASE_EXPLORATION_AT, PHASE_CLOSING_AT, SITE_PHONE
)
from app.services.knowledge import search_facts
from app.services.ai.gemini_client import call_gemini, parse_json_response
from app.core.logger import get_logger

log = get_logger("agent")

FALLBACK_ANSWER = (
    f"Наш консультант временно недоступен. "
    f"Позвоните нам: {SITE_PHONE}"
)


def sanitize_history(history: list) -> list:
    """Очищает историю: только user/assistant, макс 500 симв, макс 10 сообщ."""
    clean = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content", ""))[:500]
        content = re.sub(r"<[^>]+>", "", content)  # strip HTML
        clean.append({"role": role, "content": content})
    return clean[-AGENT_MAX_HISTORY:]


def get_phase(history: list) -> str:
    n = len(history)
    if n < PHASE_EXPLORATION_AT:
        return "initial"
    if n < PHASE_CLOSING_AT:
        return "exploration"
    return "closing"


async def ask_agent(
    question: str,
    session_id: str,
    history: list,
    request_id: str = ""
) -> dict:
    """
    Главная функция агента.
    Возвращает {answer, cta_show, cta_text, phase, confidence}.
    """
    question = question[:AGENT_MAX_QUESTION_LEN]
    history = sanitize_history(history)
    phase = get_phase(history)

    # Поиск фактов в KB
    facts = await search_facts(question, min_confidence="medium", limit=5)
    facts_text = "\n".join(
        f"- {f['fact']}" + (f" [{f.get('sales_hook','')}]" if f.get("sales_hook") else "")
        for f in facts
    ) or "Фактов по теме нет."

    # Читаем системный промпт из файла
    import os
    from app.core.config import PROMPTS_DIR
    prompt_path = os.path.join(PROMPTS_DIR, "agent_system.txt")
    try:
        with open(prompt_path, encoding="utf-8") as f:
            system_prompt = f.read().replace("{SITE_PHONE}", SITE_PHONE)
    except FileNotFoundError:
        system_prompt = "Ты — консультант по пеллетам. Отвечай только на темы: пеллеты, котлы, доставка. JSON."

    system_prompt += f"\n\n[PHASE]: {phase}"

    # Формируем user-промпт
    history_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    user_prompt = (
        f"=== БАЗА ЗНАНИЙ ===\n{facts_text}\n\n"
        f"=== ИСТОРИЯ ДИАЛОГА ===\n{history_text}\n\n"
        f"=== ТЕКУЩИЙ ВОПРОС ===\n{question}"
    )

    try:
        raw = await call_gemini(system_prompt, user_prompt, request_id=request_id)
        parsed = parse_json_response(raw)
    except RuntimeError as e:
        if "circuit_open" in str(e):
            log.warning(f"Agent: circuit open | request_id={request_id}")
        else:
            log.error(f"Agent: gemini error | error={str(e)}")
        return {
            "answer": FALLBACK_ANSWER,
            "cta_show": False, "cta_text": None,
            "phase": phase, "confidence": "low"
        }
    except Exception as e:
        log.error(f"Agent: unexpected error | error={str(e)}")
        return {
            "answer": FALLBACK_ANSWER,
            "cta_show": False, "cta_text": None,
            "phase": phase, "confidence": "low"
        }

    # HallucinationGuard: если confidence=low — предлагаем позвонить
    if parsed.get("confidence") == "low":
        answer = parsed.get("answer", FALLBACK_ANSWER)
        if SITE_PHONE not in answer:
            answer += f" Позвоните: {SITE_PHONE}"
        return {
            "answer": answer,
            "cta_show": False, "cta_text": None,
            "phase": phase, "confidence": "low"
        }

    return {
        "answer": parsed.get("answer", FALLBACK_ANSWER),
        "cta_show": bool(parsed.get("cta_show", phase == "closing")),
        "cta_text": parsed.get("cta_text", "Оформить заказ"),
        "phase": phase,
        "confidence": parsed.get("confidence", "medium")
    }