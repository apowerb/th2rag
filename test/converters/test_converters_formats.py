"""
Tests for Lot 2 & Lot 3 — RAG indexation robustesse

Lot 2: HTML, Markdown, images (PNG/JPG), AsciiDoc support in convert_any_doc
Lot 3: DOCX/PPTX OCR/image fallback

All tests use real Docling conversion on fixture files.
Only DB/S3/network dependencies are mocked.

Run: cd backend && PYTHONPATH=src .venv/bin/pytest test/converters/test_converters_formats.py -v --no-cov
"""
import os
import pytest
from unittest.mock import patch, MagicMock

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def fixture_path(filename: str) -> str:
    return os.path.abspath(os.path.join(FIXTURES_DIR, filename))


# ---------------------------------------------------------------------------
# Helpers: patch S3 upload so handle_images doesn't fail on network
# ---------------------------------------------------------------------------

def _patch_s3():
    """Context manager: replace S3 upload with a no-op."""
    return patch(
        "th2rag.rag.converters.pdf_converter.upload_file_to_s3",
        return_value="http://s3.fake/image.png",
    )


# ===========================================================================
# LOT 2 — Format dispatch tests
# ===========================================================================


class TestFormatDispatchLot2:
    """
    Ensure convert_any_doc accepts new formats without raising ValueError.
    Also verifies the returned document is non-empty.
    """

    def _run(self, filename: str) -> dict:
        """Run convert_any_doc with S3 mock and return result."""
        from th2rag.rag.converters.documents_converter import convert_any_doc
        path = fixture_path(filename)
        if not os.path.exists(path):
            pytest.skip(f"Fixture not found: {path}")
        with _patch_s3():
            return convert_any_doc(source=path)

    # --- HTML ---

    def test_html_accepted(self):
        result = self._run("sample.html")
        assert "document" in result, "result must have 'document' key"

    def test_html_non_empty(self):
        result = self._run("sample.html")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "HTML conversion produced empty document"

    def test_htm_accepted(self):
        """htm alias must also be accepted."""
        from th2rag.rag.converters.documents_converter import convert_any_doc
        html_path = fixture_path("sample.html")
        if not os.path.exists(html_path):
            pytest.skip("HTML fixture not found")
        # Create a .htm symlink or copy for this test
        htm_path = fixture_path("sample.htm")
        import shutil
        shutil.copy(html_path, htm_path)
        try:
            with _patch_s3():
                result = convert_any_doc(source=htm_path)
            assert "document" in result
        finally:
            if os.path.exists(htm_path):
                os.remove(htm_path)

    # --- Markdown ---

    def test_markdown_accepted(self):
        result = self._run("sample.md")
        assert "document" in result

    def test_markdown_non_empty(self):
        result = self._run("sample.md")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "Markdown conversion produced empty document"

    def test_markdown_alias_accepted(self):
        """'.markdown' extension must also be accepted."""
        from th2rag.rag.converters.documents_converter import convert_any_doc
        md_path = fixture_path("sample.md")
        if not os.path.exists(md_path):
            pytest.skip("Markdown fixture not found")
        markdown_path = fixture_path("sample.markdown")
        import shutil
        shutil.copy(md_path, markdown_path)
        try:
            with _patch_s3():
                result = convert_any_doc(source=markdown_path)
            assert "document" in result
        finally:
            if os.path.exists(markdown_path):
                os.remove(markdown_path)

    # --- Images ---

    def test_png_accepted(self):
        result = self._run("sample_text.png")
        assert "document" in result

    def test_png_non_empty(self):
        result = self._run("sample_text.png")
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "PNG conversion produced empty document"

    def test_jpg_accepted(self):
        """Create a JPEG copy of the PNG fixture and test acceptance."""
        from th2rag.rag.converters.documents_converter import convert_any_doc
        png_path = fixture_path("sample_text.png")
        if not os.path.exists(png_path):
            pytest.skip("PNG fixture not found")
        jpg_path = fixture_path("sample_text.jpg")
        from PIL import Image
        with Image.open(png_path) as img:
            img.convert("RGB").save(jpg_path, format="JPEG")
        try:
            with _patch_s3():
                result = convert_any_doc(source=jpg_path)
            assert "document" in result
        finally:
            if os.path.exists(jpg_path):
                os.remove(jpg_path)

    # --- AsciiDoc ---

    def test_adoc_accepted(self):
        """AsciiDoc .adoc must be accepted (dispatch coverage)."""
        from th2rag.rag.converters.documents_converter import convert_any_doc
        adoc_path = fixture_path("sample.adoc")
        # Create minimal AsciiDoc fixture on the fly
        with open(adoc_path, "w") as f:
            f.write("= th2rag AsciiDoc fixture\n\nThis is a test paragraph for AsciiDoc conversion.\n")
        try:
            with _patch_s3():
                result = convert_any_doc(source=adoc_path)
            assert "document" in result
        finally:
            if os.path.exists(adoc_path):
                os.remove(adoc_path)

    # --- Unsupported still raises ---

    def test_unsupported_format_raises_value_error(self):
        """A real file with unknown extension must raise ValueError, not FileNotFoundError."""
        import tempfile
        from th2rag.rag.converters.documents_converter import convert_any_doc
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp:
            tmp.write(b"dummy content")
            tmp_path = tmp.name
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                convert_any_doc(source=tmp_path)
        finally:
            os.remove(tmp_path)


