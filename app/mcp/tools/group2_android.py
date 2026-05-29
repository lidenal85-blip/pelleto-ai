"""
app/mcp/tools/group2_android.py
ГРУППА 2: Связь с Android и коммуникация.
Инструменты: send_telegram_notification, android_share_text,
             fetch_starmaker_data, text_to_speech_preview
"""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import httpx

LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись в лог-файл: >> [datetime] [Diff: X/10] msg."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def send_telegram_notification(
    text: str,
    chat_id: str = "",
    file_path: str = "",
    bot_token: str = ""
) -> dict:
    """
    Отправляет текстовый алерт или файл в Telegram через Bot API.
    Поддерживает HTML-разметку в тексте.

    Args:
        text: Текст уведомления (поддерживает HTML)
        chat_id: ID чата (по умолчанию — TELEGRAM_ADMIN_CHAT_ID из env)
        file_path: Путь к файлу для отправки (опционально)
        bot_token: Токен бота (по умолчанию — TELEGRAM_BOT_TOKEN из env)
    """
    token = bot_token or TELEGRAM_BOT_TOKEN
    cid = chat_id or TELEGRAM_ADMIN_CHAT_ID

    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN не задан"}
    if not cid:
        return {"ok": False, "error": "chat_id не задан (TELEGRAM_ADMIN_CHAT_ID пуст)"}

    _log(f"send_telegram_notification: chat={cid} text_len={len(text)} file='{file_path}'", diff=3)

    base_url = f"https://api.telegram.org/bot{token}"

    try:
        if file_path and Path(file_path).exists():
            # Отправляем как документ
            with open(file_path, "rb") as fp:
                resp = httpx.post(
                    f"{base_url}/sendDocument",
                    data={"chat_id": cid, "caption": text[:1024], "parse_mode": "HTML"},
                    files={"document": (Path(file_path).name, fp)},
                    timeout=30
                )
        else:
            # Текстовое сообщение (режим HTML, макс 4096 символов)
            resp = httpx.post(
                f"{base_url}/sendMessage",
                json={"chat_id": cid, "text": text[:4096], "parse_mode": "HTML"},
                timeout=15
            )

        data = resp.json()
        if data.get("ok"):
            msg_id = data.get("result", {}).get("message_id")
            _log(f"send_telegram_notification: OK message_id={msg_id}", diff=3)
            return {"ok": True, "message_id": msg_id}
        else:
            err = data.get("description", "Неизвестная ошибка Telegram API")
            _log(f"send_telegram_notification WARN: {err}", diff=6)
            return {"ok": False, "error": err}

    except Exception as e:
        _log(f"send_telegram_notification ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def android_share_text(
    text: str,
    mode: str = "clipboard"
) -> dict:
    """
    Копирует текст в буфер обмена Android или вызывает диалог «Поделиться».
    Требует Termux API. На сервере — сохраняет текст в файл clipboard.txt.

    Args:
        text: Текст для передачи
        mode: "clipboard" (буфер) или "share" (диалог «Поделиться»)
    """
    _log(f"android_share_text: mode={mode} text_len={len(text)}", diff=2)

    if mode == "clipboard" and shutil.which("termux-clipboard-set"):
        try:
            subprocess.run(
                ["termux-clipboard-set"],
                input=text.encode(),
                check=True,
                timeout=5
            )
            _log("android_share_text: скопировано в буфер Termux", diff=2)
            return {"ok": True, "mode": "clipboard", "backend": "termux"}
        except Exception as e:
            _log(f"android_share_text ERROR: {e}", diff=7)
            return {"ok": False, "error": str(e)}

    elif mode == "share" and shutil.which("termux-share"):
        try:
            proc = subprocess.Popen(["termux-share", "-a", "send"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode(), timeout=10)
            _log("android_share_text: вызван диалог Termux Share", diff=2)
            return {"ok": True, "mode": "share", "backend": "termux"}
        except Exception as e:
            _log(f"android_share_text ERROR: {e}", diff=7)
            return {"ok": False, "error": str(e)}

    else:
        # Fallback для сервера: сохраняем текст в файл
        fallback_path = Path(LOGS_DIR) / "clipboard.txt"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(text)
        _log(f"android_share_text: Termux недоступен, сохранено в {fallback_path}", diff=2)
        return {
            "ok": True,
            "mode": mode,
            "backend": "file_fallback",
            "saved_to": str(fallback_path)
        }


def fetch_starmaker_data(
    contest_url: str,
    fields: list[str] | None = None
) -> dict:
    """
    Парсит открытые данные страниц конкурсов StarMaker.
    Извлекает список участников и треков для сообщества «Союз Голосов».

    Args:
        contest_url: URL страницы конкурса StarMaker
        fields: Список полей для извлечения (по умолчанию — все)
    """
    _log(f"fetch_starmaker_data: url={contest_url[:80]}", diff=6)

    if not contest_url.startswith("http"):
        return {"ok": False, "error": "Некорректный URL (ожидается http/https)"}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0 Mobile Safari/537.36"
        )
    }

    try:
        resp = httpx.get(contest_url, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}

        # Попытка распарсить JSON-ответ если API-эндпоинт
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            data = resp.json()
            _log(f"fetch_starmaker_data: получен JSON, ключей={len(data)}", diff=6)
            return {"ok": True, "format": "json", "data": data}

        # HTML-парсинг (базовый — без selenium)
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            # Извлекаем мета-данные и заголовок
            title = soup.find("title")
            title_text = title.get_text(strip=True) if title else ""
            # Ищем блоки участников (обобщённый паттерн)
            items = []
            for tag in soup.select("[class*=user], [class*=singer], [class*=participant]"):
                name = tag.get_text(strip=True)
                if name:
                    items.append(name[:100])
            _log(f"fetch_starmaker_data: title='{title_text}' участников={len(items)}", diff=6)
            return {
                "ok": True,
                "format": "html",
                "title": title_text,
                "participants": items[:50],
                "raw_preview": resp.text[:500]
            }
        except ImportError:
            # bs4 не установлен — возвращаем сырой HTML-превью
            return {
                "ok": True,
                "format": "html_raw",
                "raw_preview": resp.text[:2000],
                "note": "Установите beautifulsoup4 для полного парсинга"
            }

    except Exception as e:
        _log(f"fetch_starmaker_data ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def text_to_speech_preview(
    text: str,
    language: str = "ru",
    rate: float = 1.0
) -> dict:
    """
    Озвучивает текст через termux-tts-speak (Android) или espeak (Linux).
    Используется для критических уведомлений и статусов архитектуры.

    Args:
        text: Текст для озвучивания
        language: Код языка (ru, en, etc.)
        rate: Скорость (0.5 — медленно, 1.0 — норма, 2.0 — быстро)
    """
    _log(f"text_to_speech_preview: lang={language} rate={rate} text='{text[:50]}'", diff=2)

    # Termux-окружение (Android)
    if shutil.which("termux-tts-speak"):
        try:
            subprocess.run(
                ["termux-tts-speak", "-l", language, "-r", str(rate), text],
                check=True, timeout=30
            )
            _log("text_to_speech_preview: озвучено через termux-tts-speak", diff=2)
            return {"ok": True, "backend": "termux-tts-speak"}
        except Exception as e:
            _log(f"text_to_speech_preview ERROR: {e}", diff=7)
            return {"ok": False, "error": str(e)}

    # Linux-сервер: попытка через espeak
    if shutil.which("espeak") or shutil.which("espeak-ng"):
        binary = "espeak-ng" if shutil.which("espeak-ng") else "espeak"
        try:
            speed = int(rate * 160)  # espeak: слов/минуту (160 = норма)
            subprocess.run(
                [binary, "-v", language, "-s", str(speed), text],
                check=True, timeout=30
            )
            _log(f"text_to_speech_preview: озвучено через {binary}", diff=2)
            return {"ok": True, "backend": binary}
        except Exception as e:
            _log(f"text_to_speech_preview ERROR: {e}", diff=7)
            return {"ok": False, "error": str(e)}

    _log("text_to_speech_preview: TTS движок не найден", diff=2)
    return {
        "ok": False,
        "error": "TTS движок не найден (нет termux-tts-speak / espeak-ng)",
        "suggestion": "В Termux: pkg install termux-api; На Linux: apt install espeak-ng"
    }
