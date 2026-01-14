# app/agents/subgraphs/strategy_gen.py
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.core.logger import logger
from app.service.vector_service import VectorService

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
    # 슬롯에 'goal'이 있으면 검색 쿼리로 사용, 없으면 원본 사용자 입력 사용
    query = slots.get('goal', user_input)
    logger.info(f"Using query for DB search: '{query}'")

    # 2. 벡터 DB에서 관련 문서 쿼리
    try:
        retrieved_docs = vector_service.search(query=query, n_results=5)
        logger.info(f"Retrieved {len(retrieved_docs)} documents from Vector DB.")
    except Exception as e:
        logger.error(f"Failed to query Vector DB: {e}", exc_info=True)
        return {"final_answer": f"오류: 데이터베이스 조회에 실패했습니다: {e}"}

    if not retrieved_docs:
        return {"final_answer": "관련된 트렌드 정보를 찾지 못했습니다."}

    # 3. 컨텍스트 조립 및 LLM 호출
    context_str = "\n\n".join([f"- {doc['text']}" for doc in retrieved_docs])
    
    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"Original Request: {user_input}\n\nContext:\n{context_str}")
    ]

    logger.info("Calling LLM to write the final report...")
    response = solar.invoke(messages)
    report_content = response.content
    logger.info("LLM call complete. Report content generated.")

    # PDF 생성 Tool 호출
    pdf_filename = f"report_{slots.get('goal', 'result')}.pdf"
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