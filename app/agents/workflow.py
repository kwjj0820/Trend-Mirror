# app/agents/workflow.py
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from app.agents.state import TMState
from app.agents.subgraphs.strategy_build import strategy_build_graph
from app.agents.subgraphs.strategy_gen import strategy_gen_node # 이름 변경
from app.agents.subgraphs.youtube_process import youtube_process_graph
from app.core.logger import logger
from app.service.sync_service import SyncService
from app.service.vector_service import VectorService


def cache_check_node(state: TMState, config: RunnableConfig):
    """
    DB 데이터 존재 여부를 확인하고, 그 결과에 따라 state를 업데이트합니다.
    """
    logger.info("--- (CACHE) Entered Cache Check Node ---")
    vector_service: VectorService = config["configurable"].get("vector_service")
    slots = state.get("slots", {})
    search_query = slots.get("search_query")
    period_days = slots.get("period_days", 7)

    if not vector_service or not search_query:
        logger.warning("VectorService or search_query not found. Skipping cache check.")
        return {"cache_hit": False}

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    cache_check_result = vector_service.check_data_existence(
        category=search_query,
        start_date=start_date_str,
        end_date=end_date_str
    )
    
    cache_status = cache_check_result.get("status")
    logger.info(f"DB Cache Check Status for '{search_query}': {cache_status}")

    if cache_status == "FULL":
        logger.info("Cache Hit (FULL): Data exists in DB. Skipping crawling and analysis.")
        return {"cache_hit": True}
    
    elif cache_status == "PARTIAL":
        logger.info("Cache Hit (PARTIAL): Partially exists. Adjusting crawl period.")
        new_start_str = cache_check_result.get("new_start")
        new_end_str = cache_check_result.get("new_end")
        
        new_start_dt = datetime.strptime(new_start_str, "%Y-%m-%d")
        new_end_dt = datetime.strptime(new_end_str, "%Y-%m-%d")
        new_period_days = (new_end_dt - new_start_dt).days + 1

        if new_period_days <= 0:
            logger.info("No new data to crawl. Treating as cache hit.")
            return {"slots": slots, "cache_hit": True}

        slots["period_days"] = new_period_days
        logger.info(f"Updated period_days for partial crawling: {new_period_days} days")
        return {"slots": slots, "cache_hit": False}

    return {"cache_hit": False}


def router_node(state: TMState):
    """분기 노드: 캐시 히트 여부와 의도에 따라 다음 단계를 결정"""
    intent = state.get("intent")
    if intent == "chitchat":
        logger.info("[Router] Intent is chitchat. Routing to END.")
        return END

    if state.get("cache_hit"):
        logger.info("[Router] Cache Hit! Skipping to Analysis.")
        # 캐시가 있으면 데이터 수집 및 분석을 건너뛰고 바로 분석으로 이동
        return "analysis"

    logger.info("[Router] Cache Miss. Routing to Data Collection (youtube_process).")
    return "youtube_process"


def sync_db_node(state: TMState, config: RunnableConfig):
    """키워드 빈도수 데이터를 DB와 동기화하는 노드"""
    logger.info("--- (DB) Entered Sync DB Node ---")
    sync_service: SyncService = config["configurable"].get("sync_service")
    frequencies_df_json = state.get("frequencies_df_json")
    slots = state.get("slots")

    if not sync_service or not frequencies_df_json or not slots:
        logger.warning("Skipping DB sync due to missing service, data, or slots.")
        return {}

    try:
        df_frequencies = pd.read_json(StringIO(frequencies_df_json), orient='split')
        sync_service.sync_dataframe_to_db(df=df_frequencies, slots=slots)
    except Exception as e:
        logger.error(f"Failed to sync data to DB in sync_db_node: {e}", exc_info=True)

    logger.info("--- Sync DB Node Finished ---")
    return {}


# 메인 그래프 정의
workflow = StateGraph(TMState)

# 노드 등록
workflow.add_node("strategy_build", strategy_build_graph)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("youtube_process", youtube_process_graph)
workflow.add_node("sync_db", sync_db_node)
workflow.add_node("analysis", strategy_gen_node) # 이름 변경

# 엣지(흐름) 정의
workflow.set_entry_point("strategy_build")
workflow.add_edge("strategy_build", "cache_check")

# 캐시 체크 후 분기
workflow.add_conditional_edges(
    "cache_check",
    router_node,
    {
        "youtube_process": "youtube_process", # Cache Miss
        "analysis": "analysis",   # Cache Hit
        END: END
    }
)

# 데이터 수집 및 분석 후 시각화로 이어지는 기본 흐름
workflow.add_edge("youtube_process", "sync_db")
workflow.add_edge("sync_db", "analysis")
workflow.add_edge("analysis", END)

# 체크포인터
memory = MemorySaver()
super_graph = workflow.compile(checkpointer=memory)
