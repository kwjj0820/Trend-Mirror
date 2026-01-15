# app/agents/tools.py
import os
import uuid
import pathlib
import requests
import json
import datetime
from typing import Dict, Any

from dotenv import load_dotenv
from langchain.tools import tool

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont

# Platypus (예쁜 PDF v2)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm

from app.core.logger import logger


# 로컬 환경에서만 .env 로드
if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()


# =========================
# 1) File/Parsing Tools
# =========================
@tool
def download_file(url: str, out_dir: str = "downloads") -> str:
    """URL에서 파일을 다운로드하여 로컬 경로를 반환합니다."""
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    local_name = url.split("/")[-1].split("?")[0]
    if not local_name:
        local_name = f"file_{uuid.uuid4().hex}.pdf"

    path = str(pathlib.Path(out_dir) / local_name)

    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return path
    except Exception as e:
        return f"Error downloading {url}: {e}"


@tool
def parse_pdf_to_markdown(pdf_path: str) -> str:
    """Upstage Layout Analysis API를 사용하여 PDF를 마크다운으로 변환합니다."""
    api_key = os.getenv("UPSTAGE_API_KEY")
    base_url = os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1").rstrip("/")
    model = os.getenv("UPSTAGE_DOC_PARSE_MODEL", "document-parse")

    if not api_key:
        return "Error: UPSTAGE_API_KEY is not set."

    url = f"{base_url}/document-digitization"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with open(pdf_path, "rb") as f:
            files = {"document": f}
            data = {"model": model, "output_formats": '["markdown"]', "ocr": "auto"}
            r = requests.post(url, headers=headers, files=files, data=data, timeout=240)

        r.raise_for_status()
        j = r.json()
        md = (
            j.get("markdown")
            or (j.get("content") or {}).get("markdown")
            or (j.get("output") or {}).get("markdown")
        )
        if not md:
            return "Error: Markdown not found in response."
        return md
    except Exception as e:
        return f"Error parsing PDF: {e}"


