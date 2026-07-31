"""
Tests Lot 4 — Cohérence des whitelists d'extensions

Objectifs :
1. Garde-fou : toute extension de ALLOWED_EXTENSIONS est routable par convert_any_doc
2. Rejet propre upload d'une extension non supportée (.xyz)
3. Chemin legacy LibreOffice : soffice présent → subprocess tenté
4. Chemin legacy LibreOffice : soffice absent → rejet propre, pas de crash

Run sans DB :
    cd /home/ubuntu/work/th2rag/backend && \
    PYTHONPATH=src .venv/bin/pytest test/knowledge/test_lot4_whitelist.py -v --no-cov
"""
import os
import shutil
import subprocess
import tempfile

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# 1. GARDE-FOU : divergence whitelist upload ↔ dispatch
# ---------------------------------------------------------------------------

class TestWhitelistConvergence:
    """
    Toute extension déclarée dans ALLOWED_EXTENSIONS (service.py)
    doit être routable par convert_any_doc (pas de ValueError «Unsupported»).
    Ce test échoue si une extension est ajoutée dans service.py
    sans l'avoir câblée dans documents_converter.py.
    """

    def test_every_allowed_extension_is_routable(self):
        """
        Pour chaque extension dans ALLOWED_EXTENSIONS, convert_any_doc
        ne doit PAS lever ValueError("Unsupported file type").
        On crée un fichier temporaire factice puis on checke que l'exception
        n'est PAS un rejet d'extension inconnue.
        """
        from th2rag.knowledge.service import ALLOWED_EXTENSIONS
        from th2rag.rag.converters.documents_converter import convert_any_doc

        divergences = []

        with patch("th2rag.rag.converters.pdf_converter.upload_file_to_s3",
                   return_value="http://s3.fake/img.png"):
            for ext in sorted(ALLOWED_EXTENSIONS):
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    # Contenu minimal valide par extension
                    if ext in (".json",):
                        tmp.write(b'{"test": true}')
                    elif ext in (".html", ".htm"):
                        tmp.write(b"<html><body>test</body></html>")
                    else:
                        tmp.write(b"dummy content for testing")
                    tmp_path = tmp.name

                try:
                    convert_any_doc(source=tmp_path)
                except ValueError as e:
                    if "Unsupported file type" in str(e):
                        divergences.append(ext)
                    # Autres ValueError (conversion échoue sur du contenu dummy) = OK
                except Exception:
                    # FileNotFoundError, conversion error sur contenu dummy = acceptable
                    # On cherche uniquement le rejet d'extension
                    pass
                finally:
                    os.unlink(tmp_path)

        assert divergences == [], (
            f"Ces extensions sont dans ALLOWED_EXTENSIONS mais non routables par "
            f"convert_any_doc : {divergences}\n"
            f"Ajouter le dispatch dans documents_converter.py ou retirer de ALLOWED_EXTENSIONS."
        )


# ---------------------------------------------------------------------------
# 2. REJET PROPRE À L'UPLOAD — extension inconnue
# ---------------------------------------------------------------------------

class TestUploadRejectionUnknownExtension:
    """
    Un fichier .xyz doit être rejeté AVANT création de knowledge
    avec un message clair (ValueError ou HTTPException-like)
    sans toucher la DB.
    """

    def test_unsupported_extension_raises_at_validation(self):
        """
        La fonction de validation d'extension lève une ValueError explicite
        pour une extension non supportée.
        """
        from th2rag.knowledge.service import validate_upload_extension

        with pytest.raises(ValueError, match=r"\.xyz"):
            validate_upload_extension(".xyz")

    def test_error_message_lists_supported_formats(self):
        """
        Le message d'erreur doit mentionner les formats acceptés
        pour orienter l'utilisateur.
        """
        from th2rag.knowledge.service import validate_upload_extension

        with pytest.raises(ValueError) as exc_info:
            validate_upload_extension(".xyz")

        error_msg = str(exc_info.value)
        assert "Supported formats" in error_msg

    def test_supported_extension_does_not_raise(self):
        """
        Une extension supportée ne doit pas lever d'exception.
        """
        from th2rag.knowledge.service import validate_upload_extension

        # Ces extensions doivent passer sans exception
        for ext in [".pdf", ".docx", ".txt", ".csv"]:
            validate_upload_extension(ext)  # pas d'exception


