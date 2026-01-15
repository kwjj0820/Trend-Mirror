# app/agents/subgraphs/youtube_process.py
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.agents.state import TMState
from app.agents.tools import youtube_crawling_tool, run_keyword_extraction
from app.core.logger import logger
import re
import json
import os

def youtube_process_node(state: TMState, config: RunnableConfig) -> dict:
    """
    유튜브 데이터 처리 워크플로우를 담당하는 노드.
    1. 유튜브 크롤링 도구 호출 (DataFrame 반환)
    2. 키워드 추출 워크플로우 호출
    """
    from datetime import datetime

    logger.info("--- (YT) Entered YouTube Processing Subgraph ---")
    # 1. 유튜브 데이터 크롤링 (DataFrame 반환)
    logger.info("Step YT.1: Calling youtube_crawling_tool...")
    user_input = state.get("user_input", "")
    slots = state.get("slots", {})
    domain = slots.get("domain", "N/A")
    crawling_query = slots.get("search_query", user_input)
    
    days_to_crawl = slots.get("period_days", 7)
    pages_to_crawl = slots.get("pages", 5)
    
    logger.info(f"Domain: '{domain}', Crawling Query: '{crawling_query}', Days: {days_to_crawl}, Pages: {pages_to_crawl}")

    result_json = youtube_crawling_tool.invoke({
        "query": crawling_query,
        "days": days_to_crawl,
        "pages": pages_to_crawl
    })

    # JSON 문자열로부터 DataFrame 복원
    try:
        from io import StringIO
        import pandas as pd
        result_df = pd.read_json(StringIO(result_json), orient='split')
    except (ValueError, KeyError):
        logger.warning("Failed to parse DataFrame from JSON. Assuming empty.")
        result_df = pd.DataFrame()


    if result_df.empty:
        logger.warning("Crawling returned no data or an invalid type. Skipping keyword extraction.")
        return {"output_path": None}

    # --- 로깅 추가 ---
    logger.info(f"youtube_process_node: Received DataFrame with shape {result_df.shape}.")
    logger.debug(f"--- DataFrame Head (youtube_process_node) ---\n{result_df.head(3).to_string()}")
    # --- 로깅 추가 끝 ---

    # 2. 키워드 추출 워크플로우 실행 (DataFrame의 JSON을 직접 전달)
    logger.info("Step YT.2: Calling run_keyword_extraction tool with DataFrame JSON...")
    
    safe_query = "".join(c for c in crawling_query if c.isalnum())
    current_date = datetime.now().strftime("%Y%m%d")
    base_export_path = os.path.join("downloads", f"youtube_{safe_query}_{current_date}_{days_to_crawl}d")

    keyword_result_str = run_keyword_extraction.invoke({
        "input_df_json": result_json, # 크롤링 결과 JSON을 직접 전달
        "base_export_path": base_export_path,
        "slots": state.get("slots", {}),
    })

    try:
        keyword_result = json.loads(keyword_result_str)
        if keyword_result.get("status") == "error":
             return {"error": keyword_result.get("message")}
        
        frequencies_df_json = keyword_result.get("frequencies_df_json")
        logger.info("--- YouTube Processing Subgraph Finished ---")
        
        return {"frequencies_df_json": frequencies_df_json}

    except json.JSONDecodeError:
        error_message = "Could not parse JSON from keyword extraction tool."
        logger.error(error_message)
        return {"error": error_message}



# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("youtube_process", youtube_process_node)
workflow.set_entry_point("youtube_process")
workflow.add_edge("youtube_process", END) # 이 서브그래프의 실행이 끝나면 워크플로우의 다음 단계로 넘어감
youtube_process_graph = workflow.compile()