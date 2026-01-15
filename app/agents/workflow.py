# app/agents/workflow.py
import pandas as pd
from io import StringIO
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from app.agents.state import TMState
from app.agents.subgraphs.strategy_build import strategy_build_graph
from app.agents.subgraphs.insight_extract import insight_extract_graph
from app.agents.subgraphs.strategy_gen import strategy_gen_graph
from app.agents.subgraphs.youtube_process import youtube_process_graph
from app.core.logger import logger
from app.service.sync_service import SyncService


def router_node(state: TMState):
    """Build 단계 결과에 따른 분기 처리"""
    intent = state.get("intent")
    if intent == "chitchat":
        logger.info("[Router] Routing to END (Chitchat)")
        return END

    if state.get("cache_hit"):
        logger.info("[Router] Cache Hit! Skipping data processing.")
        return "strategy_gen"

    # Cache miss인 경우, 항상 youtube_process 에이전트로 라우팅
    logger.info("[Router] No cache hit. Routing to YouTube Processing Subgraph.")
    return "youtube_process"


def sync_db_node(state: TMState, config: RunnableConfig):
    """키워드 빈도수 데이터를 DB와 동기화하는 노드"""
    logger.info("--- (DB) Entered Sync DB Node ---")
    sync_service: SyncService = config["configurable"].get("sync_service")
    frequencies_df_json = state.get("frequencies_df_json")
    slots = state.get("slots")

    if not sync_service:
        logger.warning("SyncService not found in config. Skipping DB sync.")
        return {}
    
    if not frequencies_df_json:
        logger.warning("Frequencies DataFrame JSON not found in state. Skipping DB sync.")
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

# 서브그래프들을 노드로 등록
workflow.add_node("strategy_build", strategy_build_graph)
workflow.add_node("insight_extract", insight_extract_graph)
workflow.add_node("youtube_process", youtube_process_graph)
workflow.add_node("sync_db", sync_db_node) # 새 노드 추가
workflow.add_node("strategy_gen", strategy_gen_graph)

# 흐름 정의
workflow.set_entry_point("strategy_build")

workflow.add_conditional_edges(
    "strategy_build",
    router_node,
    {
        "insight_extract": "insight_extract",
        "youtube_process": "youtube_process",
        "strategy_gen": "strategy_gen",
        END: END
    }
)

workflow.add_edge("insight_extract", "strategy_gen")
# 워크플로우 흐름 수정
workflow.add_edge("youtube_process", "sync_db")
workflow.add_edge("sync_db", "strategy_gen")
workflow.add_edge("strategy_gen", END)

# 체크포인터 (대화 문맥 기억)
memory = MemorySaver()
super_graph = workflow.compile(checkpointer=memory)