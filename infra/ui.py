import streamlit as st
import json
import httpx
import uuid
import os
BACKEND_URL = os.getenv("BACKEND_URL","http://localhost:8000")

st.set_page_config(
    page_title ="TREND MIRROR",
    page_icon = "📈",
    layout = "wide"
)

if "session_id" not in st.session_state:
    st.session_state.session_id  = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []


st.title("TREND_MIRROR")
st.markdown("트렌드 분석 마케팅 report")
with st.sidebar:
    st.header("설정")
    if st.button("초기화"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun() #초기화
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def response_generator(prompt, session_id):
    try:
        with httpx.stream(
            "POST",
            f"{BACKEND_URL}/agent/chat/stream",
            json={
                "query" : prompt,
                "session_id":session_id
            },
            timeout=None
        ) as response:
            if response.status_code != 200:
                yield f"오류가 발생하였습니다 (상태코드: {response.status_code})"
                return
            status = st.status("trend mirror 에이전트가 분석 중입니다....")

            is_answering = False
            
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[len("data: "):].strip()
                
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        if "error" in event:
                            yield f"\n\n error : {event['error']}"
                        
                        if "log" in event:
                            status.write(event['log'])
                            continue
                        if "answer" in event and event["answer"]:
                            if not is_answering:
                                status.update(label="분석 완료", state="complete", expanded=False)
                                is_answering=True
                            
                            yield event["answer"] # 데이터 한덩이씩 밖으로
                    except json.JSONDecodeError:
                        continue

            if not is_answering:
                status.update(label="작업 완료", state="complete", expanded=False)
            
    except Exception as e:
            yield f"연결 오류:{str(e)}"

if prompt := st.chat_input("분석하고 싶은 트렌드 주제를 입력해주세요."):

    # 1. 사용자 질문을 먼저 화면에 그리기
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. AI 답변 영역 그리기
    with st.chat_message("assistant"):
        # [핵심] response_generator가 yield하는 글자들을 실시간으로 화면에 씀
        full_response = st.write_stream(
            response_generator(prompt, st.session_state.session_id)
        )

    # 3. 답변이 다 완성되면 저장소에 기록
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response
    })

# Footer information
st.markdown("---")
st.caption("Powered by Upstage Solar LLM & LangGraph")
                                