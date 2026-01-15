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

# [시스템 프롬프트] 전문가 페르소나 및 할루시네이션 방지 규칙 설정
GEN_SYSTEM_PROMPT = """You are a Senior Market Strategy Consultant. 
Your goal is to synthesize a high-quality trend report by balancing internal SNS data with external market research.

[CRITICAL: ANTI-HALLUCINATION & GROUNDING]
1. **Fact-Based Only**: Analyze based strictly on the provided 'Internal Data' and 'External Web Data'. 
2. **Handle Incomplete Info**: If data for a specific keyword or trend is missing, explicitly state: "해당 키워드에 대한 구체적인 데이터가 부족하여 분석에서 제외됨." Do not make up information.
3. **Balanced Perspective**: Ensure a 50:50 balance between positive opportunities and critical risks/limitations.

[REPORT STRUCTURE]
- Executive Summary: Key takeaways.
- Deep Dive: Internal SNS trend analysis (Keywords, consumer reactions).
- Market Context: External news and professional market analysis (via Tavily).
- **Sustainability & Critical Review**: Is this a fad or a trend? Analysis of market saturation and risks.
- Action Plan: Strategic suggestions.

Language: Korean (Natural and professional)
Format: Structured Markdown
"""

def strategy_gen_node(state: TMState, config: RunnableConfig):
    logger.info("--- [4] Strategy Generation Node: Hybrid Search & Analysis ---")
    
    # 1. 초기 설정 및 데이터 로드
    vector_service: VectorService = config["configurable"].get("vector_service")
    user_input = state["user_input"]
    slots = state.get("slots", {})
    category = slots.get('search_query', user_input)
    sns = "youtube"
    
    # 2. 지능적 키워드 필터링
    # DB에서 빈도수 높은 키워드를 넉넉히 가져온 후 필터링 진행
    raw_keywords_data = vector_service.get_keyword_frequencies(category=category, sns=sns, n_results=10)
    
    # 필터링: 카테고리명 포함 단어, 무의미한 일반 단어 제외
    stopwords = [category, "추천", "영상", "인기", "최근", "정보", "관련", "유튜브", "내용"]
    filtered_keywords = []
    for item in raw_keywords_data:
        kw = item['keyword']
        # 카테고리명이 키워드에 포함되어 있거나(예: 연예인 뉴스) stopwords에 있으면 제외
        if any(stop in kw for stop in stopwords) or len(kw) < 2:
            continue
        filtered_keywords.append(kw)
    
    final_keywords = filtered_keywords[:5] # 최종 상위 5개 선정
    logger.info(f"Filtered Keywords for analysis: {final_keywords}")

    if not final_keywords:
        logger.warning("No meaningful keywords found after filtering.")
        # 키워드가 없을 경우 카테고리 자체로 진행하거나 에러 반환
        final_keywords = [category]

    # 3. 하이브리드 컨텍스트 수집
    # 3-1. Vector DB 검색 (내부 데이터: 구체적 텍스트 정보)
    db_context = ""
    retrieval_query = f"{category} 트렌드 {', '.join(final_keywords)} 소비자 반응 및 상세 내용"
    retrieved_docs = vector_service.search(query=retrieval_query, n_results=6)
    for doc in retrieved_docs:
        meta = doc.get('meta', {})
        db_context += f"- [핵심단어: {meta.get('keyword')}] {doc.get('text')}\n"

    # 3-2. Tavily 웹 검색 (외부 데이터: 긍정적 기회 + 비평적 리스크)
    web_context = ""
    try:
        tavily = TavilySearchResults(max_results=4)
        # 양면적 분석을 유도하는 검색 쿼리 생성
        search_query = f"{category} {', '.join(final_keywords[:2])} 시장 전망 및 성장 가능성 한계점 리스크"
        logger.info(f"Web Search Query: {search_query}")
        
        web_results = tavily.invoke({"query": search_query})
        web_context = "\n## 외부 시장 리서치 (Tavily):\n"
        for res in web_results:
            web_context += f"- [{res['url']}]: {res['content']}\n"
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        web_context = "\n(외부 시장 데이터를 불러올 수 없습니다.)\n"

    # 4. LLM 리포트 생성
    context_str = f"## 분석 키워드: {', '.join(final_keywords)}\n\n"
    context_str += "## 내부 데이터 (SNS/DB):\n" + (db_context if db_context else "데이터 없음\n")
    context_str += web_context

    solar = get_solar_chat()
    messages = [
        SystemMessage(content=GEN_SYSTEM_PROMPT),
        HumanMessage(content=f"""
[User Request]: "{user_input}"
[Category]: {category}

[Provided Context]:
{context_str}

[Final Instruction]:
1. 제공된 내부 데이터와 외부 시장 데이터를 비교하여 사실에 기반한 리포트를 작성하세요.
2. {category}와 같은 카테고리 이름은 분석의 결과물로 강조하지 말고, 구체적인 트렌드 키워드({', '.join(final_keywords)})에 집중하세요.
3. 긍정적인 정보와 비판적인 정보를 균형 있게 서술하여 독자가 객관적인 판단을 내릴 수 있도록 하세요.
4. 근거 없는 할루시네이션(환각)은 엄격히 금지하며, 데이터가 없는 경우 반드시 '확인 불가'를 명시하세요.
""")
    ]

    logger.info("Calling Solar LLM for final report generation...")
    response = solar.invoke(messages)
    report_content = response.content

    # 5. PDF 생성 및 경로 반환
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    period_days = slots.get("period_days", 30) # 분석 기간(days)을 슬롯에서 가져옴
    
    # 파일명에 분석 기간을 포함하여 캐시 키를 더 명확하게 함
    pdf_filename = f"report_{category}_{period_days}d_{current_date}.pdf"
    
    # 캐시 폴더에 저장하도록 경로 수정
    cache_dir = "cache"
    full_pdf_filename = os.path.join(cache_dir, pdf_filename)
    
    from app.agents.tools import generate_report_pdf
    pdf_path = generate_report_pdf.invoke({"content": report_content, "filename": full_pdf_filename})

    logger.info("--- Strategy Generation Workflow Complete ---")

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