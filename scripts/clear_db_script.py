import sys
import os

# Add the project root to the Python path to resolve module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from app.core.db import ChromaDBConnection
from app.core.logger import logger

# .env 파일 로드
load_dotenv()

# 로거 설정
logger.setLevel("INFO")

def reset_chroma_db():
    """
    Resets the entire ChromaDB database, deleting all collections and data.
    """
    logger.info("--- Resetting ChromaDB Database ---")
    try:
        db_connection = ChromaDBConnection()
        
        # 데이터베이스 전체 리셋
        db_connection.client.reset()
        
        logger.info("Successfully reset the entire ChromaDB database.")
        logger.info("All collections and data have been deleted.")

    except Exception as e:
        logger.error(f"Error resetting ChromaDB database: {e}", exc_info=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 사용자에게 초기화 여부를 다시 한번 확인
    confirm = input("Are you sure you want to reset the entire ChromaDB database? This will delete all data. (y/n): ")
    if confirm.lower() == 'y':
        reset_chroma_db()
    else:
        logger.info("Database reset cancelled by user.")
