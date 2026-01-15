# app/agents/state.py
from typing import TypedDict, List, Dict, Any, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from app.service.sync_service import SyncService

# 노트북의 TMState 구조 이식
class TMState(TypedDict, total=False):
    # --- User Input ---
    user_input: str

    # --- Build Agent Outputs ---
    intent: str                 # "trendmirror" | "chitchat"
    slots: Dict[str, Any]       # {"region":"KR", "period_days":30, ...}
    cache_key: str
    cache_hit: bool

    # --- Insight Extract Outputs (Tools & KB) ---
    search_results: List[Dict[str, Any]]   # serper results
    downloaded_files: List[str]            # local paths
    markdown_docs: List[Dict[str, Any]]    # [{"source":..., "markdown":...}]
    chunks: List[Dict[str, Any]]           # [{"chunk_id":..., "text":...}]
    retrieved: List[Dict[str, Any]]        # top 25 raw
    reranked: List[Dict[str, Any]]         # top 10 after judge

    # --- Data flow between nodes ---
    input_df_json: str # Serialized DataFrame for keyword extraction
    base_export_path: str # Base path for exporting temp files if needed
    frequencies_df_json: str # Serialized keyword frequencies DataFrame for DB sync

    # --- Keyword Extraction Outputs ---
    csv_path: str
    naver_blog_csv_path: str # 네이버 블로그 크롤링 결과 CSV 경로
    output_path: str

    # --- Gen Agent Outputs ---
    final_answer: str
    final_pdf_path: str

    # --- System Logs ---
    # 노트북의 simple log list 대신 LangGraph Message History와 병행 사용 권장
    logs: List[str]
    messages: Annotated[List[BaseMessage], add_messages]