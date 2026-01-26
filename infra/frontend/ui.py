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
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from fpdf import FPDF
import tempfile

# --- 설정 및 상수 ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
HISTORY_PATH = Path("reports") / "question_history.json"

# PDF 및 차트 생성에 사용할 폰트 경로 (중요)
FONT_REGULAR_PATH = "resources/fonts/NanumGothic-Regular.ttf"
FONT_BOLD_PATH = "resources/fonts/NanumGothic-Bold.ttf"

st.set_page_config(
    page_title="TREND MIRROR",
    page_icon="✨",
    layout="wide"
)

# --- CSS 스타일 (기존 유지) ---
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
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] button:hover { background: #f3f4f6 !important; }
    section[data-testid="stSidebar"] button:focus { outline: none !important; box-shadow: none !important; }

    div[data-testid="stOverlay"] { background: rgba(0, 0, 0, 0.50) !important; }

    div[data-testid="stDialog"] > div {
        border-radius: 18px;
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.18);
        padding: 22px 24px 24px 24px;
    }

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
        line-height: 1.25;
    }
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
    div[data-testid="stDialog"] div[data-testid="stRadio"] > div {
        display: grid !important;
        grid-template-columns: 220px 220px;
        gap: 16px;
        justify-content: center;
        width: 100%;
    }
    @media (max-width: 640px) {
        div[data-testid="stDialog"] div[data-testid="stRadio"] > div {
            grid-template-columns: 1fr !important;
        }
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
        width: 100% !important;
        height: 96px;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px;
        background: #ffffff;
        margin: 0 !important;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 750;
        text-align: center;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"] span[aria-hidden="true"] {
        display: none !important;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] input[type="radio"] {
        display: none !important;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        border-color: #c7d2fe;
        background: #f8fafc;
    }
    div[data-testid="stDialog"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        border-color: #1d4ed8;
        background: #eef2ff;
        box-shadow: 0 10px 22px rgba(37, 99, 235, 0.14);
    }
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
    </style>
    """,
    unsafe_allow_html=True
)

# --- 세션 상태 초기화 ---
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


# --- PDF 및 차트 생성 함수 (핵심 추가 부분) ---

def create_chart_image(data, chart_type):
    """Matplotlib을 사용하여 차트 이미지를 생성하고 임시 파일 경로를 반환"""
    if not data:
        return None

    # 한글 폰트 설정 (차트 내부 글씨 깨짐 방지)
    if os.path.exists(FONT_REGULAR_PATH):
        prop = fm.FontProperties(fname=FONT_REGULAR_PATH)
        plt.rcParams['font.family'] = prop.get_name()
    else:
        # 폰트 파일이 없으면 시스템 폰트로 대체 (깨질 수 있음)
        import platform
        system = platform.system()
        if system == 'Darwin':
            plt.rc('font', family='AppleGothic')
        elif system == 'Windows':
            plt.rc('font', family='Malgun Gothic')

    # 차트 스타일
    plt.figure(figsize=(10, 5))
    plt.style.use('bmh')

    try:
        if chart_type == 'keyword':
            df = pd.DataFrame(data)
            if df.empty: return None
            df = df.head(10)
            plt.bar(df['keyword'], df['frequency'], color='#3b82f6')
            plt.title('주요 키워드 언급 빈도', fontsize=14, pad=15)
            plt.xlabel('키워드')
            plt.ylabel('빈도')
            plt.xticks(rotation=45)

        elif chart_type == 'sentiment':
            df = pd.DataFrame(data)
            if df.empty: return None
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            plt.plot(df['date'], df['positive'], label='긍정', color='green', marker='o')
            plt.plot(df['date'], df['neutral'], label='중립', color='gray', marker='o')
            plt.plot(df['date'], df['negative'], label='부정', color='red', marker='o')
            plt.title('일별 감성 변화 추이', fontsize=14, pad=15)
            plt.legend()
            plt.grid(True, alpha=0.3)

        plt.tight_layout()

        # 임시 이미지 파일 생성
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(temp_file.name, dpi=100)
        plt.close('all')  # 메모리 누수 방지
        return temp_file.name
    except Exception as e:
        print(f"Chart creation error: {e}")
        return None


def generate_pdf_report(response_text, keyword_data, sentiment_data):
    """텍스트와 차트 이미지를 결합하여 PDF 바이너리 데이터 생성"""
    pdf = FPDF()
    pdf.add_page()

    # 폰트 등록 (필수)
    font_ok = False
    if os.path.exists(FONT_REGULAR_PATH) and os.path.exists(FONT_BOLD_PATH):
        try:
            pdf.add_font('NanumGothic', '', FONT_REGULAR_PATH, uni=True)
            pdf.add_font('NanumGothic', 'B', FONT_BOLD_PATH, uni=True)
            pdf.set_font('NanumGothic', '', 11)
            font_ok = True
        except Exception as e:
            print(f"Font loading error: {e}")

    if not font_ok:
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 10, "[Warning] Korean font not found. Text may handle incorrectly.", 0, 1)

    # 1. 타이틀
    pdf.set_font_size(16)
    if font_ok: pdf.set_font('NanumGothic', 'B', 16)
    pdf.cell(0, 15, "Trend Mirror Analysis Report", 0, 1, 'C')
    pdf.ln(5)

    # 2. 본문 텍스트 (Markdown 헤더 파싱)
    pdf.set_font_size(11)
    if font_ok: pdf.set_font('NanumGothic', '', 11)

    lines = response_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue

        if line.startswith('#'):
            # 헤더 스타일링
            clean_line = line.replace('#', '').strip()
            pdf.ln(5)
            if font_ok:
                pdf.set_font('NanumGothic', 'B', 13)
            else:
                pdf.set_font_size(13)
            pdf.cell(0, 8, clean_line, 0, 1)
            if font_ok:
                pdf.set_font('NanumGothic', '', 11)
            else:
                pdf.set_font_size(11)
        else:
            # 일반 텍스트
            pdf.multi_cell(0, 6, line)

    # 3. 차트 이미지 삽입
    pdf.add_page()
    if font_ok:
        pdf.set_font('NanumGothic', 'B', 14)
    else:
        pdf.set_font_size(14)
    pdf.cell(0, 10, "데이터 시각화 (Data Visualization)", 0, 1)
    pdf.ln(5)

    # 키워드 차트
    if keyword_data:
        kw_img = create_chart_image(keyword_data, 'keyword')
        if kw_img:
            pdf.image(kw_img, x=10, w=190)
            pdf.ln(5)
            os.unlink(kw_img)  # 임시 파일 삭제

    # 감성 차트
    if sentiment_data:
        pdf.ln(10)
        sent_img = create_chart_image(sentiment_data, 'sentiment')
        if sent_img:
            pdf.image(sent_img, x=10, w=190)
            os.unlink(sent_img)  # 임시 파일 삭제

    # 바이트 데이터 반환
    return pdf.output(dest='S').encode('latin-1')


# --- 다이얼로그 및 히스토리 함수 ---
@st.dialog("어떤 사용자로 시작할까요?")
def user_type_dialog():
    options = ["일반 자영업자", "마케터"]
    current = st.session_state.get("user_type", options[0])
    current_index = options.index(current) if current in options else 0

    st.markdown('<div class="tm-dialog-subtitle">선택한 유형에 맞춰 TrendMirror를 설정해드려요</div>', unsafe_allow_html=True)
    st.markdown('<div class="tm-section-label">사용자 유형</div>', unsafe_allow_html=True)

    choice = st.radio(
        "사용자 유형", options, index=current_index, label_visibility="collapsed", horizontal=True,
    )

    if st.button("선택 완료", type="primary", use_container_width=True):
        st.session_state.user_type = choice
        st.session_state.user_type_confirmed = True
        st.rerun()


def load_history() -> dict:
    if not HISTORY_PATH.exists(): return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


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
        return record
    return {"title": "새 대화", "messages": [], "updated_at": 0}


def save_session_record(history: dict, session_id: str, title: str, messages: list) -> None:
    if not title:
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                title = msg["content"]
                break
    if not title: title = "새 대화"
    history[session_id] = {
        "title": title,
        "messages": messages,
        "updated_at": int(time.time())
    }
    save_history(history)


# --- 메인 UI 구성 ---
st.title("TREND_MIRROR")
st.markdown("트렌드 분석 마케팅 report")

with st.sidebar:
    st.header("설정")
    st.subheader("사용자 유형")
    st.radio("분석을 요청하는 사용자를 선택하세요.", ["일반 자영업자", "마케터"], key="user_type")

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
        for session_id, record in history.items():
            title = record.get("title") or "새 대화"
            if st.button(title, key=f"hist_{session_id}"):
                st.session_state.session_id = session_id
                st.session_state.messages = record.get("messages", [])
                st.rerun()

# --- 채팅 표시 ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --- 로직 함수들 ---
def build_prompt_with_user_type(prompt, user_type):
    if not user_type: return prompt
    if user_type == "일반 자영업자":
        persona = "이 사용자는 일반 자영업자입니다. 실질적인 마케팅 인사이트와 실행 가능한 액션 위주로 설명해 주세요."
    elif user_type == "마케터":
        persona = "이 사용자는 마케터입니다. 전략, 퍼널, 지표 위주로 설명해 주세요."
    else:
        persona = f"사용자 유형: {user_type}"
    return f"[사용자 유형: {user_type}]\n{persona}\n\n{prompt}"


def response_generator(prompt, session_id):
    try:
        status = st.status("trend mirror 에이전트가 분석 중입니다....", expanded=True)
        st.session_state.last_search_query = prompt

        r = httpx.post(
            f"{BACKEND_URL}/api/v1/chat",
            json={"query": prompt, "thread_id": session_id, "bypass_crawling": False},
            timeout=None
        )

        if r.status_code != 200:
            status.update(label="오류", state="error")
            yield f"오류 발생 ({r.status_code})\n{r.text}"
            return

        data = r.json()
        answer = data.get("answer") or data.get("result") or str(data)

        # 세션 데이터 저장
        st.session_state.last_keyword_frequencies = data.get("keyword_frequencies")
        st.session_state.last_daily_sentiments = data.get("daily_sentiments")
        st.session_state.last_pdf_path = data.get("pdf_path")

        status.update(label="분석 완료", state="complete", expanded=False)
        yield answer

    except Exception as e:
        yield f"연결 오류: {str(e)}"


# --- 결과 렌더링 및 PDF 다운로드 통합 ---
def get_csv_path_by_search_query(search_query):
    downloads_dir = Path("downloads")
    if not downloads_dir.exists(): return None
    all_csv = list(downloads_dir.glob("youtube_*with_keywords.csv"))
    if all_csv: return max(all_csv, key=lambda x: x.stat().st_mtime)
    return None


def find_most_frequent_keyword(df):
    all_k = []
    for k_str in df['trend_keywords'].dropna():
        if k_str.strip():
            all_k.extend([k.strip() for k in k_str.split(',') if k.strip()])
    if all_k:
        return Counter(all_k).most_common(1)[0] + (Counter(all_k),)
    return None, 0, Counter()


def get_top_videos_by_keyword_and_views(df, keyword, top_n=3):
    df['viewCount'] = pd.to_numeric(df['viewCount'], errors='coerce')
    filtered = df[df['trend_keywords'].str.contains(keyword, case=False, na=False)]
    return filtered.nlargest(top_n, 'viewCount')


def render_top_videos_by_frequent_keyword(search_query):
    csv_path = get_csv_path_by_search_query(search_query)
    if not csv_path: return
    try:
        df = pd.read_csv(csv_path)
        mk, count, _ = find_most_frequent_keyword(df)
        if mk:
            top_videos = get_top_videos_by_keyword_and_views(df, mk, 3)
            if not top_videos.empty:
                st.subheader(f"🔥 인기 키워드: '{mk}'")
                for _, row in top_videos.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"채널: {row['channel_title']}")
                    with c2:
                        st.image(f"https://img.youtube.com/vi/{row['video_id']}/maxresdefault.jpg", width=120)
    except:
        pass


def render_integrated_results(response_text):
    keyword_frequencies = st.session_state.get("last_keyword_frequencies")
    daily_sentiments = st.session_state.get("last_daily_sentiments")
    search_query = st.session_state.get("last_search_query")

    # 1. 텍스트 렌더링
    st.markdown(response_text)

    # 2. 웹상 차트 렌더링 (Altair)
    if keyword_frequencies:
        st.subheader("📊 키워드 언급 빈도")
        df_k = pd.DataFrame(keyword_frequencies)
        c = alt.Chart(df_k).mark_arc().encode(
            theta='frequency', color='keyword'
        ).properties(height=300)
        st.altair_chart(c, use_container_width=True)

    if daily_sentiments:
        st.subheader("📈 일별 감성 변화")
        df_s = pd.DataFrame(daily_sentiments)
        df_s['date'] = pd.to_datetime(df_s['date'])
        df_melt = df_s.melt('date', ['positive', 'neutral', 'negative'], 'sentiment', 'count')
        c = alt.Chart(df_melt).mark_bar().encode(
            x='date:T', y='count:Q', color=alt.Color('sentiment',
                                                     scale=alt.Scale(domain=['positive', 'neutral', 'negative'],
                                                                     range=['#2ecc71', '#95a5a6', '#e74c3c']))
        )
        st.altair_chart(c, use_container_width=True)

    if search_query:
        st.markdown("---")
        render_top_videos_by_frequent_keyword(search_query)

    # 3. PDF 다운로드 버튼 (프론트엔드 생성 방식)
    st.markdown("---")
    st.subheader("📄 리포트 다운로드")

    if st.button("📥 PDF 생성 및 다운로드 (차트 포함)"):
        with st.spinner("PDF를 생성하고 있습니다..."):
            try:
                pdf_bytes = generate_pdf_report(
                    response_text,
                    keyword_frequencies,
                    daily_sentiments
                )

                st.download_button(
                    label="💾 PDF 파일 저장하기",
                    data=pdf_bytes,
                    file_name=f"TrendReport_{int(time.time())}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            except Exception as e:
                st.error(f"PDF 생성 실패: {e}")


# --- 채팅 입력 핸들러 ---
if prompt := st.chat_input("분석하고 싶은 트렌드 주제를 입력해주세요."):
    user_type = st.session_state.get("user_type", "일반 자영업자")
    display_prompt = f"[{user_type}] {prompt}"
    prompt_for_model = build_prompt_with_user_type(prompt, user_type)

    st.session_state.messages.append({"role": "user", "content": display_prompt})

    # 기록 저장용
    history = st.session_state.question_history
    rec = get_session_record(history, st.session_state.session_id)
    if not rec.get("title"): rec["title"] = prompt
    msgs = rec.get("messages", [])
    msgs.append({"role": "user", "content": display_prompt})
    rec["messages"] = msgs
    save_session_record(history, st.session_state.session_id, rec["title"], msgs)

    with st.chat_message("user"):
        st.markdown(display_prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = placeholder.write_stream(
            response_generator(prompt_for_model, st.session_state.session_id)
        )
        placeholder.empty()

        # 통합 결과 렌더링 (여기에 PDF 버튼이 포함됨)
        render_integrated_results(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # 어시스턴트 메시지 기록 저장
    msgs.append({"role": "assistant", "content": full_response})
    save_session_record(history, st.session_state.session_id, rec["title"], msgs)

st.markdown("---")
st.caption("Powered by Upstage Solar LLM & LangGraph")