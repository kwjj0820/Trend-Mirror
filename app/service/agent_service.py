# app/service/agent_service.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from app.agents.workflow import super_graph
from app.service.vector_service import VectorService
from app.service.sync_service import SyncService
import traceback # Import traceback for debugging

class AgentService:
    def __init__(self, vector_service: VectorService, sync_service: SyncService):
        self.vector_service = vector_service  # 의존성 주입 받음
        self.sync_service = sync_service      # DB 동기화 서비스

    def run_agent(self, user_query: str, thread_id: str = "default") -> Dict[str, Any]:
        # 1. 초기 상태 설정
        initial_state = {
            "user_input": user_query,
            "logs": [],
            "messages": [HumanMessage(content=user_query)],
        }

        # 2. Config 설정 (Graph 내부 노드/툴에 서비스 객체 전달)
        config = {
            "configurable": {
                "thread_id": thread_id,
                "vector_service": self.vector_service,
                "sync_service": self.sync_service,
            }
        }

        # 3. 그래프 실행
        try:
            # stream=False로 전체 실행 결과를 한 번에 받음
            result = super_graph.invoke(initial_state, config=config)

            return {
                "answer": result.get("final_answer", "죄송합니다. 답변을 생성하지 못했습니다."),
                "pdf_path": result.get("pdf_path"),
                "status": "success",
                "logs": result.get("logs", []),
                "keyword_frequencies": result.get("keyword_frequencies"),
                "daily_sentiments": result.get("daily_sentiments"),
            }
        except Exception as e:
            print(f"!!! CRITICAL ERROR in AgentService.run_agent: {e}")
            traceback.print_exc() # Print full traceback to console for debugging
            return {
                "answer": f"에러가 발생했습니다: {str(e)}",
                "pdf_path": None,
                "status": "fail",
                "logs": [f"오류: {str(e)}", "자세한 내용은 서버 콘솔 로그를 확인하세요."]
            }
