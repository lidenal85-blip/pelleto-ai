"""
app/services/ai/gemini_client.py
Gemini через google-generativeai SDK.
Ротация K1..K14 при ошибке 429.
Circuit breaker: 3 ошибки за 60 с -> open 30 с.
"""
import os
import time
import json
import asyncio
from app.core.logger import get_logger
from app.core.config import (
    GEMINI_MODEL, GEMINI_TIMEOUT, GEMINI_MAX_TOKENS,
    CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT, CB_WINDOW
)

log = get_logger("gemini")

_KEYS = [v for k, v in sorted(os.environ.items()) if k.startswith("GEMINI_K") and v]
_key_idx = 0

# Circuit breaker state
_cb_failures: list[float] = []
_cb_open_until: float = 0.0


def _cb_is_open() -> bool:
    now = time.time()
    if now < _cb_open_until:
        return True
    global _cb_failures
    _cb_failures = [t for t in _cb_failures if now - t < CB_WINDOW]
    return False


def _cb_record_failure():
    global _cb_failures, _cb_open_until
    _cb_failures.append(time.time())
    if len(_cb_failures) >= CB_FAILURE_THRESHOLD:
        _cb_open_until = time.time() + CB_RECOVERY_TIMEOUT
        log.warning(f"Circuit breaker OPEN | recovery_in={CB_RECOVERY_TIMEOUT}")


def _cb_record_success():
    global _cb_failures
    _cb_failures.clear()


async def call_gemini(system_prompt: str, user_prompt: str, request_id: str = "") -> str:
    """
    Вызывает Gemini, возвращает строку-ответ.
    При ошибке 429 переключается на следующий ключ.
    При circuit breaker open — бросает RuntimeError.
    """
    if _cb_is_open():
        raise RuntimeError("circuit_open")

    import google.generativeai as genai

    global _key_idx
    attempts = len(_KEYS)
    last_err = None

    for _ in range(attempts):
        key = _KEYS[_key_idx % len(_KEYS)]
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=system_prompt
            )
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    user_prompt,
                    generation_config={"max_output_tokens": GEMINI_MAX_TOKENS, "temperature": 0.3}
                ),
                timeout=GEMINI_TIMEOUT
            )
            _cb_record_success()
            log.info(f"Gemini OK | key_idx={_key_idx % len(_KEYS)} request_id={request_id}")
            return resp.text
        except Exception as e:
            err_str = str(e)
            last_err = e
            if "429" in err_str or "quota" in err_str.lower():
                log.warning(f"Gemini 429, rotating key | key_idx={_key_idx % len(_KEYS)}")
                _key_idx += 1
                continue
            _cb_record_failure()
            log.error(f"Gemini error | error={err_str} request_id={request_id}")
            raise

    _cb_record_failure()
    raise RuntimeError(f"All Gemini keys exhausted: {last_err}")


def strip_json_fences(text: str) -> str:
    """Strip ```json ... ``` или ``` ... ``` вокруг JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return text


def parse_json_response(text: str) -> dict:
    cleaned = strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Попытка найти JSON в тексте
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start:end+1])
        raise


def circuit_status() -> str:
    return "open" if _cb_is_open() else "closed"