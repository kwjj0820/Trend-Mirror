# app/agents/workflow.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import TMState
from app.agents.subgraphs.strategy_build import strategy_build_graph
from app.agents.subgraphs.insight_extract import insight_extract_graph
from app.agents.subgraphs.strategy_gen import strategy_gen_graph
from app.agents.subgraphs.youtube_process import youtube_process_graph
from app.core.logger import logger


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


# 메인 그래프 정의
workflow = StateGraph(TMState)

# 서브그래프들을 노드로 등록
workflow.add_node("strategy_build", strategy_build_graph)
workflow.add_node("insight_extract", insight_extract_graph)
workflow.add_node("youtube_process", youtube_process_graph) # 신규 노드 추가
workflow.add_node("strategy_gen", strategy_gen_graph)

# 흐름 정의
workflow.set_entry_point("strategy_build")

workflow.add_conditional_edges(
    "strategy_build",
    router_node,
    {
        "insight_extract": "insight_extract",
        "youtube_process": "youtube_process", # 신규 경로 추가
        "strategy_gen": "strategy_gen",
        END: END
    }
)

workflow.add_edge("insight_extract", "strategy_gen")
workflow.add_edge("youtube_process", "strategy_gen") # 신규 경로 추가
workflow.add_edge("strategy_gen", END)

# 체크포인터 (대화 문맥 기억)
memory = MemorySaver()
super_graph = workflow.compile(checkpointer=memory)