import streamlit as st
import json
import httpx
import uuid
import os
from pathlib import Path
import time
import pandas as pd
import altair as alt
from collections import Counter

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
    /* Sidebar 버튼 */
    section[data-testid="stSidebar"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        width: 100%;
        text-align: left;
        padding: 0.35rem 0.4rem;
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] button:hover { background: #f3f4f6 !important; }
    section[data-testid="stSidebar"] button:focus { outline: none !important; box-shadow: none !important; }

    /* Overlay & Dialog */
    div[data-testid="stOverlay"] { background: rgba(0, 0, 0, 0.50) !important; }

    div[data-testid="stDialog"] > div {
        border-radius: 18px;
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.18);
        padding: 22px 24px 24px 24px;
    }

    /* Header */
    div[data-testid="stDialog"] header {
        display: flex !important;
        align-items: flex-start !important;
        gap: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(15, 23, 42, 0.08);
        margin-bottom: 14px;
    }
    div[data-testid="stDialog"] header h2 {
        flex: 1 1 auto !important;
        font-size: 20px;
        font-weight: 800;
        margin: 0 !important;
        text-align: left !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.25;
    }
    div[data-testid="stDialog"] header button {
        flex: 0 0 auto !important;
        border-radius: 999px !important;
        width: 34px !important;
        height: 34px !important;
        margin-top: -2px;
    }

    /* Subtitle & label */
    div[data-testid="stDialog"] .tm-dialog-subtitle {
        font-size: 13px;
        font-weight: 600;
        color: #6b7280;
        margin: 6px 0 16px;
        line-height: 1.35;
    }
    div[data-testid="stDialog"] .tm-section-label {
        font-size: 12px;
        font-weight: 700;
        color: #9ca3af;
        margin: 6px 0 10px;
        letter-spacing: 0.02em;
    }

    /* ===== Radio -> centered 2 cards ===== */
    div[data-testid="stDialog"] div[data-testid="stRadio"] > div {
        display: grid !important;
        grid-template-columns: 220px 220px;  /* 카드 고정 폭 */
        gap: 16px;
        justify-content: center;             /* 가로 중앙 */
        align-content: center;
        place-content: center;
        width: 100%;
    }
    @media (max-width: 640px) {
        div[data-testid="stDialog"] div[data-testid="stRadio"] > div {
            grid-template-columns: 1fr !important;
        }
    }

    /* 카드 */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
        width: 100% !important;
        height: 96px;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px;
        background: #ffffff;
        margin: 0 !important;
        transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 750;
        position: relative;
        text-align: center;
    }

    /* 라디오 동그라미/인풋 숨김 (BaseWeb 마크까지 숨김) */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span[aria-hidden="true"] {
    display: none !important;
}
    div[data-testid="stDialog"] div[data-testid="stRadio"] input[type="radio"] {
        display: none !important;
    }

    /* 텍스트 */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-size: 16px;
        color: #111827;
        font-weight: 750;
    }

    /* Hover */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        border-color: #c7d2fe;
        background: #f8fafc;
    }

    /* Selected (체크 없이 border/bg로만 표시) */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        border-color: #1d4ed8;
        background: #eef2ff;
        box-shadow: 0 10px 22px rgba(37, 99, 235, 0.14);
    }

    /* 체크(✓) 완전 제거 */
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]::after {
        display: none !important;
        content: none !important;
    }

    /* Primary button */
    div[data-testid="stDialog"] .stButton > button {
        border-radius: 14px;
        padding: 0.95rem 1rem;
        font-weight: 800;
        background: #1d4ed8;
        border: 1px solid #1d4ed8;
        color: #ffffff;
    }
    div[data-testid="stDialog"] .stButton > button:hover {
        background: #1e40af;
        border-color: #1e40af;
    }
    div[data-testid="stDialog"] .stButton > button:disabled {
        background: #e5e7eb !important;
        border-color: #e5e7eb !important;
        color: #9ca3af !important;
        cursor: not-allowed !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# st.markdown(
#     """
#     <style>
#     section[data-testid="stSidebar"] button {
#         background: transparent !important;
#         border: none !important;
#         box-shadow: none !important;
#         width: 100%;
#         text-align: left;
#         padding: 0.35rem 0.4rem;
#         border-radius: 6px;
#     }
#     section[data-testid="stSidebar"] button:hover {
#         background: #f3f4f6 !important;
#     }
#     section[data-testid="stSidebar"] button:focus {
#         outline: none !important;
#         box-shadow: none !important;
#     }
#     div[data-testid="stOverlay"] {
#         background: rgba(0, 0, 0, 0.45) !important;
#     }
#     div[data-testid="stDialog"] > div {
#         border-radius: 18px;
#         box-shadow: 0 22px 60px rgba(15, 23, 42, 0.18);
#         padding: 24px;
#     }
#     div[data-testid="stDialog"] header {
#         padding-bottom: 12px;
#         border-bottom: 1px solid rgba(15, 23, 42, 0.08);
#         margin-bottom: 16px;
#     }
#     div[data-testid="stDialog"] header h2 {
#         font-size: 19px;
#         font-weight: 700;
#         white-space: nowrap;
#         overflow: hidden;
#         text-overflow: ellipsis;
#         text-align: center;
#         width: 100%;
#     }
#     div[data-testid="stDialog"] .tm-dialog-subtitle {
#         font-size: 12px;
#         font-weight: 600;
#         color: #9ca3af;
#         text-align: center;
#         margin: 2px 0 18px;
#         letter-spacing: 0.02em;
#     }
#     div[data-testid="stDialog"] header button {
#         border-radius: 999px !important;
#         width: 32px;
#         height: 32px;
#     }
#     div[data-testid="stDialog"] .tm-section-label {
#         font-size: 12px;
#         font-weight: 600;
#         color: #9ca3af;
#         margin: 8px 0 10px;
#         letter-spacing: 0.02em;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] {
#         display: flex;
#         flex-direction: row;
#         justify-content: center;
#         gap: 12px;
#         flex-wrap: wrap;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
#         border: 1px solid #e5e7eb;
#         border-radius: 12px;
#         padding: 16px;
#         background: #ffffff;
#         margin-bottom: 10px;
#         width: 220px;
#         height: 76px;
#         transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
#         position: relative;
#         cursor: pointer;
#         display: flex;
#         align-items: center;
#         justify-content: center;
#         font-weight: 600;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span {
#         display: inline-flex;
#         align-items: center;
#         gap: 6px;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span::before {
#         content: "[";
#         color: #64748b;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span::after {
#         content: "]";
#         color: #64748b;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] input[type="radio"] {
#         display: none;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
#         border-color: #c7d2fe;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
#         border-color: #1d4ed8;
#         background: #eef2ff;
#         box-shadow: 0 10px 22px rgba(37, 99, 235, 0.14);
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]::after {
#         content: "✓";
#         position: absolute;
#         right: 14px;
#         top: 50%;
#         transform: translateY(-50%);
#         width: 22px;
#         height: 22px;
#         border-radius: 999px;
#         background: #e2e8f0;
#         color: #64748b;
#         font-size: 12px;
#         display: grid;
#         place-items: center;
#         opacity: 0;
#         transition: opacity 0.2s ease, background 0.2s ease, color 0.2s ease;
#     }
#     div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)::after {
#         opacity: 1;
#         background: #1d4ed8;
#         color: #ffffff;
#     }
#     div[data-testid="stDialog"] .stButton > button {
#         border-radius: 12px;
#         padding: 0.85rem 1rem;
#         font-weight: 600;
#         background: #1d4ed8;
#         border: 1px solid #1d4ed8;
#         color: #ffffff;
#     }
#     div[data-testid="stDialog"] .stButton > button:hover {
#         background: #1e40af;
#         border-color: #1e40af;
#     }
#     div[data-testid="stDialog"] .stButton > button:disabled {
#         background: #e5e7eb !important;
#         color: #9ca3af !important;
#         cursor: not-allowed !important;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True
# )


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "question_history" not in st.session_state:
    st.session_state.question_history = {}
if "last_pdf_path" not in st.session_state:
    st.session_state.last_pdf_path = None
if "user_type" not in st.session_state:
    st.session_state.user_type = "일반 자영업자"
if "user_type_confirmed" not in st.session_state:
    st.session_state.user_type_confirmed = False


# @st.dialog("어떤 사용자로 시작할까요?")
# def user_type_dialog():
#     options = ["일반 자영업자", "마케터"]
#     current = st.session_state.get("user_type", options[0])
#     current_index = options.index(current) if current in options else 0
#     st.markdown('<div class="tm-dialog-subtitle">사용자 유형 선택</div>', unsafe_allow_html=True)
#     st.markdown('<div class="tm-section-label">업종 선택</div>', unsafe_allow_html=True)
#     choice = st.radio(
#         "업종 선택",
#         options,
#         index=current_index,
#         label_visibility="collapsed",
#         horizontal=True,
#     )
#     if st.button("선택 완료", type="primary", use_container_width=True):
#         st.session_state.user_type = choice
#         st.session_state.user_type_confirmed = True
#         st.rerun()
        
@st.dialog("어떤 사용자로 시작할까요?")
def user_type_dialog():
    options = ["일반 자영업자", "마케터"]
    current = st.session_state.get("user_type", options[0])
    current_index = options.index(current) if current in options else 0

    st.markdown(
        '<div class="tm-dialog-subtitle">선택한 유형에 맞춰 TrendMirror를 설정해드려요</div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="tm-section-label">사용자 유형</div>', unsafe_allow_html=True)

    choice = st.radio(
        "사용자 유형",
        options,
        index=current_index,
        label_visibility="collapsed",
        horizontal=True,
    )

    if st.button("선택 완료", type="primary", use_container_width=True):
        st.session_state.user_type = choice
        st.session_state.user_type_confirmed = True
        st.rerun()

##





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

if not st.session_state.user_type_confirmed:
    user_type_dialog()


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

    st.subheader("사용자 유형")
    st.radio(
        "분석을 요청하는 사용자를 선택하세요.",
        ["일반 자영업자", "마케터"],
        key="user_type",
    )

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


def build_prompt_with_user_type(prompt, user_type):
    """사용자 유형(일반 자영업자 / 마케터)에 따라 프롬프트에 컨텍스트를 추가합니다."""
    if not user_type:
        return prompt

    if user_type == "일반 자영업자":
        persona = (
            "이 사용자는 일반 자영업자(자영업 사장님)입니다. "
            "매장/비즈니스 운영과 관련된 실질적인 마케팅 인사이트와 "
            "실행 가능한 액션 위주로 설명해 주세요."
        )
    elif user_type == "마케터":
        persona = (
            "이 사용자는 마케터입니다. "
            "캠페인 전략, 퍼널 설계, 성과 지표, 리포트 인사이트 등 "
            "마케팅 실무 관점에서 설명해 주세요."
        )
    else:
        persona = f"이 사용자의 유형은 '{user_type}' 입니다."

    return f"[사용자 유형: {user_type}]\n{persona}\n\n{prompt}"


def response_generator(prompt, session_id):
    try:
        status = st.status("trend mirror 에이전트가 분석 중입니다....", expanded=True)

        # 검색 쿼리를 세션 상태에 저장 (CSV 파일명으로 사용)
        st.session_state.last_search_query = prompt

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
        process_status = data.get("process_status")

        if process_status == "fail":
            status.update(label="오류", state="error")
            yield answer
            return

        # Clear previous chart data on successful response
        st.session_state.last_keyword_frequencies = None
        st.session_state.last_daily_sentiments = None

        keyword_frequencies = data.get("keyword_frequencies") # Retrieve new data
        daily_sentiments = data.get("daily_sentiments") # Retrieve new data
        pdf_path = data.get("pdf_path")

        if keyword_frequencies: # Store in session state
            st.session_state.last_keyword_frequencies = keyword_frequencies
        if daily_sentiments: # Store in session state
            st.session_state.last_daily_sentiments = daily_sentiments
        if pdf_path:
            st.session_state.last_pdf_path = pdf_path

        status.update(label="분석 완료", state="complete", expanded=False)
        yield answer

    except Exception as e:
        yield f"연결 오류: {str(e)}"


def find_most_frequent_keyword(df):
    """DataFrame에서 가장 빈도수가 높은 키워드를 찾는 함수"""
    # trend_keywords 컬럼의 모든 키워드를 수집
    all_keywords = []
    for keywords_str in df['trend_keywords'].dropna():
        if keywords_str.strip():  # 빈 문자열이 아닌 경우
            # 쉼표로 분리하고 각 키워드 정리
            keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
            all_keywords.extend(keywords)

    # 키워드 빈도 계산
    keyword_counts = Counter(all_keywords)

    # 가장 빈도수가 높은 키워드 찾기
    if keyword_counts:
        most_common_keyword, count = keyword_counts.most_common(1)[0]
        return most_common_keyword, count, keyword_counts
    return None, 0, Counter()

def get_top_videos_by_keyword_and_views(df, keyword, top_n=3):
    """특정 키워드를 포함하고 조회수가 높은 상위 N개 영상 반환"""
    # viewCount를 숫자로 변환 (문자열일 수 있음)
    df['viewCount'] = pd.to_numeric(df['viewCount'], errors='coerce')

    # 키워드가 포함된 행 필터링
    filtered_df = df[df['trend_keywords'].str.contains(keyword, case=False, na=False)]

    # 조회수로 정렬하여 상위 N개 선택
    top_videos = filtered_df.nlargest(top_n, 'viewCount')

    return top_videos[['title', 'channel_title', 'viewCount', 'trend_keywords', 'video_id']]

def get_csv_path_by_search_query(search_query):
    """서치 쿼리를 기반으로 CSV 파일 경로를 반환"""
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        return None

    # 가장 최근의 모든 CSV 파일을 가져옴
    all_csv_files = list(downloads_dir.glob("youtube_*with_keywords.csv"))

    if all_csv_files:
        # 가장 최근 파일 선택 (수정 시간 기준)
        latest_file = max(all_csv_files, key=lambda x: x.stat().st_mtime)
        return latest_file

    return None

def render_top_videos_by_frequent_keyword(search_query):
    """가장 빈도수가 높은 키워드를 갖는 상위 조회수 영상 3개를 표시"""
    csv_path = get_csv_path_by_search_query(search_query)

    if not csv_path or not csv_path.exists():
        st.warning(f"CSV 파일을 찾을 수 없습니다: {search_query}")
        return

    try:
        df = pd.read_csv(csv_path)

        # 가장 빈도수가 높은 키워드 찾기
        most_keyword, count, all_counts = find_most_frequent_keyword(df)

        if not most_keyword:
            st.warning("키워드를 찾을 수 없습니다.")
            return

        # 해당 키워드를 갖는 상위 3개 영상 추출
        top_videos = get_top_videos_by_keyword_and_views(df, most_keyword, 3)

        if top_videos.empty:
            st.warning(f"'{most_keyword}' 키워드를 포함한 영상을 찾을 수 없습니다.")
            return

        st.subheader(f"🔥 가장 인기 있는 키워드: '{most_keyword}' (빈도: {count})")
        st.markdown(f"**'{most_keyword}'** 키워드를 포함한 조회수 상위 3개 영상:")

        for idx, (_, row) in enumerate(top_videos.iterrows(), 1):
            with st.container():
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"**{idx}. {row['title']}**")
                    st.caption(f"채널: {row['channel_title']}")
                    st.caption(f"키워드: {row['trend_keywords']}")

                with col2:
                    # YouTube 썸네일 URL 생성 (video_id 활용)
                    thumbnail_url = f"https://img.youtube.com/vi/{row['video_id']}/maxresdefault.jpg"
                    st.image(thumbnail_url, width=120)

                    # 조회수 포맷팅
                    view_count = f"{int(row['viewCount']):,}"
                    st.metric("조회수", view_count)

                st.markdown("---")

    except Exception as e:
        st.error(f"영상 분석 중 오류 발생: {str(e)}")

