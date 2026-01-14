# app/api/routes/chat.py
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas.chat import ChatRequest, ChatResponse
from app.service.agent_service import AgentService
from app.deps import get_agent_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
        request: ChatRequest,
        agent_service: AgentService = Depends(get_agent_service)  # deps.py를 통해 자동 주입
):
    """
    TrendMirror 에이전트와 대화하는 엔드포인트
    """
    result = agent_service.run_agent(
        user_query=request.query,
        thread_id=request.thread_id,
        bypass_crawling=request.bypass_crawling
    )

    return ChatResponse(
        answer=result["answer"],
        pdf_path=result["pdf_path"],
        process_status=result["status"],
        logs=result["logs"]
    )