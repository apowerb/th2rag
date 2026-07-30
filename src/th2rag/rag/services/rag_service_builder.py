from th2rag.rag.embeddings.base import BaseEmbedding
from th2rag.rag.embeddings.sentence_transformer import SentenceTransformerEmbedding
from th2rag.rag.generation.base import BaseGenerator
from th2rag.rag.generation.mistral_generator import MistralGenerator
from th2rag.rag.retrieval.base import BaseRetriever
from th2rag.rag.retrieval.lancedb.lancedb_retriever import LanceDBRetriever
from th2rag.rag.services.rag_service import RAGService
#things to add to integrate litellm
from th2rag.rag.generation.litellm_generator import LiteLLMGenerator


class RAGServiceBuilder:
    def __init__(self):
        self._embedding_model = None
        self._retriever = None
        self._generator = None

    def with_embedding_model(self, embedding_model: BaseEmbedding) -> "RAGServiceBuilder":
        self._embedding_model = embedding_model
        return self

    def with_retriever(self, retriever: BaseRetriever) -> "RAGServiceBuilder":
        self._retriever = retriever
        return self

    def with_generator(self, generator: BaseGenerator) -> "RAGServiceBuilder":
        self._generator = generator
        return self

    def build(self, user_config=None) -> RAGService:
        # Set default components if not provided
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformerEmbedding()
        if self._retriever is None:
            self._retriever = LanceDBRetriever(self._embedding_model)
        if self._generator is None:
            #old : self._generator = MistralGenerator()
            #new with litellm
            self._generator = LiteLLMGenerator(user_config=user_config)

        return RAGService(retriever=self._retriever, generator=self._generator)