# =========================
# 2) PDF Generator (legacy canvas)
# =========================
@tool
def generate_report_pdf(content: str, filename: str = "trendmirror_report.pdf") -> str:
    """(기존) 간단 PDF 생성. 한글은 나눔고딕 사용."""
    logger.info(f"generate_report_pdf called with filename='{filename}'")

    out_dir = "reports"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = f"{out_dir}/{filename}"

    font_path_regular = "resources/fonts/NanumGothic-Regular.ttf"
    font_path_bold = "resources/fonts/NanumGothic-Bold.ttf"

    font_name_regular = "NanumGothic-Regular"
    font_name_bold = "NanumGothic-Bold"

    try:
        regular_exists = os.path.exists(font_path_regular)
        bold_exists = os.path.exists(font_path_bold)

        if regular_exists:
            pdfmetrics.registerFont(TTFont(font_name_regular, font_path_regular))
        if bold_exists:
            pdfmetrics.registerFont(TTFont(font_name_bold, font_path_bold))

        title_font = font_name_bold if bold_exists else (font_name_regular if regular_exists else "Helvetica-Bold")
        body_font = font_name_regular if regular_exists else "Helvetica"

        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        margin_left = 50
        margin_right = 50
        margin_top = 60
        margin_bottom = 60
        body_font_size = 11
        line_height = 16
        max_width = width - margin_left - margin_right

        def wrap_text(text: str, max_line_width: int = max_width) -> list[str]:
            if not text:
                return [""]
            words = text.split(" ")
            lines, current = [], ""
            for word in words:
                test = f"{current} {word}".strip()
                if pdfmetrics.stringWidth(test, body_font, body_font_size) <= max_line_width:
                    current = test
                    continue
                if current:
                    lines.append(current)
                # 한 단어가 너무 길면 글자 단위로 분할
                if pdfmetrics.stringWidth(word, body_font, body_font_size) <= max_line_width:
                    current = word
                else:
                    chunk = ""
                    for ch in word:
                        test_chunk = f"{chunk}{ch}"
                        if pdfmetrics.stringWidth(test_chunk, body_font, body_font_size) <= max_line_width:
                            chunk = test_chunk
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    current = chunk
            if current:
                lines.append(current)
            return lines

        title_text = "TrendMirror Report"
        subtitle_text = None
        blocks = []
        last_kind = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line:
                line = line.replace("**", "").replace("__", "")
            if not line:
                if last_kind != "spacer":
                    blocks.append(("spacer", ""))
                    last_kind = "spacer"
                continue

            lowered = line.lower()
            if lowered.startswith("title:"):
                title_text = line.split(":", 1)[1].strip() or title_text
                continue
            if lowered.startswith("subtitle:"):
                subtitle_text = line.split(":", 1)[1].strip()
                continue

            if line.startswith("# "):
                blocks.append(("h1", line[2:].strip()))
                last_kind = "h1"
                continue
            if line.startswith("## "):
                blocks.append(("h2", line[3:].strip()))
                last_kind = "h2"
                continue
            if line.startswith("### "):
                blocks.append(("h3", line[4:].strip()))
                last_kind = "h3"
                continue
            if line.startswith(">") or lowered.startswith("insight:"):
                text = line[1:].strip() if line.startswith(">") else line.split(":", 1)[1].strip()
                blocks.append(("insight", text))
                last_kind = "insight"
                continue
            if line.startswith("- ") or line.startswith("* "):
                blocks.append(("li", line[2:].strip()))
                last_kind = "li"
                continue

            blocks.append(("p", line))
            last_kind = "p"

        y = height - margin_top

        def ensure_space(needed: int):
            nonlocal y
            if y - needed < margin_bottom:
                c.showPage()
                y = height - margin_top

        def draw_wrapped(text: str, font_name: str, font_size: int, indent: int = 0):
            nonlocal y
            c.setFont(font_name, font_size)
            available = max_width - indent
            for wrapped in wrap_text(text, max_line_width=available):
                ensure_space(line_height)
                c.drawString(margin_left + indent, y, wrapped)
                y -= line_height

        def draw_insight_box(text: str):
            nonlocal y
            padding_x = 10
            padding_y = 8
            label_size = 9
            available = max_width - (padding_x * 2)
            lines = wrap_text(text, max_line_width=available)
            box_height = (len(lines) * line_height) + padding_y * 2 + label_size + 4

            ensure_space(box_height + line_height)
            top = y

            c.setFillColor(colors.HexColor("#F8F2E9"))
            c.setStrokeColor(colors.HexColor("#E5D4BC"))
            c.rect(margin_left, top - box_height, max_width, box_height, fill=1, stroke=1)

            c.setFillColor(colors.HexColor("#7A5B2E"))
            c.setFont(title_font, label_size)
            c.drawString(margin_left + padding_x, top - padding_y - label_size, "DATA INSIGHT")

            c.setFillColor(colors.black)
            c.setFont(body_font, body_font_size)
            text_y = top - padding_y - label_size - 6
            for ln in lines:
                c.drawString(margin_left + padding_x, text_y, ln)
                text_y -= line_height

            y = top - box_height - line_height // 2

        # Cover
        draw_wrapped(title_text, title_font, 20)
        if subtitle_text:
            c.setFillColorRGB(0.35, 0.35, 0.35)
            draw_wrapped(subtitle_text, body_font, 11)
            c.setFillColorRGB(0, 0, 0)
        y -= line_height // 2

        pending_lead = False
        for kind, text in blocks:
            if kind == "spacer":
                y -= line_height // 3
                continue
            if kind in ("h1", "h2", "h3"):
                size = 18 if kind == "h1" else 14 if kind == "h2" else 12
                y -= line_height // 4
                draw_wrapped(text, title_font, size)
                y -= line_height // 5
                pending_lead = True
                continue
            if kind == "li":
                draw_wrapped(f"- {text}", body_font, body_font_size, indent=10)
                continue
            if kind == "insight":
                draw_insight_box(text)
                continue
            if pending_lead:
                draw_wrapped(text, title_font, body_font_size + 1)
                pending_lead = False
            else:
                draw_wrapped(text, body_font, body_font_size)

        c.save()
        return path
    except Exception as e:
        return f"Error generating PDF: {e}"

