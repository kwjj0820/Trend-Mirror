# app/agents/subgraphs/insight_extract.py
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from app.agents.state import TMState
from app.agents.tools import (
    download_file,
    parse_pdf_to_markdown,
    youtube_crawling_tool,
    run_keyword_extraction
)
# from app.repository.client.search_client import SerperSearchClient # 삭제
from app.service.vector_service import VectorService
from app.agents.utils import rerank_llm_judge
from app.core.logger import logger
import os

# Repository & Client 인스턴스
# search_client = SerperSearchClient() # 삭제


def insight_extract_node(state: TMState, config: RunnableConfig):
    logger.info("--- (3) Entered Insight Extraction Subgraph ---")
    user_input = state["user_input"]
    slots = state.get("slots", {})
    vector_service: VectorService = config["configurable"].get("vector_service")

    # 웹 검색 및 PDF 처리 로직 삭제됨

    # 1. RAG (검색) - 기존 DB에서만 검색
    retrieval_query = f"{user_input} {slots.get('region', '')}"
    logger.info(f"Step 3.1: Retrieving documents from DB with query: '{retrieval_query}'")
    if vector_service:
        retrieved_raw = vector_service.search(retrieval_query, n_results=15)
        logger.info(f"Retrieved {len(retrieved_raw)} documents.")
    else:
        retrieved_raw = []
        logger.warning("Vector service not available. Skipping retrieval.")

    # 2. Rerank (LLM Judge)
    logger.info(f"Step 3.2: Reranking {len(retrieved_raw)} retrieved documents...")
    reranked = rerank_llm_judge(user_input, retrieved_raw, top_k=5)
    logger.info(f"Reranking complete. Selected {len(reranked)} documents.")
    logger.info("--- Insight Extraction Subgraph Finished ---")

    # 상태 업데이트: search_results, downloaded_files는 더 이상 사용되지 않음
    return {
        "retrieved": retrieved_raw,
        "reranked": reranked
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("insight_extract", insight_extract_node)
workflow.set_entry_point("insight_extract")
workflow.add_edge("insight_extract", END)
insight_extract_graph = workflow.compile()