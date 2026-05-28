# Pelleto AI — Чек-лист разработки

> Последнее обновление: 2026-05-28  
> Версия проекта: 0.1.0  
> Статус сборки: **🟢 ЗАПУСКАЕТСЯ** (`/health` → 200 OK)

---

## Оценка готовности: **52%**

| Категория | Готово | Всего | % |
|-----------|--------|-------|---|
| Инфраструктура | 5 | 5 | 100% |
| База данных | 5 | 5 | 100% |
| Аутентификация | 5 | 5 | 100% |
| AI Core (Gemini) | 4 | 5 | 80% |
| Агент продаж | 4 | 5 | 80% |
| База знаний | 4 | 5 | 80% |
| Контент / очередь | 3 | 5 | 60% |
| Маршруты API | 4 | 5 | 80% |
| Лендинг (шаблон) | 2 | 5 | 40% |
| Админ-панель (шаблоны) | 3 | 5 | 60% |
| Деплой | 0 | 5 | 0% |
| E2E тесты | 0 | 5 | 0% |

---

## Sprint 1 — Foundation + Core Data

### M10: Infrastructure
- [x] SQLite схема создаётся через `executescript` (без разрыва триггеров)
- [x] WAL mode + `busy_timeout=5000` включены в `get_db()`
- [x] Структурированный JSON-логгер (`app/core/logger.py`)
- [x] `.env` + `config.py` — централизованная конфигурация
- [x] `/health` endpoint → `{status, version, agent_enabled, llm_circuit}`
- [ ] Dockerfile (есть в TODO, не реализован)
- [ ] Systemd unit для автозапуска

### M4: Auth
- [x] bcrypt-верификация мастер-ключа
- [x] Server-side сессии в SQLite (`admin_sessions`)
- [x] Rate limiting: 3 попытки → блокировка IP на 30 мин
- [x] `require_admin` FastAPI dependency (cookie-based)
- [x] Logout + инвалидация сессии
- [ ] `X-Frame-Options: DENY` + CSP на admin-маршрутах
- [ ] TapDetector (JS): 5 тапов по версии за 5 сек → `/admin/login`

### M8: KnowledgeBase
- [x] Схема таблицы `knowledge_facts` + FTS5 виртуальная таблица
- [x] Триггеры: `kf_ai`, `kf_au`, `kf_ad` (авто-синхронизация FTS)
- [x] CRUD: `add_fact`, `get_fact`, `list_facts`, `delete_fact`, `count_facts`
- [x] FTS-поиск с фильтром `min_confidence` (high/medium/low)
- [x] Seed: 30 фактов из `data/knowledge_base_seed.json` при старте
- [ ] Обновление (update) факта через AdminPanel

### M5: ContentStore
- [x] Таблица `content_blocks` (advice/faq, draft/published/archived)
- [x] `get_published_blocks`, `list_blocks`, `save_block`, `publish_block`, `reject_block`
- [x] `invalidate_cache()` при публикации (версионный счётчик)
- [ ] Sort order UI в AdminPanel

### M6: ProductStore
- [x] Таблица `products` с 4 seed-записями при старте
- [x] `list_products`, `upsert_product`, `delete_product`
- [ ] Загрузка фото (photo_url сейчас NULL)

---

## Sprint 2 — AI Core

### M7: AICore / Gemini
- [x] `gemini_client.py`: ротация K1..K14 ключей при 429
- [x] Circuit breaker: 3 ошибки за 60 сек → open на 30 сек
- [x] `strip_json_fences` + `parse_json_response` (markdown-обёртки JSON)
- [x] `circuit_status()` экспортируется в `/health`
- [x] **FIX**: сломанные f-строки `{_key_idx % len(_KEYS}` → исправлены
- [ ] Streaming ответов (сейчас — полный blocking ответ)
- [ ] Max 5 concurrent LLM requests (rate limit на входе)

