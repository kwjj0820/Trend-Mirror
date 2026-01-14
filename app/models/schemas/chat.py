# app/models/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자의 질문 또는 분석 요청")
    thread_id: str = Field(default="default_thread", description="대화 세션 ID (기억 유지용)")
    bypass_crawling: bool = Field(default=False, description="True일 경우 YouTube API 호출을 우회하고 테스트 데이터셋을 사용")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="에이전트의 최종 답변")
    pdf_path: Optional[str] = Field(None, description="생성된 리포트 PDF 경로")
    process_status: str = Field(..., description="처리 상태 (success/fail)")
    logs: Optional[List[str]] = Field(None, description="처리 로그 (선택)")