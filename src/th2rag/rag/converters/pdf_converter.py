import logging
import os
import threading
import uuid
from io import BytesIO

from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import DocumentStream
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    ThreadedPdfPipelineOptions,
)
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

from th2rag.clients.storage.s3 import upload_file_to_s3
from th2rag.config import settings

logger = logging.getLogger(__name__)

TOKEN_THRESHOLD = 50

# Mapping from extension to Docling InputFormat
EXT_TO_INPUT_FORMAT: dict[str, InputFormat] = {
    ".pdf": InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".pptx": InputFormat.PPTX,
    ".html": InputFormat.HTML,
    ".htm": InputFormat.HTML,
    ".md": InputFormat.MD,
    ".markdown": InputFormat.MD,
    ".png": InputFormat.IMAGE,
    ".jpg": InputFormat.IMAGE,
    ".jpeg": InputFormat.IMAGE,
    ".tiff": InputFormat.IMAGE,
    ".tif": InputFormat.IMAGE,
    ".bmp": InputFormat.IMAGE,
    ".adoc": InputFormat.ASCIIDOC,
    ".asciidoc": InputFormat.ASCIIDOC,
}

# Canonical extension per InputFormat (used when the real extension is an alias
# that Docling does not recognise natively, e.g. .markdown, .htm, .jpeg).
_CANONICAL_EXT: dict[InputFormat, str] = {
    InputFormat.PDF: ".pdf",
    InputFormat.DOCX: ".docx",
    InputFormat.PPTX: ".pptx",
    InputFormat.HTML: ".html",
    InputFormat.MD: ".md",
    InputFormat.IMAGE: ".png",
    InputFormat.ASCIIDOC: ".adoc",
}


def count_tokens_simple(doc) -> int:
    text = doc.export_to_markdown()
    return len(text.split()) if text else 0


def get_pipeline_options(enable_ocr: bool) -> PdfPipelineOptions:
    options = PdfPipelineOptions()
    options.do_table_structure = True
    options.table_structure_options.mode = "fast"
    options.do_ocr = enable_ocr
    options.generate_picture_images = True

    if settings.handle_img_mode == "describe":
        options.do_picture_description = True
    else:
        options.do_picture_description = False
    return options


def get_image_pipeline_options(enable_ocr: bool) -> ThreadedPdfPipelineOptions:
    """Build pipeline options for image documents (ThreadedPdfPipelineOptions)."""
    options = ThreadedPdfPipelineOptions()
    options.do_ocr = enable_ocr
    options.do_table_structure = False
    options.generate_picture_images = False
    return options


def enable_ocr(doc) -> bool:
    """
    Return True when any page has fewer than TOKEN_THRESHOLD words,
    signalling a scanned/image-only document.
    """
    if not doc.pages:
        return True

    for page_no, _page in doc.pages.items():
        text_items = [
            item.text
            for item in doc.texts
            if item.prov and item.prov[0].page_no == page_no
        ]
        page_text = " ".join(text_items)
        word_count = len(page_text.split())

        if word_count < TOKEN_THRESHOLD:
            logger.warning(
                f"Page {page_no} has only {word_count} tokens. Triggering OCR."
            )
            return True

    return False


def handle_images(doc, source_filename: str, doc_id: int = None) -> list[dict]:
    processed_images = []
    if not hasattr(doc, "pictures"):
        return processed_images

    batch_id = str(uuid.uuid4())[:8]

    for i, picture in enumerate(doc.pictures):
        try:
            image_obj = picture.get_image(doc)
            if image_obj is None:
                logger.warning(f"Image {i} could not be retrieved/generated.")
                continue

            img_byte_arr = BytesIO()
            image_obj.save(img_byte_arr, format="PNG")
            img_bytes = img_byte_arr.getvalue()

            base_name = os.path.basename(source_filename)
            name_without_ext, _ = os.path.splitext(base_name)
            img_filename = f"{name_without_ext}_img_{batch_id}_{i}.png"

            image_link = upload_file_to_s3(img_bytes, img_filename, doc_id=doc_id)

            page_number = picture.prov[0].page_no if picture.prov else 1
            description = f"Image extracted from page {page_number}"

            processed_images.append(
                {
                    "image_index": i,
                    "link": image_link,
                    "description": description,
                    "page": page_number,
                }
            )
            logger.info(f"Image processed: {image_link}")

        except Exception as e:
            logger.error(f"Failed to process image {i}: {e}")

    return processed_images


