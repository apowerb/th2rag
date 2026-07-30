"""
Conversion de formats legacy via LibreOffice headless.

Formats supportés : .doc → .docx, .ppt → .pptx, .xls → .xlsx
Pré-requis runtime : soffice ou libreoffice dans le PATH.

Si LibreOffice est absent, lève ValueError avec message explicite.
Ne crashe jamais avec FileNotFoundError ou CalledProcessError.
"""
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Mapping extension legacy → extension cible Docling-compatible
_LEGACY_TO_TARGET: dict[str, str] = {
    ".doc": ".docx",
    ".ppt": ".pptx",
    ".xls": ".xlsx",
}

LEGACY_EXTENSIONS: frozenset[str] = frozenset(_LEGACY_TO_TARGET.keys())


def _find_soffice() -> str | None:
    """Retourne le chemin de soffice/libreoffice, ou None si absent."""
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_with_libreoffice(source: str) -> str:
    """
    Convertit un fichier legacy (.doc/.ppt/.xls) en format moderne
    via LibreOffice headless, dans un répertoire temporaire.

    Args:
        source: Chemin absolu vers le fichier source.

    Returns:
        Chemin absolu vers le fichier converti (dans un tmpdir).
        L'appelant est responsable de nettoyer ce tmpdir.

    Raises:
        ValueError: Si LibreOffice est absent du PATH.
        ValueError: Si la conversion échoue (returncode != 0 ou fichier absent).
    """
    soffice = _find_soffice()
    if soffice is None:
        ext = os.path.splitext(source)[1].lower()
        target = _LEGACY_TO_TARGET.get(ext, ".docx")
        raise ValueError(
            f"Format {ext} non supporté sans LibreOffice. "
            f"Installez LibreOffice (apt install libreoffice) pour convertir "
            f"{ext} → {target}. "
            f"Formats acceptés sans LibreOffice : PDF, DOCX, PPTX, XLSX, CSV, TXT, "
            f"HTML, Markdown, images, AsciiDoc, JSON."
        )

    ext = os.path.splitext(source)[1].lower()
    if ext not in _LEGACY_TO_TARGET:
        raise ValueError(
            f"convert_with_libreoffice: extension {ext} non supportée. "
            f"Extensions legacy supportées : {sorted(LEGACY_EXTENSIONS)}"
        )

    target_ext = _LEGACY_TO_TARGET[ext]
    tmpdir = tempfile.mkdtemp(prefix="th2rag_legacy_")

    logger.info(f"Converting legacy {ext} → {target_ext} via LibreOffice: {source}")

    _success = False
    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", target_ext.lstrip("."),
             "--outdir", tmpdir, source],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise ValueError(
                f"LibreOffice conversion failed for {os.path.basename(source)} "
                f"(returncode={result.returncode}): {result.stderr[:500]}"
            )

        # Chercher le fichier converti dans tmpdir
        basename = os.path.splitext(os.path.basename(source))[0]
        converted_path = os.path.join(tmpdir, basename + target_ext)

        if not os.path.exists(converted_path):
            # Parfois soffice crée le fichier sans l'extension demandée
            candidates = [
                f for f in os.listdir(tmpdir)
                if f.startswith(basename) and f.endswith(target_ext)
            ]
            if candidates:
                converted_path = os.path.join(tmpdir, candidates[0])
            else:
                raise ValueError(
                    f"LibreOffice n'a pas produit le fichier attendu : {converted_path}. "
                    f"Contenu de {tmpdir}: {os.listdir(tmpdir)}"
                )

        logger.info(f"LibreOffice conversion successful: {converted_path}")
        _success = True
        return converted_path

    except subprocess.TimeoutExpired as e:
        raise ValueError(
            f"LibreOffice conversion timeout (120s) pour {os.path.basename(source)}"
        ) from e
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Erreur inattendue lors de la conversion LibreOffice de "
            f"{os.path.basename(source)}: {e}"
        ) from e
    finally:
        if not _success:
            shutil.rmtree(tmpdir, ignore_errors=True)