### M2: AgentWidget (backend)
- [x] `ask_agent()`: sanitize_history + get_phase + KB search + call_gemini
- [x] `HistorySanitizer`: только user/assistant, max 500 симв, max 10 сообщ
- [x] `DialoguePhaseTracker`: initial → exploration → closing
- [x] HallucinationGuard: confidence=low → fallback + телефон
- [x] Промпт из файла `prompts/agent_system.txt`
- [ ] Интеграционные тесты агента (5 сценариев из аудита)

### M3: Generator
- [x] `generate_content()`: факты из KB → Gemini → JSON
- [x] `insufficient_data` при пустом KB
- [x] Тон: expert/formal/friendly → рус. пресет
- [x] Промпт из файла `prompts/generator_system.txt`
- [ ] Очередь: авто-постановка в PublicationQueue после генерации

---

## Sprint 3 — Admin + Queue

### M3: AdminPanel (маршруты)
- [x] `/admin/login` GET/POST + rate limit
- [x] `/admin/logout`
- [x] `/admin/dashboard` — сводка (KB count, pending, products, circuit)
- [x] `/admin/queue` — очередь черновиков + approve/reject
- [x] `/admin/generate` — запуск генерации
- [x] `/admin/kb` — просмотр + добавление + удаление фактов
- [x] `/admin/products` — CRUD товаров
- [x] `/admin/dialogues` — лог диалогов + flag ошибки
- [ ] `/admin/dialogues` — фильтр по `has_error`
- [ ] Edit (обновление) факта через форму

### M11: PublicationQueue
- [x] Таблица `publication_queue` (pending/approved/rejected)
- [x] `approve_queue_item` → атомарно публикует в `content_blocks`
- [x] `reject_queue_item`
- [ ] Rollback статуса при ошибке ContentStore (транзакция M11→M5)

---

## Sprint 4 — Landing + Widget + Deploy

### M1: Landing (шаблон)
- [x] Маршрут `GET /` → рендер `landing/index.html`
- [x] Передача: advice_blocks, faq_blocks, products, site_name, phone, agent_enabled
- [x] Fallback при пустом ContentStore (шаблон должен проверять `{% if advice_blocks %}`)
- [ ] Полная HTML-вёрстка лендинга (первый экран, товары, цены, доставка, FAQ, контакты)
- [ ] Интеграция AgentWidget (виджет чата) — JS подключён, инициализация
- [ ] `GET /order` — страница заказа (шаблон `landing/order.html` нужно создать)
- [ ] Адаптивный дизайн (mobile)

### M2: AgentWidget (frontend — `static/js/agent.js`)
- [ ] State machine: idle → loading → answered → cta_shown
- [ ] DOMPurify или `textContent` вместо `innerHTML` (защита от XSS)
- [ ] localStorage: история max 10 сообщений
- [ ] Лимит 500 символов на клиенте
- [ ] Кнопка CTA «Оформить заказ» → `/order`
- [ ] Fallback при 503 / timeout

