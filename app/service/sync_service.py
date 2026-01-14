# app/service/sync_service.py
import pandas as pd
import datetime
import os
from app.service.vector_service import VectorService
from app.core.logger import logger

class SyncService:
    """
    CSV 파일의 내용을 Vector DB와 동기화하는 비즈니스 로직을 담당하는 서비스
    """
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service

    def sync_csv_to_db(self, file_path: str):
        """
        CSV 파일의 내용을 분석하여 Vector DB에 최신화(삭제 후 추가)합니다.
        
        Args:
            file_path (str): 분석할 CSV 파일 경로.
        """
        base_name = os.path.basename(file_path)
        parts = base_name.split('_')
        
        if len(parts) < 3:
            logger.error(f"파일명 형식 오류: {base_name} (필수 형식: 카테고리_SNS_... .csv)")
            return

        category = parts[0]
        sns_name = parts[1]

        logger.info(f"🔄 [{category} | {sns_name}] 트렌드 데이터를 DB에 동기화합니다...")
        try:
            self.vector_service.delete_by_metadata(filter={"$and": [{"category": category}, {"sns": sns_name}]})
            logger.info(f"기존 '{category}' 카테고리, '{sns_name}' SNS 데이터 삭제 완료.")
        except Exception as e:
            logger.warning(f"ℹ️ 이전 데이터 삭제 중 오류가 발생했거나 데이터가 존재하지 않습니다: {e}")

        df = pd.read_csv(file_path)
        documents, metadatas, ids = [], [], []
        save_time = datetime.datetime.now().isoformat()

        df_filtered = df[df['trend_keywords'].notna() & (df['trend_keywords'] != '')]

        for _, row in df_filtered.iterrows():
            keywords_str = row['trend_keywords']
            # 쉼표로 구분된 키워드를 분리하고, 각 키워드의 앞뒤 공백을 제거합니다.
            keywords_list = [k.strip() for k in keywords_str.split(',') if k.strip()]

            # 원본 행의 모든 데이터를 dict 형태로 변환
            original_data = row.to_dict()

            for kw in keywords_list:
                doc_text = f"[{sns_name} - {category}] '{row['title']}' 영상에서 언급된 트렌드 키워드: {kw}"
                documents.append(doc_text)
                
                metadatas.append({
                    "sns": sns_name,
                    "category": category,
                    "keyword": kw,  # 개별 키워드
                    "updated_at": save_time,
                    **original_data  # 원본 행의 모든 데이터를 메타데이터에 추가
                })
                
                # ID 생성 시 키워드를 포함하여 고유성 보장
                unique_id_part = row.get('url', row['title'])
                ids.append(f"{sns_name}_{category}_{unique_id_part}_{kw}")

        if not documents:
            logger.info("ℹ️ 동기화할 새로운 트렌드 키워드가 없습니다. DB 동기화를 건너뜁니다.")
            return
        
        self.vector_service.add_documents(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"✅ 동기화 완료: {len(documents)}개의 새로운 트렌드 지식이 DB에 저장되었습니다.")