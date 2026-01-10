# app/agents/subgraphs/insight_extract.py
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from app.agents.state import TMState
from app.agents.tools import download_file, parse_pdf_to_markdown
from app.repository.client.search_client import SerperSearchClient
from app.service.vector_service import VectorService
from app.agents.utils import rerank_llm_judge
from app.core.logger import logger
import os

# Repository & Client 인스턴스
search_client = SerperSearchClient()


def insight_extract_node(state: TMState, config: RunnableConfig):
    user_input = state["user_input"]
    slots = state.get("slots", {})

    # 1. 검색 쿼리 생성 (노트북 로직 간소화)
    # 실제로는 LLM을 한번 더 호출하여 정교한 쿼리를 만들 수도 있습니다.
    query = f"{user_input} {slots.get('goal', 'trend')} filetype:pdf"

    logger.info(f"[InsightExtract] Searching for: {query}")
    search_results = search_client.search(query, num=3)  # 속도를 위해 3개만

    downloaded_paths = []

    # 2. PDF 다운로드 및 처리 루프
    # Config에서 VectorService 의존성 주입 받기
    vector_service: VectorService = config["configurable"].get("vector_service")

    for item in search_results:
        link = item.get("link")
        if not link: continue

        # 2-1. 다운로드
        logger.info(f"[InsightExtract] Downloading: {link}")
        # Tool 직접 호출 방식
        pdf_path = download_file.invoke({"url": link})

        if str(pdf_path).startswith("Error"):
            logger.warning(f"Download failed: {pdf_path}")
            continue

        downloaded_paths.append(pdf_path)

        # 2-2. 파싱 (Upstage API)
        logger.info(f"[InsightExtract] Parsing PDF...")
        md_text = parse_pdf_to_markdown.invoke({"pdf_path": pdf_path})

        if str(md_text).startswith("Error"):
            logger.warning(f"Parsing failed: {md_text}")
            continue

        # 2-3. 청킹 (Chunking) - 단순화하여 문단 단위 분리
        # 노트북의 split_markdown_to_chunks 로직 대체
        chunks = [p for p in md_text.split("\n\n") if len(p) > 50]

        # 2-4. 벡터 DB 저장
        if vector_service and chunks:
            logger.info(f"[InsightExtract] Saving {len(chunks)} chunks to DB")
            metas = [{"source": link, "title": item.get("title")} for _ in chunks]
            vector_service.add_documents(documents=chunks, metadatas=metas)

    # 3. RAG (검색)
    logger.info("[InsightExtract] Retrieving from DB...")
    # slots 정보를 포함하여 검색 품질 향상
    retrieval_query = f"{user_input} {slots.get('region', '')}"

    # VectorService를 통해 검색 (반환값은 List[Dict])
    if vector_service:
        retrieved_raw = vector_service.search(retrieval_query, n_results=15)
    else:
        retrieved_raw = []

    # 4. Rerank (LLM Judge)
    logger.info(f"[InsightExtract] Reranking {len(retrieved_raw)} items...")
    reranked = rerank_llm_judge(user_input, retrieved_raw, top_k=5)

    return {
        "search_results": search_results,
        "downloaded_files": downloaded_paths,
        "retrieved": retrieved_raw,
        "reranked": reranked
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("insight_extract", insight_extract_node)
workflow.set_entry_point("insight_extract")
workflow.add_edge("insight_extract", END)
insight_extract_graph = workflow.compile()