"""
Tests for how PDFProcessor.process_single_file treats its source.

An http:// or https:// source is a file in S3 and must be downloaded first.
Anything else is a local path and must go straight to the converter.
"""

from unittest.mock import MagicMock

import pytest


async def _process(monkeypatch, source):
    """Run process_single_file with mocks; return (download mock, converted path)."""
    import th2rag.rag.tasks.process_pdf as module

    processor = module.PDFProcessor.__new__(module.PDFProcessor)
    processor.chunker = MagicMock()
    processor.chunker.chunk_document.return_value = [MagicMock(text="Some text.")]
    processor.embedding_model = MagicMock()
    processor.storage = MagicMock()
    processor._initialized = True

    download = MagicMock(return_value=b"%PDF-1.4")
    monkeypatch.setattr(module, "download_file_from_s3", download)

    converted = []

    def fake_convert(path, doc_id=None):
        converted.append(path)
        return {"document": MagicMock(), "metadata": {"source": path}}

    monkeypatch.setattr(module, "convert_any_doc", fake_convert)

    await processor.process_single_file(
        doc_id=1, source=source, file_index=1, total_files=1
    )
    return download, converted[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [
        "http://127.0.0.1:9000/bucket/1/doc.pdf",
        "https://s3.example.com/bucket/1/doc.pdf",
    ],
)
async def test_remote_source_is_downloaded_before_conversion(monkeypatch, source):
    download, converted_path = await _process(monkeypatch, source)

    download.assert_called_once_with(source)
    assert converted_path != source


@pytest.mark.asyncio
async def test_local_source_is_not_downloaded(monkeypatch):
    download, converted_path = await _process(monkeypatch, "/fake/doc.pdf")

    download.assert_not_called()
    assert converted_path == "/fake/doc.pdf"
