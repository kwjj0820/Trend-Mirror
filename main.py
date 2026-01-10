# main.py
import uvicorn
import os

def setup_directories():
    """Ensure necessary directories exist."""
    dirs = ["logs", "downloads", "reports", "chroma_tm"]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

if __name__ == "__main__":
    # 1. 필요한 디렉토리 생성
    setup_directories()

    # 포트 설정: 환경변수 또는 기본값 8000
    port = int(os.getenv("PORT", 8000))

    # Reload 옵션은 개발 환경에서만 True 권장
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)