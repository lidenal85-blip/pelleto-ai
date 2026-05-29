"""
app/services/ai/agent.py
AI-агент: HistorySanitizer, DialoguePhaseTracker, HallucinationGuard,
          MCP-инструменты через Gemini function calling.
"""
import re
import json
from app.core.config import (
    AGENT_MAX_QUESTION_LEN, AGENT_MAX_HISTORY,
    PHASE_EXPLORATION_AT, PHASE_CLOSING_AT, SITE_PHONE
)
from app.services.knowledge import search_facts
from app.services.ai.gemini_client import call_gemini, call_gemini_with_tools, parse_json_response
from app.core.logger import get_logger

log = get_logger("agent")

FALLBACK_ANSWER = (
    f"Наш консультант временно недоступен. "
    f"Позвоните нам: {SITE_PHONE}"
)

# Максимум итераций tool-use loop (защита от бесконечных циклов)
_MAX_TOOL_ITERATIONS = 3


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


def _is_tool_request(question: str) -> bool:
    """
    Эвристика: определяет, требует ли вопрос вызова MCP-инструментов.
    Активируется при явных операционных запросах (не консультация по пеллетам).
    """
    tool_keywords = (
        "логи", "база данных", "схема", "таблица", "бэкап", "резервн",
        "telegram", "уведомлен", "проверь синтаксис", "структура файла",
        "мониторинг", "ресурсы", "cpu", "ram", "промпт", "скачай",
        "markdown", "ресурсы сервера", "time log", "журнал времени"
    )
    q_lower = question.lower()
    return any(kw in q_lower for kw in tool_keywords)


async def ask_agent(
    question: str,
    session_id: str,
    history: list,
    request_id: str = "",
    use_tools: bool = False
) -> dict:
    """
    Главная функция агента.
    Возвращает {answer, cta_show, cta_text, phase, confidence, tool_calls_used}.

    use_tools=True активирует MCP-инструменты через Gemini function calling.
    Автоматически включается для операционных запросов.
    """
    question = question[:AGENT_MAX_QUESTION_LEN]
    history = sanitize_history(history)
    phase = get_phase(history)

    # Автодетект необходимости инструментов
    if not use_tools:
        use_tools = _is_tool_request(question)

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

    tool_calls_used: list[str] = []

    try:
        if use_tools:
            # ── Режим с MCP-инструментами: tool-use loop ─────────────────────
            raw, tool_calls_used = await _run_with_tools(
                system_prompt, user_prompt, request_id
            )
        else:
            # ── Обычный режим без инструментов ───────────────────────────────
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
            "phase": phase, "confidence": "low",
            "tool_calls_used": tool_calls_used
        }
    except Exception as e:
        log.error(f"Agent: unexpected error | error={str(e)}")
        return {
            "answer": FALLBACK_ANSWER,
            "cta_show": False, "cta_text": None,
            "phase": phase, "confidence": "low",
            "tool_calls_used": tool_calls_used
        }

    # HallucinationGuard: если confidence=low — предлагаем позвонить
    if parsed.get("confidence") == "low":
        answer = parsed.get("answer", FALLBACK_ANSWER)
        if SITE_PHONE not in answer:
            answer += f" Позвоните: {SITE_PHONE}"
        return {
            "answer": answer,
            "cta_show": False, "cta_text": None,
            "phase": phase, "confidence": "low",
            "tool_calls_used": tool_calls_used
        }

    return {
        "answer": parsed.get("answer", FALLBACK_ANSWER),
        "cta_show": bool(parsed.get("cta_show", phase == "closing")),
        "cta_text": parsed.get("cta_text", "Оформить заказ"),
        "phase": phase,
        "confidence": parsed.get("confidence", "medium"),
        "tool_calls_used": tool_calls_used
    }


async def _run_with_tools(
    system_prompt: str,
    user_prompt: str,
    request_id: str
) -> tuple[str, list[str]]:
    """
    Tool-use loop: Gemini запрашивает инструменты → выполняем → возвращаем результат.
    Возвращает (финальный_ответ, список_вызванных_инструментов).
    """
    from app.mcp.registry import dispatch_tool, GEMINI_TOOL_DECLARATIONS

    tool_calls_used: list[str] = []
    messages = [{"role": "user", "parts": [{"text": user_prompt}]}]

    for iteration in range(_MAX_TOOL_ITERATIONS):
        response = await call_gemini_with_tools(
            system_prompt=system_prompt,
            messages=messages,
            tools=GEMINI_TOOL_DECLARATIONS,
            request_id=request_id
        )

        # Если Gemini вернул function_call — выполняем инструмент
        if response.get("type") == "function_call":
            fn_name = response["name"]
            fn_args = response.get("args", {})

            log.info(f"Agent tool call: {fn_name}({list(fn_args.keys())}) | iter={iteration}")
            tool_calls_used.append(fn_name)

            # Выполняем инструмент
            tool_result = dispatch_tool(fn_name, fn_args)
            result_text = json.dumps(tool_result, ensure_ascii=False, default=str)

            # Добавляем вызов и результат в историю диалога с Gemini
            messages.append({
                "role": "model",
                "parts": [{"function_call": {"name": fn_name, "args": fn_args}}]
            })
            messages.append({
                "role": "user",
                "parts": [{"function_response": {"name": fn_name, "response": {"result": result_text}}}]
            })
            # Продолжаем цикл — Gemini формирует следующий шаг
            continue

        # Gemini вернул текстовый ответ — выходим из цикла
        return response.get("text", ""), tool_calls_used

    # Превышено число итераций — возвращаем последний текстовый ответ
    log.warning(f"Agent: tool loop max iterations reached ({_MAX_TOOL_ITERATIONS})")
    final = await call_gemini(system_prompt, user_prompt, request_id=request_id)
    return final, tool_calls_used
