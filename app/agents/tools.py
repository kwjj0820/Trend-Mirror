# app/agents/tools.py
import os
import uuid
import pathlib
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from langchain.tools import tool
from dotenv import load_dotenv
import json

from app.agents.subgraphs.keyword_extract import keyword_extraction_graph



if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()


@tool
def download_file(url: str, out_dir: str = "downloads") -> str:
    """URL에서 파일을 다운로드하여 로컬 경로를 반환합니다."""
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    local_name = url.split("/")[-1].split("?")[0]
    if not local_name:
        local_name = f"file_{uuid.uuid4().hex}.pdf"

    # 확장자 보정 등 노트북 로직 반영
    if not local_name.lower().endswith(".pdf"):
        pass

    path = str(pathlib.Path(out_dir) / local_name)

    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
        return path
    except Exception as e:
        return f"Error downloading {url}: {e}"


@tool
def parse_pdf_to_markdown(pdf_path: str) -> str:
    """Upstage Layout Analysis API를 사용하여 PDF를 마크다운으로 변환합니다."""
    api_key = os.getenv("UPSTAGE_API_KEY")
    base_url = os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1").rstrip("/")
    # 노트북의 doc parse 모델 환경변수 사용
    model = os.getenv("UPSTAGE_DOC_PARSE_MODEL", "document-parse")

    url = f"{base_url}/document-digitization"  # or /document-parse check notebook
    # 노트북 코드상 document-digitization 사용

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with open(pdf_path, "rb") as f:
            files = {"document": f}
            data = {"model": model, "output_formats": '["markdown"]', "ocr": "auto"}
            r = requests.post(url, headers=headers, files=files, data=data, timeout=240)
        r.raise_for_status()
        j = r.json()
        # 노트북의 결과 추출 로직
        md = j.get("markdown") or (j.get("content") or {}).get("markdown") or (j.get("output") or {}).get("markdown")
        if not md:
            return "Error: Markdown not found in response."
        return md
    except Exception as e:
        return f"Error parsing PDF: {e}"


@tool
def generate_report_pdf(content: str, filename: str = "trendmirror_report.pdf") -> str:
    """분석 결과를 PDF 파일로 생성합니다. 한글 출력을 위해 나눔고딕 폰트를 사용합니다."""
    out_dir = "reports"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = f"{out_dir}/{filename}"

    # 실제 파일 경로 지정
    font_path_regular = "resources/fonts/NanumGothic-Regular.ttf"
    font_path_bold = "resources/fonts/NanumGothic-Bold.ttf"
    
    font_name_regular = "NanumGothic-Regular"
    font_name_bold = "NanumGothic-Bold"

    try:
        # 폰트 파일 존재 여부 확인
        regular_exists = os.path.exists(font_path_regular)
        bold_exists = os.path.exists(font_path_bold)

        if regular_exists and bold_exists:
            # 두 폰트 모두 등록
            pdfmetrics.registerFont(TTFont(font_name_regular, font_path_regular))
            pdfmetrics.registerFont(TTFont(font_name_bold, font_path_bold))
            title_font = font_name_bold
            body_font = font_name_regular
        elif regular_exists:
            # 레귤러 폰트만 존재할 경우, Bold 대신 사용
            pdfmetrics.registerFont(TTFont(font_name_regular, font_path_regular))
            title_font = font_name_regular
            body_font = font_name_regular
            print(f"⚠️ 경고: Bold 폰트를 찾을 수 없어 일반 폰트로 대체합니다: '{font_path_bold}'")
        else:
            # 폰트 파일이 없으면 경고 후 기본 폰트 사용
            print(f"⚠️ 경고: 한글 폰트 파일을 찾을 수 없습니다. PDF 한글이 깨질 수 있습니다. 경로: '{font_path_regular}'")
            title_font = "Helvetica-Bold"
            body_font = "Helvetica"

        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        c.setFont(title_font, 16)
        c.drawString(50, height - 60, "TrendMirror Report")

        c.setFont(body_font, 11)
        y = height - 90
        for line in content.splitlines():
            if y < 60:
                c.showPage()
                c.setFont(body_font, 11)
                y = height - 60
            c.drawString(50, y, line[:100])
            y -= 16
        c.save()
        return path
    except Exception as e:
        return f"Error generating PDF: {e}"


@tool
def youtube_crawling_tool(query: str, max_results: int = 10) -> str:
    """
    [가상 도구] 유튜브 검색을 시뮬레이션하고 결과를 CSV 파일로 저장합니다.
    실제 구현에서는 유튜브 API를 사용하여 데이터를 크롤링해야 합니다.
    """
    import pandas as pd
    out_dir = "downloads"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    file_path = f"{out_dir}/youtube_dummy_data.csv"

    # 테스트를 위한 가상 데이터 생성
    dummy_data = {
        'title': [
            '요즘 난리난 신상 디저트 탕후루보다 맛있다고? ASMR',
            'SUB) 꽁꽁 얼어붙은 한강 위로 고양이가 걸어다닙니다',
            '요아정(요거트아이스크림의정석) 처음 먹어본 외국인 반응',
            '도쿄 여행 브이로그, 시부야 스카이와 두바이 쫀득 쿠키 먹방',
            'MZ 신조어 테스트, 당신은 얼마나 알고 있나요?',
            '누가 내 머리에 똥쌌어 챌린지 ㅋㅋㅋ',
            '2024년 여름 패션 하울! 실패없는 BEST 아이템 추천',
            'K-직장인 점심시간 브이로그 (feat.압구정 핫플)',
            '고든램지 버거 솔직리뷰! 가격이 정말..',
            '이 조합 미쳤다.. 불닭볶음면과 한우 조합, 이건 못참지'
        ],
        'url': [f'https://www.youtube.com/watch?v=dummy{i}' for i in range(10)]
    }
    df = pd.DataFrame(dummy_data)

    # 항상 전체 더미 데이터를 사용하도록 필터링 로직 제거
    # if query:
    #     df = df[df['title'].str.contains(query, case=False)]
    df = df.head(max_results)

    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    return f"유튜브 검색 결과가 다음 경로에 CSV 파일로 저장되었습니다: {file_path}"


@tool
def run_keyword_extraction(csv_path: str) -> str:
    """
    주어진 CSV 파일 경로에 대해 키워드 추출 워크플로우를 실행합니다.
    입력: CSV 파일 경로 (예: 'downloads/youtube_dummy_data.csv')
    출력: 처리 결과 메시지 (성공 시 결과 파일 경로 포함)
    """
    if not isinstance(csv_path, str) or not csv_path.endswith('.csv'):
        return "오류: 유효한 CSV 파일 경로를 입력해야 합니다. (예: 'downloads/youtube_dummy_data.csv')"

    # 정규 표현식으로 경로 추출 (Tool에서 받은 문자열에 설명이 포함될 경우)
    import re
    match = re.search(r"['\"]?([a-zA-Z0-9_/\.-]+\.csv)['\"]?", csv_path)
    if not match:
        return f"오류: '{csv_path}'에서 유효한 CSV 파일 경로를 찾을 수 없습니다."

    cleaned_path = match.group(1)

    if not os.path.exists(cleaned_path):
        return f"오류: 파일이 존재하지 않습니다: {cleaned_path}"

    # 컴파일된 그래프를 직접 호출합니다.
    initial_state = {"csv_path": cleaned_path}
    final_state = keyword_extraction_graph.invoke(initial_state)

    if final_state.get("error"):
        return json.dumps({
            "status": "error",
            "message": final_state["error"]
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "input_path": cleaned_path,
        "output_path": final_state.get("output_path")
    }, ensure_ascii=False)