### Деплой
- [ ] Dockerfile (multi-stage: pip install → copy app → uvicorn)
- [ ] Systemd unit: `/etc/systemd/system/pelleto.service`
- [ ] Nginx reverse proxy конфиг (порт 8131 → 80/443)
- [ ] Решить конфликт порта 8130 (занят code-server) → использовать 8131
- [ ] SSL сертификат (Let's Encrypt / certbot)
- [ ] Переменные окружения в продакшне (MASTER_KEY_HASH, GEMINI_K1..)

---

## Критические фиксы (по аудиту)

| # | Проблема | Статус | Реализация |
|---|----------|--------|------------|
| F1 | Prompt injection (history[]) | ✅ Закрыт | `HistorySanitizer` в agent.py |
| F2 | Agent без скрипта продажи | ✅ Закрыт | `DialoguePhaseTracker` + phase в промпте |
| F3 | Cache invalidation | ✅ Закрыт | `invalidate_cache()` при `publish_block` |
| F4 | Crawler confidence policy | ✅ Закрыт | M7 читает только medium/high из KB |
| F5 | DOM XSS в виджете | ⏳ В процессе | frontend JS не финализирован |
| F6 | Input length limit | ✅ Закрыт | max_length=500 в Pydantic + agent.py |
| F7 | Correlation ID | ✅ Закрыт | X-Request-ID через все вызовы |
| F8 | Health endpoint | ✅ Закрыт | `GET /health` реализован |
| F9 | Fallback content | ✅ Закрыт | Jinja2 `{% if advice_blocks %}` |
| F10 | LLM markdown JSON | ✅ Закрыт | `strip_json_fences` + `parse_json_response` |
| F11 | SQLite trigger split | ✅ Закрыт | `executescript` в `init_db()` |
| F12 | Seed JSON unicode | ✅ Закрыт | Починен `\u0` escape в seed файле |

---

## Известные блокеры

| Блокер | Приоритет | Решение |
|--------|-----------|---------|
| Порт 8130 занят code-server | High | Использовать PORT=8131 в .env |
| Шаблон `/order` отсутствует | High | Создать `templates/landing/order.html` |
| Frontend виджет не финализирован | High | Доработать `static/js/agent.js` |
| Нет Dockerfile | Medium | Создать для деплоя |
| Нет systemd unit | Medium | Создать для автозапуска |

---

## Следующие шаги (приоритет)

1. **[HIGH]** Изменить `PORT=8131` в `.env` (конфликт с code-server)
2. **[HIGH]** Создать `templates/landing/order.html` (сейчас 404)
3. **[HIGH]** Финализировать `static/js/agent.js` (DOMPurify, state machine)
4. **[HIGH]** Дописать HTML лендинга — блоки Первый экран, Товары, Доставка
5. **[MEDIUM]** Создать Dockerfile + systemd service
6. **[MEDIUM]** Написать интеграционные тесты для 5 сценариев агента
7. **[LOW]** Добавить edit-форму для фактов KB
8. **[LOW]** Добавить X-Frame-Options + CSP на /admin/*

---

## Структура проекта (актуальная)

```
pelleto-ai/
├── main.py                          ✅ FastAPI app + lifespan + /health
├── app/
│   ├── core/
│   │   ├── config.py                ✅ Центральный конфиг из .env
│   │   ├── database.py              ✅ aiosqlite + WAL + executescript
│   │   └── logger.py                ✅ JSON structured logging
│   ├── api/
│   │   ├── deps/auth.py             ✅ require_admin dependency
│   │   └── routes/
│   │       ├── landing.py           ✅ GET /
│   │       ├── agent.py             ✅ POST /api/agent/chat
│   │       └── admin.py             ✅ /admin/* (все разделы)
│   └── services/
│       ├── ai/
│       │   ├── agent.py             ✅ ask_agent + sanitize + phase
│       │   ├── generator.py         ✅ generate_content
│       │   └── gemini_client.py     ✅ FIXED: f-strings + circuit breaker
│       ├── auth/service.py          ✅ bcrypt + sessions + rate limit
│       ├── content/service.py       ✅ ContentStore + ProductStore + Queue
│       └── knowledge/service.py     ✅ FTS5 + CRUD
├── templates/
│   ├── base.html                    ✅
│   ├── landing/index.html           ⚠️  Нужна полная вёрстка
│   └── admin/*.html                 ✅ (login, dashboard, kb, products, queue, dialogues, generate)
├── static/
│   ├── css/main.css                 ⚠️  Нужна вёрстка
│   └── js/agent.js                  ⚠️  Нужна финализация
├── data/
│   └── knowledge_base_seed.json     ✅ FIXED: 30 фактов, unicode починен
├── prompts/
│   ├── agent_system.txt             ✅
│   └── generator_system.txt         ✅
├── .env                             ✅ (PORT нужно 8131)
├── requirements.txt                 ✅
└── CHECKLIST.md                     ✅ этот файл
```