
from th2rag.config import settings
from th2rag.rag.embeddings.sentence_transformer import SentenceTransformerEmbedding
from th2rag.rag.retrieval.base import BaseRetriever
from th2rag.rag.retrieval.lancedb.lancedb_storage import LanceDBStorage


class LanceDBRetriever(BaseRetriever):
    def __init__(
        self,
        embedding_model: SentenceTransformerEmbedding,
        db_uri: str = settings.lancedb_url,
        table_name: str = "docling",
        default_limit: int = 3,
    ):
        self.embedding_model = embedding_model
        self.storage = LanceDBStorage(db_uri, table_name)
        self.default_limit = default_limit

    def retrieve(self, query: str, doc_id: int | None = None, limit: int = None) -> list[dict]:
        if limit is None:
            limit = self.default_limit

        query_vector = self.embedding_model.encode(query)
        return self.storage.query(query_vector=query_vector, doc_id=doc_id, limit=limit)
