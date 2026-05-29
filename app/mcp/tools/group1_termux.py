"""
app/mcp/tools/group1_termux.py
ГРУППА 1: Управление окружением и процессами Termux/Linux.
Инструменты: execute_background_task, monitor_system_resources,
             manage_termux_wake, error_buffer_stream
"""
import os
import time
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Директория логов по умолчанию
LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись в лог-файл с форматом >> [datetime] [Diff: X/10] сообщение."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def execute_background_task(
    command: str,
    use_nohup: bool = True,
    log_file: str = ""
) -> dict:
    """
    Запускает долгий процесс в фоне через nohup или tmux.
    Возвращает PID запущенного процесса.

    Args:
        command: Команда для выполнения (строка shell)
        use_nohup: True — nohup, False — попытка через tmux
        log_file: Путь к файлу вывода (по умолчанию — logs/bg_<pid>.log)
    """
    _log(f"execute_background_task: command='{command[:80]}' use_nohup={use_nohup}", diff=4)
    try:
        if use_nohup:
            # Определяем файл вывода: переданный или автосгенерированный
            out = log_file or f"{LOGS_DIR}/bg_{int(time.time())}.log"
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                f"nohup {command} >> {out} 2>&1 &",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pid = proc.pid
        else:
            # Попытка запустить через tmux (если установлен)
            if not shutil.which("tmux"):
                return {"ok": False, "error": "tmux не найден, используйте use_nohup=True"}
            session = f"bg_{int(time.time())}"
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session, command],
                check=True
            )
            # Получаем PID последнего tmux-процесса
            result = subprocess.run(
                ["tmux", "list-panes", "-t", session, "-F", "#{pane_pid}"],
                capture_output=True, text=True
            )
            pid = int(result.stdout.strip()) if result.stdout.strip() else -1

        _log(f"execute_background_task: запущено pid={pid}", diff=4)
        return {"ok": True, "pid": pid, "log_file": log_file or ""}
    except Exception as e:
        _log(f"execute_background_task ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def monitor_system_resources() -> dict:
    """
    Мониторинг CPU, RAM и заряда батареи.
    Читает /proc/stat, /proc/meminfo и /sys/class/power_supply.
    Graceful-деградация на окружениях без /sys.
    """
    _log("monitor_system_resources: сбор метрик", diff=3)
    result: dict = {}

    # ── CPU через /proc/stat ──────────────────────────────────────────────────
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        # Формат: cpu  user nice system idle iowait irq softirq
        parts = line.split()
        nums = [int(x) for x in parts[1:]]
        total = sum(nums)
        idle = nums[3]
        # Ждём 0.1с и читаем повторно для дельты
        time.sleep(0.1)
        with open("/proc/stat") as f:
            line2 = f.readline()
        parts2 = line2.split()
        nums2 = [int(x) for x in parts2[1:]]
        total2 = sum(nums2)
        idle2 = nums2[3]
        d_total = total2 - total
        d_idle = idle2 - idle
        cpu_pct = round((1 - d_idle / d_total) * 100, 1) if d_total else 0.0
        result["cpu_percent"] = cpu_pct
    except Exception as e:
        result["cpu_percent"] = None
        result["cpu_error"] = str(e)

    # ── RAM через /proc/meminfo ───────────────────────────────────────────────
    try:
        mem: dict = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                mem[k.strip()] = int(v.split()[0])  # kB
        total_mb = mem.get("MemTotal", 0) // 1024
        avail_mb = mem.get("MemAvailable", 0) // 1024
        used_mb = total_mb - avail_mb
        result["ram_total_mb"] = total_mb
        result["ram_used_mb"] = used_mb
        result["ram_free_mb"] = avail_mb
        result["ram_percent"] = round(used_mb / total_mb * 100, 1) if total_mb else 0
    except Exception as e:
        result["ram_error"] = str(e)

    # ── Батарея через /sys/class/power_supply ─────────────────────────────────
    try:
        bat_path = Path("/sys/class/power_supply")
        bat_level = None
        bat_status = None
        for psu in bat_path.iterdir():
            cap_file = psu / "capacity"
            stat_file = psu / "status"
            if cap_file.exists():
                bat_level = int(cap_file.read_text().strip())
                if stat_file.exists():
                    bat_status = stat_file.read_text().strip()
                break
        result["battery_percent"] = bat_level
        result["battery_status"] = bat_status
    except Exception:
        result["battery_percent"] = "n/a (не мобильное окружение)"
        result["battery_status"] = "unknown"

    _log(f"monitor_system_resources: cpu={result.get('cpu_percent')}% ram={result.get('ram_percent')}%", diff=3)
    return result


def manage_termux_wake(action: str = "lock") -> dict:
    """
    Управление блокировкой сна Android (termux-wake-lock / termux-wake-unlock).
    На не-Termux окружениях возвращает информационный статус.

    Args:
        action: "lock" — удерживать процессор, "unlock" — освободить
    """
    if action not in ("lock", "unlock"):
        return {"ok": False, "error": "action должен быть 'lock' или 'unlock'"}

    _log(f"manage_termux_wake: action={action}", diff=2)

    cmd = f"termux-wake-{action}"
    if not shutil.which(cmd):
        # На сервере Termux-утилиты недоступны — честно сообщаем
        _log(f"manage_termux_wake: {cmd} не найден (не Termux-окружение)", diff=2)
        return {
            "ok": True,
            "status": "skipped",
            "message": f"{cmd} недоступен в текущем окружении (требуется Android/Termux)"
        }

    try:
        subprocess.run([cmd], check=True, timeout=5)
        _log(f"manage_termux_wake: {action} успешно применён", diff=2)
        return {"ok": True, "action": action}
    except subprocess.CalledProcessError as e:
        _log(f"manage_termux_wake ERROR: {e}", diff=7)
        return {"ok": False, "error": str(e)}


def error_buffer_stream(
    log_path: str = "",
    filter_keyword: str = "",
    last_n: int = 50
) -> dict:
    """
    Чтение и фильтрация последних записей из лог-файла ошибок.
    Аналог WebSocket-логгера eb_listener для просмотра в MCP-клиенте.

    Args:
        log_path: Путь к лог-файлу (по умолчанию — logs/mcp_tools.log)
        filter_keyword: Ключевое слово для фильтрации строк (пусто = всё)
        last_n: Количество последних строк для возврата
    """
    target = log_path or str(Path(LOGS_DIR) / "pelleto.log")
    _log(f"error_buffer_stream: читаю {target} last_n={last_n} filter='{filter_keyword}'", diff=2)

    if not Path(target).exists():
        # Пробуем альтернативный лог
        alt = Path(LOGS_DIR) / "mcp_tools.log"
        if alt.exists():
            target = str(alt)
        else:
            return {"ok": False, "error": f"Лог-файл не найден: {target}"}

    try:
        with open(target, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Берём последние last_n строк
        tail = lines[-last_n:]

        # Фильтрация по ключевому слову (регистронезависимо)
        if filter_keyword:
            kw = filter_keyword.lower()
            tail = [l for l in tail if kw in l.lower()]

        return {
            "ok": True,
            "log_path": target,
            "lines_total": len(lines),
            "lines_returned": len(tail),
            "content": "".join(tail)
        }
    except Exception as e:
        _log(f"error_buffer_stream ERROR: {e}", diff=7)
        return {"ok": False, "error": str(e)}
