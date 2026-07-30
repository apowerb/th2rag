"""
Tests pour les corrections de review globale :
- Correction 1 : pas de fuite tmpdir dans legacy_converter.py
- Correction 2 : URL S3 absente de error_message dans process_pdf.py
"""
import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ===========================================================================
# Correction 1 -- Fuite tmpdir legacy_converter
# ===========================================================================

class TestLegacyConverterTmpdirCleanup:
    """Le tmpdir doit etre nettoye dans TOUS les cas d echec."""

    def _make_fake_doc_file(self) -> str:
        fd, path = tempfile.mkstemp(suffix=".doc")
        os.write(fd, b"dummy doc content")
        os.close(fd)
        return path

    def test_tmpdir_cleaned_on_subprocess_returncode_nonzero(self):
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        source = self._make_fake_doc_file()
        try:
            captured_tmpdir = {}
            original_mkdtemp = tempfile.mkdtemp

            def fake_mkdtemp(**kwargs):
                d = original_mkdtemp(**kwargs)
                captured_tmpdir["path"] = d
                return d

            fake_result = MagicMock()
            fake_result.returncode = 1
            fake_result.stderr = "conversion failed"

            with patch("tempfile.mkdtemp", side_effect=fake_mkdtemp), \
                 patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=fake_result):
                with pytest.raises(ValueError, match="LibreOffice conversion failed"):
                    convert_with_libreoffice(source)

            assert "path" in captured_tmpdir, "mkdtemp n a pas ete appele"
            assert not os.path.exists(captured_tmpdir["path"]), (
                f"Le tmpdir {captured_tmpdir['path']} existe encore apres returncode != 0"
            )
        finally:
            if os.path.exists(source):
                os.remove(source)

    def test_tmpdir_cleaned_on_timeout(self):
        import subprocess
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        source = self._make_fake_doc_file()
        try:
            captured_tmpdir = {}
            original_mkdtemp = tempfile.mkdtemp

            def fake_mkdtemp(**kwargs):
                d = original_mkdtemp(**kwargs)
                captured_tmpdir["path"] = d
                return d

            with patch("tempfile.mkdtemp", side_effect=fake_mkdtemp), \
                 patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="soffice", timeout=120)):
                with pytest.raises(ValueError, match="timeout"):
                    convert_with_libreoffice(source)

            assert "path" in captured_tmpdir
            assert not os.path.exists(captured_tmpdir["path"]), (
                f"Le tmpdir {captured_tmpdir['path']} existe encore apres TimeoutExpired"
            )
        finally:
            if os.path.exists(source):
                os.remove(source)

    def test_tmpdir_cleaned_when_converted_file_missing(self):
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        source = self._make_fake_doc_file()
        try:
            captured_tmpdir = {}
            original_mkdtemp = tempfile.mkdtemp

            def fake_mkdtemp(**kwargs):
                d = original_mkdtemp(**kwargs)
                captured_tmpdir["path"] = d
                return d

            fake_result = MagicMock()
            fake_result.returncode = 0
            fake_result.stderr = ""

            with patch("tempfile.mkdtemp", side_effect=fake_mkdtemp), \
                 patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=fake_result):
                with pytest.raises(ValueError, match="n'a pas produit"):
                    convert_with_libreoffice(source)

            assert "path" in captured_tmpdir
            assert not os.path.exists(captured_tmpdir["path"]), (
                f"Le tmpdir {captured_tmpdir['path']} existe encore quand fichier converti absent"
            )
        finally:
            if os.path.exists(source):
                os.remove(source)

    def test_tmpdir_kept_on_success(self):
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        source = self._make_fake_doc_file()
        real_tmpdir = tempfile.mkdtemp(prefix="th2rag_test_")
        fake_converted = os.path.join(
            real_tmpdir,
            os.path.splitext(os.path.basename(source))[0] + ".docx"
        )
        with open(fake_converted, "wb") as f:
            f.write(b"fake docx")

        captured_tmpdir = {}

        try:
            def fake_mkdtemp(**kwargs):
                captured_tmpdir["path"] = real_tmpdir
                return real_tmpdir

            fake_result = MagicMock()
            fake_result.returncode = 0
            fake_result.stderr = ""

            with patch("tempfile.mkdtemp", side_effect=fake_mkdtemp), \
                 patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=fake_result):
                result_path = convert_with_libreoffice(source)

            assert os.path.exists(captured_tmpdir["path"]), (
                "Le tmpdir ne doit PAS etre supprime en cas de succes"
            )
            assert result_path == fake_converted
        finally:
            if os.path.exists(source):
                os.remove(source)
            if os.path.exists(real_tmpdir):
                shutil.rmtree(real_tmpdir, ignore_errors=True)


