# app/main.py # Intentionally cause an error for debugging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import chat
from dotenv import load_dotenv
import os

# 환경변수 로드
if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrendMirror API",
        description="AI Agentic Workflow for Trend Analysis",
        version="1.0.0"
    )

    # CORS 설정 (프론트엔드 연동 대비)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

    @app.get("/trendmirror")
    def trendmirror_check():
        return {"status": "ok"}

    return app


app = create_app()