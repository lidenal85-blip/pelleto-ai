# Отчёт сессии — 2026-05-29
**Проект:** Pelleto AI | **Сервер:** root@78.17.24.96 | **Ветка:** main

---

## 1. MCP-сервер Pelleto AI (порт 8132)

### Создана структура

```
/opt/pelleto-ai/
├── app/mcp/
│   ├── __init__.py
│   ├── server.py          # FastMCP сервер, порт 8132, Streamable HTTP
│   ├── registry.py        # Реестр инструментов + Gemini FunctionDeclaration
│   └── tools/
│       ├── __init__.py
│       ├── group1_termux.py    # 4 инструмента
│       ├── group2_android.py   # 4 инструмента
│       ├── group3_vibe.py      # 4 инструмента
│       ├── group4_network.py   # 4 инструмента
│       ├── group5_database.py  # 3 инструмента
│       └── group6_torrent.py   # 1 инструмент
├── mcp_server_start.sh    # Скрипт управления сервером
└── .mcp.json              # Конфиг MCP для Claude Code
```

### 20 инструментов по группам

| # | Инструмент | Группа | Описание |
|---|-----------|--------|----------|
| 1 | `execute_background_task` | Termux/Linux | Запуск процесса в фоне через nohup/tmux → PID |
| 2 | `monitor_system_resources` | Termux/Linux | CPU/RAM/батарея через /proc/stat |
| 3 | `manage_termux_wake` | Termux/Linux | lock/unlock сна Android |
| 4 | `error_buffer_stream` | Termux/Linux | Чтение/фильтрация лог-файлов |
| 5 | `send_telegram_notification` | Android/Связь | Текст + файл в Telegram Bot API |
| 6 | `android_share_text` | Android/Связь | Буфер обмена / Share-диалог |
| 7 | `fetch_starmaker_data` | Android/Связь | Парсинг конкурсов StarMaker |
| 8 | `text_to_speech_preview` | Android/Связь | TTS через termux-tts-speak / espeak |
| 9 | `search_prompt_library` | Vibe Coding | Поиск промптов по #TAG в директории |
| 10 | `git_auto_commit_sync` | Vibe Coding | Автокоммит + push с автогенерацией сообщения |
| 11 | `code_structure_analyzer` | Vibe Coding | AST-парсинг Python без чтения тела файла |
| 12 | `validate_python_syntax` | Vibe Coding | ast + py_compile + flake8 |
| 13 | `cloudflare_dns_manager` | Сеть/Медиа | CRUD DNS через Cloudflare API v4 |
| 14 | `secure_credential_vault` | Сеть/Медиа | Зашифрованный vault.json для API-ключей |
| 15 | `web_page_markdownify` | Сеть/Медиа | URL → Markdown через bs4 |
| 16 | `download_media_loader` | Сеть/Медиа | yt-dlp: видео/аудио по ссылке |
| 17 | `sqlite_schema_inspector` | БД/Мониторинг | Схема + safe SELECT к pelleto.db |
| 18 | `project_time_logger` | БД/Мониторинг | Журнал времени → logs/time_log.md |
| 19 | `compress_and_backup` | БД/Мониторинг | tar.gz/zip бэкап с timestamp |
| 20 | `torrent_download_manager` | Торренты | aria2c → transmission → libtorrent |

### Логирование всех инструментов

Формат дозаписи (`>>`):
```
>> [YYYY-MM-DD HH:MM:SS] [Diff: X/10] сообщение
```
Файл: `logs/mcp_tools.log`

---

## 2. Интеграция MCP с AI-агентом

### Обновлён `app/services/ai/gemini_client.py`

Добавлена функция `call_gemini_with_tools()`:
- Принимает список `GEMINI_TOOL_DECLARATIONS` из `registry.py`
- Создаёт `FunctionDeclaration` объекты для Gemini SDK
- Возвращает `{"type": "function_call", "name": ..., "args": {...}}` или `{"type": "text", "text": ...}`
- Поддерживает ротацию ключей и circuit breaker (как основной `call_gemini`)

### Обновлён `app/services/ai/agent.py`

Добавлен **tool-use loop**:
- `_is_tool_request(question)` — эвристика автодетекта операционных запросов по ключевым словам (логи, база данных, мониторинг, telegram, бэкап и др.)
- `_run_with_tools()` — цикл до 3 итераций: Gemini → function_call → dispatch_tool → результат → Gemini
- `ask_agent()` — новый параметр `use_tools=False`, включается автоматически или по флагу
- Поле `tool_calls_used` в ответе агента

### Реестр `app/mcp/registry.py`

