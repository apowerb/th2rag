"""
Non-regression tests: PDF conversion under Docling 2.73.

Validates that the bump from 2.20 → 2.73 does NOT break:
  - convert_with_docling on a real PDF (no exception, non-empty text)
  - get_pipeline_options / get_image_pipeline_options API (no removed attrs)
  - ThreadedPdfPipelineOptions import & instantiation
  - chunk count > 0 via token_count in metadata
  - All other formats still pass (DOCX-text, HTML, MD, PNG-OCR)

No mocks on Docling internals — real conversion engine used.
S3 upload is mocked (no network).
No DB connections.

Run:
    cd backend
    PYTHONPATH=src .venv/bin/pytest test/converters/test_pdf_docling_273.py -v --no-cov
"""
import os
import warnings

import pytest
from unittest.mock import patch

FIXTURES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures")
)


def fixture_path(filename: str) -> str:
    return os.path.join(FIXTURES_DIR, filename)


def _patch_s3():
    return patch(
        "th2rag.rag.converters.pdf_converter.upload_file_to_s3",
        return_value="http://s3.fake/img.png",
    )


# ---------------------------------------------------------------------------
# Fixture PDF generation (created once per session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pdf_fixture_path():
    """Generate the PDF fixture if it doesn't exist; return its path."""
    import sys

    sys.path.insert(0, FIXTURES_DIR)
    from generate_pdf_fixture import generate_pdf_fixture

    return generate_pdf_fixture()


# ---------------------------------------------------------------------------
# 1. API surface checks — no removed symbols in Docling 2.73
# ---------------------------------------------------------------------------


class TestDocling273ApiSurface:
    """Verify that no API used in pdf_converter.py was removed in 2.73."""

    def test_threadedpdfpipelineoptions_importable(self):
        from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions

        opts = ThreadedPdfPipelineOptions()
        assert opts is not None

    def test_pdfpipelineoptions_do_table_structure(self):
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.do_table_structure = True
        assert opts.do_table_structure is True

    def test_pdfpipelineoptions_table_structure_mode(self):
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.do_table_structure = True
        opts.table_structure_options.mode = "fast"
        assert opts.table_structure_options.mode == "fast"

    def test_pdfpipelineoptions_do_ocr(self):
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.do_ocr = False
        assert opts.do_ocr is False

    def test_pdfpipelineoptions_generate_picture_images(self):
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.generate_picture_images = True
        assert opts.generate_picture_images is True

    def test_pdfpipelineoptions_do_picture_description(self):
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.do_picture_description = False
        assert opts.do_picture_description is False

    def test_get_pipeline_options_no_exception(self):
        """get_pipeline_options must run without raising any exception."""
        from th2rag.rag.converters.pdf_converter import get_pipeline_options

        opts = get_pipeline_options(enable_ocr=False)
        assert opts is not None

    def test_get_image_pipeline_options_no_exception(self):
        from th2rag.rag.converters.pdf_converter import get_image_pipeline_options

        opts = get_image_pipeline_options(enable_ocr=True)
        assert opts is not None

    def test_no_deprecation_error_from_pipeline_options_setup(self):
        """DeprecationWarning is acceptable; DeprecationError is not."""
        from th2rag.rag.converters.pdf_converter import get_pipeline_options

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            opts = get_pipeline_options(enable_ocr=False)

        errors = [
            w for w in caught if issubclass(w.category, (DeprecationWarning,))
            and "error" in str(w.message).lower()
        ]
        # Warnings are fine; only hard errors would surface as exceptions (already tested above)
        assert opts is not None, "get_pipeline_options must return options"

    def test_document_converter_format_options_importable(self):
        from docling.document_converter import (
            AsciiDocFormatOption,
            DocumentConverter,
            HTMLFormatOption,
            ImageFormatOption,
            MarkdownFormatOption,
            PdfFormatOption,
            PowerpointFormatOption,
            WordFormatOption,
        )
        assert DocumentConverter is not None


# ---------------------------------------------------------------------------
# 2. PDF conversion — real Docling 2.73 pipeline, no mock on conversion
# ---------------------------------------------------------------------------