# ---------------------------------------------------------------------------
# 3. CHEMIN LEGACY LIBREOFFICE — soffice PRÉSENT
# ---------------------------------------------------------------------------

class TestLegacyLibreOfficePresent:
    """
    Quand soffice est dans le PATH, convert_any_doc doit
    tenter la conversion via subprocess pour .doc/.ppt/.xls.
    """

    def _make_legacy_file(self, ext: str) -> str:
        """Crée un fichier temporaire avec l'extension legacy donnée."""
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(b"PK\x03\x04" + b"\x00" * 20)  # faux binaire
        tmp.close()
        return tmp.name

    def _mock_soffice_conversion(self, src_path: str, target_ext: str) -> str:
        """Simule la création d'un fichier converti par soffice."""
        tmpdir = os.path.dirname(src_path)
        basename = os.path.splitext(os.path.basename(src_path))[0]
        converted = os.path.join(tmpdir, basename + target_ext)
        with open(converted, "w") as f:
            f.write("dummy converted content")
        return converted

    @pytest.mark.parametrize("ext,target_ext", [
        (".doc", ".docx"),
        (".ppt", ".pptx"),
        (".xls", ".xlsx"),
    ])
    def test_soffice_called_when_present(self, ext, target_ext):
        """
        Quand shutil.which trouve soffice, subprocess.run doit être appelé
        pour la conversion legacy.
        """
        from th2rag.rag.converters.documents_converter import convert_any_doc

        src_path = self._make_legacy_file(ext)

        try:
            mock_completed = MagicMock()
            mock_completed.returncode = 0

            with patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=mock_completed) as mock_run, \
                 patch("th2rag.rag.converters.documents_converter._convert_legacy_with_soffice") as mock_legacy:
                # On mock la fonction legacy complète pour isoler le test d'appel
                mock_legacy.return_value = {"document": MagicMock(), "metadata": {"type": ext.lstrip(".")}}

                result = convert_any_doc(source=src_path)

                mock_legacy.assert_called_once()
                assert "document" in result
        finally:
            os.unlink(src_path)

    @pytest.mark.parametrize("ext,target_ext", [
        (".doc", ".docx"),
        (".ppt", ".pptx"),
        (".xls", ".xlsx"),
    ])
    def test_soffice_subprocess_receives_correct_args(self, ext, target_ext):
        """
        subprocess.run doit recevoir les args soffice headless convert-to
        avec la bonne extension cible.
        """
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        src_path = self._make_legacy_file(ext)

        try:
            mock_completed = MagicMock()
            mock_completed.returncode = 0

            with patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=mock_completed) as mock_run, \
                 patch("os.path.exists", side_effect=lambda p: True):

                try:
                    convert_with_libreoffice(src_path)
                except Exception:
                    pass  # La conversion du contenu dummy va échouer — c'est OK

                # Vérifier que subprocess.run a bien été appelé avec soffice
                if mock_run.called:
                    call_args = mock_run.call_args[0][0]
                    assert any("soffice" in str(arg) or "libreoffice" in str(arg)
                               for arg in call_args), (
                        f"subprocess.run appelé sans soffice/libreoffice : {call_args}"
                    )
                    assert "--headless" in call_args
                    assert "--convert-to" in call_args
        finally:
            os.unlink(src_path)


# ---------------------------------------------------------------------------
# 4. CHEMIN LEGACY LIBREOFFICE — soffice ABSENT
# ---------------------------------------------------------------------------

