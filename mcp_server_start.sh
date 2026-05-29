#!/usr/bin/env bash
# mcp_server_start.sh — Запуск/перезапуск MCP-сервера Pelleto AI
# Использование:
#   ./mcp_server_start.sh          — перезапустить (убить старый, запустить новый)
#   ./mcp_server_start.sh stop     — только остановить
#   ./mcp_server_start.sh status   — показать статус

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_PORT="${MCP_PORT:-8132}"
PID_FILE="$PROJECT_DIR/logs/mcp_server.pid"
LOG_FILE="$PROJECT_DIR/logs/mcp_server.log"

mkdir -p "$PROJECT_DIR/logs"

case "${1:-restart}" in

  stop)
    if [ -f "$PID_FILE" ]; then
      OLD_PID=$(cat "$PID_FILE")
      if kill -0 "$OLD_PID" 2>/dev/null; then
        echo ">> Останавливаю MCP-сервер PID=$OLD_PID"
        kill "$OLD_PID" && rm -f "$PID_FILE"
        sleep 1
        echo ">> Остановлен."
      else
        echo ">> PID $OLD_PID уже не запущен, очищаю PID-файл."
        rm -f "$PID_FILE"
      fi
    else
      # Ищем по порту
      PIDS=$(lsof -ti tcp:$MCP_PORT 2>/dev/null || true)
      if [ -n "$PIDS" ]; then
        echo ">> Убиваю процессы на порту $MCP_PORT: $PIDS"
        echo "$PIDS" | xargs kill 2>/dev/null || true
      else
        echo ">> MCP-сервер не запущен."
      fi
    fi
    ;;

  status)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        echo ">> MCP-сервер запущен: PID=$PID порт=$MCP_PORT"
      else
        echo ">> PID-файл существует ($PID), но процесс мёртв."
      fi
    else
      echo ">> PID-файл отсутствует."
    fi
    # Проверяем через lsof
    PIDS=$(lsof -ti tcp:$MCP_PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
      echo ">> Порт $MCP_PORT занят процессом(ами): $PIDS"
    fi
    ;;

  restart|start)
    # Останавливаем старый экземпляр
    bash "$0" stop

    echo ">> Запускаю MCP-сервер на порту $MCP_PORT..."
    cd "$PROJECT_DIR"

    nohup python3 -m app.mcp.server >> "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"

    sleep 2

    if kill -0 "$NEW_PID" 2>/dev/null; then
      echo ">> MCP-сервер запущен: PID=$NEW_PID порт=$MCP_PORT"
      echo ">> Лог: $LOG_FILE"
    else
      echo ">> ОШИБКА: процесс упал. Проверьте $LOG_FILE"
      tail -20 "$LOG_FILE"
      exit 1
    fi
    ;;

  *)
    echo "Использование: $0 [start|stop|restart|status]"
    exit 1
    ;;
esac
