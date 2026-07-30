from abc import ABC, abstractmethod


class BaseEmbedding(ABC):
    """
    Abstract base class for embeddings.
    """

    @abstractmethod
    def encode(self, text: str) -> list[float]:
        """
        Compute the embedding vector for the given text.
        """
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Return the dimension of the embedding vector.
        """
        pass
