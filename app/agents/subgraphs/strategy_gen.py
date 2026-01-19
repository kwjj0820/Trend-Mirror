from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.core.logger import logger
from app.service.vector_service import VectorService
import datetime
import os
import pandas as pd

# [System Prompt] English Version - Senior Consultant Persona (Emoji-free)
GEN_SYSTEM_PROMPT = """You are a Senior Market Strategy Consultant. 
Your goal is to synthesize a high-quality trend report by balancing internal SNS data with external market research.

[CRITICAL: ANTI-HALLUCINATION AND GROUNDING]
1. Fact-Based Only: Analyze based strictly on the provided Internal Data and External Web Data.
2. Handle Incomplete Info: If data for a specific keyword or trend is missing, explicitly state: Information for this keyword is insufficient for analysis and has been excluded. Do not invent information.
3. Balanced Perspective: Maintain a neutral stance by providing an equal balance between positive opportunities and critical risks or limitations.

[REPORT STRUCTURE]
1. Executive Summary: Key takeaways of the report.
2. Internal SNS Trend Analysis: Keywords and detailed consumer reactions.
3. Market Context: External news and professional market analysis via Tavily.
4. Sustainability and Critical Review: Analysis of market saturation, risks, and whether the trend is a fad or long-term.
5. Strategic Action Plan: Data-driven strategic suggestions.

Language: Korean (Natural and professional)
Format: Structured Markdown
Note: Do not use emojis or decorative icons in the output.
"""

def build_daily_sentiment_series(docs, start_date, end_date):
    if not docs:
        return []

    records = []
    for doc in docs:
        ts = doc.get("published_at")
        sentiment = doc.get("sentiment")
        if ts and sentiment:
            try:
                dt = datetime.datetime.fromtimestamp(float(ts))
                records.append({"date": pd.Timestamp(dt).normalize(), "sentiment": sentiment})
            except (ValueError, TypeError):
                continue

    if not records:
        return []

    df = pd.DataFrame(records)
    df_pivot = df.groupby(["date", "sentiment"]).size().unstack(fill_value=0)

    for s in ["positive", "neutral", "negative"]:
        if s not in df_pivot.columns:
            df_pivot[s] = 0

    full_date_range = pd.date_range(start=start_date, end=end_date, freq="D").normalize()
    df_pivot = df_pivot.reindex(full_date_range, fill_value=0)
    df_pivot = df_pivot[["positive", "neutral", "negative"]]

    daily_sentiments = df_pivot.reset_index().rename(columns={"index": "date"})
    daily_sentiments["date"] = daily_sentiments["date"].dt.strftime("%Y-%m-%d")
    return daily_sentiments.to_dict("records")


def strategy_gen_node(state: TMState, config: RunnableConfig):
    logger.info("--- [4] Strategy Generation Node: Hybrid Search & Analysis ---")

    # 1. Configuration and Data Loading
    vector_service: VectorService = config["configurable"].get("vector_service")
    user_input = state["user_input"]
    slots = state.get("slots", {})
    category = slots.get('search_query', user_input)
    period_days = slots.get("period_days", 30)
    sns = "youtube"
    end_date_dt = datetime.datetime.now()
    start_date_dt = end_date_dt - datetime.timedelta(days=period_days)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")

    # 2. Refined Keyword Filtering
    raw_keywords_data = vector_service.get_keyword_frequencies(category=category, sns=sns, n_results=20)
    keyword_freq_data = vector_service.get_keyword_frequencies(
        category=category,
        sns=sns,
        n_results=10,
        start_date=start_date_str,
        end_date=end_date_str,
    )
    all_docs = vector_service.get_documents_for_period(
        category=category,
        sns=sns,
        start_date=start_date_str,
        end_date=end_date_str,
    )
    daily_sentiments_for_frontend = build_daily_sentiment_series(
        all_docs,
        start_date_dt,
        end_date_dt,
    )

    clean_category = category.replace(" ", "").lower()
    stopwords = ["추천", "영상", "인기", "최근", "정보", "관련", "유튜브", "내용", "조회수", "순위", "가지", "방법", "꿀팁", "이유"]

    filtered_keywords = []
    for item in raw_keywords_data:
        kw = item['keyword'].strip()
        kw_clean = kw.lower().replace(" ", "")

        if kw_clean == clean_category or len(kw) < 2 or any(stop in kw for stop in stopwords):
            continue
        filtered_keywords.append(kw)

    final_keywords = filtered_keywords[:5]
    logger.info(f"Filtered Keywords for analysis: {final_keywords}")

    if not final_keywords:
        logger.warning("No meaningful keywords found after filtering. Using category name.")
        final_keywords = [category]

    # 3. Hybrid Context Collection
    db_context = ""
    seen_docs = set()

    for kw in final_keywords:
        retrieval_query = f"{category} {kw} consumer response and market trend details"
        kw_docs = vector_service.search(query=retrieval_query, n_results=2)

        for doc in kw_docs:
            text = doc.get('text', '').strip()
            if text and text not in seen_docs:
                db_context += f"- [Keyword: {kw}] {text}\n"
                seen_docs.add(text)

    # 3-2. Tavily Web Search
    web_context = ""
    try:
        tavily = TavilySearchResults(max_results=4)
        web_search_query = f"{category} {' '.join(final_keywords[:2])} market outlook and risks"
        web_results = tavily.invoke({"query": web_search_query})
        web_context = "\n## External Market Research (Tavily):\n"
        for res in web_results:
            web_context += f"- [{res['url']}]: {res['content']}\n"
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        web_context = "\n(External market data unavailable)\n"

    # 4. LLM Report Generation
    context_str = f"## Analysis Keywords: {', '.join(final_keywords)}\n\n"
    context_str += "## Internal Data (SNS/DB):\n" + (db_context if db_context else "No internal data found.\n")
    context_str += web_context

    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"""
[User Request]: "{user_input}"
[Target Category]: {category}
[Provided Context]:
{context_str}
[Final Instructions]:
1. Synthesize a fact-based report by comparing Internal Data and External Market Research.
2. Focus your analysis on the specific keywords: {', '.join(final_keywords)}.
3. Ensure all identified keywords are discussed.
4. Maintain a balance between positive opportunities and critical risks.
5. No Hallucinations: If data is missing, explicitly state it is unavailable.
""")
    ]

    response = solar.invoke(messages)
    report_content = response.content

    # -----------------------------------------------------------
    # 5. PDF Generation: reports/ 폴더에 직접 저장
    # -----------------------------------------------------------
    current_date = datetime.datetime.now().strftime("%Y%m%d")

    category = "".join(c for c in category if c.isalnum())
    pdf_filename = f"report_{category}_{period_days}d_{current_date}.pdf"

    from app.agents.tools import generate_report_pdf_v2_tool
    pdf_path = generate_report_pdf_v2_tool.invoke({"content": report_content, "filename": pdf_filename})

    logger.info(f"Strategy Generation Workflow Complete. PDF saved at: {pdf_path}")

    return {
        "final_answer": report_content,
        "pdf_path": str(pdf_path),
        "keyword_frequencies": keyword_freq_data,
        "daily_sentiments": daily_sentiments_for_frontend,
    }


# Graph Construction
workflow = StateGraph(TMState)
workflow.add_node("strategy_gen", strategy_gen_node)
workflow.set_entry_point("strategy_gen")
workflow.add_edge("strategy_gen", END)
strategy_gen_graph = workflow.compile()
