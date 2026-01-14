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
GEN_SYSTEM_PROMPT = """You are a helpful assistant who summarizes the provided context into a simple report.
Based on the 'Context' below, create a concise summary of the key trends.
Do not add any information that is not in the context.

Format: Markdown
Language: Korean
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
    domain = slots.get('domain', user_input) # 기존 goal 대신 domain 사용
    sns = "youtube" # 현재는 youtube로 가정, 필요시 확장 가능
    
    logger.info(f"Report generation for Domain: '{domain}'")

    # 2. Vector DB에서 키워드 빈도수 기반 상위 키워드 조회
    top_keywords_n = 5
    top_keywords_data = vector_service.get_keyword_frequencies(category=domain, sns=sns, n_results=top_keywords_n)
    top_keywords = [item['keyword'] for item in top_keywords_data]
    logger.info(f"Retrieved top {top_keywords_n} keywords for '{domain}' from DB: {top_keywords}")

    # 3. 상위 키워드를 활용하여 상세 정보 검색 쿼리 구성
    if top_keywords:
        # 상위 키워드를 포함하여 더 집중된 검색 쿼리 생성
        retrieval_query = f"{domain}의 주요 트렌드 키워드는 {', '.join(top_keywords)}입니다. 이 키워드들과 관련된 상세 영상 내용을 요약해주세요."
    else:
        # 상위 키워드를 찾지 못한 경우, 원본 사용자 입력 또는 도메인으로 대체
        retrieval_query = user_input
    
    logger.info(f"Using retrieval query for detailed search: '{retrieval_query}'")

    # 4. 구성된 쿼리로 벡터 DB에서 관련 문서 쿼리 (더 많은 결과를 가져와 컨텍스트로 활용)
    search_n_results = 10
    try:
        retrieved_docs = vector_service.search(query=retrieval_query, n_results=search_n_results) # 더 많은 문서를 가져와 풍부한 컨텍스트 생성
        logger.info(f"Retrieved {len(retrieved_docs)} detailed documents from Vector DB using n_results={search_n_results}.")
    except Exception as e:
        logger.error(f"Failed to query Vector DB: {e}", exc_info=True)
        return {"final_answer": f"오류: 데이터베이스 조회에 실패했습니다: {e}"}

    if not retrieved_docs and not top_keywords:
        return {"final_answer": "관련된 트렌드 정보를 찾지 못했습니다."}

    # 5. 컨텍스트 조립 및 LLM 호출
    context_str = ""
    if top_keywords:
        context_str += f"## 주요 트렌드 키워드 (빈도 기반 상위 5개):\n- {', '.join(top_keywords)}\n\n"
    
    if retrieved_docs:
        context_str += "## 관련 영상 상세 내용:\n"
        for doc in retrieved_docs:
            context_str += f"- [키워드: {doc['meta'].get('keyword', 'N/A')}] 제목: '{doc['meta'].get('title', 'N/A')}', 설명: '{doc['meta'].get('description', 'N/A')}'\n"
    
    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"Original Request: {user_input}\n\nContext:\n{context_str}\n\n위 컨텍스트를 바탕으로 '{domain}'에 대한 종합적인 트렌드 분석 보고서를 작성해 주세요.")
    ]

    logger.info("Calling LLM to write the final report...")
    response = solar.invoke(messages)
    report_content = response.content
    logger.info("LLM call complete. Report content generated.")

    # PDF 생성 Tool 호출
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    # goal 대신 domain을 사용하며, 날짜를 포함시킵니다.
    domain_name = slots.get('domain', 'result')
    pdf_filename = f"report_{domain_name}_{current_date}.pdf"
    logger.info(f"Generating PDF report: {pdf_filename}")
    
    # generate_report_pdf는 @tool로 감싸져 있으므로 직접 호출 대신 .invoke() 사용 고려
    # tools.py의 구현을 직접 참조하여 로직 실행
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