# ===========================================================================
# Correction 2 -- URL S3 absente de error_message
# ===========================================================================

class TestErrorMessageNoS3Url:
    """error_message ne doit JAMAIS contenir une URL S3 (https:// ou s3://)."""

    @pytest.mark.asyncio
    async def test_sync_all_failed_error_message_no_s3_url(self, monkeypatch):
        """
        process_pdfs_sync : quand tous les fichiers echouent, le PREMIER appel
        update_knowledge_status(FAILED) doit contenir le basename et non l URL S3.
        Le code peut appeler update_knowledge_status plusieurs fois (comportement connu) ;
        on verifie que le premier appel meaningful ne contient pas d URL.
        """
        import th2rag.rag.tasks.process_pdf as module
        from th2rag.models import Status

        s3_url = "https://s3.eu-west-3.amazonaws.com/my-bucket/docs/report.pdf"
        mock_processor_instance = MagicMock()
        mock_processor_instance.process_single_file = AsyncMock(
            side_effect=Exception(
                f"Document processing failed for {s3_url}: 0 chunks"
            )
        )
        monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

        captured_calls = []

        async def fake_update_status(knowledge_id, new_status, db, error_message=None):
            captured_calls.append({"status": new_status, "error_message": error_message})

        monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)
        mock_db = AsyncMock()

        with pytest.raises(Exception):
            await module.process_pdfs_sync(
                doc_id=1,
                sources=[s3_url],
                db=mock_db,
            )

        failed_calls = [c for c in captured_calls if c["status"] == Status.FAILED]
        assert failed_calls, "Aucun appel FAILED"

        # Le premier appel FAILED doit avoir un error_message avec le basename, sans URL
        first_failed_with_msg = next(
            (c for c in failed_calls if c["error_message"]), None
        )
        assert first_failed_with_msg is not None, (
            f"Aucun appel FAILED avec error_message non vide. Appels: {failed_calls}"
        )
        msg = first_failed_with_msg["error_message"]
        assert "https://" not in msg, (
            f"URL S3 complete dans error_message : {msg!r}"
        )
        assert "s3://" not in msg, (
            f"URL s3:// dans error_message : {msg!r}"
        )
        assert "report.pdf" in msg, (
            f"Le basename doit etre dans error_message : {msg!r}"
        )

    @pytest.mark.asyncio
    async def test_sync_zero_chunks_error_message_no_s3_url(self, monkeypatch):
        """
        Le cas 0-chunks (ValueError avec source URL S3) ne doit pas laisser
        l URL dans le premier error_message meaningful.
        """
        import th2rag.rag.tasks.process_pdf as module
        from th2rag.models import Status

        s3_url = "https://bucket.s3.amazonaws.com/path/to/document.pdf"

        async def fake_process_single(doc_id, source, file_index, total_files):
            raise ValueError(
                f"Document converti mais aucun texte extractible (0 chunks): {source}"
            )

        mock_processor_instance = MagicMock()
        mock_processor_instance.process_single_file = AsyncMock(side_effect=fake_process_single)
        monkeypatch.setattr(module, "PDFProcessor", lambda: mock_processor_instance)

        captured_calls = []

        async def fake_update_status(knowledge_id, new_status, db, error_message=None):
            captured_calls.append({"status": new_status, "error_message": error_message})

        monkeypatch.setattr(module, "update_knowledge_status", fake_update_status)
        mock_db = AsyncMock()

        with pytest.raises(Exception):
            await module.process_pdfs_sync(
                doc_id=2,
                sources=[s3_url],
                db=mock_db,
            )

        failed_calls = [c for c in captured_calls if c["status"] == Status.FAILED]
        assert failed_calls

        first_failed_with_msg = next(
            (c for c in failed_calls if c["error_message"]), None
        )
        assert first_failed_with_msg is not None, (
            f"Aucun appel FAILED avec error_message. Appels: {failed_calls}"
        )
        msg = first_failed_with_msg["error_message"]
        assert "https://" not in msg, f"URL S3 dans error_message : {msg!r}"
        assert "document.pdf" in msg, f"basename manquant dans error_message : {msg!r}"
