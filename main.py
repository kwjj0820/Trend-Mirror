# main.py
import uvicorn
import os

if __name__ == "__main__":
    # 포트 설정: 환경변수 또는 기본값 8000
    port = int(os.getenv("PORT", 8000))

    # Reload 옵션은 개발 환경에서만 True 권장
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)