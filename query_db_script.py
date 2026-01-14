
import os
from dotenv import load_dotenv
from app.core.db import ChromaDBConnection
from app.repository.client.llm_client import UpstageClient
from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.embedding_service import EmbeddingService
from app.service.vector_service import VectorService
from app.core.logger import logger

# .env 파일 로드
load_dotenv()

# 로거 설정 (선택 사항이지만, 스크립트 실행 시 로그를 볼 수 있도록)
logger.setLevel("INFO")

def query_vector_db():
    try:
        # 1. 의존성 초기화
        db_connection = ChromaDBConnection()
        llm_client = UpstageClient()
        
        embedding_service = EmbeddingService()
        vector_repository = ChromaDBRepository()
        vector_service = VectorService(
            vector_repository=vector_repository,
            embedding_service=embedding_service
        )

        print("\n--- Vector DB Query Examples ---")

        # 예시 1: 일반 검색 (semantic search)
        query_text = "요즘 유행하는 카페 메뉴는 뭐야?"
        print(f"\nSearching for: '{query_text}'")
        search_results = vector_service.search(query=query_text, n_results=3)
        if search_results:
            for i, result in enumerate(search_results):
                print(f"  Result {i+1}:")
                print(f"    Text: {result.get('text')}")
                print(f"    Meta: {result.get('meta')}")
                print(f"    Distance: {result.get('distance')}")
        else:
            print("  No search results found.")

        # 예시 2: 키워드 빈도수 조회 (metadata-only retrieval)
        category = "음식" # 예시 카테고리
        sns = "youtube"   # 예시 SNS
        print(f"\nGetting keyword frequencies for Category='{category}', SNS='{sns}'")
        freq_results = vector_service.get_keyword_frequencies(category=category, sns=sns, n_results=5)
        if freq_results:
            for i, result in enumerate(freq_results):
                print(f"  Top Keyword {i+1}: {result.get('keyword')} (Frequency: {result.get('frequency')})")
        else:
            print(f"  No keyword frequencies found for category='{category}', sns='{sns}'.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    query_vector_db()
