"""
app/core/templates.py — единый Jinja2Templates с root_path как глобальной переменной.
"""
from fastapi.templating import Jinja2Templates
from app.core.config import TEMPLATES_DIR, ROOT_PATH

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Добавляем root_path во все шаблоны
templates.env.globals["root_path"] = ROOT_PATH