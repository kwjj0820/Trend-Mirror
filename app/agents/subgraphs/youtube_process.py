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
    1. 유튜브 크롤링 도구 호출 (또는 우회)
    2. 키워드 추출 워크플로우 호출
    """
    logger.info("--- (YT) Entered YouTube Processing Subgraph ---")
    user_input = state.get("user_input", "")

    bypass_crawling = config["configurable"].get("bypass_crawling", False)
    mock_csv_path = "scripts/food_youtube_analysis.csv" # 임시 우회용 CSV 파일

    if bypass_crawling:
        logger.warning(f"Step YT.1: Bypassing youtube_crawling_tool. Using mock CSV: {mock_csv_path}")
        crawl_result_str = f"유튜브 검색 결과가 다음 경로에 CSV 파일로 저장되었습니다: {mock_csv_path}"
    else:
        # 1. 유튜브 데이터 크롤링
        logger.info("Step YT.1: Calling youtube_crawling_tool...")
        query = state.get("slots", {}).get("goal", user_input)
        crawl_result_str = youtube_crawling_tool.invoke({"query": query})
        logger.info(f"Crawling tool returned: {crawl_result_str}")

    # Tool 결과에서 CSV 경로 추출
    try:
        csv_path = crawl_result_str.rsplit(": ", 1)[1].strip()
    except IndexError:
        error_message = "Failed to find a valid CSV path from youtube_crawling_tool output."
        logger.error(error_message)
        return {"error": error_message}

    if not ".csv" in csv_path:
        error_message = f"Extracted path '{csv_path}' does not appear to be a CSV file."
        logger.error(error_message)
        return {"error": error_message}
    
    # 실제 파일 존재 여부 확인 (특히 우회 모드에서 중요)
    if not os.path.exists(csv_path):
        error_message = f"CSV file not found at '{csv_path}'. Please ensure it exists for bypass mode."
        logger.error(error_message)
        return {"error": error_message}
    
    logger.info(f"Extracted CSV path: {csv_path}")

    # 2. 키워드 추출 워크플로우 실행
    logger.info("Step YT.2: Calling run_keyword_extraction tool...")
    keyword_result_str = run_keyword_extraction.invoke({"csv_path": csv_path, "slots": state.get("slots", {}), "config": config})
    logger.info(f"Keyword extraction tool returned: {keyword_result_str}")

    try:
        keyword_result = json.loads(keyword_result_str)
        if keyword_result.get("status") == "error":
             return {"error": keyword_result.get("message")}
        
        output_path = keyword_result.get("output_path")
        logger.info("--- YouTube Processing Subgraph Finished ---")
        
        return {"output_path": output_path}

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
