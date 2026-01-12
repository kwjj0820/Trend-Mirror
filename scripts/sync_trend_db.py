import pandas as pd
import datetime
import sys
import os

sys.path.append(os.getcwd())

from app.service.vector_service import VectorService
from app.service.embedding_service import EmbeddingService
from app.repository.vector.vector_repo import ChromaDBRepository

def sync_data(file_path: str):
    """
    파일명(예: food_youtube_analysis.csv)을 파싱하여 
    해당 카테고리와 SNS의 기존 DB 데이터를 삭제한 후 최신화합니다.
    """
    base_name = os.path.basename(file_path)
    parts = base_name.split('_')
    
    if len(parts) < 3:
        print(f"파일명 형식 오류: {base_name} (필수 형식: 카테고리_SNS_analysis.csv)")
        return

    category = parts[0]
    sns_name = parts[1]

    repo = ChromaDBRepository()
    embed_svc = EmbeddingService()
    vector_service = VectorService(repo, embed_svc)

    print(f"🔄 [{category} | {sns_name}] 트렌드 데이터를 최신화합니다...")
    try:
        repo.collection.delete(where={"$and": [{"category": category}, {"sns": sns_name}]})
    except Exception as e:
        print(f"ℹ️ 이전 데이터가 존재하지 않거나 무시되었습니다: {e}")


    df = pd.read_csv(file_path)
    documents, metadatas, ids = [], [], []
    save_time = datetime.datetime.now().isoformat()

    for _, row in df.iterrows():
        kw = row['Keyword']
        
        doc_text = f"[{sns_name} - {category}] 트렌드 키워드: {kw} (언급 빈도: {row['Frequency']}회, 현재 순위: {row['Rank']}위)"
        documents.append(doc_text)
        
        metadatas.append({
            "sns": sns_name,
            "category": category,
            "keyword": kw,
            "rank": int(row['Rank']),
            "frequency": int(row['Frequency']),
            "updated_at": save_time
        })
        
        ids.append(f"{sns_name}_{category}_{kw}")

    vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    print(f"✅ 동기화 완료: {len(documents)}개의 최신 트렌드 지식이 적재되었습니다.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sync_data(sys.argv[1])
    else:
        print("사용법: python scripts/sync_trend_db.py [CSV_파일_경로]")