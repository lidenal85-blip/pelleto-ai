"""
app/mcp/tools/group5_database.py
ГРУППА 5: Базы данных и мониторинг.
Инструменты: sqlite_schema_inspector, project_time_logger, compress_and_backup
"""
import os
import sqlite3
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path

LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")
DATA_DIR = os.environ.get("DATA_DIR", "/opt/pelleto-ai/data")
DB_PATH = os.environ.get("DB_PATH", "/opt/pelleto-ai/data/pelleto.db")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись >> [datetime] [Diff: X/10] msg."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def sqlite_schema_inspector(
    db_path: str = "",
    table_name: str = "",
    query: str = ""
) -> dict:
    """
    Читает схему, индексы и выполняет безопасные SELECT-запросы к SQLite БД.
    Защита: разрешены только SELECT-запросы (DML/DDL блокируются).

    Args:
        db_path: Путь к .db файлу (по умолчанию — основная БД проекта)
        table_name: Имя таблицы для детального инспектирования
        query: Произвольный SELECT-запрос (только чтение!)
    """
    path = db_path or DB_PATH
    _log(f"sqlite_schema_inspector: db={path} table='{table_name}' query_len={len(query)}", diff=4)

    if not Path(path).exists():
        return {"ok": False, "error": f"БД не найдена: {path}"}

    # Защита: блокируем любые изменяющие операции
    if query:
        q_upper = query.strip().upper()
        forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
                     "REPLACE", "TRUNCATE", "PRAGMA JOURNAL")
        for kw in forbidden:
            if q_upper.startswith(kw):
                return {"ok": False, "error": f"Запрос '{kw}' запрещён (только SELECT)"}

    result: dict = {"ok": True, "db": path}

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Список таблиц
        cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cur.fetchall()
        result["tables"] = [{"name": t["name"], "sql": t["sql"]} for t in tables]

        # Список индексов
        cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
        indexes = cur.fetchall()
        result["indexes"] = [
            {"name": idx["name"], "table": idx["tbl_name"]}
            for idx in indexes if idx["name"]
        ]

        # Детальная схема конкретной таблицы
        if table_name:
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            row_count = cur.fetchone()["cnt"]
            result["table_detail"] = {
                "name": table_name,
                "row_count": row_count,
                "columns": [
                    {
                        "cid": c["cid"],
                        "name": c["name"],
                        "type": c["type"],
                        "notnull": bool(c["notnull"]),
                        "default": c["dflt_value"],
                        "pk": bool(c["pk"])
                    }
                    for c in cols
                ]
            }

        # Выполнение SELECT-запроса
        if query:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            result["query_result"] = {
                "columns": columns,
                "rows": [dict(r) for r in rows[:100]],  # Лимит 100 строк
                "total": len(rows)
            }

        conn.close()
        _log(f"sqlite_schema_inspector: OK таблиц={len(result['tables'])}", diff=4)
        return result

    except sqlite3.Error as e:
        _log(f"sqlite_schema_inspector ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def project_time_logger(
    task: str,
    diff_level: int = 5,
    duration_minutes: float = 0,
    tags: list[str] | None = None,
    phase: str = ""
) -> dict:
    """
    Ведёт журнал учёта времени разработки в файл logs/time_log.md.
    Каждая запись — строка с временной меткой, задачей, сложностью.

    Args:
        task: Описание задачи или события
        diff_level: Уровень сложности 1-10 (влияет на пометку в логе)
        duration_minutes: Затраченное время в минутах (0 = не указано)
        tags: Теги для категоризации (#feature, #bugfix, ...)
        phase: Фаза работы (planning, coding, review, deploy, debug)
    """
    _log(f"project_time_logger: task='{task[:60]}' diff={diff_level} dur={duration_minutes}мин", diff=diff_level)

    log_path = Path(LOGS_DIR) / "time_log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_only = datetime.now().strftime("%Y-%m-%d")

    # Формирование строки лога
    tags_str = " ".join(f"#{t.lstrip('#')}" for t in (tags or []))
    duration_str = f" | ⏱ {duration_minutes:.0f}мин" if duration_minutes > 0 else ""
    phase_str = f" | phase:{phase}" if phase else ""
    diff_bar = "█" * diff_level + "░" * (10 - diff_level)

    entry = (
        f">> [{ts}] [Diff: {diff_level}/10 {diff_bar}]{duration_str}{phase_str}\n"
        f"   **{task}** {tags_str}\n\n"
    )

    # Дозапись в файл
    with open(log_path, "a", encoding="utf-8") as f:
        # Добавляем заголовок дня если начинается новый день
        if log_path.stat().st_size == 0:
            f.write(f"# Project Time Log\n\n")
        f.write(entry)

    # Считаем статистику за сегодня
    total_today = 0.0
    entries_today = 0
    try:
        lines = log_path.read_text(encoding="utf-8").split("\n")
        for line in lines:
            if f"[{date_only}" in line:
                entries_today += 1
                dur_match = __import__("re").search(r"⏱ (\d+(?:\.\d+)?)мин", line)
                if dur_match:
                    total_today += float(dur_match.group(1))
    except Exception:
        pass

    _log(f"project_time_logger: записано | сегодня {entries_today} записей {total_today:.0f}мин", diff=diff_level)
    return {
        "ok": True,
        "logged_at": ts,
        "task": task,
        "diff_level": diff_level,
        "log_path": str(log_path),
        "today_entries": entries_today,
        "today_total_minutes": total_today
    }


