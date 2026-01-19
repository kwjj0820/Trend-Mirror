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
   - period_days: Analysis period in days (default: 7) 해당 사용자가 지난 몇 일간의 데이터를 원하는 지 분석해야 합니다.
   - pages: Number of pages to crawl for YouTube (default: 10)
   - channels: Target channels (e.g., "Youtube", "Instagram", "Blog")
   - domain: The specific topic for trend analysis (e.g., "trend_food", "marketing_strategy", "카페 음식")
   - search_query: 'domain'이 속하는 가장 넓은 범위의 **핵심 카테고리 또는 유형**을 추출하세요.
        이는 유튜브 크롤링 검색 쿼리로 사용됩니다.
        `domain`의 핵심적인 의미를 유지하면서도 검색 범위를 확장하여 더 많은 관련 데이터를 가져오는 데 목적이 있습니다.
        최대한 단순하고 한 단어 형태에 가까워야 합니다.
        또한, 단어의 양끝에 띄어쓰기가 존재하지 않도록 만드세요.
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
  }
}
"""


def strategy_build_node(state: TMState):
    """
    사용자 입력을 분석하여 의도를 파악하고, 캐시 존재 여부를 확인하여
    전체 워크플로우를 실행할지, 아니면 캐시된 결과를 즉시 반환할지 결정합니다.
    """
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

    if not parsed:
        logger.error("Failed to parse JSON from LLM response.")
        return { "intent": "chitchat", "final_answer": "죄송합니다. 의도를 정확히 파악하지 못했습니다." }

    intent = parsed.get("intent")
    slots = parsed.get("slots", {})
    logger.info(f"Intent analysis complete. Parsed parameters: {json.dumps(parsed, ensure_ascii=False)}")

    if intent == "chitchat":
        logger.info("--- Strategy Builder Subgraph Finished (Chitchat) ---")
        return {
            "intent": "chitchat",
            "final_answer": "안녕하세요! 저는 트렌드 분석 전문가 TrendMirror입니다. 👋\n분석하고 싶은 주제(예: '요즘 한국 유행 음식')를 말씀해 주시면 리포트를 작성해 드릴게요!"
        }

    # 캐시 로직이 AgentService로 이동함에 따라 기존 캐시 확인 로직 제거.
    # 항상 전체 워크플로우를 시작하도록 설정.
    logger.info("Proceeding with full analysis workflow.")
    logger.info("--- Strategy Builder Subgraph Finished ---")
    return {
        "intent": intent,
        "slots": slots,
        "cache_hit": False # 항상 False로 설정하여 전체 분석 시작
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("strategy_build", strategy_build_node)
workflow.set_entry_point("strategy_build")
workflow.add_edge("strategy_build", END)
strategy_build_graph = workflow.compile()