# app/agents/utils.py
import json
import re
import tiktoken
from datetime import datetime
from app.core.llm import get_solar_chat
from langchain_core.messages import SystemMessage, HumanMessage

# 토크나이저 초기화 (전역)
try:
    ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    ENC = None

def get_current_time_str():
    """현재 시간을 문자열로 반환 (Guidebook Step 5.1 참조)"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clean_and_parse_json(text: str):
    """LLM 응답에서 JSON만 추출하여 파싱"""
    try:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match: text = match.group(1)
        else:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match: text = match.group(1)
        return json.loads(text)
    except:
        return None

def count_tokens(text: str) -> int:
    """텍스트 토큰 수 계산"""
    if ENC is None:
        return max(1, len(text) // 4)
    return len(ENC.encode(text))

def truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    """토큰 수 제한에 맞춰 텍스트 자르기"""
    if count_tokens(text) <= max_tokens:
        return text
    if ENC is None:
        return text[: max_tokens * 4]
    ids = ENC.encode(text)
    ids = ids[:max_tokens]
    return ENC.decode(ids)


def rerank_llm_judge(query: str, retrieved_items: list, top_k: int = 5) -> list:
    """
    LLM을 사용하여 검색된 문서의 관련성을 평가하고 상위 k개를 선정합니다.

    """
    solar = get_solar_chat()

    # 노트북의 프롬프트 로직 이식
    candidates_text = ""
    for i, item in enumerate(retrieved_items):
        # 텍스트 길이 제한 (토큰 절약)
        snippet = item['text'][:600]
        candidates_text += f"[{i}] {snippet}\n\n"

    system_prompt = """You are a relevance judge.
Given a User Query and a list of retrieved document chunks, select the top chunks that are most relevant and helpful for answering the query.
Output format: JSON list of indices, e.g. [0, 3, 5]
Select up to 5 indices. If none are relevant, return []."""

    user_prompt = f"Query: {query}\n\nCandidates:\n{candidates_text}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = solar.invoke(messages)

    # JSON 파싱
    import json
    import re
    try:
        # clean_and_parse_json 함수 활용 권장
        text = response.content
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            indices = json.loads(match.group(0))
        else:
            indices = []
    except:
        indices = []

    # 선택된 인덱스에 해당하는 항목만 필터링
    reranked = []
    for idx in indices:
        if isinstance(idx, int) and 0 <= idx < len(retrieved_items):
            reranked.append(retrieved_items[idx])

    return reranked[:top_k]