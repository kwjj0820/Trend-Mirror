from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.agents.utils import clean_and_parse_json
from app.core.logger import logger
import json # Import json

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
   - domain: The specific topic for trend analysis (e.g., "trend_food", "marketing_strategy", "카페 음식")
   - search_query: 'domain'이 속하는 가장 넓은 범위의 **핵심 카테고리 또는 유형**을 추출하세요. 이는 유튜브 크롤링 검색 쿼리로 사용됩니다. `domain`의 핵심적인 의미를 유지하면서도 검색 범위를 확장하여 더 많은 관련 데이터를 가져오는 데 목적이 있습니다. 최대한 단순하고 한 단어 형태에 가까워야 합니다.
     (예: domain이 "카페 신메뉴 추천"이면 search_query는 "디저트" 또는 "음료", domain이 "여름 패션 트렌드"이면 "패션", domain이 "아이돌 팬덤 문화"이면 "아이돌" 또는 "팬덤" -> "엔터테인먼트"는 너무 광범위함)

Output strictly in JSON format:
{
  "intent": "trendmirror" | "chitchat",
  "slots": {
    "region": "...",
    "period_days": 30,
    "channels": [],
    "domain": "...",
    "search_query": "..."
  },
  "cache_key": "generated_key_string"
}
"""


def strategy_build_node(state: TMState):
    logger.info("--- (1) Entered Strategy Builder Subgraph ---")
    user_input = state["user_input"]
    solar = get_solar_chat()

    messages = [
        SystemMessage(content=BUILD_SYSTEM_PROMPT),
        HumanMessage(content=f"User Input: '{user_input}'")
    ]

    logger.info(f"Analyzing user input: '{user_input}'")
    logger.info("Calling LLM to analyze user intent...")
    response = solar.invoke(messages)
    parsed = clean_and_parse_json(response.content)

    # [수정 포인트 1] 파싱 실패 시 기본 에러 메시지 반환
    if not parsed:
        logger.error("Failed to parse JSON from LLM response.")
        return {
            "intent": "chitchat",
            "final_answer": "죄송합니다. 의도를 정확히 파악하지 못했습니다. 트렌드 분석을 원하시면 주제를 말씀해 주세요."
        }

    intent = parsed.get("intent")
    logger.info(f"Intent analysis complete. Parsed parameters: {json.dumps(parsed, ensure_ascii=False)}")
    logger.info("--- Strategy Builder Subgraph Finished ---")

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