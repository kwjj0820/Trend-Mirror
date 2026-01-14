# app/agents/subgraphs/strategy_gen.py
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.core.logger import logger
from app.service.vector_service import VectorService
import datetime # Import datetime
import json # Import json

# 새로운 목표에 맞춘 시스템 프롬프트
GEN_SYSTEM_PROMPT = """You are a Senior Market Trend Analyst specialized in data-driven reporting. 
Your goal is to synthesize the provided context into a professional trend report.

[CRITICAL: ANTI-HALLUCINATION RULES]
1. DO NOT fabricate meanings for abbreviations or neologisms (e.g., "Dujjonku").
2. CROSS-REFERENCE: Look for full names in the provided 'Context' (titles/descriptions). If "Dujjonku" appears in the same context as "Dubai Jjondeuk Cookie", treat it as an abbreviation.
3. If no clear evidence is found in the Context, explicitly state: "Information regarding this keyword is insufficient for a definitive definition."

[REPORT STRUCTURE]
- Executive Summary: A high-level overview of the trend.
- Deep Dive: Detailed analysis of top keywords and their market context.
- Consumer Demographic Analysis: Logically infer target age groups (e.g., 10s-20s for Shorts/Challenges, 20s-40s for detailed reviews or home-cafe recipes).
- Action Plan: Strategic suggestions for marketing or business.

Language: Korean (Translate your analysis into natural, professional Korean)
Format: Structured Markdown
"""

import pandas as pd
import os

def strategy_gen_node(state: TMState, config: RunnableConfig):
    logger.info("--- (4) Entered Strategy Generation Subgraph ---")
    
    # 1. 서비스 및 상태 값 가져오기
    vector_service: VectorService = config["configurable"].get("vector_service")
    if not vector_service:
        logger.error("VectorService not found in config. Aborting generation.")
        return {"final_answer": "오류: VectorService가 설정되지 않았습니다."}

    user_input = state["user_input"]
    slots = state.get("slots", {})
    category = slots.get('search_query', user_input)
    naver_blog_csv_path = state.get("naver_blog_csv_path") # 네이버 블로그 CSV 경로

    logger.info(f"Report generation for Category: '{category}'")

    # 2. DB에서 유튜브 기반 '대표' 상위 키워드 조회
    top_keywords_n = 5
    try:
        top_keywords_data = vector_service.get_keyword_frequencies(category=category, sns="youtube", n_results=top_keywords_n)
        top_keywords = [item['keyword'] for item in top_keywords_data]
        logger.info(f"Retrieved top {len(top_keywords)} YouTube keywords for '{category}': {top_keywords}")
    except Exception as e:
        logger.error(f"Failed to get top keywords from DB: {e}", exc_info=True)
        top_keywords = []

    # 3. 네이버 블로그 CSV 데이터를 컨텍스트로 로드
    context_str = ""
    if top_keywords:
        context_str += f"## 주요 트렌드 키워드 (YouTube 기반):\n- {', '.join(top_keywords)}\n\n"
    
    if naver_blog_csv_path and os.path.exists(naver_blog_csv_path):
        logger.info(f"Loading Naver Blog context from: {naver_blog_csv_path}")
        try:
            df = pd.read_csv(naver_blog_csv_path)
            context_str += "## 네이버 블로그 상세 반응 (상위 15개):\n"
            for _, row in df.head(15).iterrows():
                title = row.get('title', 'N/A')
                description = row.get('description', 'N/A')
                context_str += f"- 제목: {title}\n  - 내용: {description[:200]}...\n" # 내용은 일부만 표시
        except Exception as e:
            logger.error(f"Failed to read or process Naver Blog CSV '{naver_blog_csv_path}': {e}")
            context_str += "## 네이버 블로그 상세 반응:\n- (데이터 파일을 처리하는 중 오류가 발생했습니다.)\n"
    else:
        logger.warning("Naver Blog CSV path not found in state or file does not exist.")

    if not context_str:
        return {"final_answer": "분석을 위한 충분한 정보를 수집하지 못했습니다."}

    # 4. LLM 호출하여 최종 리포트 생성
    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"""
[User Request]
"{user_input}"

[Target Domain]
{category}

[Provided Context]
{context_str}

[Final Instruction]
1. Based on the Context, synthesize a trend report following the requested structure (Executive Summary, Deep Dive, etc.).
2. For the Deep Dive, use the detailed reactions from the Naver Blog context to elaborate on the main trend keywords from YouTube.
3. Generate a comprehensive trend report in Korean.
""")
    ]

    logger.info("Calling LLM to write the final report...")
    response = solar.invoke(messages)
    report_content = response.content
    logger.info("LLM call complete. Report content generated.")

    # 5. PDF 생성 Tool 호출
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    safe_category_name = "".join(c for c in category if c.isalnum())
    pdf_filename = f"report_{safe_category_name}_{current_date}.pdf"

    from app.agents.tools import generate_report_pdf
    pdf_path = generate_report_pdf.invoke({"content": report_content, "filename": pdf_filename})

    if "Error" in str(pdf_path):
        logger.error(f"Failed to generate PDF: {pdf_path}")
    else:
        logger.info(f"Report saved at: {pdf_path}")

    logger.info("--- Strategy Generation Subgraph Finished ---")

    return {
        "final_answer": report_content,
        "final_pdf_path": str(pdf_path)
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("strategy_gen", strategy_gen_node)
workflow.set_entry_point("strategy_gen")
workflow.add_edge("strategy_gen", END)
strategy_gen_graph = workflow.compile()