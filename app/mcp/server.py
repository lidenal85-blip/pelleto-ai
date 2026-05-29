"""
app/mcp/server.py
MCP-сервер Pelleto AI — 20 инструментов из 6 групп.
Запуск: python -m app.mcp.server   (SSE на порту 8132)
        python -m app.mcp.server --stdio   (stdio-транспорт для Claude Desktop)
"""
import os
import sys
from pathlib import Path

# Гарантируем корень проекта в PYTHONPATH при запуске напрямую
_ROOT = str(Path(__file__).parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mcp.server.fastmcp import FastMCP

# Импорт всех групп инструментов
from app.mcp.tools.group1_termux import (
    execute_background_task,
    monitor_system_resources,
    manage_termux_wake,
    error_buffer_stream,
)
from app.mcp.tools.group2_android import (
    send_telegram_notification,
    android_share_text,
    fetch_starmaker_data,
    text_to_speech_preview,
)
from app.mcp.tools.group3_vibe import (
    search_prompt_library,
    git_auto_commit_sync,
    code_structure_analyzer,
    validate_python_syntax,
)
from app.mcp.tools.group4_network import (
    cloudflare_dns_manager,
    secure_credential_vault,
    web_page_markdownify,
    download_media_loader,
)
from app.mcp.tools.group5_database import (
    sqlite_schema_inspector,
    project_time_logger,
    compress_and_backup,
)
from app.mcp.tools.group6_torrent import torrent_download_manager

# Инициализация MCP-сервера
mcp = FastMCP(
    name="pelleto-mcp",
    instructions=(
        "MCP-сервер Pelleto AI. Предоставляет 20 инструментов для управления "
        "окружением Termux/Linux, отправки уведомлений, работы с кодом, сетью, "
        "базами данных и торрент-загрузками."
    ),
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", "8132")),
)

# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 1: Управление окружением и процессами Termux
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_execute_background_task(command: str, use_nohup: bool = True, log_file: str = "") -> dict:
    """
    Запуск долгого процесса в фоне через nohup или tmux.
    Возвращает PID запущенного процесса и путь к лог-файлу.
    """
    return execute_background_task(command, use_nohup, log_file)


@mcp.tool()
def tool_monitor_system_resources() -> dict:
    """
    Мониторинг загрузки CPU, RAM и уровня заряда батареи.
    Читает /proc/stat, /proc/meminfo и /sys/class/power_supply.
    """
    return monitor_system_resources()


@mcp.tool()
def tool_manage_termux_wake(action: str = "lock") -> dict:
    """
    Управление блокировкой сна Android (termux-wake-lock / termux-wake-unlock).
    action: 'lock' — удерживать CPU активным, 'unlock' — снять блокировку.
    """
    return manage_termux_wake(action)


@mcp.tool()
def tool_error_buffer_stream(
    log_path: str = "",
    filter_keyword: str = "",
    last_n: int = 50
) -> dict:
    """
    Чтение и фильтрация последних записей из лог-файла ошибок.
    Аналог WebSocket-логгера eb_listener для просмотра в MCP-клиенте.
    """
    return error_buffer_stream(log_path, filter_keyword, last_n)


# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 2: Связь с Android и коммуникация
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_send_telegram_notification(
    text: str,
    chat_id: str = "",
    file_path: str = "",
    bot_token: str = ""
) -> dict:
    """
    Отправка текстового алерта или файла в Telegram через Bot API.
    Поддерживает HTML-разметку. Использует TELEGRAM_BOT_TOKEN из env.
    """
    return send_telegram_notification(text, chat_id, file_path, bot_token)


@mcp.tool()
def tool_android_share_text(text: str, mode: str = "clipboard") -> dict:
    """
    Копирует текст в буфер обмена Android или вызывает диалог «Поделиться».
    mode: 'clipboard' | 'share'. На сервере сохраняет в logs/clipboard.txt.
    """
    return android_share_text(text, mode)


@mcp.tool()
def tool_fetch_starmaker_data(contest_url: str, fields: list[str] | None = None) -> dict:
    """
    Парсинг открытых данных страниц конкурсов StarMaker.
    Возвращает список участников и треков для сообщества «Союз Голосов».
    """
    return fetch_starmaker_data(contest_url, fields)


@mcp.tool()
def tool_text_to_speech_preview(
    text: str,
    language: str = "ru",
    rate: float = 1.0
) -> dict:
    """
    Озвучивание текста через termux-tts-speak (Android) или espeak-ng (Linux).
    language: 'ru', 'en', etc. rate: 0.5–2.0 (1.0 = нормальная скорость).
    """
    return text_to_speech_preview(text, language, rate)


# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 3: Умная архитектура и Vibe Coding
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_search_prompt_library(
    query: str = "",
    tags: list[str] | None = None,
    directory: str = ""
) -> dict:
    """
    Поиск промптов по ключевым словам и тегам (#TAG).
    Сканирует /opt/pelleto-ai/prompts и /storage/emulated/0/Documents/ПРОМТЫ.
    """
    return search_prompt_library(query, tags, directory)


@mcp.tool()
def tool_git_auto_commit_sync(
    repo_path: str = "",
    commit_message: str = "",
    push: bool = False,
    add_all: bool = True
) -> dict:
    """
    Автоматический коммит изменений с генерацией сообщения из git diff --stat.
    push=True — выполнить git push (требует подтверждения).
    """
    return git_auto_commit_sync(repo_path, commit_message, push, add_all)


@mcp.tool()
def tool_code_structure_analyzer(
    file_path: str,
    include_docstrings: bool = False
) -> dict:
    """
    Парсинг структуры Python-файла через AST: классы, функции, FastAPI-маршруты.
    Не читает всё тело файла — экономит токены контекста.
    """
    return code_structure_analyzer(file_path, include_docstrings)


@mcp.tool()
def tool_validate_python_syntax(
    code: str = "",
    file_path: str = ""
) -> dict:
    """
    Линтинг и проверка синтаксиса Python через ast.parse + py_compile.
    Опционально — через flake8 если установлен.
    """
    return validate_python_syntax(code, file_path)


# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 4: Сеть, API и медиа
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_cloudflare_dns_manager(
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
    action: list_zones | list_records | create_record | delete_record | check_status.
    """
    return cloudflare_dns_manager(
        action, zone_id, record_name, record_type, record_content, proxied, api_token
    )


@mcp.tool()
def tool_secure_credential_vault(
    action: str,
    key: str = "",
    value: str = "",
    session_token: str = ""
) -> dict:
    """
    Чтение и запись API-ключей в зашифрованный vault.json.
    action: read | write | list | delete. Требует VAULT_SESSION_TOKEN.
    """
    return secure_credential_vault(action, key, value, session_token)


@mcp.tool()
def tool_web_page_markdownify(
    url: str,
    include_links: bool = False,
    max_length: int = 5000
) -> dict:
    """
    Скачивает веб-страницу, очищает от HTML-мусора и конвертирует в Markdown.
    Требует beautifulsoup4. max_length ограничивает размер результата.
    """
    return web_page_markdownify(url, include_links, max_length)


@mcp.tool()
def tool_download_media_loader(
    url: str,
    output_dir: str = "",
    audio_only: bool = False,
    quality: str = "best"
) -> dict:
    """
    Загрузка видео/аудио через yt-dlp. Поддерживает YouTube, VK, TikTok и др.
    quality: 'best' | '720p' | '480p' | 'worst'. audio_only=True → mp3.
    """
    return download_media_loader(url, output_dir, audio_only, quality)


# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 5: Базы данных и мониторинг
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_sqlite_schema_inspector(
    db_path: str = "",
    table_name: str = "",
    query: str = ""
) -> dict:
    """
    Чтение схемы, индексов и выполнение безопасных SELECT-запросов к SQLite.
    По умолчанию — основная БД проекта pelleto.db. Только SELECT-запросы.
    """
    return sqlite_schema_inspector(db_path, table_name, query)


@mcp.tool()
def tool_project_time_logger(
    task: str,
    diff_level: int = 5,
    duration_minutes: float = 0,
    tags: list[str] | None = None,
    phase: str = ""
) -> dict:
    """
    Ведёт журнал учёта времени разработки в logs/time_log.md.
    diff_level: 1-10 (сложность), phase: planning|coding|review|deploy|debug.
    """
    return project_time_logger(task, diff_level, duration_minutes, tags, phase)


@mcp.tool()
def tool_compress_and_backup(
    source_path: str,
    output_dir: str = "",
    format: str = "tar.gz",
    confirm: bool = False
) -> dict:
    """
    Создание сжатого бэкапа папки/файла с временной меткой в имени архива.
    format: 'tar.gz' | 'zip'. confirm=False → preview без выполнения.
    """
    return compress_and_backup(source_path, output_dir, format, confirm)


# ═══════════════════════════════════════════════════════════════════════════════
# ГРУППА 6: Торрент-менеджер
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def tool_torrent_download_manager(
    source: str = "",
    output_dir: str = "",
    action: str = "start",
    peer_limit: int = 50
) -> dict:
    """
    Управление торрент-загрузками через aria2c / transmission / libtorrent.
    source: magnet-ссылка или путь к .torrent. action: start|status|stop.
    """
    return torrent_download_manager(source, output_dir, action, peer_limit)


# ═══════════════════════════════════════════════════════════════════════════════
# Точка запуска
# ═══════════════════════════════════════════════════════════════════════════════

def get_mcp_app():
    """Возвращает ASGI-приложение Streamable HTTP для монтирования в FastAPI."""
    return mcp.streamable_http_app()


if __name__ == "__main__":
    transport = "stdio" if "--stdio" in sys.argv else "streamable-http"
    # host/port передаются через конструктор FastMCP
    mcp.run(transport=transport)
