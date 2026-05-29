"""
app/core/config.py — Центральная конфигурация из .env
VSE moduli importhiruyut otsyuda. Nikto ne chitaet os.environ napryamuyu.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─ FastAPI
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-change-me")
DEBUG: bool = os.getenv("FLASK_ENV", "production") == "development"
PORT: int = int(os.getenv("PORT", "8130"))

# ─ Admin Auth
MASTER_KEY_HASH: str = os.getenv("MASTER_KEY_HASH", "")
SESSION_LIFETIME_HOURS: int = int(os.getenv("SESSION_LIFETIME_HOURS", "24"))
MAX_LOGIN_ATTEMPTS: int = 3
LOCKOUT_MINUTES: int = 30
TAP_COUNT_REQUIRED: int = 5
TAP_WINDOW_SECONDS: int = 5

# ─ Gemini
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "10"))
GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "1500"))
# Circuit breaker
CB_FAILURE_THRESHOLD: int = 3
CB_RECOVERY_TIMEOUT: int = 30
CB_WINDOW: int = 60

# ─ Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

# ─ Database
DB_PATH: str = os.getenv("DB_PATH", "./data/pelleto.db")
DB_BUSY_TIMEOUT_MS: int = int(os.getenv("DB_BUSY_TIMEOUT_MS", "5000"))

# ─ Agent
AGENT_ENABLED: bool = os.getenv("AGENT_ENABLED", "true").lower() == "true"
AGENT_MAX_QUESTION_LEN: int = int(os.getenv("AGENT_MAX_QUESTION_LEN", "500"))
AGENT_MAX_HISTORY: int = int(os.getenv("AGENT_MAX_HISTORY", "10"))
# Phase thresholds
PHASE_EXPLORATION_AT: int = 1   # >= msgs
PHASE_CLOSING_AT: int = 4       # >= msgs

# ─ Site
SITE_NAME: str = os.getenv("SITE_NAME", "Тёплый Склад")
SITE_PHONE: str = os.getenv("SITE_PHONE", "+7 (999) 123-45-67")
SITE_ADDRESS: str = os.getenv("SITE_ADDRESS", "Москва и МО")
SITE_VERSION: str = os.getenv("SITE_VERSION", "1.0.0")
ORDER_URL: str = os.getenv("ORDER_URL", "/order")

# ─ Paths
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROMPTS_DIR: str = os.path.join(BASE_DIR, "prompts")
LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
DATA_DIR: str = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR: str = os.path.join(BASE_DIR, "templates")
STATIC_DIR: str = os.path.join(BASE_DIR, "static")
ROOT_PATH: str = os.getenv("ROOT_PATH", "")