import re

_MD_BOLD_ITALIC_RE = re.compile(r"(\*\*|__|\*|_)(.*?)\1")
_MD_CODE_RE = re.compile(r"`{1,3}([^`]+)`{1,3}")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

def clean_md_inline(text: str) -> str:
    if not text:
        return ""

    t = text

    # 이미지 ![alt](url) -> alt (없으면 제거)
    t = _MD_IMG_RE.sub(lambda m: (m.group(1) or "").strip(), t)

    # 링크 [text](url) -> text
    t = _MD_LINK_RE.sub(lambda m: m.group(1).strip(), t)

    # 코드 `code` / ```code``` -> code
    t = _MD_CODE_RE.sub(lambda m: m.group(1), t)

    # 굵게/기울임 **text** __text__ *text* _text_ -> text
    # (중첩은 완벽하진 않지만 보고서용으론 충분)
    while True:
        new_t = _MD_BOLD_ITALIC_RE.sub(lambda m: m.group(2), t)
        if new_t == t:
            break
        t = new_t

    # 남는 **, __ 같은 찌꺼기 제거
    t = t.replace("**", "").replace("__", "").replace("`", "")

    # 과한 공백 정리
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t
# =========================
# 3) PDF Generator v2 (Notion/Figma style, Platypus)
# =========================
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generate_report_pdf_v2(content: str, filename: str = "trendmirror_report.pdf") -> str:
    """
    Notion/Figma 느낌의 깔끔한 '기획서/보고서/레포트' 스타일 PDF 생성 (Platypus)
    - wordWrap="CJK" (한글 줄바꿈/오른쪽 잘림 방지)
    - splitByRow + VALIGN=TOP (카드/테이블 페이지 분할 안정화)
    - Cover + Cards + Insight box + Footer
    """
    out_dir = "reports"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(pathlib.Path(out_dir) / filename)

    # Fonts (Korean)
    font_path_regular = "resources/fonts/NanumGothic-Regular.ttf"
    font_path_bold = "resources/fonts/NanumGothic-Bold.ttf"
    font_regular = "NanumGothic-Regular"
    font_bold = "NanumGothic-Bold"

    # 한글 보고서면 폰트 없을 때가 더 치명적이라 명확히 실패 처리
    if not os.path.exists(font_path_regular):
        return f"Error generating PDF: Korean font not found: {font_path_regular}"
    pdfmetrics.registerFont(TTFont(font_regular, font_path_regular))

    if os.path.exists(font_path_bold):
        pdfmetrics.registerFont(TTFont(font_bold, font_path_bold))
    else:
        font_bold = font_regular

    # Palette (subtle)
    TEXT = colors.HexColor("#111827")
    MUTED = colors.HexColor("#6B7280")
    LINE = colors.HexColor("#E5E7EB")
    CARD_BG = colors.HexColor("#F9FAFB")
    INSIGHT_BG = colors.HexColor("#F5F0E8")

    # Doc
    left_margin = 18 * mm
    right_margin = 18 * mm
    top_margin = 18 * mm
    bottom_margin = 18 * mm
    usable_w = A4[0] - left_margin - right_margin

    created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def footer(c, doc):
        c.saveState()
        c.setFont(font_regular, 9)
        c.setFillColor(MUTED)
        c.drawString(left_margin, 12 * mm, f"Generated: {created}")
        c.drawRightString(A4[0] - right_margin, 12 * mm, str(doc.page))
        c.restoreState()

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title="TrendMirror Report",
    )

    styles = getSampleStyleSheet()

    # ✅ wordWrap="CJK" 전부 적용
    Title = ParagraphStyle(
        "TM_Title",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=22,
        leading=28,
        textColor=TEXT,
        alignment=TA_LEFT,
        spaceAfter=8,
        wordWrap="CJK",
    )
    Subtitle = ParagraphStyle(
        "TM_Subtitle",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=11,
        leading=16,
        textColor=MUTED,
        spaceAfter=18,
        wordWrap="CJK",
    )
    H1 = ParagraphStyle(
        "TM_H1",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=16,
        leading=22,
        textColor=TEXT,
        spaceBefore=10,
        spaceAfter=8,
        wordWrap="CJK",
    )
    H2 = ParagraphStyle(
        "TM_H2",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=13,
        leading=18,
        textColor=TEXT,
        spaceBefore=8,
        spaceAfter=6,
        wordWrap="CJK",
    )
    Body = ParagraphStyle(
        "TM_Body",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=10.5,
        leading=16,
        textColor=TEXT,
        spaceAfter=6,
        wordWrap="CJK",
    )
    Bullet = ParagraphStyle(
        "TM_Bullet",
        parent=Body,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=4,
        wordWrap="CJK",
    )
    Small = ParagraphStyle(
        "TM_Small",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9,
        leading=12,
        textColor=MUTED,
        wordWrap="CJK",
    )
    InsightLabel = ParagraphStyle(
        "TM_InsightLabel",
        parent=Small,
        fontName=font_bold,
        textColor=MUTED,
        spaceAfter=6,
        wordWrap="CJK",
    )
    H3 = ParagraphStyle(
        "TM_H3",
        parent=styles["Heading3"],
        fontName=font_bold,
        fontSize=11.5,
        leading=16,
        textColor=TEXT,
        spaceBefore=6,
        spaceAfter=4,
        wordWrap="CJK",
    )

    def parse_blocks(md: str):
        title_text = "TrendMirror Report"
        subtitle_text = ""
        blocks = []

        for raw in md.splitlines():
            line = raw.strip()
            line = clean_md_inline(line) 
            if not line:
                blocks.append(("spacer", ""))
                continue

            low = line.lower()
            if low.startswith("title:"):
                title_text = line.split(":", 1)[1].strip() or title_text
                continue
            if low.startswith("subtitle:"):
                subtitle_text = line.split(":", 1)[1].strip()
                continue

            # --- 같은 구분선은 HR로 처리(텍스트로 찍히는 문제 방지)
            if line in ("---", "—", "–––"):
                blocks.append(("hr", ""))
                continue

            if line.startswith("# "):
                blocks.append(("h1", line[2:].strip()))
            elif line.startswith("## "):
                blocks.append(("h2", line[3:].strip()))
            elif line.startswith("### "):
                blocks.append(("h3", line[4:].strip()))
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append(("li", line[2:].strip()))
            elif line.startswith(">") or low.startswith("insight:"):
                text = line[1:].strip() if line.startswith(">") else line.split(":", 1)[1].strip()
                blocks.append(("insight", text))
            else:
                blocks.append(("p", line))

        return title_text, subtitle_text, blocks

    # ✅ splitByRow + VALIGN=TOP 적용
    def card(flowables, bg=CARD_BG, pad=10):
        t = Table([[flowables]], colWidths=[usable_w], splitByRow=1)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), pad),
            ("TOPPADDING", (0, 0), (-1, -1), pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ]))
        return t

    def insight_box(text: str):
        body = [
            Paragraph("INSIGHT", InsightLabel),
            Paragraph(text, Body),
        ]
        return card(body, bg=INSIGHT_BG, pad=10)

    title_text, subtitle_text, blocks = parse_blocks(content)

    story = []

    # Cover
    story.append(Spacer(1, 18))
    story.append(Paragraph(title_text, Title))
    if subtitle_text:
        story.append(Paragraph(subtitle_text, Subtitle))
    story.append(Paragraph(f"<font color='#6B7280'>Created</font>&nbsp;&nbsp;{created}", Small))
    story.append(Spacer(1, 18))

    # Divider line (safe)
    line_tbl = Table([[""]], colWidths=[usable_w], rowHeights=[1], splitByRow=1)
    line_tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LINE)]))
    story.append(line_tbl)
    story.append(Spacer(1, 16))

    # Body: sections as cards
    current_card = []

    def flush_card():
        nonlocal current_card
        if current_card:
            story.append(card(current_card))
            story.append(Spacer(1, 10))
            current_card = []

    for kind, text in blocks:
        if kind == "spacer":
            if current_card:
                current_card.append(Spacer(1, 6))
            continue
        if kind == "h3":
            flush_card()
            story.append(Paragraph(f"– {text}", H3))
            story.append(Spacer(1, 4))
            continue
        if kind == "hr":
            flush_card()
            hr = Table([[""]], colWidths=[usable_w], rowHeights=[1], splitByRow=1)
            hr.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LINE)]))
            story.append(hr)
            story.append(Spacer(1, 10))
            continue

        if kind in ("h1", "h2"):
            flush_card()
            icon = "•"  # 미니멀 아이콘
            style = H1 if kind == "h1" else H2
            story.append(Paragraph(f"{icon} {text}", style))
            story.append(Spacer(1, 6))
            continue

        if kind == "insight":
            flush_card()
            story.append(insight_box(text))
            story.append(Spacer(1, 10))
            continue

        if kind == "li":
            current_card.append(Paragraph(f"• {text}", Bullet))
            continue

        if kind == "p":
            current_card.append(Paragraph(text, Body))
            continue

    flush_card()

    try:
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return path
    except Exception as e:
        return f"Error generating PDF: {e}"


