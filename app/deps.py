# app/deps.py
from fastapi import Depends
from app.repository.vector.vector_repo import ChromaDBRepository
from app.service.embedding_service import EmbeddingService
from app.service.vector_service import VectorService
from app.service.agent_service import AgentService

# 1. Repository & Basic Services
def get_vector_repository() -> ChromaDBRepository:
    return ChromaDBRepository() #

def get_embedding_service() -> EmbeddingService:
    return EmbeddingService() #

# 2. VectorService (Repo + EmbService 주입)
def get_vector_service(
    vector_repo: ChromaDBRepository = Depends(get_vector_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> VectorService:
    return VectorService(vector_repository=vector_repo, embedding_service=embedding_service)

# 3. AgentService (VectorService 주입) - 최종적으로 API에서 호출
def get_agent_service(
    vector_service: VectorService = Depends(get_vector_service),
) -> AgentService:
    return AgentService(vector_service=vector_service)