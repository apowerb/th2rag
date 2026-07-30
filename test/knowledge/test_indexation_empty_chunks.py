"""
Tests for the 0-chunks guard in PDFProcessor.process_single_file.

Lot 1 — RAG indexation robustesse:
- When chunking produces 0 chunks (e.g. graphic-only PDF), the pipeline must
  NOT call add_chunks([]) and must NOT crash with a LanceDBStorageException.
- The call should raise an exception with a clear message, so the caller
  (process_pdfs_background / process_pdfs_sync) can mark the knowledge FAILED.

All external dependencies are mocked:
- LanceDBStorage (no real LanceDB connection)
- SentenceTransformerEmbedding (no model loading)
- HybridTextChunker (returns configurable chunk list)
- convert_any_doc (returns a stub document)
- download_file_from_s3 (not exercised in these tests)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_processor():
    """
    Build a PDFProcessor with all heavy dependencies mocked.
    Returns (processor, mock_storage, mock_chunker, mock_embedding).
    """
    from th2rag.rag.tasks.process_pdf import PDFProcessor

    mock_storage = MagicMock()
    mock_chunker = MagicMock()
    mock_embedding = MagicMock()

    processor = PDFProcessor.__new__(PDFProcessor)
    processor.chunker = mock_chunker
    processor.embedding_model = mock_embedding
    processor.storage = mock_storage
    processor._initialized = True

    return processor, mock_storage, mock_chunker, mock_embedding


def _stub_convert(monkeypatch, doc_obj=None):
    """Patch convert_any_doc to return a stub document."""
    import th2rag.rag.tasks.process_pdf as module

    if doc_obj is None:
        doc_obj = MagicMock(name="stub_document")

    monkeypatch.setattr(
        module,
        "convert_any_doc",
        lambda path, doc_id=None: {"document": doc_obj, "metadata": {"source": path}},
    )
    return doc_obj


# ---------------------------------------------------------------------------
# RED tests — these describe the EXPECTED behaviour after the fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_chunks_does_not_call_add_chunks(monkeypatch):
    """
    When chunking returns 0 chunks, add_chunks must NEVER be called.
    Before the fix this test fails because add_chunks IS called with [].
    """
    processor, mock_storage, mock_chunker, _ = _make_processor()
    mock_chunker.chunk_document.return_value = []
    _stub_convert(monkeypatch)

    with pytest.raises(Exception):
        await processor.process_single_file(
            doc_id=42,
            source="/fake/empty.pdf",
            file_index=1,
            total_files=1,
        )

    mock_storage.add_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_empty_chunks_raises_with_explicit_message(monkeypatch):
    """
    When chunking returns 0 chunks, process_single_file wraps a ValueError
    (raised by the 0-chunks guard) in a generic Exception.
    We verify:
      - the outer exception is raised (via pytest.raises)
      - the root cause (__context__) is a ValueError
      - the ValueError message contains '0 chunk'
    This is stricter than checking the wrapped message only.
    """
    processor, _, mock_chunker, _ = _make_processor()
    mock_chunker.chunk_document.return_value = []
    _stub_convert(monkeypatch)

    with pytest.raises(Exception) as exc_info:
        await processor.process_single_file(
            doc_id=42,
            source="/fake/empty.pdf",
            file_index=1,
            total_files=1,
        )

    root_cause = exc_info.value.__context__
    assert isinstance(root_cause, ValueError), (
        f"Expected root cause to be ValueError, got {type(root_cause).__name__!r}: {root_cause!r}"
    )
    assert "0 chunk" in str(root_cause).lower(), (
        f"Expected '0 chunk' in ValueError message, got: {root_cause!r}"
    )


@pytest.mark.asyncio
async def test_empty_chunks_does_not_call_embedding(monkeypatch):
    """
    When chunking returns 0 chunks, embedding.encode must NEVER be called
    (no point generating embeddings for nothing).
    """
    processor, _, mock_chunker, mock_embedding = _make_processor()
    mock_chunker.chunk_document.return_value = []
    _stub_convert(monkeypatch)

    with pytest.raises(Exception):
        await processor.process_single_file(
            doc_id=42,
            source="/fake/empty.pdf",
            file_index=1,
            total_files=1,
        )

    mock_embedding.encode.assert_not_called()


@pytest.mark.asyncio
async def test_non_empty_chunks_still_works(monkeypatch):
    """
    Regression guard: when chunking returns actual chunks, the pipeline
    must proceed normally (add_chunks IS called).
    """
    processor, mock_storage, mock_chunker, mock_embedding = _make_processor()

    fake_chunk = MagicMock()
    fake_chunk.text = "Some real text from the document."
    mock_chunker.chunk_document.return_value = [fake_chunk]
    mock_embedding.encode.return_value = [0.1] * 768

    _stub_convert(monkeypatch)

    result = await processor.process_single_file(
        doc_id=99,
        source="/fake/real.pdf",
        file_index=1,
        total_files=1,
    )

    mock_storage.add_chunks.assert_called_once()
    assert result["chunk_count"] == 1
    assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Unit test for the LanceDBStorage.add_chunks defensive guard
# ---------------------------------------------------------------------------


def test_add_chunks_empty_list_no_op():
    """
    After the fix, LanceDBStorage.add_chunks([]) must return without calling
    self.table.add and without raising any exception.
    Before the fix it raises LanceDBStorageException (wrapping the IndexError).
    """
    from th2rag.rag.retrieval.lancedb.lancedb_storage import LanceDBStorage

    storage = LanceDBStorage.__new__(LanceDBStorage)
    mock_table = MagicMock()
    storage.table = mock_table
    storage.table_name = "docling"

    storage.add_chunks([])

    mock_table.add.assert_not_called()


def test_add_chunks_non_empty_still_delegates():
    """
    Regression guard: non-empty list must still be passed to self.table.add.
    """
    from th2rag.rag.retrieval.lancedb.lancedb_storage import LanceDBStorage

    storage = LanceDBStorage.__new__(LanceDBStorage)
    mock_table = MagicMock()
    storage.table = mock_table
    storage.table_name = "docling"

    chunks = [{"doc_id": 1, "text": "hello", "vector": [0.0], "metadata": {}}]
    storage.add_chunks(chunks)

    mock_table.add.assert_called_once_with(chunks)
