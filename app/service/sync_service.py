import pandas as pd
import os
from datetime import datetime, timedelta
from app.service.vector_service import VectorService
from app.core.logger import logger

class SyncService:
    """
    특정 형식의 트렌드 분석 CSV 파일을 Vector DB와 동기화하는 서비스
    - 허용 파일명: (SNS)_(카테고리)_(날짜)_7d_real_data_keyword_frequencies.csv
    - 정책: 30일 보관, 빈도수 3 이상 적재, Rank 제외
    """
    
    # 허용할 파일명의 접미사 (Suffix) 정의
    REQUIRED_SUFFIX = "_30d_real_data_keyword_frequencies.csv"

    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service

    def sync_csv_to_db(self, file_path: str):
        """지정한 파일의 이름 형식을 검증하고 데이터를 DB에 적재합니다."""
        base_name = os.path.basename(file_path)

        # 1. 파일명 뒷부분(Suffix) 검증
        if not base_name.endswith(self.REQUIRED_SUFFIX):
            logger.error(f"❌ 건너븜: 파일 형식이 일치하지 않습니다. ({base_name})")
            logger.info(f"💡 필수 형식: [SNS]_[카테고리]_[날짜]{self.REQUIRED_SUFFIX}")
            return

        # 2. 파일명에서 정보 추출
        # 뒷부분 접미사를 제거한 후 '_'로 분리
        prefix = base_name.replace(self.REQUIRED_SUFFIX, "")
        parts = prefix.split("_")
        
        if len(parts) < 3:
            logger.error(f"❌ 파일명 정보 부족: {base_name} (SNS, 카테고리, 날짜 정보가 필요합니다)")
            return

        sns_name = parts[0]
        category = parts[1]
        file_date_str = parts[2]

        try:
            target_date = datetime.strptime(file_date_str, "%Y%m%d")
            # 30일 보관 정책을 위한 기준일 계산
            cutoff_date_int = int((target_date - timedelta(days=30)).strftime("%Y%m%d"))
            current_date_int = int(file_date_str)
        except ValueError:
            logger.error(f"❌ 날짜 형식 오류: {file_date_str} (YYYYMMDD 형식이 아닙니다)")
            return

        logger.info(f"🔄 [{sns_name} | {category}] 검증 완료. 데이터 분석 시작 (기준일: {file_date_str})")

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
            logger.debug(f"ℹ️ DB 정리 중 참고사항: {e}")

        # 4. CSV 데이터 로드 및 전처리
        try:
            # 소문자 keyword, frequency 컬럼 대응
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            df.columns = [col.strip().lower() for col in df.columns]
        except Exception as e:
            logger.error(f"❌ 파일 읽기 실패: {e}")
            return

        if 'keyword' not in df.columns or 'frequency' not in df.columns:
            logger.error(f"❌ 필수 컬럼(keyword, frequency) 누락. 현재 컬럼: {list(df.columns)}")
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
            logger.info(f"✅ 동기화 완료: {len(ids)}개의 유효 키워드가 DB에 저장되었습니다.")
        else:
            logger.warning(f"⚠️ {base_name}에 빈도수 3 이상의 적재할 데이터가 없습니다.")