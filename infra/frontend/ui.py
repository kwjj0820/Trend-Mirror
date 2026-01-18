

import streamlit as st
import json
import httpx
import uuid
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../")) # infra/frontend/ 니까 두 번 올라감
sys.path.append(root_dir)

from pathlib import Path
import time
from app.core.logger import logger

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
HISTORY_PATH = Path("reports") / "question_history.json"

st.set_page_config(
    page_title="TREND MIRROR",
    page_icon="✨",
    layout="wide"
)

st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        width: 100%;
        text-align: left;
        padding: 0.35rem 0.4rem;
        border-radius: 6px;
    }
    section[data-testid="stSidebar"] button:hover {
        background: #f3f4f6 !important;
    }
    section[data-testid="stSidebar"] button:focus {
        outline: none !important;
        box-shadow: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "question_history" not in st.session_state:
    st.session_state.question_history = {}
if "last_pdf_path" not in st.session_state:
    st.session_state.last_pdf_path = None


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


if not st.session_state.question_history:
    st.session_state.question_history = load_history()

if not st.session_state.messages:
    history = st.session_state.question_history
    current_record = history.get(st.session_state.session_id)
    if isinstance(current_record, dict):
        st.session_state.messages = current_record.get("messages", [])


def get_session_record(history: dict, session_id: str) -> dict:
    record = history.get(session_id)
    if isinstance(record, dict):
        record.setdefault("updated_at", 0)
        if not record.get("title") or record.get("title") == "새 대화":
            for msg in record.get("messages", []):
                if msg.get("role") == "user" and msg.get("content"):
                    record["title"] = msg["content"]
                    break
        return record
    # Backward compatibility: older format was a list of questions.
    if isinstance(record, list):
        title = record[0] if record else "새 대화"
        return {"title": title, "messages": [{"role": "user", "content": q} for q in record]}
    return {"title": "새 대화", "messages": [], "updated_at": 0}


def save_session_record(history: dict, session_id: str, title: str, messages: list) -> None:
    if not title:
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                title = msg["content"]
                break
    if not title:
        title = "새 대화"
    history[session_id] = {
        "title": title,
        "messages": messages,
        "updated_at": int(time.time())
    }
    save_history(history)

st.title("TREND_MIRROR")
st.markdown("트렌드 분석 마케팅 report")

with st.sidebar:
    st.header("설정")
    top_cols = st.columns([1, 1], gap="small")
    if top_cols[0].button("새 대화"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()
    if top_cols[1].button("초기화"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.subheader("질문 기록")
    history = st.session_state.question_history
    if history:
        search = st.text_input("검색", key="history_search")
        normalized = {}
        updated = False
        for session_id, record in history.items():
            if not isinstance(record, dict):
                record = get_session_record(history, session_id)
            normalized[session_id] = record
            if history.get(session_id) != record:
                history[session_id] = record
                updated = True
        if updated:
            save_history(history)
        items = sorted(
            normalized.items(),
            key=lambda item: item[1].get("updated_at", 0),
            reverse=True
        )
        if search:
            items = [
                (sid, rec)
                for sid, rec in items
                if search in (rec.get("title") or "") or any(
                    search in (m.get("content") or "")
                    for m in rec.get("messages", [])
                )
            ]
        for session_id, record in items:
            title = record.get("title") or "새 대화"
            cols = st.columns([6, 1])
            if cols[0].button(title, key=f"history-{session_id}"):
                st.session_state.session_id = session_id
                st.session_state.messages = record.get("messages", [])
                st.rerun()
            if cols[1].button("🗑", key=f"delete-{session_id}"):
                history.pop(session_id, None)
                save_history(history)
                if st.session_state.session_id == session_id:
                    st.session_state.messages = []
                    st.session_state.session_id = str(uuid.uuid4())
                st.rerun()
        with st.expander("대화 제목 편집"):
            active_id = st.session_state.session_id
            active_record = get_session_record(history, active_id)
            new_title = st.text_input("대화 제목", value=active_record.get("title") or "", key="edit_title")
            if st.button("제목 저장"):
                save_session_record(history, active_id, new_title.strip() or "새 대화", active_record.get("messages", []))
                st.rerun()
    else:
        st.caption("아직 질문 기록이 없습니다.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def response_generator(prompt, session_id):
    try:
        status = st.status("trend mirror 에이전트가 분석 중입니다....", expanded=True)

        r = httpx.post(
            f"{BACKEND_URL}/api/v1/chat",
            json={
                "query": prompt,
                "thread_id": session_id,
                "bypass_crawling": False
            },
            timeout=None
        )

        if r.status_code != 200:
            status.update(label="오류", state="error")
            yield f"오류 발생 ({r.status_code})\n{r.text}"
            return

        data = r.json()
        answer = data.get("answer") or data.get("result") or str(data)
        pdf_path = data.get("pdf_path")
        if pdf_path:
            st.session_state.last_pdf_path = pdf_path

        status.update(label="분석 완료", state="complete", expanded=False)
        yield answer

    except Exception as e:
        yield f"연결 오류: {str(e)}"


if prompt := st.chat_input("분석하고 싶은 트렌드 주제를 입력해주세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    history = st.session_state.question_history
    record = get_session_record(history, st.session_state.session_id)
    if not record.get("title"):
        record["title"] = prompt
    record_messages = record.get("messages", [])
    record_messages.append({"role": "user", "content": prompt})
    record["messages"] = record_messages
    save_session_record(history, st.session_state.session_id, record.get("title") or prompt, record_messages)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        full_response = st.write_stream(
            response_generator(prompt, st.session_state.session_id)
        )

        pdf_path = st.session_state.last_pdf_path
        
        # --- START OF LOGGING DEBUG BLOCK ---
        logger.info("--- UI DEBUGGING BLOCK START ---")
        logger.info(f"Value of st.session_state.last_pdf_path: '{pdf_path}'")
        if pdf_path:
            pdf_file = Path(pdf_path)
            absolute_path = pdf_file.absolute()
            file_exists = pdf_file.exists()
            
            logger.info(f"Resolved absolute path: '{absolute_path}'")
            logger.info(f"Result of pdf_file.exists(): {file_exists}")
            
            if file_exists:
                logger.info("File exists. Creating download button.")
                st.download_button(
                    label="PDF 다운로드",
                    data=pdf_file.read_bytes(),
                    file_name=pdf_file.name,
                    mime="application/pdf"
                )
            else:
                logger.error("File path received, but file does not exist at that path.")
        else:
            logger.warning("No pdf_path found in session state.")
        logger.info("--- UI DEBUGGING BLOCK END ---")

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response
    })
    history = st.session_state.question_history
    record = get_session_record(history, st.session_state.session_id)
    record_messages = record.get("messages", [])
    record_messages.append({"role": "assistant", "content": full_response})
    record["messages"] = record_messages
    save_session_record(history, st.session_state.session_id, record.get("title") or "새 대화", record_messages)

st.markdown("---")
st.caption("Powered by Upstage Solar LLM & LangGraph")
