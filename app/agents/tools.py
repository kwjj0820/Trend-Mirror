# app/agents/tools.py
import os
import uuid
import pathlib
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from langchain.tools import tool
from dotenv import load_dotenv

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
    """분석 결과를 PDF 파일로 생성합니다."""
    out_dir = "reports"
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = f"{out_dir}/{filename}"

    try:
        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 60, "TrendMirror Report")

        c.setFont("Helvetica", 11)
        y = height - 90
        for line in content.splitlines():
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - 60
            # 노트북의 truncate 로직 대신 간단한 길이 제한
            c.drawString(50, y, line[:100])
            y -= 16
        c.save()
        return path
    except Exception as e:
        return f"Error generating PDF: {e}"