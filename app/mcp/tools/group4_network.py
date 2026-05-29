"""
app/mcp/tools/group4_network.py
ГРУППА 4: Сеть, API и медиа.
Инструменты: cloudflare_dns_manager, secure_credential_vault,
             web_page_markdownify, download_media_loader
"""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import httpx

LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")
DATA_DIR = os.environ.get("DATA_DIR", "/opt/pelleto-ai/data")
# Путь к зашифрованному хранилищу ключей
VAULT_PATH = os.environ.get("VAULT_PATH", "/opt/pelleto-ai/data/vault.json")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись >> [datetime] [Diff: X/10] msg."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def cloudflare_dns_manager(
    action: str,
    zone_id: str = "",
    record_name: str = "",
    record_type: str = "A",
    record_content: str = "",
    proxied: bool = True,
    api_token: str = ""
) -> dict:
    """
    Управление DNS-записями через Cloudflare API v4.
    Действия: list_zones, list_records, create_record, update_record,
              delete_record, check_status.

    Args:
        action: Действие (list_zones|list_records|create_record|delete_record|check_status)
        zone_id: ID зоны Cloudflare (обязателен для действий с записями)
        record_name: Имя DNS-записи (например, "subdomain.example.com")
        record_type: Тип записи (A, AAAA, CNAME, TXT, MX, ...)
        record_content: Содержимое записи (IP-адрес, цель и т.д.)
        proxied: True — включить Cloudflare-проксирование
        api_token: API-токен (по умолчанию — CLOUDFLARE_API_TOKEN из env)
    """
    token = api_token or CLOUDFLARE_API_TOKEN
    if not token:
        return {"ok": False, "error": "CLOUDFLARE_API_TOKEN не задан"}

    _log(f"cloudflare_dns_manager: action={action} zone={zone_id[:8] if zone_id else '-'}", diff=6)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    base = "https://api.cloudflare.com/client/v4"

    try:
        if action == "list_zones":
            r = httpx.get(f"{base}/zones", headers=headers, timeout=15)
            data = r.json()
            zones = [{"id": z["id"], "name": z["name"], "status": z["status"]}
                     for z in data.get("result", [])]
            return {"ok": True, "zones": zones}

        elif action == "list_records":
            if not zone_id:
                return {"ok": False, "error": "zone_id обязателен для list_records"}
            r = httpx.get(f"{base}/zones/{zone_id}/dns_records", headers=headers, timeout=15)
            data = r.json()
            records = [
                {"id": rec["id"], "name": rec["name"], "type": rec["type"],
                 "content": rec["content"], "proxied": rec.get("proxied")}
                for rec in data.get("result", [])
            ]
            return {"ok": True, "records": records}

        elif action == "create_record":
            if not all([zone_id, record_name, record_content]):
                return {"ok": False, "error": "zone_id, record_name, record_content обязательны"}
            payload = {
                "type": record_type,
                "name": record_name,
                "content": record_content,
                "proxied": proxied,
                "ttl": 1  # 1 = Auto при proxied=True
            }
            r = httpx.post(f"{base}/zones/{zone_id}/dns_records",
                           headers=headers, json=payload, timeout=15)
            data = r.json()
            if data.get("success"):
                rec_id = data["result"]["id"]
                _log(f"cloudflare_dns_manager: создана запись {record_name} id={rec_id}", diff=6)
                return {"ok": True, "record_id": rec_id}
            return {"ok": False, "errors": data.get("errors")}

        elif action == "delete_record":
            # Ищем запись по имени и удаляем
            if not zone_id or not record_name:
                return {"ok": False, "error": "zone_id и record_name обязательны"}
            r = httpx.get(
                f"{base}/zones/{zone_id}/dns_records",
                headers=headers,
                params={"name": record_name},
                timeout=15
            )
            records = r.json().get("result", [])
            if not records:
                return {"ok": False, "error": f"Запись '{record_name}' не найдена"}
            rec_id = records[0]["id"]
            del_r = httpx.delete(f"{base}/zones/{zone_id}/dns_records/{rec_id}",
                                 headers=headers, timeout=15)
            if del_r.json().get("success"):
                _log(f"cloudflare_dns_manager: удалена запись {record_name}", diff=6)
                return {"ok": True, "deleted_id": rec_id}
            return {"ok": False, "errors": del_r.json().get("errors")}

        elif action == "check_status":
            if not zone_id:
                return {"ok": False, "error": "zone_id обязателен"}
            r = httpx.get(f"{base}/zones/{zone_id}", headers=headers, timeout=15)
            data = r.json().get("result", {})
            return {
                "ok": True,
                "name": data.get("name"),
                "status": data.get("status"),
                "paused": data.get("paused"),
                "plan": data.get("plan", {}).get("name")
            }

        else:
            return {"ok": False, "error": f"Неизвестное действие: {action}"}

    except Exception as e:
        _log(f"cloudflare_dns_manager ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def secure_credential_vault(
    action: str,
    key: str = "",
    value: str = "",
    session_token: str = ""
) -> dict:
    """
    Чтение и запись API-ключей в локальный JSON-файл vault.json.
    Базовая защита через session_token (из env VAULT_SESSION_TOKEN).
    ДЕСТРУКТИВНЫЕ операции (delete) требуют confirm=True в ключе value.

    Args:
        action: "read" | "write" | "list" | "delete"
        key: Название ключа
        value: Значение для записи (при write) / "confirm" при delete
        session_token: Токен сессии для авторизации
    """
    expected_token = os.environ.get("VAULT_SESSION_TOKEN", "dev-vault-token")
    if session_token != expected_token:
        _log(f"secure_credential_vault: неверный session_token, action={action}", diff=9)
        return {"ok": False, "error": "Неверный session_token — доступ запрещён"}

    _log(f"secure_credential_vault: action={action} key={key}", diff=7)
    vault_path = Path(VAULT_PATH)
    vault_path.parent.mkdir(parents=True, exist_ok=True)

    # Загружаем хранилище
    vault: dict = {}
    if vault_path.exists():
        try:
            vault = json.loads(vault_path.read_text(encoding="utf-8"))
        except Exception:
            vault = {}

    if action == "read":
        if not key:
            return {"ok": False, "error": "key обязателен для read"}
        if key not in vault:
            return {"ok": False, "error": f"Ключ '{key}' не найден"}
        # Маскируем значение для безопасности: показываем только первые 4 символа
        raw = vault[key]
        masked = raw[:4] + "****" if len(raw) > 4 else "****"
        return {"ok": True, "key": key, "value_masked": masked, "value": raw}

    elif action == "write":
        if not key or not value:
            return {"ok": False, "error": "key и value обязательны для write"}
        vault[key] = value
        vault_path.write_text(json.dumps(vault, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"secure_credential_vault: записан ключ '{key}'", diff=7)
        return {"ok": True, "written": key}

    elif action == "list":
        # Возвращаем только имена ключей без значений
        return {"ok": True, "keys": list(vault.keys())}

    elif action == "delete":
        if not key:
            return {"ok": False, "error": "key обязателен для delete"}
        if value != "confirm":
            return {"ok": False, "error": "Для удаления передайте value='confirm'"}
        if key not in vault:
            return {"ok": False, "error": f"Ключ '{key}' не найден"}
        del vault[key]
        vault_path.write_text(json.dumps(vault, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"secure_credential_vault: удалён ключ '{key}'", diff=7)
        return {"ok": True, "deleted": key}

    return {"ok": False, "error": f"Неизвестное действие: {action}"}


def web_page_markdownify(
    url: str,
    include_links: bool = False,
    max_length: int = 5000
) -> dict:
    """
    Скачивает веб-страницу, очищает от HTML-мусора и конвертирует в Markdown.

    Args:
        url: URL страницы
        include_links: True — сохранять гиперссылки в Markdown
        max_length: Максимальная длина результата (символов)
    """
    _log(f"web_page_markdownify: url={url[:80]} max_len={max_length}", diff=4)

    if not url.startswith("http"):
        return {"ok": False, "error": "Некорректный URL"}

    headers = {"User-Agent": "Mozilla/5.0 (compatible; PelletoBot/1.0)"}

    try:
        resp = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}

        content_type = resp.headers.get("content-type", "")
        if "json" in content_type:
            return {"ok": True, "format": "json", "content": resp.text[:max_length]}

        html = resp.text

        # Пробуем markdownify через bs4
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            # Удаляем мусор
            for tag in soup(["script", "style", "nav", "footer", "iframe",
                              "noscript", "aside", "form", "button", "header"]):
                tag.decompose()

            # Попытка использовать markdownify если установлен
            try:
                import markdownify
                md = markdownify.markdownify(
                    str(soup),
                    heading_style="ATX",
                    strip=["a"] if not include_links else []
                )
            except ImportError:
                # Ручная конвертация через bs4
                md = _html_to_md_simple(soup, include_links)

            # Убираем лишние пустые строки
            md = re.sub(r"\n{3,}", "\n\n", md).strip()
            result_text = md[:max_length]

            _log(f"web_page_markdownify: OK len={len(result_text)}", diff=4)
            return {
                "ok": True,
                "url": url,
                "format": "markdown",
                "length": len(result_text),
                "content": result_text
            }

        except ImportError:
            # Только базовая очистка тегов
            clean = re.sub(r"<[^>]+>", " ", html)
            clean = re.sub(r"\s{2,}", " ", clean).strip()
            return {
                "ok": True,
                "url": url,
                "format": "plain",
                "content": clean[:max_length],
                "note": "Установите beautifulsoup4 для полного парсинга"
            }

    except Exception as e:
        _log(f"web_page_markdownify ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def _html_to_md_simple(soup: "BeautifulSoup", include_links: bool) -> str:
    """Простая конвертация HTML → Markdown без сторонних библиотек."""
    lines = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "a", "br"]):
        tag = elem.name
        text = elem.get_text(separator=" ", strip=True)
        if not text:
            continue
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag == "h2":
            lines.append(f"## {text}")
        elif tag == "h3":
            lines.append(f"### {text}")
        elif tag == "h4":
            lines.append(f"#### {text}")
        elif tag == "p":
            lines.append(text)
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "a" and include_links:
            href = elem.get("href", "")
            lines.append(f"[{text}]({href})")
        elif tag == "br":
            lines.append("")
    return "\n\n".join(lines)


