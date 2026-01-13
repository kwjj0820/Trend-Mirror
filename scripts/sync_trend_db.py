import pandas as pd
import sys
import os
import glob
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가 및 환경 변수 로드
sys.path.append(os.getcwd())
load_dotenv()

from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.embedding_service import EmbeddingService

class TrendLoader:
    def __init__(self):
        self.repo = ChromaDBRepository()
        self.embed_svc = EmbeddingService()

    def process_file(self, file_path):
        """단일 CSV 파일을 DB에 적재하는 핵심 로직"""
        file_name = os.path.basename(file_path)
        parts = file_name.replace(".csv", "").split("_")
        
        # 파일명 형식 체크 (category_sns_YYYYMMDD.csv)
        if len(parts) < 3:
            print(f"건너븜: {file_name} (형식이 올바르지 않습니다)")
            return

        category, sns, file_date_str = parts[0], parts[1], parts[2]
        
        try:
            target_date = datetime.strptime(file_date_str, "%Y%m%d")
            # 30일 이전 날짜 계산 (숫자형 비교를 위해 int 변환)
            cutoff_date_int = int((target_date - timedelta(days=30)).strftime("%Y%m%d"))
            current_date_int = int(file_date_str)
        except ValueError:
            print(f"에러: {file_name} 파일의 날짜 형식이 잘못되었습니다")
            return

        print(f"정보: [{category} | {sns}] 적재 시작 (기준일: {file_date_str})")

        # 1. 오래된 데이터 삭제 (현재 파일 날짜 기준 30일 이전)
        self.repo.collection.delete(where={"$and": [
            {"category": category},
            {"sns": sns},
            {"timestamp": {"$lt": cutoff_date_int}}
        ]})

        # 2. CSV 데이터 로드 및 컬럼 이름 맞춤
        df = pd.read_csv(file_path)
        col_map = {'Keyword': 'keyword', 'Frequency': 'count'}
        
        # 컬럼명 앞뒤 공백 제거 및 대소문자 매핑
        df.columns = [col.strip() for col in df.columns]
        df = df.rename(columns=col_map)

        if 'keyword' not in df.columns or 'count' not in df.columns:
            print(f"에러: {file_name}에서 필요한 컬럼(Keyword, Frequency)을 찾을 수 없습니다")
            return

        ids, documents, metadatas = [], [], []

        for _, row in df.iterrows():
            keyword = str(row['keyword']).strip()
            count = int(row['count'])
            
            # 빈도수가 3 이상인 데이터만 수집
            if count >= 3:
                doc_id = f"{sns}_{category}_{keyword}_{file_date_str}"
                doc_text = f"[{sns} - {category}] '{keyword}' 언급 빈도: {count}회 (기준일: {file_date_str})"
                
                ids.append(doc_id)
                documents.append(doc_text)
                metadatas.append({
                    "category": category,
                    "sns": sns,
                    "keyword": keyword,
                    "count": count,
                    "timestamp": current_date_int,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })

        # 3. DB 적재
        if ids:
            embeddings = self.embed_svc.create_embeddings(documents)
            self.repo.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            print(f"성공: {file_date_str} 기준 {len(ids)}개의 키워드를 저장했습니다")
        else:
            print(f"경고: {file_name}에 유효한 데이터(빈도수 3 이상)가 없습니다")

    def sync_folder(self, folder_path):
        """폴더 내의 모든 CSV 파일을 스캔하여 적재"""
        csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
        if not csv_files:
            print(f"정보: {folder_path} 폴더에 CSV 파일이 없습니다")
            return

        print(f"배치 작업: 총 {len(csv_files)}개의 파일을 찾았습니다. 동기화를 시작합니다.")
        for file in sorted(csv_files):
            self.process_file(file)
        print("완료: 모든 데이터 동기화 작업을 마쳤습니다.")

if __name__ == "__main__":
    loader = TrendLoader()
    if len(sys.argv) > 1:
        loader.process_file(sys.argv[1])
    else:
        # 기본적으로 scripts 폴더를 스캔하도록 설정
        loader.sync_folder("scripts")