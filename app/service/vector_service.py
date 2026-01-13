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
        주어진 카테고리와 SNS에 대해 키워드 언급 빈도를 계산하여 반환합니다.
        """
        # 해당 카테고리와 SNS에 대한 모든 문서를 가져옵니다.
        # 주의: 이 방법은 모든 메타데이터를 로드하므로, 데이터 양이 매우 많을 경우 성능에 영향을 줄 수 있습니다.
        # ChromaDB의 query 메서드는 n_results를 사용하지만, where 절만으로 모든 관련 문서를 가져오기 위해선
        # n_results를 충분히 크게 설정하거나, ChromaDB의 collection.get 기능을 고려할 수 있습니다.
        results = self.vector_repository.get_by_metadata(
            where={"$and": [{"category": category}, {"sns": sns}]},
            include=['metadatas']
        )
        # get_by_metadata는 n_results를 직접 받지 않으므로, 여기서 상위 N개 제한은 적용하지 않고,
        # 모든 메타데이터를 가져온 후 Python 코드에서 빈도수를 계산합니다.

        keyword_counts = {}
        if results and results['metadatas']:
            for metadata_list in results['metadatas']:
                for meta in metadata_list:
                    keyword = meta.get("keyword")
                    if keyword:
                        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        # 빈도수 기준으로 정렬
        sorted_keywords = sorted(keyword_counts.items(), key=lambda item: item[1], reverse=True)
        return [{"keyword": kw, "frequency": count} for kw, count in sorted_keywords]