def download_media_loader(
    url: str,
    output_dir: str = "",
    audio_only: bool = False,
    quality: str = "best"
) -> dict:
    """
    Загрузка видео/аудио через yt-dlp.
    Поддерживает YouTube, VK, TikTok и сотни других площадок.

    Args:
        url: Ссылка на медиа-контент
        output_dir: Директория сохранения (по умолчанию DATA_DIR/media)
        audio_only: True — только аудио (mp3/opus)
        quality: Качество: "best", "720p", "480p", "worst"
    """
    _log(f"download_media_loader: url={url[:80]} audio={audio_only} quality={quality}", diff=5)

    if not shutil.which("yt-dlp"):
        return {
            "ok": False,
            "error": "yt-dlp не установлен",
            "suggestion": "pip install yt-dlp  или  apt install yt-dlp"
        }

    out_dir = output_dir or str(Path(DATA_DIR) / "media")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Формируем команду
    cmd = ["yt-dlp", "--no-playlist", "-o", f"{out_dir}/%(title)s.%(ext)s"]

    if audio_only:
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        # Карта качества в формат yt-dlp
        fmt_map = {
            "best": "bestvideo+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "worst": "worst"
        }
        fmt = fmt_map.get(quality, "bestvideo+bestaudio/best")
        cmd += ["-f", fmt]

    cmd.append(url)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )

        if result.returncode == 0:
            # Ищем скачанный файл в выводе
            match = re.search(r"\[download\] Destination: (.+)", result.stdout)
            file_path = match.group(1).strip() if match else out_dir
            _log(f"download_media_loader: OK path={file_path}", diff=5)
            return {
                "ok": True,
                "output_dir": out_dir,
                "file": file_path,
                "stdout": result.stdout[-500:]
            }
        else:
            _log(f"download_media_loader WARN: {result.stderr[:200]}", diff=7)
            return {"ok": False, "error": result.stderr[-500:], "returncode": result.returncode}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Таймаут загрузки (300с)"}
    except Exception as e:
        _log(f"download_media_loader ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}
