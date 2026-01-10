from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.agents.utils import clean_and_parse_json
from app.core.logger import logger

# 노트북의 시스템 프롬프트 이식
BUILD_SYSTEM_PROMPT = """You are the StrategyBuildAgent for TrendMirror.
Your job is to analyze the user's input and determine the intent.

1. Intent Classification:
   - "trendmirror": If the user wants to analyze trends, market research, or create a strategy report.
   - "chitchat": If the user is just saying hello or asking general questions unrelated to trend analysis.

2. Slot Extraction (only for 'trendmirror'):
   - region: Target region (default: "Global" or "KR")
   - period_days: Analysis period in days (default: 30)
   - channels: Target channels (e.g., "Youtube", "Instagram", "Blog")
   - goal: The specific goal (e.g., "trend_food", "marketing_strategy")

Output strictly in JSON format:
{
  "intent": "trendmirror" | "chitchat",
  "slots": {
    "region": "...",
    "period_days": 30,
    "channels": [],
    "goal": "..."
  },
  "cache_key": "generated_key_string"
}
"""


def strategy_build_node(state: TMState):
    user_input = state["user_input"]
    solar = get_solar_chat()

    messages = [
        SystemMessage(content=BUILD_SYSTEM_PROMPT),
        HumanMessage(content=user_input)
    ]

    logger.info(f"[StrategyBuild] Analyzing intent for: {user_input}")
    response = solar.invoke(messages)
    parsed = clean_and_parse_json(response.content)

    # [수정 포인트 1] 파싱 실패 시 기본 에러 메시지 반환
    if not parsed:
        logger.error("[StrategyBuild] Failed to parse JSON")
        return {
            "intent": "chitchat",
            "final_answer": "죄송합니다. 의도를 정확히 파악하지 못했습니다. 트렌드 분석을 원하시면 주제를 말씀해 주세요."
        }

    intent = parsed.get("intent")
    logger.info(f"[StrategyBuild] Result: {parsed}")

    # [수정 포인트 2] Chitchat인 경우 안내 메시지(final_answer) 추가
    if intent == "chitchat":
        return {
            "intent": "chitchat",
            "final_answer": "안녕하세요! 저는 트렌드 분석 전문가 TrendMirror입니다. 👋\n분석하고 싶은 주제(예: '요즘 한국 유행 음식')를 말씀해 주시면 리포트를 작성해 드릴게요!"
        }

    # TrendMirror 인텐트인 경우 기존 로직 유지
    return {
        "intent": intent,
        "slots": parsed.get("slots", {}),
        "cache_key": parsed.get("cache_key"),
        "cache_hit": False
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("strategy_build", strategy_build_node)
workflow.set_entry_point("strategy_build")
workflow.add_edge("strategy_build", END)
strategy_build_graph = workflow.compile()