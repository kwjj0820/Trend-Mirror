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
import pandas as pd
from typing import Dict, Any
import datetime # Import datetime
from app.core.logger import logger # Import logger

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
    logger.info(f"generate_report_pdf called with filename='{filename}'")
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
def youtube_crawling_tool(query: str, days: int = 7, pages: int = 5) -> "pd.DataFrame":
    """
    Performs YouTube trend data collection with an incremental caching strategy.
    It maintains a master cache for each query, fetches only new data since the last
    crawl, and returns the requested data subset as a pandas DataFrame.
    """
    from app.repository.client.youtube_client import collect_youtube_trend_candidates_df
    from datetime import datetime, timedelta, timezone

    logger.info(f"youtube_crawling_tool called with query='{query}', days='{days}', pages='{pages}'")

    out_dir = "downloads"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    safe_query = "".join(c for c in query if c.isalnum())
    
    master_cache_path = os.path.join(out_dir, f"youtube_{safe_query}_master_cache.csv")
    
    master_df = None
    newest_date_in_cache = None
    should_crawl = True
    crawl_params = {
        "query": query,
        "days": days,
        "pages": pages,
        "published_after_date": None
    }

    # 1. Load master cache if it exists
    if os.path.exists(master_cache_path):
        logger.info(f"Master cache found for query '{query}'. Loading cache...")
        master_df = pd.read_csv(master_cache_path)
        if not master_df.empty and 'published_at' in master_df.columns:
            master_df['published_at'] = pd.to_datetime(master_df['published_at'], errors='coerce').dt.tz_convert('UTC')
            newest_date_in_cache = master_df['published_at'].max()

    # 2. Determine if and how to crawl
    if newest_date_in_cache:
        # If cache is very recent (less than a day old), skip crawl
        if (datetime.now(timezone.utc) - newest_date_in_cache).days < 1:
            logger.info(f"Cache is very recent (from {newest_date_in_cache}). Skipping crawl.")
            should_crawl = False
        else:
            # Otherwise, perform incremental crawl from the last known date
            logger.info(f"Performing incremental crawl since {newest_date_in_cache}.")
            crawl_params["published_after_date"] = newest_date_in_cache.isoformat()
    else:
        logger.info(f"No master cache found. Performing full crawl for {days} days.")

    # 3. Crawl new data if necessary
    if should_crawl:
        logger.info(f"Crawling new data with params: {crawl_params}")
        new_df = collect_youtube_trend_candidates_df(**crawl_params)
        
        if not new_df.empty:
            logger.info(f"Crawl found {len(new_df)} new items.")
            # Ensure the 'published_at' column is in the correct format before merging
            new_df['published_at'] = pd.to_datetime(new_df['published_at'], errors='coerce').dt.tz_convert('UTC')
            
            # 4. Merge, deduplicate, and update master cache
            if master_df is not None:
                master_df = pd.concat([master_df, new_df]).drop_duplicates(subset=['video_id']).reset_index(drop=True)
            else:
                master_df = new_df
            
            logger.info(f"Master cache updated. Total items now: {len(master_df)}")
            logger.info(f"Updating master cache file: {master_cache_path}")
            master_df.to_csv(master_cache_path, index=False, encoding='utf-8-sig')
        else:
            logger.info("Crawl found 0 new items.")

    # 5. Filter and return the final DataFrame for the requested period
    if master_df is None or master_df.empty:
        logger.warning("No data found or collected for the query.")
        return pd.DataFrame()
        
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    result_df = master_df[master_df['published_at'] >= cutoff_date].copy()
    
    logger.info(f"youtube_crawling_tool: Returning DataFrame with shape {result_df.shape}.")
    logger.debug(f"--- DataFrame Head (youtube_crawling_tool) ---\n{result_df.head(3).to_string()}")
    
    return result_df


# @tool
# def naver_blog_crawling_tool(queries: list[str], main_query: str, days: int = 30) -> str:
#     """
#     주어진 쿼리 목록으로 네이버 블로그를 검색하여 트렌드 후보 데이터를 수집하고,
#     CSV 파일로 저장한 뒤 그 경로를 반환합니다.
#     파일명은 main_query를 기반으로 생성됩니다.
#     """
#     from app.repository.client.naver_blog_client import collect_naver_blog_candidates, filter_food_posts
#     import pandas as pd

#     logger.info(f"naver_blog_crawling_tool called with main_query='{main_query}', {len(queries)} queries, days='{days}'")

#     out_dir = "downloads"
#     pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    
#     # main_query를 기반으로 파일명 생성
#     safe_identifier = "".join(c for c in main_query if c.isalnum())
#     current_date = datetime.datetime.now().strftime("%Y%m%d")
#     file_path = f"{out_dir}/naver_blog_{safe_identifier}_{current_date}_{days}d_real_data.csv"

#     try:
#         # 네이버 블로그 데이터 수집
#         raw_posts = collect_naver_blog_candidates(queries=queries, days=days)
#         # '음식' 관련 포스트 필터링 (현재는 음식 관련으로 되어있으나, 추후 일반화 가능)
#         filtered_posts = filter_food_posts(raw_posts)
        
#         df = pd.DataFrame(filtered_posts)
#         if "post_date" in df.columns:
#             df["post_date"] = df["post_date"].astype(str)

#         df.to_csv(file_path, index=False, encoding='utf-8-sig')
#         return f"네이버 블로그 검색 결과가 다음 경로에 CSV 파일로 저장되었습니다: {file_path}"
#     except Exception as e:
#         logger.error(f"Error during naver blog crawling: {e}", exc_info=True)
#         return f"Error during naver blog crawling: {e}"


@tool
def run_keyword_extraction(input_df_json: str, base_export_path: str, slots: Dict[str, Any]) -> str:
    """
    DataFrame의 JSON 문자열을 키워드 추출 워크플로우로 그대로 전달합니다.
    입력:
    - input_df_json: pandas DataFrame을 JSON으로 변환한 문자열
    - base_export_path: 출력 파일명을 생성하기 위한 기본 경로
    - slots: 사용자 의도에서 추출된 슬롯 정보
    출력: 처리 결과 메시지 (성공 시 결과 파일 경로 포함)
    """
    logger.info(f"run_keyword_extraction: Received JSON string (len: {len(input_df_json)}). Passing to graph.")

    if not isinstance(input_df_json, str) or not input_df_json:
        return json.dumps({
            "status": "error",
            "message": "입력 데이터가 유효한 JSON 문자열이 아닙니다."
        }, ensure_ascii=False)

    # 그래프가 JSON 문자열을 직접 처리하도록 전달합니다.
    initial_state = {
        "input_df_json": input_df_json,
        "base_export_path": base_export_path,
        "slots": slots
    }
    final_state = keyword_extraction_graph.invoke(initial_state)

    if final_state.get("error"):
        return json.dumps({
            "status": "error",
            "message": final_state["error"]
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "frequencies_df_json": final_state.get("frequencies_df_json")
    }, ensure_ascii=False)