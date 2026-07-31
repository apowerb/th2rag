import lancedb

from th2rag.config import settings
from th2rag.rag.retrieval import exceptions
from th2rag.rag.retrieval.lancedb.schemas import Chunks
from th2rag.utils.logger import setup_logger

logger = setup_logger(__name__)


class LanceDBStorage:
    def __init__(self, db_uri: str = settings.lancedb_url, table_name: str = "docling"):
        self.db = lancedb.connect(db_uri)
        self.table_name = table_name

        if self.table_name in self.db.table_names():
            self.table = self.db.open_table(table_name)
        else:
            self.table = self.db.create_table(table_name, schema=Chunks)

    def add_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            logger.warning("add_chunks called with an empty list — no-op")
            return
        try:
            self.table.add(chunks)
        except Exception:
            raise exceptions.LanceDBStorageException("Something went wrong with adding the chunks")

    def query(self, query_vector: list[float], doc_id: int = None, limit: int = 3) -> list[dict]:
        if doc_id is None:
            raise exceptions.KnowledgeNotProvidedException("The knowledge document is not provided")

        try:
            search = self.table.search(query_vector).where(where=f"doc_id == {doc_id}")
            result = search.limit(limit)
            return result.to_pandas().to_dict(orient="records")
        except Exception:
            raise exceptions.LanceDBRetreiverException(
                "Something went wrong with retreiveing the related documents"
            )

    def delete_chunks(self, doc_id: int):
        try:
            self.table.delete(f"doc_id == {doc_id}")
        except Exception:
            raise exceptions.LanceDBStorageException(
                "Something went wrong with deleting the documents from the vector database"
            )
