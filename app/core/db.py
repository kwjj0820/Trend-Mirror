# app/core/db.py
import os
import chromadb
from dotenv import load_dotenv

# 로컬 개발 환경에서만 .env 로드
if os.getenv("KUBERNETES_SERVICE_HOST") is None:
    load_dotenv()


class ChromaDBConnection:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            # 노트북의 설정을 반영하여 로컬 경로 지정
            persist_path = os.getenv("CHROMA_PERSIST_PATH", "chroma_tm")

            # PersistentClient 사용 (노트북과 동일)
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=persist_path,
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )

    @property
    def client(self) -> chromadb.ClientAPI:
        return self._client

    def get_collection(self, collection_name: str = "trendmirror_kb"):
        return self._client.get_or_create_collection(name=collection_name)