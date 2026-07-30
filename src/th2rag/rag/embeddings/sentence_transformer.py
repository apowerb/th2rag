import threading

from sentence_transformers import SentenceTransformer

from th2rag.config import settings
from th2rag.rag.embeddings import exceptions
from th2rag.rag.embeddings.base import BaseEmbedding
from th2rag.utils.logger import setup_logger

logger = setup_logger(__name__)

# Le modele est lourd (gtr-t5-large ~670 Mo). L instancier par tache/PDF
# provoquait, en lot concurrent, la race accelerate/meta-device
# "Cannot copy out of meta tensor; no data!" -> docs FAILED de facon
# intermittente. On charge chaque (model_name, cache_folder) UNE fois,
# sous verrou, et on partage l instance.
_MODEL_CACHE: dict = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _get_shared_model(model_name: str, cache_folder: str) -> "SentenceTransformer":
    key = (model_name, cache_folder)
    model = _MODEL_CACHE.get(key)
    if model is not None:
        return model
    with _MODEL_CACHE_LOCK:
        model = _MODEL_CACHE.get(key)
        if model is None:
            logger.info(f"Loading embedding model once (shared): {model_name}")
            model = SentenceTransformer(model_name, cache_folder=cache_folder)
            _MODEL_CACHE[key] = model
        return model

class SentenceTransformerEmbedding(BaseEmbedding):

    """
    Embedding implementation using SentenceTransformer
    """

    # def __init__(self, model_name: str = "sentence-transformers/gtr-t5-large"):
    #     self.model = SentenceTransformer(model_name)
    #     self.embedding_dims = self.model.get_sentence_embedding_dimension()

    def __init__(self, model_name: str = None, cache_folder: str = None):
        self.model_name = model_name or settings.embedding_model_name
        self.cache_folder = cache_folder or settings.embedding_cache_folder

        logger.info(f"Loading embedding model: {self.model_name}")
        logger.info(f"Cache folder: {self.cache_folder}")

        try:
            self.model = _get_shared_model(self.model_name, self.cache_folder)
            self.embedding_dims = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dims}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise exceptions.EmbeddingException(
                f"Failed to load model '{self.model_name}': {str(e)}"
            )


    # def encode(self, text: str) -> list[float]:
    #     """
    #     Encode text into a vector using SentenceTransformer.
    #     """
    #     try:
    #         return self.model.encode(text, convert_to_numpy=True).tolist()
    #     except Exception:
    #         raise exceptions.EmbeddingException("Something went wrong with the embedding")

    def encode(self, text: str) -> list[float]:
        """
        Encode text into a vector using SentenceTransformer.
    
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True).tolist()
            logger.debug(f"Encoded text of length {len(text)} to vector of dimension {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Embedding encoding failed: {e}")
            raise exceptions.EmbeddingException(
                f"Failed to encode text: {str(e)}"
            )


    # def get_embedding_dimension(self):
    #     return self.embedding_dims

    def ndims(self):
        return self.embedding_dims

    def get_embedding_dimension(self) -> int:
        """
        Returns Integer dimension of embeddings produced by this model
        """
        return self.embedding_dims
