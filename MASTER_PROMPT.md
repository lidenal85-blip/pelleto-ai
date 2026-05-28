# MASTER PROMPT — Pelleto AI
## Используй в начале каждой новой сессии

## Контекст проекта
Проект: **Pelleto AI** — автономный продающий лендинг топливных пеллет.

**Repo:** https://github.com/lidenal85-blip/pelleto-ai  
**Server:** root@78.17.24.96 | путь: /opt/pelleto-ai  
**Port:** 8130  
**Stack:** FastAPI + Google Gemini (gemini-2.0-flash) + aiogram3 + SQLite FTS5  
**Стиль:** Тёплый Склад (#1C3A2F + #E8A23A + #F5F0E8)  
**Сервис:** pelleto-ai.service (systemd)  

## Экосистема LEVIATHAN (существующие порты)
| Порт | Сервис |
|------|--------|
| 8200 | Leviathan Agent |
| 8095 | ArbitrCockpit |
| 8110 | KinoVibe |
| 8120 | VoiceStudio |
| **8130** | **Pelleto AI** |

## Архитектура
```
FastAPI (port 8130)
  GET  /              -> landing (Jinja2, стиль Тёплый Склад)
  POST /api/agent/chat -> ИИ-агент (Gemini)
  GET  /admin         -> admin panel (master key auth)
  POST /api/generate  -> генератор контента
  GET  /health        -> health check

SQLite /opt/pelleto-ai/data/pelleto.db:
  knowledge_facts (FTS5) — база знаний
  content_blocks          — статьи/FAQ
  products                — товары
  admin_sessions          — сессии
  login_attempts          — rate limiting
  dialogue_logs           — логи агента
  publication_queue       — очередь публикаций

Telegram Bot (aiogram3):
  /stat  — статистика диалогов
  /queue — очередь публикаций
  /pub <id> — опубликовать
  /rej <id> — отклонить
```

## Checklist статуса (обновлять при каждом деплое)
- [x] Repo создан: github.com/lidenal85-blip/pelleto-ai
- [x] Структура директорий: /opt/pelleto-ai
- [x] PASSPORT.md
- [x] MASTER_PROMPT.md
- [ ] requirements.txt
- [ ] .env (создать из .env.example)
- [ ] app/core/config.py
- [ ] app/core/logger.py
- [ ] app/core/database.py
- [ ] data/knowledge_base_seed.json (30 тем)
- [ ] prompts/agent_system.txt
- [ ] prompts/generator_system.txt
- [ ] app/services/ (auth, knowledge, content, ai)
- [ ] app/api/routes/ (landing, agent, admin, products)
- [ ] main.py
- [ ] templates/ (landing, admin)
- [ ] static/ (pelleto.css, agent.js, admin.js)
- [ ] bot/bot.py (aiogram3)
- [ ] config/pelleto-ai.service
- [ ] systemd установлен и запущен

## Ключевые правила
1. FastAPI async везде (aiosqlite, httpx)
2. Gemini через `google-generativeai` SDK, ключи GEMINI_K1..K14
3. HallucinationGuard: только факты из KB (confidence >= medium)
4. DialoguePhaseTracker: 0 msg=initial, 1-3=exploration, 4+=closing
5. HistorySanitizer: только role=user|assistant, max 500 chars, max 10 msgs
6. DOMPurify в widget.js перед render LLM ответа
7. Correlation ID: X-Request-ID через все слои
8. Secrets только в .env, никогда в git
9. Мастер-ключ: bcrypt hash, 5 тапов по версии в футере
10. База знаний пополняется из одобренных статей (publication_queue)

## Для продолжения работы
```bash
# Читай паспорт
cat /opt/pelleto-ai/PASSPORT.md

# Смотри статус
ls -la /opt/pelleto-ai/
cat /opt/pelleto-ai/MASTER_PROMPT.md

# Первый незавершённый шаг — следующая задача
```

## Gemini ключи (на сервере)
Доступны в /opt/leviathan_engine/agent_service/.env как GEMINI_K1..K14
Для Pelleto копировать нужные в /opt/pelleto-ai/.env