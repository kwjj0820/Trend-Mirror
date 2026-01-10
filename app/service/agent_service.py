# app/service/agent_service.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from app.agents.workflow import super_graph
from app.service.vector_service import VectorService


class AgentService:
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service  # 의존성 주입 받음

    def run_agent(self, user_query: str, thread_id: str = "default") -> Dict[str, Any]:
        # 1. 초기 상태 설정
        initial_state = {
            "user_input": user_query,
            "logs": [],
            # LangGraph 메시지 히스토리 초기화 (선택적)
            "messages": [HumanMessage(content=user_query)]
        }

        # 2. Config 설정 (Graph 내부 노드/툴에 객체 전달)
        config = {
            "configurable": {
                "thread_id": thread_id,
                # 여기서 주입해야 Tools에서 vector_service를 꺼내 쓸 수 있음
                "vector_service": self.vector_service,
            }
        }

        # 3. 그래프 실행
        try:
            # stream=False로 전체 실행 결과를 한 번에 받음
            result = super_graph.invoke(initial_state, config=config)

            return {
                "answer": result.get("final_answer", "죄송합니다. 답변을 생성하지 못했습니다."),
                "pdf_path": result.get("final_pdf_path"),
                "status": "success",
                "logs": result.get("logs", [])
            }
        except Exception as e:
            return {
                "answer": f"에러가 발생했습니다: {str(e)}",
                "pdf_path": None,
                "status": "fail",
                "logs": [str(e)]
            }