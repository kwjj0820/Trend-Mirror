import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService
from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.sync_service import SyncService # 우리가 만든 서비스를 호출
from app.core.logger import logger

def main():
    """
    명령행 인자로 받은 파일을 SyncService를 통해 DB에 적재합니다.
    """
    if len(sys.argv) < 2:
        print("❌ 사용법: python scripts/sync_trend_db.py [CSV_파일_경로]")
        print("예시: python scripts/sync_trend_db.py downloads/youtube_디저트_20260113_7d_real_data_keyword_frequencies.csv")
        return

    file_path = sys.argv[1]

    # 1. 의존성 준비
    try:
        repo = ChromaDBRepository()
        embed_svc = EmbeddingService()
        vector_svc = VectorService(repo, embed_svc)
        
        # 2. 통합된 SyncService 호출
        sync_svc = SyncService(vector_svc)
        
        # 3. 데이터 동기화 실행
        # 이 안에서 파일명 검증(_keyword_frequencies.csv), 순서 파싱, 30일 보관 로직이 실행됩니다.
        sync_svc.sync_csv_to_db(file_path)
        
    except Exception as e:
        logger.error(f"💥 실행 중 치명적 오류 발생: {e}")

if __name__ == "__main__":
    main()