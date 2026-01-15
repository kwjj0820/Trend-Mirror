import os
import uuid
import pathlib
import requests
import json
import datetime
import pandas as pd
from typing import Dict, Any
from dotenv import load_dotenv

# PDF 생성 고도화 (Platypus 사용)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

from langchain.tools import tool
from app.core.logger import logger
from app.agents.subgraphs.keyword_extract import keyword_extraction_graph

if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()

@tool
def download_file(url: str, out_dir: str = "downloads") -> str:
    """URL에서 파일을 다운로드합니다."""
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    local_name = url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4().hex}.pdf"
    path = str(pathlib.Path(out_dir) / local_name)
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
        return path
    except Exception as e:
        return f"Error: {e}"

@tool
def parse_pdf_to_markdown(pdf_path: str) -> str:
    """Upstage API로 PDF를 마크다운으로 변환합니다."""
    api_key, base_url = os.getenv("UPSTAGE_API_KEY"), os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with open(pdf_path, "rb") as f:
            r = requests.post(f"{base_url}/document-digitization", headers=headers, 
                              files={"document": f}, data={"model": "document-parse", "output_formats": '["markdown"]'})
        r.raise_for_status()
        return r.json().get("markdown") or "Error: Markdown not found."
    except Exception as e:
        return f"Error: {e}"

@tool
def generate_report_pdf(content: str, filename: str = "trendmirror_report.pdf") -> str:
    """자동 줄바꿈이 적용된 PDF 보고서를 생성합니다."""
    out_dir = "reports"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = f"{out_dir}/{filename}"
    font_path = "resources/fonts/NanumGothic-Regular.ttf"
    font_name = "NanumGothic"
    
    try:
        if os.path.exists(font_path): pdfmetrics.registerFont(TTFont(font_name, font_path))
        else: font_name = "Helvetica"

        doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        # 스타일 정의: wordWrap='CJK'가 핵심 (한글 줄바꿈 자동화)
        style = ParagraphStyle('Normal', fontName=font_name, fontSize=11, leading=16, spaceAfter=10, wordWrap='CJK')
        title_style = ParagraphStyle('Title', fontName=font_name, fontSize=18, spaceAfter=20, alignment=1)

        elements = [Paragraph("TrendMirror 마케팅 전략 보고서", title_style), Spacer(1, 0.2*inch)]
        for line in content.splitlines():
            if not line.strip(): elements.append(Spacer(1, 0.1*inch))
            else: elements.append(Paragraph(line.replace('**', '').replace('#', '').strip(), style))
        
        doc.build(elements)
        return path
    except Exception as e:
        return f"Error: {e}"

@tool
def youtube_crawling_tool(query: str, days: int = 30, pages: int = 10) -> "pd.DataFrame":
    """데이터 부족 시 추가 수집을 수행하는 유튜브 크롤러입니다."""
    from app.repository.client.youtube_client import collect_youtube_trend_candidates_df
    from datetime import datetime, timedelta, timezone

    out_dir = "downloads"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    master_cache_path = os.path.join(out_dir, f"youtube_{''.join(c for c in query if c.isalnum())}_master_cache.csv")
    
    master_df = pd.read_csv(master_cache_path) if os.path.exists(master_cache_path) else pd.DataFrame()
    if not master_df.empty:
        master_df['published_at'] = pd.to_datetime(master_df['published_at'], errors='coerce').dt.tz_convert('UTC')
    
    newest_date = master_df['published_at'].max() if not master_df.empty else None
    should_crawl, published_after = True, None

    # [수정] 데이터 수집량 확보 로직
    if newest_date:
        # 데이터가 너무 적으면(100개 미만) 전체 기간 다시 조회, 아니면 1시간 이내 중복 방지
        if len(master_df) < 100: published_after = None
        elif (datetime.now(timezone.utc) - newest_date).total_seconds() < 3600:
            should_crawl, published_after = False, newest_date.isoformat()
        else: published_after = newest_date.isoformat()

    if should_crawl:
        try:
            new_df = collect_youtube_trend_candidates_df(query=query, days=days, pages=pages, published_after_date=published_after)
            if not new_df.empty:
                new_df['published_at'] = pd.to_datetime(new_df['published_at'], errors='coerce').dt.tz_convert('UTC')
                master_df = pd.concat([master_df, new_df]).drop_duplicates(subset=['video_id']).reset_index(drop=True)
                master_df.to_csv(master_cache_path, index=False, encoding='utf-8-sig')
        except Exception as e: logger.error(f"Crawl Error: {e}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return master_df[master_df['published_at'] >= cutoff].copy() if not master_df.empty else pd.DataFrame()

@tool
def run_keyword_extraction(input_df_json: str, base_export_path: str, slots: Dict[str, Any]) -> str:
    """키워드 추출 서브그래프를 호출합니다."""
    initial_state = {"input_df_json": input_df_json, "base_export_path": base_export_path, "slots": slots}
    final_state = keyword_extraction_graph.invoke(initial_state)
    if final_state.get("error"): return json.dumps({"status": "error", "message": final_state["error"]}, ensure_ascii=False)
    return json.dumps({"status": "success", "frequencies_df_json": final_state.get("frequencies_df_json")}, ensure_ascii=False)