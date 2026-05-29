"""
app/mcp/tools/group6_torrent.py
ГРУППА 6: Торрент-менеджер (P2P стриминг и загрузка).
Инструмент: torrent_download_manager
"""
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

LOGS_DIR = os.environ.get("LOGS_DIR", "/opt/pelleto-ai/logs")
DATA_DIR = os.environ.get("DATA_DIR", "/opt/pelleto-ai/data")
TORRENT_DIR = os.environ.get("TORRENT_DIR", "/opt/pelleto-ai/data/torrents")


def _log(msg: str, diff: int = 5) -> None:
    """Дозапись >> [datetime] [Diff: X/10] msg."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f">> [{ts}] [Diff: {diff}/10] {msg}\n"
    log_path = Path(LOGS_DIR) / "mcp_tools.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def _detect_backend() -> str | None:
    """Определяет доступный торрент-клиент в системе."""
    if shutil.which("aria2c"):
        return "aria2c"
    if shutil.which("transmission-remote") and shutil.which("transmission-daemon"):
        return "transmission"
    # python-libtorrent (устанавливается в PRoot/Ubuntu как python3-libtorrent)
    try:
        import libtorrent  # noqa
        return "libtorrent"
    except ImportError:
        pass
    return None


def torrent_download_manager(
    source: str,
    output_dir: str = "",
    action: str = "start",
    peer_limit: int = 50
) -> dict:
    """
    Программное управление торрент-загрузками в Termux/Linux.
    Автоматически выбирает бэкенд: aria2c → transmission → libtorrent.

    Args:
        source: Magnet-ссылка (magnet:?xt=...) или путь к .torrent файлу
        output_dir: Директория для сохранения файлов
        action: "start" — начать/проверить загрузку | "status" — статус всех задач | "stop" — остановить
        peer_limit: Максимальное количество пиров
    """
    out_dir = output_dir or TORRENT_DIR
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    _log(f"torrent_download_manager: action={action} source='{source[:60]}'", diff=5)

    backend = _detect_backend()
    if not backend:
        return {
            "ok": False,
            "error": "Торрент-клиент не найден",
            "suggestion": (
                "Установите один из: "
                "aria2c (pkg install aria2 / apt install aria2), "
                "Transmission (apt install transmission-daemon), "
                "или python3-libtorrent (apt install python3-libtorrent)"
            )
        }

    _log(f"torrent_download_manager: используется бэкенд={backend}", diff=5)

    # ── Бэкенд: aria2c ───────────────────────────────────────────────────────
    if backend == "aria2c":
        return _aria2c_action(source, out_dir, action, peer_limit)

    # ── Бэкенд: transmission ─────────────────────────────────────────────────
    elif backend == "transmission":
        return _transmission_action(source, out_dir, action)

    # ── Бэкенд: python-libtorrent ─────────────────────────────────────────────
    elif backend == "libtorrent":
        return _libtorrent_action(source, out_dir, action, peer_limit)

    return {"ok": False, "error": "Неизвестный бэкенд"}


def _aria2c_action(source: str, out_dir: str, action: str, peer_limit: int) -> dict:
    """Управление загрузкой через aria2c."""
    if action == "status":
        # aria2c статичен (без демона) — читаем список запущенных процессов
        ps = subprocess.run(
            ["pgrep", "-a", "aria2c"],
            capture_output=True, text=True
        )
        return {
            "ok": True,
            "backend": "aria2c",
            "running_processes": ps.stdout.strip() or "нет активных загрузок"
        }

    if action == "stop":
        subprocess.run(["pkill", "aria2c"], capture_output=True)
        _log("torrent_download_manager: aria2c процессы остановлены", diff=5)
        return {"ok": True, "backend": "aria2c", "action": "stopped"}

    # action == "start"
    if not source:
        return {"ok": False, "error": "source (magnet или .torrent) обязателен"}

    cmd = [
        "aria2c",
        "--dir", out_dir,
        "--max-connection-per-server=4",
        f"--bt-max-peers={peer_limit}",
        "--seed-time=0",       # Не раздавать после завершения
        "--console-log-level=notice",
        "--log", f"{LOGS_DIR}/aria2c.log",
        "--log-level=notice",
        source
    ]

    try:
        # Запускаем в фоне через nohup
        bg_log = f"{LOGS_DIR}/torrent_{int(datetime.now().timestamp())}.log"
        proc = subprocess.Popen(
            f"nohup {' '.join(cmd)} >> {bg_log} 2>&1 &",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        _log(f"torrent_download_manager: aria2c запущен pid={proc.pid} log={bg_log}", diff=5)
        return {
            "ok": True,
            "backend": "aria2c",
            "action": "started",
            "pid": proc.pid,
            "output_dir": out_dir,
            "log_file": bg_log
        }
    except Exception as e:
        _log(f"torrent_download_manager aria2c ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}


def _transmission_action(source: str, out_dir: str, action: str) -> dict:
    """Управление через transmission-remote."""
    remote = ["transmission-remote", "localhost:9091"]

    try:
        if action == "status":
            result = subprocess.run(remote + ["-l"], capture_output=True, text=True, timeout=10)
            return {
                "ok": True,
                "backend": "transmission",
                "list": result.stdout
            }

        elif action == "stop":
            result = subprocess.run(remote + ["-tall", "--stop"], capture_output=True, text=True, timeout=10)
            _log("torrent_download_manager: transmission все задачи остановлены", diff=5)
            return {"ok": True, "backend": "transmission", "action": "stopped", "output": result.stdout}

        elif action == "start":
            if not source:
                return {"ok": False, "error": "source обязателен"}
            args = remote + ["-a", source, "--download-dir", out_dir]
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                # Извлекаем ID задачи из вывода
                id_match = re.search(r"torrent #(\d+)", result.stdout)
                tid = int(id_match.group(1)) if id_match else None
                _log(f"torrent_download_manager: transmission задача добавлена id={tid}", diff=5)
                return {"ok": True, "backend": "transmission", "torrent_id": tid, "output": result.stdout}
            return {"ok": False, "error": result.stderr}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Transmission не отвечает (timeout 10с)"}
    except Exception as e:
        _log(f"torrent_download_manager transmission ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Неизвестное действие: {action}"}


def _libtorrent_action(source: str, out_dir: str, action: str, peer_limit: int) -> dict:
    """Управление через python-libtorrent (синхронный мониторинг 30с)."""
    try:
        import libtorrent as lt
    except ImportError:
        return {"ok": False, "error": "python-libtorrent не установлен"}

    if action == "status":
        return {
            "ok": True,
            "backend": "libtorrent",
            "note": "libtorrent не поддерживает глобальный статус без сессии"
        }

    if action != "start":
        return {"ok": False, "error": f"libtorrent поддерживает только action='start', получено: {action}"}

    if not source:
        return {"ok": False, "error": "source обязателен"}

    try:
        ses = lt.session()
        ses.listen_on(6881, 6891)

        # Загружаем источник
        if source.startswith("magnet:"):
            params = lt.parse_magnet_uri(source)
            params.save_path = out_dir
            handle = ses.add_torrent(params)
        else:
            info = lt.torrent_info(source)
            handle = ses.add_torrent({"ti": info, "save_path": out_dir})

        handle.set_max_connections(peer_limit)

        _log(f"torrent_download_manager: libtorrent сессия запущена out={out_dir}", diff=5)

        # Ждём 10 секунд и возвращаем начальный статус
        import time
        time.sleep(10)
        s = handle.status()

        return {
            "ok": True,
            "backend": "libtorrent",
            "name": handle.name(),
            "progress_pct": round(s.progress * 100, 1),
            "download_rate_kbs": round(s.download_rate / 1024, 1),
            "num_peers": s.num_peers,
            "state": str(s.state),
            "output_dir": out_dir,
            "note": "Сессия запущена. Для продолжения мониторинга вызовите снова с action='status'"
        }

    except Exception as e:
        _log(f"torrent_download_manager libtorrent ERROR: {e}", diff=8)
        return {"ok": False, "error": str(e)}
