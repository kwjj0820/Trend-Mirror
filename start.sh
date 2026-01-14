#!/usr/bin/env bash
set -x
set -euo pipefail

echo "기존 ?�로?�스�?종료?�니??.."

# Backend 종료
if [ -f app.pid ]; then
  PID=$(cat app.pid || true)
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Backend(PID: $PID) 종료 �?.."
    kill "$PID" || true
  fi
  rm -f app.pid
fi

# Frontend 종료
if [ -f ui.pid ]; then
  PID=$(cat ui.pid || true)
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Frontend(PID: $PID) 종료 �?.."
    kill "$PID" || true
  fi
  rm -f ui.pid
fi

echo "2. ?�존???�치 �?.."
uv sync

echo "3. 백엔???�버(FastAPI) ?�작 �?.."
# ?�트 ?�일: main.py 기본 PORT=8000?�면 ?�기?�도 8000 추천
export PORT="${PORT:-8000}"

#nohup uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > app.log 2>&1 &
nohup uv run python main.py > app.log 2>&1 &
echo $! > app.pid

echo "4. ?�비??준�??�태 ?�인 �?.."
while true; do
  TREND_JSON=$(curl -s "http://localhost:$PORT/trendmirror" || echo '{"status":"waiting"}')
  TREND_STATUS=$(echo "$TREND_JSON" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

  if [ "$TREND_STATUS" != "ok" ] && [ "$TREND_STATUS" != "trendmirror" ]; then
    echo -ne "
[*] ???????????????????? ????????.."
    sleep 5
    continue
  fi

  break
done

echo -e "streaming 작업 시작"
export BACKEND_URL="http://localhost:$PORT"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS="false"
export STREAMLIT_SERVER_HEADLESS="true"

nohup uv run streamlit run infra/ui.py --server.port 8002 > ui.log 2>&1 &
echo $! > ui.pid

echo -e "\n--------------------------------------------------"
echo "?�비?��? ?�공?�으�??�작?�었?�니??"
echo "백엔???�속: http://localhost:$PORT"
echo "?�론?�엔???�속: http://localhost:8002"
echo "로그 ?�인: tail -f app.log / tail -f ui.log"
echo "--------------------------------------------------"
