# app/service/vector_service.py
from typing import List, Dict, Any
from app.service.embedding_service import EmbeddingService
from app.repository.vector.vector_repo import ChromaDBRepository


class VectorService:
    def __init__(self, vector_repository: ChromaDBRepository, embedding_service: EmbeddingService):
        self.vector_repository = vector_repository
        self.embedding_service = embedding_service

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]] = None, ids: List[str] = None):
        # 1. 텍스트 -> 임베딩 변환
        embeddings = self.embedding_service.create_embeddings(documents)
        # 2. DB 저장 (Upsert)
        self.vector_repository.add_documents(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)

    def search(self, query: str, n_results: int = 25) -> List[Dict[str, Any]]:
        # 1. 질문 -> 임베딩 변환
        query_embedding = self.embedding_service.create_embedding(query)
        # 2. DB 검색
        results = self.vector_repository.query(query_embeddings=[query_embedding], n_results=n_results)

        # 3. 노트북과 동일한 반환 포맷으로 변환 (List of Dicts)
        out = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                out.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "meta": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                })
        return out

    def delete_by_metadata(self, filter: Dict[str, Any]):
        """
        메타데이터 필터를 기반으로 문서를 삭제합니다.
        """
        return self.vector_repository.delete(where=filter)

    def get_keyword_frequencies(self, category: str, sns: str, n_results: int = 100) -> List[Dict[str, Any]]:
        """
        주어진 카테고리와 SNS에 대해 **개별 키워드**의 언급 빈도를 정확히 계산하여 반환합니다.
        콤마로 구분된 키워드 문자열을 분리하여 각 키워드의 빈도를 집계합니다.
        """
        from collections import Counter

        results = self.vector_repository.get_by_metadata(
            where={"$and": [{"category": category}, {"sns": sns}]},
            include=['metadatas']
        )

        keyword_counts = Counter()
        if results and results['metadatas']:
            for meta in results['metadatas']:
                keywords_str = meta.get("keyword")
                if keywords_str and isinstance(keywords_str, str):
                    # 콤마로 구분된 키워드 문자열을 개별 키워드로 분리
                    individual_keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                    keyword_counts.update(individual_keywords)
        
        # 빈도수 기준으로 상위 n_results개의 키워드를 가져옴
        most_common_keywords = keyword_counts.most_common(n_results)
        
        return [{"keyword": kw, "frequency": count} for kw, count in most_common_keywords]