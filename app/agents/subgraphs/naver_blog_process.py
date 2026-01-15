# app/agents/subgraphs/naver_blog_process.py
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.agents.state import TMState
from app.core.logger import logger
from app.service.vector_service import VectorService
import os

def naver_blog_process_node(state: TMState, config: RunnableConfig) -> dict:
    """
    네이버 블로그 데이터를 수집하고, 그 결과 CSV 파일 경로를 반환합니다.
    1. DB에서 현재 카테고리의 상위 키워드를 가져옵니다.
    2. 상위 키워드로 네이버 블로그 크롤링 도구를 호출하여 CSV를 생성합니다.
    3. 생성된 CSV 경로를 상태에 저장하여 다음 노드로 전달합니다.
    """
    logger.info("--- (NB) Entered Naver Blog Processing Subgraph ---")
    
    # 1. 이전 단계에서 생성된 상위 키워드 가져오기
    vector_service: VectorService = config["configurable"].get("vector_service")
    if not vector_service:
        logger.error("VectorService not found in config. Aborting Naver Blog process.")
        return {} 

    slots = state.get("slots", {})
    category = slots.get('search_query', state.get("user_input"))
    
    logger.info(f"Step NB.1: Fetching top YouTube keywords for category '{category}' to use as Naver queries...")
    try:
        top_keywords_data = vector_service.get_keyword_frequencies(category=category, sns="youtube", n_results=5)
        top_keywords = [item['keyword'] for item in top_keywords_data]
        if not top_keywords:
            logger.warning("No top keywords found from YouTube data. Using original category as query.")
            top_keywords = [category]
        logger.info(f"Top keywords to be used as queries: {top_keywords}")
    except Exception as e:
        logger.error(f"Failed to get top keywords from DB: {e}", exc_info=True)
        top_keywords = [category]

    # 2. 네이버 블로그 데이터 크롤링
    logger.info("Step NB.2: Calling naver_blog_crawling_tool...")
    crawl_result_str = naver_blog_crawling_tool.invoke({"queries": top_keywords, "main_query": category})
    logger.info(f"Naver crawling tool returned: {crawl_result_str}")

    # Tool 결과에서 CSV 경로 추출
    try:
        csv_path = crawl_result_str.rsplit(": ", 1)[1].strip()
    except IndexError:
        error_message = "Failed to find a valid CSV path from naver_blog_crawling_tool output."
        logger.error(error_message)
        return {}

    if not ".csv" in csv_path or not os.path.exists(csv_path):
        error_message = f"Invalid or non-existent CSV path from Naver crawl: '{csv_path}'"
        logger.error(error_message)
        return {}

    logger.info(f"Extracted Naver Blog CSV path: {csv_path}")
    logger.info("--- Naver Blog Processing Subgraph Finished ---")

    # 다음 strategy_gen 노드가 사용할 수 있도록, 크롤링된 원본 CSV 경로를 상태에 추가
    return {"naver_blog_csv_path": csv_path}


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("naver_blog_process", naver_blog_process_node)
workflow.set_entry_point("naver_blog_process")
workflow.add_edge("naver_blog_process", END)
naver_blog_process_graph = workflow.compile()