# ===========================================================================
# LOT 2 — ALLOWED_EXTENSIONS whitelist tests
# ===========================================================================


class TestAllowedExtensionsLot2:
    """Verify new formats are registered in the service whitelist."""

    def _get_allowed(self):
        from th2rag.knowledge.service import ALLOWED_EXTENSIONS
        return ALLOWED_EXTENSIONS

    def test_html_in_allowed(self):
        assert ".html" in self._get_allowed()

    def test_htm_in_allowed(self):
        assert ".htm" in self._get_allowed()

    def test_md_in_allowed(self):
        assert ".md" in self._get_allowed()

    def test_markdown_in_allowed(self):
        assert ".markdown" in self._get_allowed()

    def test_png_in_allowed(self):
        assert ".png" in self._get_allowed()

    def test_jpg_in_allowed(self):
        assert ".jpg" in self._get_allowed()

    def test_jpeg_in_allowed(self):
        assert ".jpeg" in self._get_allowed()

    def test_tiff_in_allowed(self):
        assert ".tiff" in self._get_allowed()

    def test_tif_in_allowed(self):
        assert ".tif" in self._get_allowed()

    def test_bmp_in_allowed(self):
        assert ".bmp" in self._get_allowed()

    def test_adoc_in_allowed(self):
        assert ".adoc" in self._get_allowed()

    def test_asciidoc_in_allowed(self):
        assert ".asciidoc" in self._get_allowed()

    # Regression: existing extensions still present
    def test_pdf_still_in_allowed(self):
        assert ".pdf" in self._get_allowed()

    def test_docx_still_in_allowed(self):
        assert ".docx" in self._get_allowed()

    def test_txt_still_in_allowed(self):
        assert ".txt" in self._get_allowed()


# ===========================================================================
# LOT 3 — DOCX text extraction
# ===========================================================================


class TestDocxConversionLot3:
    """
    Verify that a DOCX with native text content produces > 0 content.
    OCR on graphical DOCX requires LibreOffice (not available on VM),
    so we test the text extraction path instead.
    """

    def test_docx_text_accepted(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc
        path = fixture_path("sample_text.docx")
        if not os.path.exists(path):
            pytest.skip("DOCX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        assert "document" in result

    def test_docx_text_non_empty(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc
        path = fixture_path("sample_text.docx")
        if not os.path.exists(path):
            pytest.skip("DOCX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "DOCX with text content produced 0 text"
        assert "th2rag" in text.lower() or "fixture" in text.lower(), (
            f"Expected 'th2rag' or 'fixture' in extracted text, got: {text[:200]}"
        )

    def test_docx_metadata_present(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc
        path = fixture_path("sample_text.docx")
        if not os.path.exists(path):
            pytest.skip("DOCX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        assert "metadata" in result
        assert result["metadata"]["type"] in ("docx", "word", "office")


class TestPptxConversionLot3:
    """
    PPTX native text extraction must produce > 0 content.
    OCR on DrawingML graphics requires LibreOffice (not installed on this VM);
    the converter logs a warning for graphical-only slides.
    """

    def test_pptx_text_accepted(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc

        path = fixture_path("sample_text.pptx")
        if not os.path.exists(path):
            pytest.skip("PPTX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        assert "document" in result

    def test_pptx_text_non_empty(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc

        path = fixture_path("sample_text.pptx")
        if not os.path.exists(path):
            pytest.skip("PPTX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        doc = result["document"]
        text = doc.export_to_markdown()
        assert len(text.strip()) > 0, "PPTX with text content produced 0 text"
        assert "th2rag" in text.lower() or "fixture" in text.lower(), (
            f"Expected 'th2rag' or 'fixture' in extracted text, got: {text[:200]}"
        )

    def test_pptx_metadata_present(self):
        from th2rag.rag.converters.documents_converter import convert_any_doc

        path = fixture_path("sample_text.pptx")
        if not os.path.exists(path):
            pytest.skip("PPTX fixture not found")
        with _patch_s3():
            result = convert_any_doc(source=path)
        assert "metadata" in result
        assert result["metadata"]["type"] == "pptx"