def _build_format_options(input_format: InputFormat, enable_ocr_flag: bool) -> dict:
    """Return format_options dict for DocumentConverter based on input_format."""
    if input_format == InputFormat.PDF:
        return {
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=get_pipeline_options(enable_ocr_flag)
            )
        }

    if input_format == InputFormat.DOCX:
        return {InputFormat.DOCX: WordFormatOption()}

    if input_format == InputFormat.PPTX:
        return {InputFormat.PPTX: PowerpointFormatOption()}

    if input_format == InputFormat.IMAGE:
        return {
            InputFormat.IMAGE: ImageFormatOption(
                pipeline_options=get_image_pipeline_options(enable_ocr_flag)
            )
        }

    if input_format == InputFormat.HTML:
        return {InputFormat.HTML: HTMLFormatOption()}

    if input_format == InputFormat.MD:
        return {InputFormat.MD: MarkdownFormatOption()}

    if input_format == InputFormat.ASCIIDOC:
        return {InputFormat.ASCIIDOC: AsciiDocFormatOption()}

    return {}


# DocumentConverter loads PyTorch models (layout / table-structure / OCR).
# Instantiating it on every conversion triggered, on concurrent batches, the same
# meta-device race as the embedding model. We cache one instance per configuration
# (input_format, ocr, format restriction) and reuse it under a lock.
_CONVERTER_CACHE: dict = {}
_CONVERTER_LOCK = threading.Lock()


def _get_converter(
    input_format: InputFormat,
    enable_ocr_flag: bool,
    restrict_format: bool,
) -> DocumentConverter:
    key = (input_format, enable_ocr_flag, restrict_format)
    conv = _CONVERTER_CACHE.get(key)
    if conv is not None:
        return conv
    with _CONVERTER_LOCK:
        conv = _CONVERTER_CACHE.get(key)
        if conv is None:
            kwargs = {
                "format_options": _build_format_options(input_format, enable_ocr_flag)
            }
            if restrict_format:
                kwargs["allowed_formats"] = [input_format]
            conv = DocumentConverter(**kwargs)
            _CONVERTER_CACHE[key] = conv
        return conv


