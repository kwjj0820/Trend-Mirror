# app/repository/client/llm_client.py
import os
from langchain_upstage import ChatUpstage, UpstageEmbeddings
from dotenv import load_dotenv
from app.repository.client.base import BaseLLMClient

# Kubernetes 환경 변수 체크 (로컬일 경우 .env 로드)
if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()

class UpstageClient(BaseLLMClient):
    def __init__(self):
        self.api_key = os.getenv("UPSTAGE_API_KEY")
        # 노트북 설정 반영: solar-pro2, solar-embedding-1-large
        self.chat_model_name = os.getenv("UPSTAGE_LLM_MODEL", "solar-pro2")
        self.embedding_model_name = os.getenv("UPSTAGE_EMB_QUERY_MODEL", "solar-embedding-1-large")
        self._chat_instance = None
        self._embedding_instance = None

    def get_chat_model(self, temperature=0.1) -> ChatUpstage:
        # Singleton 패턴 적용
        if self._chat_instance is None:
            self._chat_instance = ChatUpstage(
                api_key=self.api_key,
                model=self.chat_model_name,
                temperature=temperature
            )
        return self._chat_instance

    def get_embedding_model(self) -> UpstageEmbeddings:
        if self._embedding_instance is None:
            self._embedding_instance = UpstageEmbeddings(
                api_key=self.api_key,
                model=self.embedding_model_name
            )
        return self._embedding_instance