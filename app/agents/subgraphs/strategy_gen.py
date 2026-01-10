# app/agents/subgraphs/strategy_gen.py
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.state import TMState
from app.core.llm import get_solar_chat
from app.agents.tools import generate_report_pdf
from app.core.logger import logger

# 노트북의 Gen 프롬프트 이식
GEN_SYSTEM_PROMPT = """You are the StrategyGenAgent.
Using the provided 'Context' (reranked chunks) and user 'Slots', write a comprehensive Trend Report.
The report should include:
1. Executive Summary
2. Key Trends identified
3. Marketing/Business Strategy Suggestion based on the trends
4. Conclusion

Format: Markdown
Language: Korean
"""


def strategy_gen_node(state: TMState):
    user_input = state["user_input"]
    reranked = state.get("reranked", [])

    # 컨텍스트 조립
    context_str = "\n\n".join([f"- {item['text']}" for item in reranked])

    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"User Query: {user_input}\n\nContext:\n{context_str}")
    ]

    logger.info("[StrategyGen] Generating report...")
    response = solar.invoke(messages)
    report_content = response.content

    # PDF 생성 Tool 호출
    pdf_filename = f"report_{state.get('slots', {}).get('goal', 'result')}.pdf"
    pdf_path = generate_report_pdf.invoke({"content": report_content, "filename": pdf_filename})

    logger.info(f"[StrategyGen] Report saved at: {pdf_path}")

    return {
        "final_answer": report_content,
        "final_pdf_path": str(pdf_path)
    }


# 그래프 구성
workflow = StateGraph(TMState)
workflow.add_node("strategy_gen", strategy_gen_node)
workflow.set_entry_point("strategy_gen")
workflow.add_edge("strategy_gen", END)
strategy_gen_graph = workflow.compile()