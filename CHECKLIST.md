# Pelleto AI — Чек-лист разработки

> Последнее обновление: 2026-05-29 (реальная проверка)
> Версия: 0.1.0
> Статус: РАБОТАЕТ (health OK, nginx:80→8131)

---

## Оценка готовности: 72%

| Категория | % | Комментарий |
|-----------|---|-------------|
| Инфраструктура | 86 | Нет Dockerfile |
| База данных | 100 | 30 фактов, 4 продукта, WAL включён |
| Аутентификация | 83 | Нет X-Frame-Options/CSP |
| AI Core (Gemini) | 80 | Нет streaming, нет rate limit |
| Агент продаж (backend) | 100 | Всё реализовано, отвечает ~3с |
| База знаний | 80 | Нет edit-факта |
| Контент / очередь | 80 | Нет rollback M11→M5 |
| Маршруты API | 100 | /health /order /api/order /api/agent/chat |
| Лендинг (шаблон) | 100 | Полная вёрстка + TapDetector |
| Страница /order | 100 | Форма заказа + валидация |
| Frontend виджет (JS) | 80 | XSS-safe, нет явного state machine |
| Admin-панель | 80 | Нет has_error-фильтра, нет edit-факта |
| Деплой | 80 | systemd+nginx есть, нет Dockerfile |
| SSL | 0 | Нет для pelleto-домена |
| E2E тесты | 0 | Не написаны |

---

## Что работает сейчас

- GET / — лендинг: hero, товары, доставка, советы-fallback, контакты, agent-виджет
- GET /order — форма заказа с валидацией
- POST /api/agent/chat — ~3с, phase=initial, correlation_id есть
- POST /api/order — работает (200)
- GET /admin/* — все маршруты работают (200)
- GET /health — {status:ok, llm_circuit:closed}
- Systemd pelleto.service — active, 2 workers
- Nginx :80 → 127.0.0.1:8131 + static cached 7d
- SQLite: все таблицы, FTS5, 30 KB-фактов, 4 продукта
- bcrypt + rate-limit (3/30мин) + server sessions
- HistorySanitizer + DialoguePhaseTracker + HallucinationGuard
- Circuit breaker Gemini (3 ошибки/60с → open 30с)
- Cache invalidation при публикации
- XSS: textContent (не innerHTML) в agent.js
- Лимит 500 симв. (клиент + Pydantic)
- X-Request-ID через все вызовы
- strip_json_fences (парсинг markdown-JSON)
- TapDetector: 5 кликов по версии → /admin/login

---

## Чего нет

- Dockerfile
- SSL для pelleto-домена (работает по HTTP)
- E2E-тесты
- X-Frame-Options / CSP на /admin/*
- Rate limiting на /api/agent/chat
- Edit-форма факта KB
- Фильтр has_error в /admin/dialogues
- Rollback M11→M5
- State machine в agent.js
- Streaming ответов (блокинг ~3с)
- Фото товаров (photo_url = NULL)

---

## Приоритет

### HIGH
1. Rate limit /api/agent/chat (риск DoS)
2. SSL + домен для pelleto
3. Проверка мобильной адаптации

### MEDIUM
4. Dockerfile
5. Фильтр has_error в /admin/dialogues
6. Edit-форма факта KB
7. Rollback M11→M5
8. X-Frame-Options + CSP
9. State machine в agent.js

### LOW
10. E2E-тесты
11. Streaming ответов
12. Фото товаров
13. Sort order UI

---

## Статус всех fix-ов

| # | Fix | Статус |
|---|-----|--------|
| F1 | Prompt injection | OK sanitize_history() |
| F2 | Скрипт продажи | OK get_phase() |
| F3 | Cache invalidation | OK invalidate_cache() |
| F4 | Crawler confidence | OK medium/high only |
| F5 | DOM XSS | OK textContent |
| F6 | Input limit 500 | OK client+server |
| F7 | Correlation ID | OK X-Request-ID |
| F8 | /health | OK |
| F9 | Fallback content | OK Jinja2 if |
| F10 | Markdown JSON | OK strip_json_fences |
| F11 | SQLite triggers | OK executescript |
| F12 | Seed unicode | OK |
| F13 | Порт 8130→8131 | OK .env |

---

## Инфраструктура

- pelleto.service — active, EnvironmentFile=/opt/pelleto-ai/.env
- Uvicorn 127.0.0.1:8131, 2 workers
- Nginx listen 80 server_name _ → 8131, static 7d
- SSL: нет (только leviathanstory.ru)
- Домен: server_name _ (доступ по IP)
- Git: 3 коммита, ветка main
