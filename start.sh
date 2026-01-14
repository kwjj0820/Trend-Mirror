#!/usr/bin/env bash
set -x
set -euo pipefail

echo "기존 프로세스를 종료합니다..."

# Backend 종료
if [ -f app.pid ]; then
  PID=$(cat app.pid || true)
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Backend(PID: $PID) 종료 중..."
    kill "$PID" || true
  fi
  rm -f app.pid
fi

# Frontend 종료
if [ -f ui.pid ]; then
  PID=$(cat ui.pid || true)
  if [ -n "${PID:-}" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "- Frontend(PID: $PID) 종료 중..."
    kill "$PID" || true
  fi
  rm -f ui.pid
fi

echo "2. 의존성 설치 중..."
uv sync

echo "3. 백엔드 서버(FastAPI) 시작 중..."
# 포트 통일: main.py 기본 PORT=8000이면 여기서도 8000 추천
export PORT="${PORT:-8000}"

nohup uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > app.log 2>&1 &
echo $! > app.pid

echo "4. 서비스 준비 상태 확인 중..."
while true; do
  HEALTH_JSON=$(curl -s "http://localhost:$PORT/agent/health" || echo '{"status":"waiting"}')
  HEALTH_STATUS=$(echo "$HEALTH_JSON" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

  if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo -ne "\r[*] 백엔드 서비스 응답 대기 중..."
    sleep 5
    continue
  fi

  STATUS_JSON=$(curl -s "http://localhost:$PORT/agent/seed-status" || echo '{"status":"waiting"}')
  STATUS=$(echo "$STATUS_JSON" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  MESSAGE=$(echo "$STATUS_JSON" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)

  if [ "$STATUS" = "completed" ]; then
    STATS_JSON=$(curl -s "http://localhost:$PORT/agent/stats" || echo '{"count":0}')
    COUNT=$(echo "$STATS_JSON" | grep -o '"count":[0-9]*' | cut -d':' -f2)

    if [ -n "${COUNT:-}" ] && [ "$COUNT" -gt 0 ]; then
      echo -e "\n[✓] 서비스 및 데이터 준비 완료! (총 $COUNT 개의 문서)"
      break
    fi
  elif [ "$STATUS" = "in_progress" ]; then
    echo -ne "\r[*] 데이터 시딩 진행 중... ($MESSAGE)"
  fi

  sleep 5
done

echo -e "\n5. 프론트엔드 서버(Streamlit) 시작 중..."
export BACKEND_URL="http://localhost:$PORT"

nohup uv run streamlit run infra/frontend/ui.py --server.port 8002 > ui.log 2>&1 &
echo $! > ui.pid

echo -e "\n--------------------------------------------------"
echo "서비스가 성공적으로 시작되었습니다."
echo "백엔드 접속: http://localhost:$PORT"
echo "프론트엔드 접속: http://localhost:8002"
echo "로그 확인: tail -f app.log / tail -f ui.log"
echo "--------------------------------------------------"
