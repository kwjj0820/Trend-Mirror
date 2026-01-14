#!/usr/bin/env bash
set -euo pipefail
set -x

echo "Restarting services..."

# -----------------------------
# 1) Stop existing processes
# -----------------------------
echo "Stopping existing processes..."

# Backend 종료
if [ -f app.pid ]; then
  PID="$(cat app.pid || true)"
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Stopping Backend(PID: $PID)..."
    kill "$PID" || true

    # graceful wait (최대 10초)
    for _ in {1..10}; do
      ps -p "$PID" > /dev/null 2>&1 || break
      sleep 1
    done

    # still alive -> force
    if ps -p "$PID" > /dev/null 2>&1; then
      echo "- Backend still alive, forcing kill -9 (PID: $PID)"
      kill -9 "$PID" || true
    fi
  fi
  rm -f app.pid
else
  echo "No Backend PID file found"
fi

# Frontend 종료
if [ -f ui.pid ]; then
  PID="$(cat ui.pid || true)"
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Stopping Frontend(PID: $PID)..."
    kill "$PID" || true

    # graceful wait (최대 10초)
    for _ in {1..10}; do
      ps -p "$PID" > /dev/null 2>&1 || break
      sleep 1
    done

    # still alive -> force
    if ps -p "$PID" > /dev/null 2>&1; then
      echo "- Frontend still alive, forcing kill -9 (PID: $PID)"
      kill -9 "$PID" || true
    fi
  fi
  rm -f ui.pid
else
  echo "No Frontend PID file found"
fi

# -----------------------------
# 2) Install deps
# -----------------------------
echo "2. Installing dependencies..."
uv sync

# -----------------------------
# 3) Start backend
# -----------------------------
echo "3. Starting backend..."
export PORT="${PORT:-8000}"

nohup uv run python main.py > app.log 2>&1 &
echo $! > app.pid

# -----------------------------
# 4) Wait until backend ready
# -----------------------------
echo "4. Waiting for backend health..."
while true; do
  TREND_JSON="$(curl -s "http://localhost:$PORT/trendmirror" || echo '{"status":"waiting"}')"
  TREND_STATUS="$(echo "$TREND_JSON" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || true)"

  if [ "${TREND_STATUS:-}" != "ok" ] && [ "${TREND_STATUS:-}" != "trendmirror" ]; then
    echo -ne "\r[*] Backend not ready yet... (status=${TREND_STATUS:-none})"
    sleep 5
    continue
  fi

  echo -e "\n[*] Backend is ready (status=${TREND_STATUS})"
  break
done

# -----------------------------
# 5) Start UI (Streamlit)
# -----------------------------
echo "5. Starting UI (Streamlit)..."
export BACKEND_URL="http://localhost:$PORT"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS="false"
export STREAMLIT_SERVER_HEADLESS="true"

nohup uv run streamlit run infra/ui.py --server.port 8002 > ui.log 2>&1 &
echo $! > ui.pid

echo -e "\n--------------------------------------------------"
echo "Services restarted successfully"
echo "Backend:  http://localhost:$PORT"
echo "Frontend: http://localhost:8002"
echo "Logs:     tail -f app.log / tail -f ui.log"
echo "--------------------------------------------------"
