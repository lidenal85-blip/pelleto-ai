"""
app/mcp/tools/group3_vibe.py
ГРУППА 3: Умная архитектура и Vibe Coding.
Инструменты: search_prompt_library, git_auto_commit_sync,
             code_structure_analyzer, validate_python_syntax
"""
import ast
import os
import re
import subprocess
import py_compile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")
PROMPTS_DIR = os.environ.get("PROMPTS_DIR", "/opt/pelleto-ai/prompts")
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/pelleto-ai")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись >> [datetime] [Diff: X/10] msg."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def search_prompt_library(
    query: str = "",
    tags: list[str] | None = None,
    directory: str = ""
) -> dict:
    """
    Поиск, фильтрация по тегам и чтение системных промптов.
    Ищет в директории ПРОМТЫ по ключевым словам и тегам (#TAG в теле файла).

    Args:
        query: Поисковый запрос по тексту файла
        tags: Список тегов для фильтрации (ищет #TAG в тексте)
        directory: Директория поиска (по умолчанию PROMPTS_DIR)
    """
    search_dir = directory or PROMPTS_DIR
    # Дополнительный путь для Termux-среды
    termux_dir = "/storage/emulated/0/Documents/ПРОМТЫ"

    _log(f"search_prompt_library: query='{query}' tags={tags} dir={search_dir}", diff=3)

    results = []
    dirs_to_search = [search_dir]
    if Path(termux_dir).exists():
        dirs_to_search.append(termux_dir)

    for base_dir in dirs_to_search:
        if not Path(base_dir).exists():
            continue
        # Рекурсивный обход всех .txt, .md файлов
        for fpath in Path(base_dir).rglob("*"):
            if fpath.suffix.lower() not in (".txt", ".md", ".prompt"):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Фильтр по тексту запроса
            if query and query.lower() not in content.lower():
                continue

            # Фильтр по тегам (#TAG)
            if tags:
                file_tags = re.findall(r"#([A-ZА-ЯЁa-zа-яё0-9_]+)", content)
                file_tags_lower = [t.lower() for t in file_tags]
                required = [t.lstrip("#").lower() for t in tags]
                if not any(r in file_tags_lower for r in required):
                    continue

            # Краткий превью — первые 200 символов
            preview = content[:200].replace("\n", " ").strip()
            results.append({
                "path": str(fpath),
                "name": fpath.name,
                "size": fpath.stat().st_size,
                "preview": preview,
                "tags": re.findall(r"#[A-ZА-ЯЁa-zа-яё0-9_]+", content)[:10]
            })

    _log(f"search_prompt_library: найдено {len(results)} файлов", diff=3)
    return {
        "ok": True,
        "query": query,
        "tags": tags,
        "count": len(results),
        "results": results[:20]  # Ограничение: 20 результатов
    }


def git_auto_commit_sync(
    repo_path: str = "",
    commit_message: str = "",
    push: bool = False,
    add_all: bool = True
) -> dict:
    """
    Автоматический анализ изменений, генерация сообщения коммита и git push.
    Если commit_message пуст — формирует сообщение на основе git diff --stat.

    Args:
        repo_path: Путь к репозиторию (по умолчанию PROJECT_ROOT)
        commit_message: Сообщение коммита (пусто = автогенерация)
        push: True — выполнить git push после коммита
        add_all: True — git add -A перед коммитом
    """
    cwd = repo_path or PROJECT_ROOT
    _log(f"git_auto_commit_sync: repo={cwd} push={push} add_all={add_all}", diff=5)

    def git(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )

    # Статус изменений
    status = git(["status", "--porcelain"])
    if not status.stdout.strip():
        _log("git_auto_commit_sync: нет изменений для коммита", diff=3)
        return {"ok": True, "status": "nothing_to_commit", "message": "Нет изменений"}

    # Статистика diff для формирования сообщения
    diff_stat = git(["diff", "--stat", "--cached"]).stdout
    if not diff_stat:
        diff_stat = git(["diff", "--stat"]).stdout

    # Автогенерация сообщения коммита
    if not commit_message:
        lines = [l.strip() for l in status.stdout.strip().split("\n") if l.strip()]
        changed = len([l for l in lines if l.startswith((" M", "M ", "MM"))])
        added = len([l for l in lines if l.startswith("??")])
        deleted = len([l for l in lines if l.startswith(" D") or l.startswith("D ")])
        parts = []
        if added:
            parts.append(f"add {added} files")
        if changed:
            parts.append(f"update {changed} files")
        if deleted:
            parts.append(f"delete {deleted} files")
        commit_message = f"auto: {', '.join(parts)}" if parts else "auto: update"

    if add_all:
        git(["add", "-A"])

    # Коммит
    commit_res = git(["commit", "-m", commit_message])
    if commit_res.returncode != 0:
        _log(f"git_auto_commit_sync WARN: {commit_res.stderr[:200]}", diff=7)
        return {"ok": False, "error": commit_res.stderr, "stdout": commit_res.stdout}

    _log(f"git_auto_commit_sync: коммит создан '{commit_message}'", diff=5)
    result = {"ok": True, "commit_message": commit_message, "pushed": False}

    # Push (только если явно запрошен)
    if push:
        push_res = git(["push"])
        if push_res.returncode == 0:
            result["pushed"] = True
            _log("git_auto_commit_sync: push выполнен успешно", diff=5)
        else:
            result["push_error"] = push_res.stderr
            _log(f"git_auto_commit_sync WARN push: {push_res.stderr[:100]}", diff=7)

    return result


