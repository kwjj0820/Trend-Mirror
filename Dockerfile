# 1. 빌드 스테이지: 의존성 설치를 위한 임시 공간
FROM python:3.12-slim AS builder
# 파이썬 최적화 환경변수 및 uv 환경 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1 \
UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# 2. 필수 빌드 도구 및 uv 설치
# build-essential, gcc 등은 패키지 컴파일에 필요하지만 런타임엔 불필요하므로 빌더에서만 사용
RUN apt-get update && \
apt-get install -y --no-install-recommends build-essential gcc libffi-dev && \
pip install --no-cache-dir uv && \
rm -rf /var/lib/apt/lists/*
# 3. 의존성 파일 복사 및 설치
COPY pyproject.toml ./
# uv sync: 가상환경(.venv)에 의존성 설치 (개발용 패키지 제외로 용량 절약)
RUN uv sync --no-dev --no-cache
# 4. 전체 코드 복사 (이후 단계에서 필요한 파일만 골라서 가져감)
COPY . .
# -------------------------------------------------------
# backend 런타임 스테이지
# -------------------------------------------------------
FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1
WORKDIR /app
# 1. 보안을 위해 루트 권한이 아닌 별도 사용자 생성
RUN useradd -m appuser
# 2. [핵심] 빌더(builder)에서 만든 가상환경만 복사해옴
COPY --from=builder /app/.venv /app/.venv
# 3. 백엔드 구동에 필요한 소스코드만 선별 복사
COPY --from=builder /app/main.py /app/main.py
COPY --from=builder /app/app /app/app
COPY --from=builder /app/infra /app/infra
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/resources /app/resources
# 파일 소유권 변경
RUN chown -R appuser:appuser /app
# 4. 가상환경을 기본 Python 경로로 설정 (별도 activate 불필요)
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# 보안 사용자로 전환
USER appuser
EXPOSE 8000
# FastAPI 서버 실행
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
# -------------------------------------------------------
# frontend 런타임 스테이지
# -------------------------------------------------------
FROM python:3.12-slim AS frontend
ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd -m appuser
# 빌더에서 가상환경 복사
COPY --from=builder /app/.venv /app/.venv
# 프론트엔드 코드 복사 (infra 폴더 등)
COPY --from=builder /app/infra /app/infra
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/resources /app/resources
# 가상환경 경로 설정
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# 파일 소유권 변경
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8002
# Streamlit 실행
CMD ["/app/.venv/bin/streamlit", "run", "infra/frontend/ui.py", "--server.port", "8002", "--server.address", "0.0.0.0"]
