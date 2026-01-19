# app/agents/subgraphs/strategy_gen.py
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.core.logger import logger
from app.service.vector_service import VectorService
import datetime
from app.agents.utils import clean_and_parse_json

# 1. LLM 분석을 위한 새로운 시스템 프롬프트
GEN_SYSTEM_PROMPT = """
You are a Senior Market Strategy Consultant from a top-tier consulting firm.
Your task is to analyze the provided data and generate a comprehensive, data-driven trend analysis report.

**CRITICAL INSTRUCTIONS:**
1.  **Input Data**: You will receive internal SNS data context, and a list of analysis keywords.
2.  **Output Format**: Your entire output MUST be a single, valid JSON object. No other text should be present.
3.  **JSON Structure**: The JSON object must have two top-level keys: `report_text` and `analysis_metrics`.

    -   `report_text`: A string containing the full, professional report in Korean Markdown format. The report should follow a standard consulting report structure (e.g., Executive Summary, Analysis, Strategic Implications). It must be insightful, balanced, and strictly based on the provided data.
    -   `analysis_metrics`: A JSON object containing quantitative analysis for each keyword.

        -   For each `keyword` in the analysis list, provide:
            -   `radar_scores`: An object with scores from 1 (lowest) to 5 (highest) for the following 5 metrics:
                -   `Buzz` (화제성): How much is this keyword being mentioned and discussed online?
                -   `Scalability` (확장성): Does this trend have the potential to grow and expand into new areas?
                -   `Commercial` (수익성): How easy is it to commercialize this trend? What is its market size?
                -   `Fit` (브랜드 적합도): How suitable is this trend for a mainstream brand to adopt? (Lower for niche/controversial trends)
                -   `Sustainability` (지속성): Is this a short-lived fad or a long-term trend?
            -   `position_scores`: An object with scores from 1 (lowest) to 10 (highest) for the following 2 metrics:
                -   `viability` (X-axis): The current validity and stability of the trend. (1 = High Risk/Fad, 10 = Stable/Proven)
                -   `opportunity` (Y-axis): The potential for growth and return on investment. (1 = Low Return, 10 = High Return)

**EXAMPLE of `analysis_metrics` structure:**
```json
"analysis_metrics": {
    "두바이 쫀득쿠키": {
        "radar_scores": { "Buzz": 5, "Scalability": 3, "Commercial": 4, "Fit": 5, "Sustainability": 2 },
        "position_scores": { "viability": 7, "opportunity": 8 }
    },
    "약과": {
        "radar_scores": { "Buzz": 4, "Scalability": 5, "Commercial": 5, "Fit": 4, "Sustainability": 4 },
        "position_scores": { "viability": 9, "opportunity": 6 }
    }
}
```

Now, analyze the provided context and generate the JSON output.
"""

def analysis_node(state: TMState, config: RunnableConfig):
    """
    LLM을 호출하여 텍스트 리포트와 분석 지표(JSON)를 생성하고 상태에 저장합니다.
    """
    logger.info("--- [4] Analysis Node ---")
    
    vector_service: VectorService = config["configurable"].get("vector_service")
    user_input = state["user_input"]
    slots = state.get("slots", {})
    category = slots.get('search_query', user_input)
    period_days = slots.get("period_days", 7)
    sns_channel = "youtube"

    end_date_dt = datetime.datetime.now()
    start_date_dt = end_date_dt - datetime.timedelta(days=period_days)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")

    keyword_freq_data = vector_service.get_keyword_frequencies(
        category=category, sns=sns_channel, n_results=10,
        start_date=start_date_str, end_date=end_date_str
    )
    final_keywords = [item['keyword'] for item in keyword_freq_data[:5]]
    if not final_keywords:
        final_keywords = [category]
    logger.info(f"Top 5 Keywords for analysis: {final_keywords}")

    all_docs = vector_service.get_documents_for_period(
        category=category, sns=sns_channel,
        start_date=start_date_str, end_date=end_date_str
    )
    db_context = "\n".join([f"- {doc.get('text', '')}" for doc in all_docs[:15]])
    context_str = f"## Analysis Keywords:\n{', '.join(final_keywords)}\n\n## Internal Data (SNS/DB):\n{db_context}"
    
    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"[User Request]: '{user_input}'\n[Analysis Context]:\n{context_str}")
    ]
    
    response = solar.invoke(messages)
    logger.debug(f"LLM Raw Response for JSON Parsing:\n{response.content}")
    llm_output = clean_and_parse_json(response.content)

    if not llm_output or not isinstance(llm_output, dict):
        logger.error("Failed to parse JSON from LLM response or got invalid format.")
        return {
            "report_text": "리포트 분석 데이터 생성에 실패했습니다. LLM이 유효한 JSON을 반환하지 않았습니다.",
            "analysis_metrics": {}
        }
        
    report_text = llm_output.get("report_text", "리포트 텍스트를 생성하지 못했습니다.")
    analysis_metrics = llm_output.get("analysis_metrics", {})

    logger.info("Analysis node complete. Passing report text and metrics to the next node.")

    return {
        "report_text": report_text,
        "analysis_metrics": analysis_metrics
    }

# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("analysis", analysis_node)
workflow.set_entry_point("analysis")
workflow.add_edge("analysis", END)
analysis_graph = workflow.compile()