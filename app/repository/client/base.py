# app/repository/client/base.py
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    def get_chat_model(self):
        pass

    @abstractmethod
    def get_embedding_model(self):
        pass

class BaseSearchClient(ABC):
    @abstractmethod
    def search(self, query: str) -> list:
        pass