@tool
def generate_report_pdf_v2_tool(content: str, filename: str = "trendmirror_report.pdf") -> str:
    """(툴) Platypus 기반 v2 PDF 생성"""
    logger.info(f"generate_report_pdf_v2_tool called with filename='{filename}'")
    return generate_report_pdf_v2(content=content, filename=filename)

# =========================
# 4) YouTube Tool
# =========================
@tool
def youtube_crawling_tool(query: str, days: int = 7, pages: int = 1) -> str:
    """
    YouTube 트렌드 데이터를 수집하여 DataFrame을 JSON 문자열로 반환합니다.
    실제 app.repository.client.youtube_client를 사용합니다.
    """
    from app.repository.client.youtube_client import collect_youtube_trend_candidates_df
    import pandas as pd

    logger.info(f"youtube_crawling_tool called with query='{query}', days='{days}', pages='{pages}'")

    try:
        df = collect_youtube_trend_candidates_df(query=query, days=days, pages=pages)
        if df.empty:
            logger.warning("YouTube crawling returned an empty DataFrame.")
        # DataFrame을 JSON 문자열로 변환하여 반환
        return df.to_json(orient='split', force_ascii=False)
    except Exception as e:
        logger.error(f"Error during youtube crawling: {e}")
        # 오류 발생 시 빈 DataFrame의 JSON을 반환
        return pd.DataFrame().to_json(orient='split')


# =========================
# 5) Keyword Extraction Tool (LAZY IMPORT to avoid circular import)
# =========================
@tool
def run_keyword_extraction(input_df_json: str, base_export_path: str, slots: Dict[str, Any]) -> str:
    """
    주어진 DataFrame JSON 문자열에 대해 키워드 추출 워크플로우를 실행합니다.
    입력: DataFrame JSON 문자열, base_export_path, slots
    출력: 처리 결과 메시지(JSON)
    """
    from app.agents.subgraphs.keyword_extract import keyword_extraction_graph

    if not isinstance(input_df_json, str):
        return json.dumps({"status": "error", "message": "입력 데이터가 유효한 JSON 문자열이 아닙니다."})

    initial_state = {
        "input_df_json": input_df_json,
        "base_export_path": base_export_path,
        "slots": slots
    }
    final_state = keyword_extraction_graph.invoke(initial_state)

    if final_state.get("error"):
        return json.dumps({"status": "error", "message": final_state["error"]}, ensure_ascii=False)

    return json.dumps(
        {
            "status": "success",
            "output_path": final_state.get("output_path"),
            "frequencies_df_json": final_state.get("frequencies_df_json"),
        },
        ensure_ascii=False,
    )