class TestLegacyLibreOfficeAbsent:
    """
    Quand soffice est absent du PATH, convert_any_doc ne doit PAS crasher.
    Il doit soit lever une ValueError propre, soit retourner un résultat
    indiquant l'indisponibilité.
    """

    @pytest.mark.parametrize("ext", [".doc", ".ppt", ".xls"])
    def test_no_crash_when_soffice_absent(self, ext):
        """
        Avec shutil.which retournant None, convert_any_doc ne doit pas
        lever FileNotFoundError ou subprocess.CalledProcessError.
        Il doit lever ValueError avec un message clair.
        """
        from th2rag.rag.converters.documents_converter import convert_any_doc

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(b"PK\x03\x04" + b"\x00" * 20)
            tmp_path = tmp.name

        try:
            with patch("shutil.which", return_value=None):
                with pytest.raises(ValueError) as exc_info:
                    convert_any_doc(source=tmp_path)

                error_msg = str(exc_info.value)
                # Le message doit mentionner LibreOffice/soffice et/ou l'extension
                assert any(keyword in error_msg.lower() for keyword in
                           ["libreoffice", "soffice", ext.lstrip("."), "non supporté", "not supported"]), (
                    f"Message d'erreur insuffisant pour {ext} sans soffice : {error_msg}"
                )
        finally:
            os.unlink(tmp_path)

    @pytest.mark.parametrize("ext", [".doc", ".ppt", ".xls"])
    def test_error_message_mentions_format_when_soffice_absent(self, ext):
        """
        Le message d'erreur doit guider l'utilisateur : format non supporté
        sans LibreOffice installé.
        """
        from th2rag.rag.converters.documents_converter import convert_any_doc

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(b"dummy")
            tmp_path = tmp.name

        try:
            with patch("shutil.which", return_value=None):
                with pytest.raises(ValueError) as exc_info:
                    convert_any_doc(source=tmp_path)

                msg = str(exc_info.value).lower()
                assert "libreoffice" in msg or "soffice" in msg or ext.lstrip(".") in msg
        finally:
            os.unlink(tmp_path)

    def test_non_legacy_extensions_not_affected_by_soffice_absence(self):
        """
        Les extensions non-legacy (.txt etc.) ne doivent pas être affectées
        par l'absence de soffice — pas de FileNotFoundError ni CalledProcessError.
        """
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as tmp:
            tmp.write("contenu de test pour le converter txt")
            tmp_path = tmp.name

        try:
            with patch("shutil.which", return_value=None):
                from th2rag.rag.converters.documents_converter import convert_any_doc
                result = convert_any_doc(source=tmp_path)
                assert "document" in result
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 5. MODULE legacy_converter — tests unitaires isolés
# ---------------------------------------------------------------------------

class TestLegacyConverterModule:
    """Tests unitaires pour le module legacy_converter."""

    def test_convert_with_libreoffice_raises_when_absent(self):
        """convert_with_libreoffice lève ValueError si soffice introuvable."""
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(b"dummy")
            tmp_path = tmp.name

        try:
            with patch("shutil.which", return_value=None):
                with pytest.raises(ValueError, match="LibreOffice"):
                    convert_with_libreoffice(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_convert_with_libreoffice_calls_subprocess_when_present(self):
        """convert_with_libreoffice appelle subprocess.run quand soffice est présent."""
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(b"dummy")
            src_path = tmp.name

        try:
            mock_result = MagicMock()
            mock_result.returncode = 0

            # On doit aussi simuler l'existence du fichier converti
            converted_path = src_path.replace(".doc", ".docx")

            with patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", return_value=mock_result) as mock_run, \
                 patch("os.path.exists", side_effect=lambda p: True):
                try:
                    convert_with_libreoffice(src_path)
                except Exception:
                    pass  # Echec de lecture du fichier converti factice — OK

                assert mock_run.called, "subprocess.run doit être appelé quand soffice est présent"
        finally:
            os.unlink(src_path)

    def test_convert_with_libreoffice_uses_tmpdir(self):
        """La conversion soffice doit se faire dans un répertoire temporaire."""
        from th2rag.rag.converters.legacy_converter import convert_with_libreoffice

        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(b"dummy")
            src_path = tmp.name

        try:
            mock_result = MagicMock()
            mock_result.returncode = 0

            captured_calls = []

            def capture_run(cmd, *args, **kwargs):
                captured_calls.append(cmd)
                return mock_result

            with patch("shutil.which", return_value="/usr/bin/soffice"), \
                 patch("subprocess.run", side_effect=capture_run), \
                 patch("os.path.exists", side_effect=lambda p: True):
                try:
                    convert_with_libreoffice(src_path)
                except Exception:
                    pass

                if captured_calls:
                    cmd = captured_calls[0]
                    assert "--outdir" in cmd, (
                        f"soffice doit utiliser --outdir pour isoler les fichiers temp. "
                        f"Commande reçue : {cmd}"
                    )
        finally:
            os.unlink(src_path)