def code_structure_analyzer(
    file_path: str,
    include_docstrings: bool = False
) -> dict:
    """
    Парсит структуру Python-файла через AST: классы, функции, импорты, эндпоинты.
    Не читает всё тело файла — экономит токены.

    Args:
        file_path: Путь к Python-файлу
        include_docstrings: True — включить первые строки докстрингов
    """
    _log(f"code_structure_analyzer: файл={file_path}", diff=4)

    if not Path(file_path).exists():
        return {"ok": False, "error": f"Файл не найден: {file_path}"}

    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        return {"ok": False, "error": f"Синтаксическая ошибка: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    structure: dict[str, Any] = {
        "file": file_path,
        "lines": source.count("\n") + 1,
        "imports": [],
        "functions": [],
        "classes": [],
        "fastapi_routes": []
    }

    for node in ast.walk(tree):
        # Импорты
        if isinstance(node, ast.Import):
            for alias in node.names:
                structure["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [a.name for a in node.names]
            structure["imports"].append(f"{module}: {', '.join(names)}")

        # Функции верхнего уровня
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if not any(isinstance(p, ast.ClassDef) for p in ast.walk(tree)
                       if hasattr(p, "body") and node in getattr(p, "body", [])):
                fn: dict[str, Any] = {
                    "name": node.name,
                    "line": node.lineno,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "args": [a.arg for a in node.args.args],
                }
                # FastAPI-декораторы (@router.get, @app.post и т.д.)
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                    if any(x in dec_str for x in (".get(", ".post(", ".put(", ".delete(", ".patch(")):
                        structure["fastapi_routes"].append({
                            "handler": node.name,
                            "decorator": dec_str,
                            "line": node.lineno
                        })
                if include_docstrings:
                    doc = ast.get_docstring(node)
                    fn["docstring"] = doc[:100] if doc else None
                structure["functions"].append(fn)

        # Классы
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) if hasattr(ast, "unparse") else "" for b in node.bases]
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            cls: dict[str, Any] = {
                "name": node.name,
                "line": node.lineno,
                "bases": bases,
                "methods": methods
            }
            if include_docstrings:
                doc = ast.get_docstring(node)
                cls["docstring"] = doc[:100] if doc else None
            structure["classes"].append(cls)

    _log(
        f"code_structure_analyzer: {len(structure['functions'])} функций, "
        f"{len(structure['classes'])} классов, "
        f"{len(structure['fastapi_routes'])} маршрутов",
        diff=4
    )
    return {"ok": True, **structure}


def validate_python_syntax(
    code: str = "",
    file_path: str = ""
) -> dict:
    """
    Линтинг и проверка синтаксиса Python-кода через py_compile и ast.parse.
    Опционально — через flake8 если установлен.

    Args:
        code: Строка кода для проверки (приоритет над file_path)
        file_path: Путь к файлу для проверки
    """
    _log(f"validate_python_syntax: code_len={len(code)} file='{file_path}'", diff=3)

    result: dict[str, Any] = {
        "ok": False,
        "syntax_valid": False,
        "errors": [],
        "warnings": []
    }

    # Определяем источник кода
    if code:
        # Записываем во временный файл для py_compile
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as tf:
            tf.write(code)
            tmp_path = tf.name
        source = code
    elif file_path and Path(file_path).exists():
        tmp_path = file_path
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    else:
        return {"ok": False, "error": "Нужен code или существующий file_path"}

    # 1. Проверка через ast.parse (быстрее)
    try:
        ast.parse(source, filename=tmp_path)
        result["syntax_valid"] = True
    except SyntaxError as e:
        result["errors"].append({
            "type": "SyntaxError",
            "message": str(e.msg),
            "line": e.lineno,
            "text": e.text
        })
        result["syntax_valid"] = False

    # 2. py_compile для более точных сообщений
    if result["syntax_valid"]:
        try:
            py_compile.compile(tmp_path, doraise=True)
        except py_compile.PyCompileError as e:
            result["errors"].append({"type": "CompileError", "message": str(e)})
            result["syntax_valid"] = False

    # 3. flake8 (если установлен) — предупреждения стиля
    import shutil
    if shutil.which("flake8") and result["syntax_valid"]:
        fl = subprocess.run(
            ["flake8", "--max-line-length=120", tmp_path],
            capture_output=True, text=True, timeout=15
        )
        if fl.stdout.strip():
            for line in fl.stdout.strip().split("\n")[:20]:
                result["warnings"].append(line)

    # Удаляем временный файл если был создан
    if code:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    result["ok"] = True
    status = "valid" if result["syntax_valid"] else "invalid"
    _log(
        f"validate_python_syntax: {status} errors={len(result['errors'])} "
        f"warnings={len(result['warnings'])}",
        diff=3
    )
    return result