- `dispatch_tool(name, args)` — единая точка вызова любого из 20 инструментов
- `GEMINI_TOOL_DECLARATIONS` — 10 наиболее полезных для AI деклараций
- `list_tools()` — список всех зарегистрированных имён

---

## 3. Управление MCP-сервером Pelleto

```bash
bash mcp_server_start.sh restart   # убить старый → запустить новый
bash mcp_server_start.sh status    # показать PID и порт
bash mcp_server_start.sh stop      # остановить
```

Скрипт: `/opt/pelleto-ai/mcp_server_start.sh`
PID-файл: `logs/mcp_server.pid`
Лог запуска: `logs/mcp_server.log`

---

## 4. Зависимости

### Установлено

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `mcp` | 1.27.1 | FastMCP сервер |
| `beautifulsoup4` | 4.12+ | web_page_markdownify |
| `starlette` | 0.41.3 | **Критично:** mcp тянет 1.2.0, несовместимую с FastAPI 0.115.5 — принудительно даунгрейд |

### Добавлено в `requirements.txt`

```
mcp>=1.27.0
beautifulsoup4>=4.12.0
```

> ⚠️ **Важно при деплое:** после `pip install -r requirements.txt` проверить версию starlette.
> Если стала 1.x — выполнить: `pip install "starlette==0.41.3" --force-reinstall`

---

## 5. Leviathan MCP Server (порт 8300)

### Обнаружен существующий сервер

- Файл: `/opt/leviathan_engine/agent_service/mcp_server/leviathan_mcp_server.py`
- Процесс: PID 2732042, запущен от venv проекта
- Транспорт: Streamable HTTP, порт 8300
- Auth: Bearer token

### 19 инструментов `lev_*`

`lev_read_file`, `lev_write_file`, `lev_patch`, `lev_list_dir`, `lev_bash`,
`lev_git`, `lev_systemctl`, `lev_health`, `lev_agent_task`, `lev_find`,
`lev_web_fetch`, `lev_web_search`, `lev_http_request`, `lev_check_url`,
`lev_parse_csv`, `lev_json_query`, `lev_convert_file`, `lev_cron_list`,
`lev_download_file`

### Подключён в Claude Code

Создан `/opt/pelleto-ai/.mcp.json`:
```json
{
  "mcpServers": {
    "leviathan": {
      "type": "http",
      "url": "http://78.17.24.96:8300/mcp",
      "headers": {
        "Authorization": "Bearer den4ik1985!"
      }
    }
  }
}
```

Добавлен `"enableAllProjectMcpServers": true` в `~/.claude/settings.json`.

---

## 6. Telegram-уведомления

### Найдены и использованы боты

| Бот | Токен (источник) | Статус |
|-----|-----------------|--------|
| `@Pelleto_bot` | `/opt/pelleto-ai/.env` → `TELEGRAM_BOT_TOKEN` | Активен |
| `@Levi_Engi_bot` | `/root/Leviathan_Agent_ARCHIVED_20260525/.env` → `TG_BOT_TOKEN` | Активен ✅ |

- Отчёт отправлен через `@Levi_Engi_bot` в чат `@vaalchik` (chat_id: 7709651193)

---

## 7. Контекст экосистемы

### Проекты на сервере 78.17.24.96

| Порт | Проект |
|------|--------|
| 8095 | ArbitrCockpit — `/opt/arbitr_cockpit/` |
| 8110 | KinoVibe — `/var/www/kinovibe/` |
| 8120 | VoiceStudio — `/var/www/voicestudio/` |
| 8130 | **Pelleto AI** — `/opt/pelleto-ai/` |
| 8132 | MCP-сервер Pelleto (новый) |
| 8200 | Leviathan Engine — `/opt/leviathan_engine/` |
| 8300 | Leviathan MCP Server (существующий) |

### Стек

- FastAPI + Gemini + aiogram3 + SQLite
- Репозиторий: `github.com/lidenal85-blip/Leviathan_Agent`

---

## 8. Тесты (финальные)

```
✅ 11/11 файлов Python — синтаксис OK
✅ 20/20 инструментов зарегистрированы в FastMCP
✅ monitor_system_resources — CPU: 66.7%, RAM: 57.5%
✅ sqlite_schema_inspector — 13 таблиц pelleto.db
✅ validate_python_syntax — syntax_valid: True
✅ MCP сервер порт 8132 — HTTP 200
✅ Leviathan MCP порт 8300 — HTTP 200
✅ main.py импорт — "MCP server mounted at /mcp"
✅ Telegram @Levi_Engi_bot — отправка OK
```
