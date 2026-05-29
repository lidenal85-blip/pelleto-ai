"""
app/mcp/registry.py
Реестр MCP-инструментов для Gemini function calling.
Содержит декларации инструментов в формате genai.protos.Tool
и диспетчер вызовов по имени функции.
"""
from __future__ import annotations
from typing import Any

# Карта: имя_функции -> callable
_TOOL_MAP: dict[str, Any] = {}


def _register_tools():
    """Ленивая регистрация инструментов (вызывается один раз при импорте)."""
    from app.mcp.tools.group1_termux import (
        execute_background_task, monitor_system_resources,
        manage_termux_wake, error_buffer_stream,
    )
    from app.mcp.tools.group2_android import (
        send_telegram_notification, android_share_text,
        fetch_starmaker_data, text_to_speech_preview,
    )
    from app.mcp.tools.group3_vibe import (
        search_prompt_library, git_auto_commit_sync,
        code_structure_analyzer, validate_python_syntax,
    )
    from app.mcp.tools.group4_network import (
        cloudflare_dns_manager, secure_credential_vault,
        web_page_markdownify, download_media_loader,
    )
    from app.mcp.tools.group5_database import (
        sqlite_schema_inspector, project_time_logger, compress_and_backup,
    )
    from app.mcp.tools.group6_torrent import torrent_download_manager

    _TOOL_MAP.update({
        "execute_background_task": execute_background_task,
        "monitor_system_resources": monitor_system_resources,
        "manage_termux_wake": manage_termux_wake,
        "error_buffer_stream": error_buffer_stream,
        "send_telegram_notification": send_telegram_notification,
        "android_share_text": android_share_text,
        "fetch_starmaker_data": fetch_starmaker_data,
        "text_to_speech_preview": text_to_speech_preview,
        "search_prompt_library": search_prompt_library,
        "git_auto_commit_sync": git_auto_commit_sync,
        "code_structure_analyzer": code_structure_analyzer,
        "validate_python_syntax": validate_python_syntax,
        "cloudflare_dns_manager": cloudflare_dns_manager,
        "secure_credential_vault": secure_credential_vault,
        "web_page_markdownify": web_page_markdownify,
        "download_media_loader": download_media_loader,
        "sqlite_schema_inspector": sqlite_schema_inspector,
        "project_time_logger": project_time_logger,
        "compress_and_backup": compress_and_backup,
        "torrent_download_manager": torrent_download_manager,
    })


_register_tools()


def dispatch_tool(name: str, args: dict) -> Any:
    """
    Вызывает инструмент по имени с переданными аргументами.
    Возвращает результат или словарь с ошибкой.
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return {"ok": False, "error": f"Инструмент не найден: {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"ok": False, "error": f"Ошибка аргументов для {name}: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Ошибка выполнения {name}: {e}"}


def list_tools() -> list[str]:
    """Возвращает список имён всех зарегистрированных инструментов."""
    return list(_TOOL_MAP.keys())


# ── Декларации инструментов для Gemini function calling ──────────────────────
# Подмножество наиболее полезных для AI-агента инструментов

GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "monitor_system_resources",
        "description": "Мониторинг загрузки CPU, RAM и заряда батареи сервера.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "error_buffer_stream",
        "description": "Чтение последних строк из лог-файла ошибок с возможностью фильтрации.",
        "parameters": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string", "description": "Путь к лог-файлу"},
                "filter_keyword": {"type": "string", "description": "Ключевое слово для фильтрации"},
                "last_n": {"type": "integer", "description": "Количество последних строк (по умолчанию 50)"}
            },
            "required": []
        }
    },
    {
        "name": "send_telegram_notification",
        "description": "Отправить уведомление или файл в Telegram администратору.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Текст уведомления (поддерживает HTML)"},
                "chat_id": {"type": "string", "description": "ID чата (опционально)"},
                "file_path": {"type": "string", "description": "Путь к файлу для отправки (опционально)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "search_prompt_library",
        "description": "Поиск промптов по ключевым словам и тегам в библиотеке промптов.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Теги для фильтрации"}
            },
            "required": []
        }
    },
    {
        "name": "validate_python_syntax",
        "description": "Проверка синтаксиса Python-кода перед запуском.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Строка кода для проверки"},
                "file_path": {"type": "string", "description": "Путь к файлу (альтернатива code)"}
            },
            "required": []
        }
    },
    {
        "name": "sqlite_schema_inspector",
        "description": "Просмотр схемы базы данных и выполнение SELECT-запросов к pelleto.db.",
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Путь к .db файлу"},
                "table_name": {"type": "string", "description": "Имя таблицы для детального анализа"},
                "query": {"type": "string", "description": "SELECT-запрос для выполнения"}
            },
            "required": []
        }
    },
    {
        "name": "web_page_markdownify",
        "description": "Скачать веб-страницу и конвертировать в Markdown для анализа.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL страницы"},
                "include_links": {"type": "boolean", "description": "Включить ссылки"},
                "max_length": {"type": "integer", "description": "Максимальная длина результата"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "code_structure_analyzer",
        "description": "Анализ структуры Python-файла: классы, функции, FastAPI-маршруты.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Путь к Python-файлу"},
                "include_docstrings": {"type": "boolean", "description": "Включить докстринги"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "compress_and_backup",
        "description": "Создать резервную копию папки или файла проекта.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "description": "Путь к источнику"},
                "output_dir": {"type": "string", "description": "Директория для архива"},
                "format": {"type": "string", "description": "Формат: tar.gz или zip"},
                "confirm": {"type": "boolean", "description": "True = выполнить, False = preview"}
            },
            "required": ["source_path"]
        }
    },
    {
        "name": "project_time_logger",
        "description": "Записать задачу и время разработки в журнал logs/time_log.md.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Описание задачи"},
                "diff_level": {"type": "integer", "description": "Сложность 1-10"},
                "duration_minutes": {"type": "number", "description": "Время в минутах"},
                "phase": {"type": "string", "description": "Фаза: planning|coding|review|deploy|debug"}
            },
            "required": ["task"]
        }
    }
]
