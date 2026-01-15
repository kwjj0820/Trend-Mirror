import re
import pandas as pd
import os
from datetime import datetime, timedelta
from app.service.vector_service import VectorService
from app.core.logger import logger

import re
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from app.service.vector_service import VectorService
from app.core.logger import logger

class SyncService:
    """
    특정 형식의 트렌드 분석 데이터를 Vector DB와 동기화하는 서비스
    - 정책: N일 보관, 빈도수 3 이상 적재
    """
    
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service

    def sync_dataframe_to_db(self, df: pd.DataFrame, slots: Dict[str, Any], sns_name: str = "youtube"):
        """DataFrame과 slots 정보를 기반으로 데이터를 DB에 적재합니다."""
        
        # 1. slots에서 정보 추출
        category = slots.get("search_query", "unknown")
        period_days = slots.get("period_days", 7)
        current_date = datetime.now()
        current_date_str = current_date.strftime("%Y%m%d")
        current_date_int = int(current_date_str)
        cutoff_date_int = int((current_date - timedelta(days=period_days)).strftime("%Y%m%d"))

        logger.info(f"[SYNC] [{sns_name} | {category}] Syncing DataFrame to DB for date: {current_date_str}")

        # 2. DB 정리 (오래된 데이터 및 오늘 데이터 삭제)
        try:
            self.vector_service.delete_by_metadata(filter={
                "$and": [{"sns": sns_name}, {"category": category}, {"timestamp": {"$lt": cutoff_date_int}}]
            })
            self.vector_service.delete_by_metadata(filter={
                "$and": [{"sns": sns_name}, {"category": category}, {"timestamp": current_date_int}]
            })
        except Exception as e:
            logger.debug(f"[INFO] Note during DB cleanup: {e}")

        # 3. 데이터 적재 준비 (빈도수 3 이상만)
        documents, metadatas, ids = [], [], []
        save_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        for _, row in df.iterrows():
            kw = str(row['keyword']).strip()
            count = int(row['frequency'])
            
            if count >= 3:
                doc_text = f"[{sns_name} - {category}] '{kw}' 언급 빈도: {count}회 (기준일: {current_date_str})"
                documents.append(doc_text)
                metadatas.append({
                    "sns": sns_name,
                    "category": category,
                    "keyword": kw,
                    "count": count,
                    "timestamp": current_date_int,
                    "updated_at": save_time
                })
                ids.append(f"{sns_name}_{category}_{current_date_int}_{kw}")

        # 4. 최종 Vector DB 적재
        if ids:
            self.vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            logger.info(f"[SUCCESS] Sync complete: {len(ids)} valid keywords saved to DB.")
            
            df_synced = pd.DataFrame(metadatas)[['keyword', 'count']].rename(columns={'count': 'frequency'})
            df_synced = df_synced.sort_values(by='frequency', ascending=False)
            logger.info(f"--- Top 5 Synced Keywords ---\n{df_synced.head(5).to_string(index=False)}")
        else:
            logger.warning(f"[WARNING] No data to load in DataFrame with frequency >= 3.")
    
    def sync_csv_to_db(self, file_path: str):
        """지정한 파일의 이름 형식을 검증하고 데이터를 DB에 적재합니다."""
        base_name = os.path.basename(file_path)

        # 1. Regex를 이용한 새로운 파일명 검증
        pattern = re.compile(r"^(?P<sns>\w+)_(?P<category>.+)_(?P<date>\d{8})_(?P<days>\d+)d_real_data_keyword_frequencies\.csv$")
        match = pattern.match(base_name)

        if not match:
            logger.error(f"[SKIP] Invalid file format or structure: {base_name}")
            logger.info("[INFO] Required format: [SNS]_[CATEGORY]_[DATE]_[DAYS]d_real_data_keyword_frequencies.csv")
            return

        # 2. Regex 그룹에서 정보 추출
        file_info = match.groupdict()
        sns_name = file_info['sns']
        category = file_info['category']
        file_date_str = file_info['date']
        days_in_file = int(file_info['days'])

        try:
            target_date = datetime.strptime(file_date_str, "%Y%m%d")
            # 파일명에서 추출한 days를 사용하여 기준일 계산
            cutoff_date_int = int((target_date - timedelta(days=days_in_file)).strftime("%Y%m%d"))
            current_date_int = int(file_date_str)
        except ValueError:
            logger.error(f"[ERROR] Invalid date format in filename: {file_date_str} (must be YYYYMMDD)")
            return

        logger.info(f"[SYNC] [{sns_name} | {category}] Validation complete. Starting data analysis for date: {file_date_str}")

        # 3. DB 정리 (30일 초과 데이터 삭제 및 동일 날짜 데이터 교체)
        try:
            # 오래된 데이터 삭제 ($lt: Less Than)
            self.vector_service.delete_by_metadata(filter={
                "$and": [
                    {"sns": sns_name},
                    {"category": category},
                    {"timestamp": {"$lt": cutoff_date_int}}
                ]
            })
            # 중복 방지를 위해 오늘 날짜 데이터 삭제
            self.vector_service.delete_by_metadata(filter={
                "$and": [
                    {"sns": sns_name},
                    {"category": category},
                    {"timestamp": current_date_int}
                ]
            })
        except Exception as e:
            logger.debug(f"[INFO] Note during DB cleanup: {e}")

        # 4. CSV 데이터 로드 및 전처리
        try:
            # 소문자 keyword, frequency 컬럼 대응
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            df.columns = [col.strip().lower() for col in df.columns]
        except Exception as e:
            logger.error(f"[ERROR] Failed to read file: {e}")
            return

        if 'keyword' not in df.columns or 'frequency' not in df.columns:
            logger.error(f"[ERROR] Missing required columns (keyword, frequency). Current columns: {list(df.columns)}")
            return

        # 5. 데이터 적재 준비 (빈도수 3 이상만)
        documents, metadatas, ids = [], [], []
        save_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        for _, row in df.iterrows():
            kw = str(row['keyword']).strip()
            count = int(row['frequency'])
            
            if count >= 3:
                # 자연어 문서 생성 (Rank 제외)
                doc_text = f"[{sns_name} - {category}] '{kw}' 언급 빈도: {count}회 (기준일: {file_date_str})"
                
                documents.append(doc_text)
                metadatas.append({
                    "sns": sns_name,
                    "category": category,
                    "keyword": kw,
                    "count": count,
                    "timestamp": current_date_int,
                    "updated_at": save_time
                })
                # 고유 ID 생성 (SNS_카테고리_날짜_키워드)
                ids.append(f"{sns_name}_{category}_{current_date_int}_{kw}")

        # 6. 최종 Vector DB 적재
        if ids:
            self.vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            logger.info(f"[SUCCESS] Sync complete: {len(ids)} valid keywords saved to DB.")

            # 저장된 데이터의 상위 5개를 로깅하기 위한 로직 추가
            df_synced = pd.DataFrame(metadatas)[['keyword', 'count']].rename(columns={'count': 'frequency'})
            df_synced = df_synced.sort_values(by='frequency', ascending=False)
            logger.info(f"--- Top 5 Synced Keywords ---\n{df_synced.head(5).to_string(index=False)}")
        else:
            logger.warning(f"[WARNING] No data to load in {base_name} with frequency >= 3.")