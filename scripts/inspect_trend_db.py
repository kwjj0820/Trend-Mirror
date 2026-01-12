import sys
import os
from dotenv import load_dotenv

# 1. 환경 설정 및 경로 로드
sys.path.append(os.getcwd())
load_dotenv()

from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService

def inspect():
    # 2. 서비스 초기화
    repo = ChromaDBRepository()
    embed_svc = EmbeddingService()
    vector_service = VectorService(repo, embed_svc)

    # 3. 전체 데이터 통계 확인
    total_count = repo.collection.count()
    print(f"\n📊 [DB 통계] 현재 적재된 총 데이터 수: {total_count}개")

    if total_count == 0:
        print("DB가 비어 있습니다. 로더(Loader)를 먼저 실행해 주세요.")
        return

    # 4. 특정 카테고리(음식) 데이터 샘플 확인
    print("\n🔍 [데이터 검증] 'food' 카테고리 샘플 데이터 (최대 3개):")
    samples = repo.collection.get(
        where={"category": "food"},
        limit=3
    )

    for i in range(len(samples['ids'])):
        print(f"📍 ID: {samples['ids'][i]}")
        print(f"   내용: {samples['documents'][i]}")
        print(f"   메타데이터: {samples['metadatas'][i]}")
        print("-" * 40)

    # 5. 검색 품질 테스트 (RAG 성능 확인)
    test_query = "유튜브에서 요즘 유행하는 디저트나 간식 추천해줘"
    print(f"\n🔎 [검색 테스트] 질문: '{test_query}'")
    
    results = vector_service.search(test_query, n_results=3)
    
    for i, res in enumerate(results):
        print(f"{i+1}위. {res['text']}")
        print(f"   유사도 거리(Distance): {res['distance']:.4f}")

if __name__ == "__main__":
    inspect()