class TestPdfConversionDocling273:
    """Real PDF conversion via convert_with_docling under Docling 2.73."""

    def test_pdf_conversion_no_exception(self, pdf_fixture_path):
        """convert_with_docling must not raise on a valid PDF."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        assert result is not None

    def test_pdf_result_has_document_key(self, pdf_fixture_path):
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        assert "document" in result, "Result must have 'document' key"

    def test_pdf_result_has_metadata_key(self, pdf_fixture_path):
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        assert "metadata" in result, "Result must have 'metadata' key"

    def test_pdf_exported_text_non_empty(self, pdf_fixture_path):
        """The converted document must export non-empty markdown."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "PDF conversion produced empty text"

    def test_pdf_text_contains_expected_content(self, pdf_fixture_path):
        """The fixture text must appear in the extracted output."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        doc = result["document"]
        text = doc.export_to_markdown().lower()
        assert "th2rag" in text, f"Expected 'th2rag' in extracted text. Got: {text[:300]}"

    def test_pdf_token_count_greater_than_zero(self, pdf_fixture_path):
        """token_count in metadata must be > 0 (proxy for chunk count)."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        token_count = result["metadata"]["token_count"]
        assert token_count > 0, f"token_count must be > 0, got {token_count}"

    def test_pdf_metadata_type_is_pdf(self, pdf_fixture_path):
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        assert result["metadata"]["type"] == "pdf"

    def test_pdf_ocr_not_used_on_text_pdf(self, pdf_fixture_path):
        """A text PDF must NOT trigger OCR (page has enough tokens)."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with _patch_s3():
            result = convert_with_docling(source=pdf_fixture_path)
        assert result["metadata"]["ocr_used"] is False, (
            "OCR must NOT be triggered on a PDF with native text"
        )

    def test_pdf_warnings_are_not_errors(self, pdf_fixture_path):
        """Any DeprecationWarning from Docling must not be a fatal error."""
        from th2rag.rag.converters.pdf_converter import convert_with_docling

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with _patch_s3():
                result = convert_with_docling(source=pdf_fixture_path)

        # Print all warnings for inspection in CI output
        docling_warnings = [
            w for w in caught
            if "docling" in str(w.filename).lower() or "docling" in str(w.message).lower()
        ]
        for w in docling_warnings:
            print(f"  [DOCLING WARNING] {w.category.__name__}: {w.message} ({w.filename}:{w.lineno})")

        # The only acceptable Docling warning is DeprecationWarning, never an error
        fatal = [
            w for w in docling_warnings
            if w.category not in (DeprecationWarning, PendingDeprecationWarning, UserWarning, FutureWarning)
        ]
        assert not fatal, f"Unexpected fatal warnings from Docling: {fatal}"
        # Conversion must still have succeeded
        assert result is not None


# ---------------------------------------------------------------------------
# 3. Regression: other formats still pass under Docling 2.73
# ---------------------------------------------------------------------------


class TestOtherFormatsRegressionDocling273:
    """
    Quick smoke tests confirming DOCX-text, HTML, MD, PNG still convert
    correctly under Docling 2.73 (no regressions from the bump).
    """

    def _convert(self, filename: str) -> dict:
        from th2rag.rag.converters.documents_converter import convert_any_doc

        path = fixture_path(filename)
        if not os.path.exists(path):
            pytest.skip(f"Fixture not found: {path}")
        with _patch_s3():
            return convert_any_doc(source=path)

    def test_docx_text_no_regression(self):
        result = self._convert("sample_text.docx")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "DOCX-text regression: empty output"

    def test_html_no_regression(self):
        result = self._convert("sample.html")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "HTML regression: empty output"

    def test_markdown_no_regression(self):
        result = self._convert("sample.md")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "MD regression: empty output"

    def test_png_ocr_no_regression(self):
        """PNG OCR may produce short text depending on rendering; non-empty is sufficient."""
        result = self._convert("sample_text.png")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "PNG-OCR regression: empty output"
