# app/service/vector_service.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.service.embedding_service import EmbeddingService
from app.repository.vector.vector_repo import ChromaDBRepository


class VectorService:
    def __init__(self, vector_repository: ChromaDBRepository, embedding_service: EmbeddingService):
        self.vector_repository = vector_repository
        self.embedding_service = embedding_service

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]] = None, ids: List[str] = None):
        embeddings = self.embedding_service.create_embeddings(documents)
        self.vector_repository.add_documents(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)

    def search(self, query: str, n_results: int = 25) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_service.create_embedding(query)
        results = self.vector_repository.query(query_embeddings=[query_embedding], n_results=n_results)
        out = []
        if results.get('ids') and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                out.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "meta": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                })
        return out

    def delete_by_metadata(self, filter: Dict[str, Any]):
        return self.vector_repository.delete(where=filter)

    def get_keyword_frequencies(self, category: str, sns: str, n_results: int = 100, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        from collections import Counter
        where_filter = {"$and": [{"category": category}, {"sns": sns}]}
        
        if start_date and end_date:
            start_dt = datetime.strptime(f"{start_date}T00:00:00", "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(f"{end_date}T23:59:59", "%Y-%m-%dT%H:%M:%S")
            where_filter["$and"].append({"published_at": {"$gte": start_dt.timestamp()}})
            where_filter["$and"].append({"published_at": {"$lte": end_dt.timestamp()}})

        from app.core.logger import logger # Import logger locally for debugging
        logger.debug(f"ChromaDB where filter: {where_filter}")
        
        results = self.vector_repository.get_by_metadata(where=where_filter, include=['metadatas'])
        keyword_counts = Counter()
        if results and results.get('metadatas'):
            for meta in results['metadatas']:
                keywords_str = meta.get("keyword")
                if keywords_str and isinstance(keywords_str, str):
                    individual_keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                    keyword_counts.update(individual_keywords)
        
        return [{"keyword": kw, "frequency": count} for kw, count in keyword_counts.most_common(n_results)]

    def get_sentiment_frequencies(self, category: str, sns: str, n_results: int = 100, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        from collections import Counter
        where_filter = {"$and": [{"category": category}, {"sns": sns}]}

        if start_date and end_date:
            start_dt = datetime.strptime(f"{start_date}T00:00:00", "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(f"{end_date}T23:59:59", "%Y-%m-%dT%H:%M:%S")
            where_filter["$and"].append({"published_at": {"$gte": start_dt.timestamp()}})
            where_filter["$and"].append({"published_at": {"$lte": end_dt.timestamp()}})

        results = self.vector_repository.get_by_metadata(where=where_filter, include=['metadatas'])
        sentiment_counts = Counter()
        if results and results.get('metadatas'):
            for meta in results['metadatas']:
                sentiment_str = meta.get("sentiment")
                if sentiment_str and isinstance(sentiment_str, str):
                    sentiment_counts.update([sentiment_str])
        
        most_common_sentiments = sentiment_counts.most_common(n_results)
        
        return [{"sentiment": s, "frequency": count} for s, count in most_common_sentiments]

    def get_documents_for_period(self, category: str, sns: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        주어진 기간 내의 모든 문서 메타데이터와 내용을 반환합니다.
        """
        where_filter = {"$and": [{"category": category}, {"sns": sns}]}
        
        if start_date and end_date:
            start_dt = datetime.strptime(f"{start_date}T00:00:00", "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(f"{end_date}T23:59:59", "%Y-%m-%dT%H:%M:%S")
            where_filter["$and"].append({"published_at": {"$gte": start_dt.timestamp()}})
            where_filter["$and"].append({"published_at": {"$lte": end_dt.timestamp()}})

        from app.core.logger import logger
        logger.debug(f"ChromaDB filter for get_documents_for_period: {where_filter}")
        
        # Include 'documents' to get the actual text content
        results = self.vector_repository.get_by_metadata(where=where_filter, include=['metadatas', 'documents'])
        
        output_docs = []
        if results and results.get('metadatas') and results.get('documents'):
            for i in range(len(results['metadatas'])):
                doc_metadata = results['metadatas'][i]
                doc_text = results['documents'][i]
                # Combine metadata and text into a single dictionary
                output_docs.append({"text": doc_text, **doc_metadata})
        
        return output_docs

    def check_data_existence(self, category: str, start_date: str, end_date: str) -> Dict[str, Any]:
        user_start_ts = datetime.strptime(f"{start_date}T00:00:00", "%Y-%m-%dT%H:%M:%S").timestamp()
        user_end_ts = datetime.strptime(f"{end_date}T23:59:59", "%Y-%m-%dT%H:%M:%S").timestamp()

        results = self.vector_repository.get_by_metadata(where={"category": category}, include=['metadatas'])

        if not results or not results.get('metadatas'):
            return {"status": "NONE", "new_start": start_date, "new_end": end_date}

        published_timestamps = [meta['published_at'] for meta in results['metadatas'] if meta.get('published_at') and isinstance(meta['published_at'], (int, float))]
        
        if not published_timestamps:
            return {"status": "NONE", "new_start": start_date, "new_end": end_date}

        db_min_ts = min(published_timestamps)
        db_max_ts = max(published_timestamps)
        db_min_dt = datetime.fromtimestamp(db_min_ts)
        db_max_dt = datetime.fromtimestamp(db_max_ts)

        if db_min_ts <= user_start_ts and db_max_ts >= user_end_ts:
            return {"status": "FULL", "db_start": db_min_dt.strftime("%Y-%m-%d"), "db_end": db_max_dt.strftime("%Y-%m-%d")}

        if user_end_ts < db_min_ts or user_start_ts > db_max_ts:
            return {"status": "NONE", "new_start": start_date, "new_end": end_date}
        
        new_start_dt = datetime.fromtimestamp(user_start_ts)
        new_end_dt = datetime.fromtimestamp(user_end_ts)
        
        if user_start_ts < db_min_ts and user_end_ts > db_max_ts:
            pass
        elif user_start_ts < db_min_ts:
            new_end_dt = db_min_dt - timedelta(days=1)
        elif user_end_ts > db_max_ts:
            new_start_dt = db_max_dt + timedelta(days=1)
        
        return {
            "status": "PARTIAL",
            "new_start": new_start_dt.strftime("%Y-%m-%d"),
            "new_end": new_end_dt.strftime("%Y-%m-%d"),
            "db_start": db_min_dt.strftime("%Y-%m-%d"),
            "db_end": db_max_dt.strftime("%Y-%m-%d")
        }