def compress_and_backup(
    source_path: str,
    output_dir: str = "",
    format: str = "tar.gz",
    confirm: bool = False
) -> dict:
    """
    Создание сжатой резервной копии папки/файла с временной меткой в названии.
    Формат имени: <basename>_<YYYYMMDD_HHMMSS>.<ext>

    Args:
        source_path: Путь к папке или файлу для резервной копии
        output_dir: Директория для сохранения архива (по умолчанию DATA_DIR/backups)
        format: Формат архива: "tar.gz" | "zip"
        confirm: Подтверждение операции (True — выполнить, False — предварительный просмотр)
    """
    src = Path(source_path)
    if not src.exists():
        return {"ok": False, "error": f"Источник не найден: {source_path}"}

    out_dir = Path(output_dir or str(Path(DATA_DIR) / "backups"))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{src.name}_{ts}.{format.lstrip('.')}"
    archive_path = out_dir / archive_name

    _log(f"compress_and_backup: src={source_path} -> {archive_path} confirm={confirm}", diff=5)

    # Предварительный просмотр без выполнения
    if not confirm:
        size_mb = sum(f.stat().st_size for f in src.rglob("*") if f.is_file()) / 1_048_576
        return {
            "ok": True,
            "status": "preview",
            "source": str(src),
            "archive": str(archive_path),
            "format": format,
            "source_size_mb": round(size_mb, 2),
            "message": "Передайте confirm=True для выполнения резервного копирования"
        }

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if format in ("tar.gz", "tgz"):
            with tarfile.open(str(archive_path), "w:gz") as tar:
                tar.add(str(src), arcname=src.name)
        elif format == "zip":
            with zipfile.ZipFile(str(archive_path), "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_dir():
                    for fpath in src.rglob("*"):
                        if fpath.is_file():
                            zf.write(str(fpath), str(fpath.relative_to(src.parent)))
                else:
                    zf.write(str(src), src.name)
        else:
            return {"ok": False, "error": f"Неподдерживаемый формат: {format}"}

        size_bytes = archive_path.stat().st_size
        _log(f"compress_and_backup: создан {archive_name} ({size_bytes // 1024}КБ)", diff=5)
        return {
            "ok": True,
            "archive": str(archive_path),
            "size_bytes": size_bytes,
            "size_kb": round(size_bytes / 1024, 1)
        }

    except Exception as e:
        _log(f"compress_and_backup ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}
