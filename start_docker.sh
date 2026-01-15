#!/bin/bash
set -e

echo "1. Docker 이미지 빌드 및 실행 중..."
# 백엔드/프론트엔드 최신 코드 반영을 위해 빌드 후 실행
docker-compose up -d --build

echo "2. 서비스 준비 상태 확인 중..."
while true; do
    # A) 컨테이너 실행 여부 확인
    if ! docker ps | grep -q trend-mirror-backend || ! docker ps | grep -q trend-mirror-frontend; then
        echo -ne "\r[*] 컨테이너가 아직 실행되지 않았습니다. 대기 중..."
        sleep 5
        continue
    fi

    # B) 백엔드 헬스 체크 (수정됨: /docs 페이지 접속 확인)
    # 특정 JSON 응답을 파싱하는 대신, 서버가 정상적으로 켜져서
    # 문서 페이지(/docs)에 200 OK 응답을 주는지 확인합니다.
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)

    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "\n[V] 백엔드 서비스 준비 완료!"
        break
    else
        # 000이나 404 등이 뜬다면 아직 부팅 중이거나 에러 상태임
        echo -ne "\r[*] 백엔드 시동 중... (현재 응답 코드: $HTTP_CODE)"
        sleep 3
        continue
    fi
done

echo -e "\n----------------------------------------"
echo "서비스가 성공적으로 시작되었습니다."
echo "백엔드 접속: http://localhost:8000"
echo "프론트엔드 접속: http://localhost:8002"
echo "ChromaDB 접속: http://localhost:8800"
echo "로그 확인: docker-compose logs -f"
echo "----------------------------------------"