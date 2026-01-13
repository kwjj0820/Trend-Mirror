# app/repository/vector/vector_repo.py
from typing import List, Dict, Any
from app.core.db import ChromaDBConnection
from app.core.logger import logger # Import logger
import uuid # Import uuid

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

    def delete(self, where: Dict[str, Any]):
        """
        메타데이터 필터를 기반으로 DB에서 문서를 삭제합니다.
        """
        return self.collection.delete(where=where)

    def get_by_metadata(self, where: Dict[str, Any], include: List[str] = None) -> Dict[str, Any]:
        """
        메타데이터 필터를 기반으로 문서를 검색합니다 (임베딩 검색 아님).
        """
        if not self.collection:
            logger.error("ChromaDB collection is not initialized.")
            return {}
        
        try:
            results = self.collection.get(
                where=where,
                include=include if include else ['documents', 'metadatas', 'ids']
            )
            return results
        except Exception as e:
            logger.error(f"Error getting from ChromaDB by metadata: {e}", exc_info=True)
            return {}