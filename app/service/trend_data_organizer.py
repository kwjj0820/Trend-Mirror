import os
import sys
from datetime import datetime
from collections import defaultdict

# 프로젝트 루트 경로 추가 (app 패키지를 찾기 위함)
sys.path.append(os.getcwd())

from app.repository.vector.vector_repo import ChromaDBRepository

class TrendDataOrganizer:
    def __init__(self):
        self.repo = ChromaDBRepository()

    def organize_data(self, category: str, sns: str):
        """
        DB에서 특정 카테고리와 SNS의 데이터를 가져와 날짜별로 요약합니다.
        """
        # 1. DB 데이터 조회
        results = self.repo.collection.get(
            where={"$and": [
                {"category": category},
                {"sns": sns}
            ]},
            include=["metadatas"]
        )

        if not results['metadatas']:
            return f"정보: {category} 및 {sns}에 대한 저장된 데이터가 없습니다."

        # 2. 날짜(timestamp)별로 데이터 그룹화
        daily_groups = defaultdict(list)
        for meta in results['metadatas']:
            date_key = meta.get('timestamp')
            
            # [조치 1] 날짜 정보가 없는(None) 데이터는 에러 방지를 위해 제외합니다.
            if date_key is None:
                continue
                
            daily_groups[date_key].append(meta)

        # 유효한 날짜 그룹이 하나도 없는 경우 처리
        if not daily_groups:
            return "정보: 분석 가능한 유효한 날짜 데이터가 DB에 존재하지 않습니다."

        # 3. 날짜순 정렬 (최신 날짜가 위로 오도록 역순 정렬)
        # 이제 모든 key가 숫자(int)이므로 TypeError 없이 정렬됩니다.
        sorted_dates = sorted(daily_groups.keys(), reverse=True)
        
        output = []
        output.append(f"분석 대상: {category} 트렌드 (채널: {sns})")
        output.append(f"보관 기간: 최근 {len(sorted_dates)}일치 데이터")
        output.append("-" * 30)

        for date in sorted_dates:
            # 해당 날짜의 데이터를 빈도수(count) 기준 내림차순 정렬
            day_data = sorted(daily_groups[date], key=lambda x: x.get('count', 0), reverse=True)
            
            # 날짜 형식 변환 (예: 20260112 -> 2026년 01월 12일)
            date_str = str(date)
            try:
                formatted_date = f"{date_str[:4]}년 {date_str[4:6]}월 {date_str[6:]}일"
            except IndexError:
                formatted_date = f"알 수 없는 날짜({date_str})"
            
            output.append(f"기준일: {formatted_date}")

            # 상위 5개 키워드 (자연어 형식 상세 요약)
            top_5 = day_data[:5]
            others = day_data[5:]

            output.append("주요 트렌드 상위 5개:")
            for i, item in enumerate(top_5, 1):
                keyword = item.get('keyword', '알 수 없음')
                count = item.get('count', 0)
                output.append(f"  {i}위: '{keyword}' 키워드가 {count}회 언급되었습니다.")

            # 나머지 키워드 (가볍게 리스트업)
            if others:
                other_list = [f"{item.get('keyword')}({item.get('count')}회)" for item in others]
                output.append("기타 언급 키워드:")
                output.append("  " + ", ".join(other_list))
            
            output.append("-" * 30)

        return "\n".join(output)

if __name__ == "__main__":
    # 터미널 테스트 실행용
    organizer = TrendDataOrganizer()
    # 예시로 food 카테고리의 youtube 데이터를 출력
    summary = organizer.organize_data("food", "youtube")
    print(summary)