# app/repository/vector/vector_repo.py
from typing import List, Dict, Any
from app.core.db import ChromaDBConnection


class ChromaDBRepository:
    def __init__(self, collection_name: str = "trendmirror_kb"):
        self._connection = ChromaDBConnection()
        self.collection = self._connection.get_collection(collection_name)

    def add_documents(self, documents: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]] = None,
                      ids: List[str] = None):
        # 노트북의 chroma_upsert 로직 구현
        if ids is None:
            import uuid
            ids = [f"{uuid.uuid4().hex}" for _ in range(len(documents))]

        if metadatas is None:
            metadatas = [{"text": doc} for doc in documents]

        self.collection.upsert(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict[str, Any]:
        # 노트북의 chroma_search 로직 구현
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )