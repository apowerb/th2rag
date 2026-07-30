from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

embedding_registry_model = (
    get_registry().get("sentence-transformers").create(name="sentence-transformers/gtr-t5-large")
)


class ChunkMetadata(LanceModel):
    filename: str | None
    page_numbers: list[int] | None
    title: str | None


class Chunks(LanceModel):
    doc_id: int
    text: str
    vector: Vector(embedding_registry_model.ndims()) = embedding_registry_model.VectorField() # type: ignore
    metadata: ChunkMetadata
