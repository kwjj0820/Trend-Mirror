import sys
import os
from dotenv import load_dotenv

# 1. 환경 설정 및 프로젝트 경로 로드
sys.path.append(os.getcwd())
load_dotenv()

from app.repository.vector.vector_repo import ChromaDBRepository

def check_db_contents():
    # 2. 레포지토리 초기화 (단순 조회를 위해 Repo만 사용)
    repo = ChromaDBRepository()

    print("\n" + "="*50)
    print("📋 [Trend Mirror] DB 적재 데이터 상세 점검")
    print("="*50)

    # 3. 전체 데이터 통계 확인
    total_count = repo.collection.count()
    print(f"📊 현재 DB에 저장된 총 데이터 수: {total_count}개")

    if total_count == 0:
        print("❌ DB가 비어 있습니다. 로더 스크립트를 먼저 실행하세요.")
        return

    # 4. 'food' 카테고리 데이터가 잘 들어갔는지 샘플 확인
    print("\n🔍 [카테고리별 샘플 확인] 'food' 카테고리 (최대 5개):")
    print("-" * 50)
    
    # get() 메소드를 사용하여 실제 저장된 데이터를 필터링해서 가져옴
    samples = repo.collection.get(
        where={"category": "food"},
        limit=5
    )

    if not samples['ids']:
        print("ℹ️ 'food' 카테고리로 저장된 데이터가 없습니다.")
    else:
        for i in range(len(samples['ids'])):
            print(f"📍 ID: {samples['ids'][i]}")
            print(f"   내용: {samples['documents'][i]}")
            print(f"   메타데이터: {samples['metadatas'][i]}")
            print("-" * 50)

    # 5. SNS 채널 분포 확인 (데이터가 섞여있는지 확인용)
    metas = repo.collection.get(include=['metadatas'])['metadatas']
    sns_list = set([m.get('sns') for m in metas if m.get('sns')])
    print(f"\n📱 현재 DB에 포함된 SNS 채널 목록: {sns_list}")
    print("="*50)

if __name__ == "__main__":
    check_db_contents()