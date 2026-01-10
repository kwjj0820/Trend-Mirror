# app/core/llm.py
from app.repository.client.llm_client import UpstageClient

# 전역 클라이언트 인스턴스
_client = UpstageClient()

def get_solar_chat():
    return _client.get_chat_model()

def get_upstage_embeddings():
    return _client.get_embedding_model()