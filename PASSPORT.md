# PASSPORT: Pelleto AI

## Идентификация
| Поле | Значение |
|------|----------|
| **Название** | Pelleto AI |
| **Репозиторий** | github.com/lidenal85-blip/pelleto-ai |
| **Сервер** | root@78.17.24.96 (LEVIATHAN) |
| **Путь** | /opt/pelleto-ai |
| **Порт** | **8130** |
| **Версия** | 0.1.0 |
| **Статус** | 🔧 IN DEVELOPMENT |
| **Создан** | 2026-05-28 |

## Назначение
Автономный продающий лендинг топливных пеллет:
- ИИ-агент консультирует посетителей и ведёт к заказу
- ИИ-генератор создаёт статьи из Базы знаний
- Администратор управляет через защищённую панель
- Telegram-бот для уведомлений (aiogram3)

## Стек
| Слой | Технология |
|------|------------|
| Backend | FastAPI + Uvicorn (Python 3.12) |
| LLM | Google Gemini (gemini-2.0-flash) |
| Telegram | aiogram3 |
| БД | SQLite FTS5 + aiosqlite |
| Frontend | Jinja2 + Vanilla JS |
| Стиль | Тёплый Склад |
| Деплой | systemd pelleto-ai.service |

## Порты LEVIATHAN
| Порт | Сервис |
|------|--------|
| 8200 | Leviathan Agent |
| 8095 | ArbitrCockpit |
| 8110 | KinoVibe |
| 8120 | VoiceStudio |
| **8130** | **Pelleto AI** |

## История
| Дата | Версия | Описание |
|------|--------|----------|
| 2026-05-28 | 0.1.0 | Init: паспорт, структура, seed KB |
