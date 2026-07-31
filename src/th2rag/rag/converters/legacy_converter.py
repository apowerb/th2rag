"""
Legacy format conversion through headless LibreOffice.

Supported formats: .doc → .docx, .ppt → .pptx, .xls → .xlsx
Runtime prerequisite: soffice or libreoffice on the PATH.

When LibreOffice is missing, raises ValueError with an explicit message.
Never crashes with FileNotFoundError or CalledProcessError.
"""
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Mapping from legacy extension → Docling-compatible target extension
_LEGACY_TO_TARGET: dict[str, str] = {
    ".doc": ".docx",
    ".ppt": ".pptx",
    ".xls": ".xlsx",
}

LEGACY_EXTENSIONS: frozenset[str] = frozenset(_LEGACY_TO_TARGET.keys())


def _find_soffice() -> str | None:
    """Return the path to soffice/libreoffice, or None if missing."""
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_with_libreoffice(source: str) -> str:
    """
    Convert a legacy file (.doc/.ppt/.xls) to a modern format through
    headless LibreOffice, in a temporary directory.

    Args:
        source: Absolute path to the source file.

    Returns:
        Absolute path to the converted file (inside a tmpdir).
        The caller is responsible for cleaning up that tmpdir.

    Raises:
        ValueError: If LibreOffice is missing from the PATH.
        ValueError: If the conversion fails (returncode != 0 or file missing).
    """
    soffice = _find_soffice()
    if soffice is None:
        ext = os.path.splitext(source)[1].lower()
        target = _LEGACY_TO_TARGET.get(ext, ".docx")
        raise ValueError(
            f"Format {ext} is not supported without LibreOffice. "
            f"Install LibreOffice (apt install libreoffice) to convert "
            f"{ext} → {target}. "
            f"Formats accepted without LibreOffice: PDF, DOCX, PPTX, XLSX, CSV, TXT, "
            f"HTML, Markdown, images, AsciiDoc, JSON."
        )

    ext = os.path.splitext(source)[1].lower()
    if ext not in _LEGACY_TO_TARGET:
        raise ValueError(
            f"convert_with_libreoffice: extension {ext} is not supported. "
            f"Supported legacy extensions: {sorted(LEGACY_EXTENSIONS)}"
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

        # Look for the converted file in tmpdir
        basename = os.path.splitext(os.path.basename(source))[0]
        converted_path = os.path.join(tmpdir, basename + target_ext)

        if not os.path.exists(converted_path):
            # soffice sometimes writes the file without the requested extension
            candidates = [
                f for f in os.listdir(tmpdir)
                if f.startswith(basename) and f.endswith(target_ext)
            ]
            if candidates:
                converted_path = os.path.join(tmpdir, candidates[0])
            else:
                raise ValueError(
                    f"LibreOffice did not produce the expected file: {converted_path}. "
                    f"Contents of {tmpdir}: {os.listdir(tmpdir)}"
                )

        logger.info(f"LibreOffice conversion successful: {converted_path}")
        _success = True
        return converted_path

    except subprocess.TimeoutExpired as e:
        raise ValueError(
            f"LibreOffice conversion timeout (120s) for {os.path.basename(source)}"
        ) from e
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Unexpected error during LibreOffice conversion of "
            f"{os.path.basename(source)}: {e}"
        ) from e
    finally:
        if not _success:
            shutil.rmtree(tmpdir, ignore_errors=True)
