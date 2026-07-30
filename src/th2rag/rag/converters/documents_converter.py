import logging
import os

from th2rag.rag.converters.json_converter import convert_json
from th2rag.rag.converters.legacy_converter import (
    LEGACY_EXTENSIONS,
    convert_with_libreoffice,
)
from th2rag.rag.converters.pdf_converter import (
    EXT_TO_INPUT_FORMAT,
    convert_with_docling,
)
from th2rag.rag.converters.spreadsheet_converter import convert_spreadsheet
from th2rag.rag.converters.txt_converter import convert_txt

logger = logging.getLogger(__name__)

# Extensions handled natively by Docling (via convert_with_docling)
_DOCLING_EXTENSIONS: frozenset[str] = frozenset(EXT_TO_INPUT_FORMAT.keys())

# Human-readable list for error messages
_ALL_SUPPORTED: list[str] = sorted(
    _DOCLING_EXTENSIONS | {".csv", ".xlsx", ".json", ".txt"} | LEGACY_EXTENSIONS
)


def _convert_legacy_with_soffice(source: str, doc_id: int | None) -> dict:
    """
    Conversion via LibreOffice puis Docling.
    Exposée séparément pour faciliter le mock dans les tests.
    Lève ValueError si LibreOffice est absent ou si la conversion échoue.
    """
    converted_path = convert_with_libreoffice(source)
    try:
        result = convert_with_docling(source=converted_path, doc_id=doc_id)
    finally:
        # Nettoyage du tmpdir créé par convert_with_libreoffice
        tmpdir = os.path.dirname(converted_path)
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
    return result


def convert_any_doc(source: str, doc_id: int = None) -> dict:
    """
    Convert any supported document format to a standardised internal representation.

    Supported formats
    -----------------
    Via Docling (convert_with_docling):
        PDF, DOCX, PPTX, HTML, HTM, MD, MARKDOWN,
        PNG, JPG, JPEG, TIFF, TIF, BMP, ADOC, ASCIIDOC

    Via dedicated converters:
        CSV, XLSX  → convert_spreadsheet
        JSON       → convert_json
        TXT        → convert_txt

    Via LibreOffice + Docling (si LibreOffice installé) :
        DOC → DOCX, PPT → PPTX, XLS → XLSX
        Si LibreOffice absent : ValueError avec message explicite.
    """
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")

    ext = os.path.splitext(source)[1].lower()
    logger.debug(f"Converting file: {os.path.basename(source)} (extension: {ext})")

    if not ext:
        raise ValueError(f"File has no extension: {source}")

    logger.info(f"Converting document with extension: {ext} from {source}")

    try:
        if ext in _DOCLING_EXTENSIONS:
            logger.debug(f"Routing {ext} to Docling converter")
            result = convert_with_docling(source=source, doc_id=doc_id)

        elif ext in (".csv", ".xlsx"):
            logger.debug(f"Using spreadsheet converter for {ext}")
            result = convert_spreadsheet(source=source)

        elif ext == ".json":
            logger.debug(f"Using JSON converter for {ext}")
            result = convert_json(source=source)

        elif ext == ".txt":
            logger.debug(f"Using TXT converter for {ext}")
            result = convert_txt(source=source)

        elif ext in LEGACY_EXTENSIONS:
            logger.debug(f"Routing legacy {ext} through LibreOffice → Docling")
            result = _convert_legacy_with_soffice(source, doc_id)

        else:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported types: {', '.join(_ALL_SUPPORTED)}"
            )

        if not isinstance(result, dict):
            raise ValueError(f"Converter returned invalid type: {type(result)}")

        if "document" not in result:
            raise ValueError("Converter result missing 'document' key")

        logger.info(f"Successfully converted {ext} document")
        return result

    except ValueError as e:
        logger.error(f"Validation error converting {source}: {e}")
        raise

    except FileNotFoundError:
        logger.error(f"File not found: {source}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error converting {source}: {e}", exc_info=True)
        raise Exception(f"Failed to convert {ext} document: {str(e)}") from e
