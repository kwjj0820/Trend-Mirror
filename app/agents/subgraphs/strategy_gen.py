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

def strategy_gen_node(state: TMState, config: RunnableConfig):
    logger.info("--- (4) Entered Strategy Generation Subgraph (DB Query) ---")
    
    # 1. 서비스 및 사용자 쿼리 가져오기
    vector_service: VectorService = config["configurable"].get("vector_service")
    if not vector_service:
        logger.error("VectorService not found in config. Aborting generation.")
        return {"final_answer": "오류: VectorService가 설정되지 않았습니다."}

    user_input = state["user_input"]
    slots = state.get("slots", {})
    category = slots.get('search_query', user_input) # DB category로 사용될 'search_query'
    sns = "youtube" # 현재는 youtube로 가정
    
    logger.info(f"Report generation for Category: '{category}'")

    # 2. Vector DB에서 키워드 빈도수 기반 상위 키워드 조회
    top_keywords_n = 5
    top_keywords_data = vector_service.get_keyword_frequencies(category=category, sns=sns, n_results=top_keywords_n)
    top_keywords = [item['keyword'] for item in top_keywords_data]
    logger.info(f"Retrieved top {top_keywords_n} keywords for '{category}' from DB: {top_keywords}")

    # 3. 상위 키워드를 활용하여 상세 정보 검색 쿼리 구성
    if top_keywords:
        # 상위 키워드를 포함하여 더 집중된 검색 쿼리 생성
        retrieval_query = f"{category}의 주요 트렌드 키워드는 {', '.join(top_keywords)}입니다. 이 키워드들과 관련된 상세 영상 내용을 요약해주세요."
    else:
        # 상위 키워드를 찾지 못한 경우, 원본 사용자 입력 또는 카테고리로 대체
        retrieval_query = user_input
    
    logger.info(f"Using retrieval query for detailed search: '{retrieval_query}'")

    # 4. 구성된 쿼리로 벡터 DB에서 관련 문서 쿼리
    search_n_results = 10
    try:
        retrieved_docs = vector_service.search(query=retrieval_query, n_results=search_n_results)
        logger.info(f"Retrieved {len(retrieved_docs)} detailed documents from Vector DB using n_results={search_n_results}.")
    except Exception as e:
        logger.error(f"Failed to query Vector DB: {e}", exc_info=True)
        return {"final_answer": f"오류: 데이터베이스 조회에 실패했습니다: {e}"}

    if not retrieved_docs and not top_keywords:
        return {"final_answer": "관련된 트렌드 정보를 찾지 못했습니다."}

    # 5. 컨텍스트 조립 및 LLM 호출
    context_str = ""
    if top_keywords:
        context_str += f"## 주요 트렌드 키워드 (빈도 기반 상위 {top_keywords_n}개):\n- {', '.join(top_keywords)}\n\n"
    
    if retrieved_docs:
        context_str += "## 관련 영상 상세 내용:\n"
        # 참고: search 결과의 meta는 dict. get()으로 안전하게 접근
        for doc in retrieved_docs:
            meta = doc.get('meta', {})
            context_str += f"- [키워드: {meta.get('keyword', 'N/A')}] (내용: {doc.get('text', '')})\n"

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
    1. Based on the Context, decode any slang or abbreviations by cross-referencing titles and descriptions. (e.g., If 'Dujjonku' and 'Dubai Jjondeuk Cookie' appear together, connect them.)
    2. Analyze the 'Target Age Group' for each key trend. Provide logical reasoning based on content format (Shorts vs. Long-form) and topic.
    3. Generate a comprehensive trend report in Korean.
    """)
        ]

        logger.info("Calling LLM to write the final report...")
        response = solar.invoke(messages)
        report_content = response.content
        logger.info("LLM call complete. Report content generated.")

        # 6. PDF 생성 Tool 호출
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        domain_name = slots.get('domain', 'result')
        pdf_filename = f"report_{domain_name}_{current_date}.pdf"

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