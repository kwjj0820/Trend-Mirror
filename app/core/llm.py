# app/core/llm.py
from app.repository.client.llm_client import UpstageClient

# 전역 클라이언트 인스턴스
_client = UpstageClient()

def get_solar_chat():
    return _client.get_chat_model()

def get_upstage_embeddings():
    return _client.get_embedding_model()

def get_solar_pro_chat_client():
    """키워드 추출용 Solar-pro 모델 클라이언트를 반환합니다."""
    return _client.get_solar_pro_client()