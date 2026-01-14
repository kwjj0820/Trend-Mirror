import os
import sys
from collections import defaultdict
from datetime import datetime

# 프로젝트 루트 경로 추가 (app 패키지 인식용)
sys.path.append(os.getcwd())

from app.repository.vector.vector_repo import ChromaDBRepository
from app.core.logger import logger

class TrendDataOrganizer:
    """
    Vector DB에 저장된 트렌드 데이터를 분석하고 
    사용자가 읽기 좋은 형태로 요약하는 클래스
    """
    def __init__(self):
        try:
            self.repo = ChromaDBRepository()
        except Exception as e:
            logger.error(f"❌ DB 연결 실패: {e}")
            raise

    def list_all_stored_data(self):
        """[진단용] 현재 DB에 저장된 모든 SNS와 카테고리 조합을 출력합니다."""
        print("\n🔍 [1. DB 내역 요약 조사]")
        results = self.repo.collection.get(include=["metadatas"])
        metas = results.get('metadatas', [])

        if not metas:
            print("   -> ❌ DB가 완전히 비어있습니다.")
            return

        existing_pairs = set()
        for m in metas:
            sns = m.get('sns', 'N/A')
            cat = m.get('category', 'N/A')
            existing_pairs.add(f"SNS: '{sns}' | 카테고리: '{cat}'")
        
        for pair in sorted(list(existing_pairs)):
            print(f"   -> {pair}")
        print("-" * 45)

    def organize_all_data(self):
        """
        필터 없이 DB의 모든 데이터를 가져와서 SNS/카테고리별로 분류하여 리포트를 생성합니다.
        """
        print("\n📊 [2. DB 전체 데이터 리포트 생성]")
        
        # 1. DB의 모든 데이터 가져오기 (where 필터 제거)
        results = self.repo.collection.get(include=["metadatas"])
        metadatas = results.get('metadatas', [])

        if not metadatas:
            return "❌ DB에 표시할 데이터가 없습니다."

        # 2. 계층 구조로 그룹화: SNS -> 카테고리 -> 날짜
        structured_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        for meta in metadatas:
            sns = meta.get('sns', 'unknown').upper()
            cat = meta.get('category', 'unknown')
            ts = meta.get('timestamp', 0)
            structured_data[sns][cat][ts].append(meta)

        # 3. 결과 문자열 생성
        output = []
        for sns, categories in structured_data.items():
            output.append(f"\n🚀 SNS: {sns}")
            output.append("=" * 50)
            
            for cat, dates in categories.items():
                output.append(f"📁 카테고리: {cat}")
                output.append("-" * 30)
                
                # 날짜 최신순 정렬
                sorted_dates = sorted(dates.keys(), reverse=True)
                for date in sorted_dates:
                    day_data = sorted(dates[date], key=lambda x: x.get('count', 0), reverse=True)
                    ds = str(date)
                    formatted_date = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}" if len(ds) == 8 else ds
                    
                    output.append(f"  📅 {formatted_date} 트렌드")
                    
                    # 상위 키워드 출력
                    keywords_line = []
                    for i, item in enumerate(day_data[:10], 1): # 최대 10개까지
                        keywords_line.append(f"{item.get('keyword')}({item.get('count')}회)")
                    
                    output.append(f"    ✨ TOP 키워드: {', '.join(keywords_line)}")
                output.append("") # 카테고리 간 간격
        
        return "\n".join(output)

if __name__ == "__main__":
    organizer = TrendDataOrganizer()
    
    # 1단계: 간단한 요약 목록 먼저 확인
    organizer.list_all_stored_data()
    
    # 2단계: DB에 있는 모든 데이터를 리포트 형태로 출력
    print(organizer.organize_all_data())