def convert_with_docling(
    source: str,
    doc_id: int = None,
    input_format: InputFormat | None = None,
) -> dict:
    """
    Generic Docling conversion for any supported format.

    For PDF: two-pass strategy (fast scan then OCR if needed).
    For images: OCR enabled by default (image documents are always raster).
    For DOCX/PPTX: native text extraction; OCR on embedded images requires
        LibreOffice (not available in this environment — logged as warning).
    For HTML/Markdown/AsciiDoc: direct conversion via Docling pipelines.

    Args:
        source: Local file path.
        doc_id: Optional knowledge DB id for S3 image naming.
        input_format: Docling InputFormat. Inferred from extension if None.

    Returns:
        dict with keys: "document", "metadata".
    """
    if input_format is None:
        ext = os.path.splitext(source)[1].lower()
        input_format = EXT_TO_INPUT_FORMAT.get(ext)
        if input_format is None:
            raise ValueError(f"Cannot infer Docling InputFormat from extension: {ext}")

    doc_type = input_format.value

    # Docling detects file format from the file extension in the path.
    # Alias extensions (e.g. .markdown, .htm, .jpeg, .adoc) may not be
    # recognised natively. We wrap the file in a DocumentStream with the
    # canonical extension so Docling always gets a name it understands.
    real_ext = os.path.splitext(source)[1].lower()
    canonical_ext = _CANONICAL_EXT.get(input_format, real_ext)
    if real_ext != canonical_ext:
        base_name = os.path.splitext(os.path.basename(source))[0] + canonical_ext
        with open(source, "rb") as fh:
            docling_source: str | DocumentStream = DocumentStream(
                name=base_name, stream=BytesIO(fh.read())
            )
        logger.debug(
            f"Alias extension {real_ext} → stream with canonical name {base_name}"
        )
    else:
        docling_source = source

    # --- PDF: two-pass with adaptive OCR ---
    if input_format == InputFormat.PDF:
        logger.info(f"Pass 1: Fast scan for {source}")
        converter = _get_converter(InputFormat.PDF, False, restrict_format=False)
        result = converter.convert(docling_source)
        doc = result.document
        ocr_used = False

        if enable_ocr(doc):
            logger.info("Sparse text detected. Retrying with OCR...")
            # Re-open the file for the second pass when using DocumentStream
            if isinstance(docling_source, DocumentStream):
                with open(source, "rb") as fh:
                    docling_source_2: str | DocumentStream = DocumentStream(
                        name=docling_source.name, stream=BytesIO(fh.read())
                    )
            else:
                docling_source_2 = docling_source
            converter_ocr = _get_converter(InputFormat.PDF, True, restrict_format=False)
            result = converter_ocr.convert(docling_source_2)
            doc = result.document
            ocr_used = True

        extracted_images = handle_images(doc, source, doc_id=doc_id)
        full_text = doc.export_to_markdown()
        return {
            "document": doc,
            "metadata": {
                "source": source,
                "type": doc_type,
                "ocr_used": ocr_used,
                "token_count": len(full_text.split()) if full_text else 0,
                "images": extracted_images,
            },
        }

    # --- DOCX / PPTX: native text extraction + image extraction ---
    if input_format in (InputFormat.DOCX, InputFormat.PPTX):
        logger.info(
            f"Converting {doc_type.upper()} via Docling native backend: {source}"
        )
        # Note: OCR on embedded DrawingML images requires LibreOffice (docx_to_pdf converter).
        # get_docx_to_pdf_converter() returns None on this VM (LibreOffice not installed).
        # Docling logs a warning and skips those images; native text is always extracted.
        converter = _get_converter(input_format, False, restrict_format=True)
        result = converter.convert(docling_source)
        doc = result.document
        extracted_images = handle_images(doc, source, doc_id=doc_id)
        full_text = doc.export_to_markdown()

        if not full_text.strip():
            logger.warning(
                f"{doc_type.upper()} produced 0 text. Document may be graphical-only. "
                "LibreOffice is required for DOCX→PDF→OCR fallback (not installed)."
            )

        return {
            "document": doc,
            "metadata": {
                "source": source,
                "type": doc_type,
                "ocr_used": False,
                "token_count": len(full_text.split()) if full_text else 0,
                "images": extracted_images,
            },
        }

    # --- Images: OCR enabled by default ---
    if input_format == InputFormat.IMAGE:
        logger.info(f"Converting image with OCR: {source}")
        converter = _get_converter(InputFormat.IMAGE, True, restrict_format=True)
        result = converter.convert(docling_source)
        doc = result.document
        full_text = doc.export_to_markdown()
        return {
            "document": doc,
            "metadata": {
                "source": source,
                "type": "image",
                "ocr_used": True,
                "token_count": len(full_text.split()) if full_text else 0,
                "images": [],
            },
        }

    # --- HTML / Markdown / AsciiDoc: simple pipeline ---
    logger.info(f"Converting {doc_type} via Docling simple pipeline: {source}")
    converter = _get_converter(input_format, False, restrict_format=True)
    result = converter.convert(docling_source)
    doc = result.document
    full_text = doc.export_to_markdown()
    return {
        "document": doc,
        "metadata": {
            "source": source,
            "type": doc_type,
            "ocr_used": False,
            "token_count": len(full_text.split()) if full_text else 0,
            "images": [],
        },
    }


def convert_pdf(source: str, doc_id: int = None) -> dict:
    """
    Convert a PDF to an internal document representation.

    Delegates to convert_with_docling for consistency.
    Kept for backward compatibility with existing callers.
    """
    return convert_with_docling(
        source=source, doc_id=doc_id, input_format=InputFormat.PDF
    )
