from abc import ABC, abstractmethod


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, doc_id: int = None, limit: int = 3) -> list[dict]:
        """
        Given a user query and optional doc_id, return relevant chunks
        (e.g., from a vector DB or other knowledge store).
        """
        pass