def render_integrated_results(response_text):
    """텍스트와 차트를 통합해서 표시하는 함수"""
    keyword_frequencies = st.session_state.get("last_keyword_frequencies")
    daily_sentiments = st.session_state.get("last_daily_sentiments")
    pdf_path = st.session_state.get("last_pdf_path")
    search_query = st.session_state.get("last_search_query")

    # 텍스트를 라인별로 분리
    lines = response_text.split('\n')
    current_section = ""
    section_content = []

    for line in lines:
        # 헤더(#)로 시작하는 라인을 섹션 구분자로 사용
        if line.startswith('#'):
            # 이전 섹션 처리
            if current_section and section_content:
                render_section_with_charts(current_section, section_content,
                                         keyword_frequencies, daily_sentiments,
                                         pdf_path, search_query)

            # 새 섹션 시작
            current_section = line
            section_content = [line]
        else:
            section_content.append(line)

    # 마지막 섹션 처리
    if current_section and section_content:
        render_section_with_charts(current_section, section_content,
                                 keyword_frequencies, daily_sentiments,
                                 pdf_path, search_query)


def render_section_with_charts(section_header, section_content, keyword_frequencies,
                              daily_sentiments, pdf_path, search_query):
    """섹션별로 텍스트와 차트를 렌더링"""
    # 섹션 텍스트 표시
    section_text = '\n'.join(section_content)
    st.markdown(section_text)
    st.markdown("")  # 간격 추가

    # 섹션별로 적절한 차트 삽입
    if "Internal SNS Trend Analysis" in section_header and keyword_frequencies:
        # 키워드 빈도 차트
        st.subheader("📊 키워드 언급 빈도 분석")
        df_keywords = pd.DataFrame(keyword_frequencies)
        if not df_keywords.empty:
            chart = alt.Chart(df_keywords).mark_arc().encode(
                theta=alt.Theta(field="frequency", type="quantitative"),
                color=alt.Color(field="keyword", type="nominal", title="키워드")
            ).properties(
                title="키워드별 언급 빈도"
            )
            st.altair_chart(chart, use_container_width=True)
            with st.expander("📋 키워드 데이터 상세보기"):
                st.dataframe(df_keywords, use_container_width=True, hide_index=True)

    elif "Sustainability and Critical Review" in section_header and daily_sentiments:
        # 감성 변화 차트
        st.subheader("📈 일별 감성 변화 분석")
        df_sentiments = pd.DataFrame(daily_sentiments)
        if not df_sentiments.empty:
            df_sentiments["date"] = pd.to_datetime(df_sentiments["date"])

            df_sentiments_melted = df_sentiments.melt(
                id_vars=["date"],
                value_vars=["positive", "neutral", "negative"],
                var_name="sentiment",
                value_name="count"
            )

            chart = alt.Chart(df_sentiments_melted).mark_bar().encode(
                x=alt.X("date:T", title="날짜"),
                y=alt.Y("count:Q", title="언급 빈도"),
                color=alt.Color(
                    "sentiment:N",
                    scale=alt.Scale(
                        domain=["positive", "neutral", "negative"],
                        range=["#2ecc71", "#95a5a6", "#e74c3c"]
                    ),
                    title="감성"
                ),
                order=alt.Order(
                  "sentiment",
                  sort="ascending"
                )
            ).properties(
                title="일별 감성 변화 추이"
            )
            st.altair_chart(chart, use_container_width=True)
            with st.expander("📋 감성 데이터 상세보기"):
                st.dataframe(
                    df_sentiments.sort_values("date"),
                    use_container_width=True,
                    hide_index=True,
                )

    elif "Strategic Action Plan" in section_header:
        # 전략 섹션 뒤에 인기 영상과 PDF 다운로드
        if search_query:
            st.markdown("---")
            render_top_videos_by_frequent_keyword(search_query)

        if pdf_path:
            st.markdown("---")
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                st.subheader("📄 분석 리포트 다운로드")
                with pdf_file.open("rb") as f:
                    st.download_button(
                        label="📥 PDF 리포트 다운로드",
                        data=f,
                        file_name=pdf_file.name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.caption(f"PDF 파일을 찾을 수 없습니다: {pdf_file}")


def render_latest_results():
    """기존 함수 - 하위 호환성 유지"""
    keyword_frequencies = st.session_state.get("last_keyword_frequencies")
    daily_sentiments = st.session_state.get("last_daily_sentiments")
    pdf_path = st.session_state.get("last_pdf_path")

    if not (keyword_frequencies or daily_sentiments or pdf_path):
        return

    st.subheader("분석 결과")

    if keyword_frequencies:
        st.subheader("키워드 언급 빈도")
        df_keywords = pd.DataFrame(keyword_frequencies)
        if not df_keywords.empty:
            chart = alt.Chart(df_keywords).mark_arc().encode(
                theta=alt.Theta(field="frequency", type="quantitative"),
                color=alt.Color(field="keyword", type="nominal", title="키워드")
            ).properties(
                title="키워드별 언급 빈도"
            )
            st.altair_chart(chart, use_container_width=True)
            with st.expander("Keyword data table"):
                st.dataframe(df_keywords, use_container_width=True, hide_index=True)

    if daily_sentiments:
        st.subheader("일별 감성 변화")
        df_sentiments = pd.DataFrame(daily_sentiments)
        if not df_sentiments.empty:
            df_sentiments["date"] = pd.to_datetime(df_sentiments["date"])

            df_sentiments_melted = df_sentiments.melt(
                id_vars=["date"],
                value_vars=["positive", "neutral", "negative"],
                var_name="sentiment",
                value_name="count"
            )

            chart = alt.Chart(df_sentiments_melted).mark_bar().encode(
                x=alt.X("date:T", title="날짜"),
                y=alt.Y("count:Q", title="언급 빈도"),
                color=alt.Color(
                    "sentiment:N",
                    scale=alt.Scale(
                        domain=["positive", "neutral", "negative"],
                        range=["#2ecc71", "#95a5a6", "#e74c3c"]
                    ),
                    title="감성"
                ),
                order=alt.Order(
                  "sentiment",
                  sort="ascending"
                )
            ).properties(
                title="일별 감성 변화 추이"
            )
            st.altair_chart(chart, use_container_width=True)
            with st.expander("Daily sentiment data table"):
                st.dataframe(
                    df_sentiments.sort_values("date"),
                    use_container_width=True,
                    hide_index=True,
                )

    if pdf_path:
        pdf_file = Path(pdf_path)
        if pdf_file.exists():
            with pdf_file.open("rb") as f:
                st.download_button(
                    label="리포트 PDF 다운로드",
                    data=f,
                    file_name=pdf_file.name,
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.caption(f"PDF 파일을 찾을 수 없습니다: {pdf_file}")

    # 가장 빈도수가 높은 키워드의 상위 조회수 영상 표시
    search_query = st.session_state.get("last_search_query")
    if search_query:
        st.markdown("---")
        render_top_videos_by_frequent_keyword(search_query)


if prompt := st.chat_input("분석하고 싶은 트렌드 주제를 입력해주세요."):
    user_type = st.session_state.get("user_type", "일반 자영업자")
    display_prompt = f"[{user_type}] {prompt}" if user_type else prompt
    prompt_for_model = build_prompt_with_user_type(prompt, user_type)

    st.session_state.messages.append({"role": "user", "content": display_prompt})
    history = st.session_state.question_history
    record = get_session_record(history, st.session_state.session_id)
    if not record.get("title"):
        record["title"] = prompt
    record_messages = record.get("messages", [])
    record_messages.append({"role": "user", "content": display_prompt})
    record["messages"] = record_messages
    save_session_record(
        history,
        st.session_state.session_id,
        record.get("title") or prompt,
        record_messages,
    )

    with st.chat_message("user"):
        st.markdown(display_prompt)

    with st.chat_message("assistant"):
        full_response = st.write_stream(
            response_generator(prompt_for_model, st.session_state.session_id)
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": full_response,
        }
    )
    history = st.session_state.question_history
    record = get_session_record(history, st.session_state.session_id)
    record_messages = record.get("messages", [])
    record_messages.append({"role": "assistant", "content": full_response})
    record["messages"] = record_messages
    save_session_record(
        history,
        st.session_state.session_id,
        record.get("title") or "새 대화",
        record_messages,
    )

    # 텍스트와 차트를 통합해서 표시
    render_integrated_results(full_response)

st.markdown("---")
st.caption("Powered by Upstage Solar LLM & LangGraph")
