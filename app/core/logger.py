# app/core/logger.py
import logging
import os
from datetime import datetime
import sys

# 1. 로그 디렉토리 생성
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 2. 로거 초기화
logger = logging.getLogger("trend_mirror")
logger.setLevel(logging.INFO)

# 중복 핸들러 방지 (서버 재실행 시 로그 중복 출력 방지)
if not logger.handlers:
    # 3. 포맷 설정
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 4. 파일 핸들러 (날짜별 파일 저장)
    current_date = datetime.now().strftime("%Y%m%d")
    log_filename = f"agent_flow_{current_date}.log"
    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, log_filename),
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 5. 콘솔 핸들러 (터미널 출력)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# 6. 외부에서 편하게 쓸 함수 (선택 사항)
def log_agent_step(agent_name: str, message: str, data: dict = None):
    """
    에이전트 단계별 로깅 헬퍼 함수

    """
    log_msg = f"[{agent_name}] {message}"
    if data:
        # 데이터가 너무 길면 잘라서 출력
        data_str = str(data)
        if len(data_str) > 500:
            data_str = data_str[:500] + "...(truncated)"
        log_msg += f" | Data: {data_str}"

    logger.info(log_msg)