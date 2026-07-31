import json
import logging
import os
from typing import Any

from docling_core.types.doc import DoclingDocument

logger = logging.getLogger(__name__)

# A document is treated as the article/JDS schema if it carries ANY of these
# markers (content OR identity). For such documents only the whitelisted
# metadata is embedded — never a raw dump of _source, to avoid leaking
# internal fields into RAG-retrievable content.
_ARTICLE_MARKERS = ("titre", "chapeau", "texte", "id_article", "id_element", "etat")


def load_json_source(source: str) -> Any:
    """Load a JSON file, falling back to NDJSON (one object per line).

    Plain ``json.load`` chokes on newline-delimited JSON (``{...}\n{...}``)
    with an "Extra data" error. When the whole-file parse fails and the file
    has more than one non-empty line, retry line by line and return the list
    of objects.
    """
    with open(source, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            try:
                return [json.loads(ln) for ln in lines]
            except json.JSONDecodeError:
                pass
        raise json.JSONDecodeError(
            f"Invalid JSON syntax in file {source}: {str(exc)}", exc.doc, exc.pos
        )


def render_generic_content(obj: Any, prefix: str = "") -> str:
    """Render an arbitrary JSON value as readable ``key: value`` lines.

    Used when a document has none of the article fields (titre/chapeau/texte),
    so a plain JSON object or array still produces meaningful embedding content
    instead of an empty metadata line.
    """
    lines: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                nested = render_generic_content(value, f"{prefix}{key}.")
                # Keep empty containers visible (distinguish from absent keys).
                lines.append(nested if nested else f"{prefix}{key}: {value}")
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            if isinstance(value, (dict, list)):
                nested = render_generic_content(value, f"{prefix}{idx}.")
                lines.append(nested if nested else f"{prefix}{idx}: {value}")
            else:
                lines.append(f"{prefix}{idx}: {value}")
    else:
        lines.append(f"{prefix}{obj}")
    return "\n".join(line for line in lines if line)


def build_embedding_content(doc: dict, max_length: int = 512) -> str:
    """
    Build content for embedding with length limit to avoid token overflow.
    
    Args:
        doc: Document dictionary with _source key
        max_length: Maximum character length (roughly translates to ~100-150 tokens)
    
    Returns:
        Truncated content string
    """
    source = doc["_source"]

    parts = []

    if source.get("titre"):
        parts.append(f"Title: {source['titre']}")

    if source.get("chapeau"):
        parts.append(f"Summary: {source['chapeau']}")

    if source.get("texte"):
        parts.append(f"Content:\n{source['texte']}")

    if any(source.get(k) for k in _ARTICLE_MARKERS):
        # Article/JDS schema (even if title/body are empty): only the
        # whitelisted metadata is embedded — never a raw dump of _source.
        parts.append(f"metadata {build_metadata(doc)}")
    else:
        # Genuinely generic JSON object (no article markers): render its
        # keys/values so the content is embeddable instead of an empty line.
        parts.append(render_generic_content(source))

    # Join and truncate if necessary
    full_content = "\n\n".join(parts)

    if len(full_content) > max_length:
        # Truncate and add indicator
        full_content = full_content[:max_length] + "\n... [content truncated]"

    return full_content


def build_metadata(doc: dict) -> dict:
    source = doc["_source"]

    return {
        "id_article": source.get("id_article", ""),
        "id_element": source.get("id_element", ""),
        "etat": source.get("etat", ""),
        "created_at": source.get("created_at", ""),
        "updated_at": source.get("updated_at", ""),
        "index": doc.get("_index", ""),
        "doc_id": doc.get("_id", ""),
    }


def normalize_to_wrapped_format(doc: Any) -> dict:
    """
    Normalize a document to the wrapped format with _source key.
    
    Args:
        doc: Document (may be dict or other type)
        
    Returns:
        Document in wrapped format with _source key
        
    Raises:
        ValueError: If doc is not a dictionary
    """
    if not isinstance(doc, dict):
        raise ValueError(f"Expected dictionary, got {type(doc).__name__}: {doc}")

    # Already in wrapped format
    if "_source" in doc:
        return doc

    # Convert direct format to wrapped format
    return {"_source": doc}


def detect_multi_doc(raw_content: Any) -> bool | int:
    """
    Auto-detect if the JSON contains multiple documents.
    """
    # Case 1: Array at top level with more than one item
    if isinstance(raw_content, list):
        count = len(raw_content)
        return count if count > 1 else False

    # Ensure it's a dictionary for other cases
    if not isinstance(raw_content, dict):
        return False

    # Case 2: Elasticsearch response format
    if "hits" in raw_content and isinstance(raw_content["hits"], dict):
        hits = raw_content["hits"].get("hits", [])
        count = len(hits)
        return count if count > 1 else False

    # Case 3: Dictionary with multiple numeric keys
    numeric_keys = [k for k in raw_content.keys() if str(k).isdigit()]
    if numeric_keys:
        count = len(numeric_keys)
        return count if count > 1 else False

    # Case 4: Dictionary with multiple non-metadata keys that are dicts
    metadata_keys = {"took", "timed_out", "_shards", "hits"}
    dict_values = [
        v for k, v in raw_content.items()
        if isinstance(v, dict) and k not in metadata_keys
    ]
    count = len(dict_values)
    return count if count > 1 else False


def extract_first_document(raw_content: Any) -> dict:
    """
    Extract the first valid document from various JSON formats.
    
    Args:
        raw_content: Parsed JSON content
        
    Returns:
        First document in wrapped format
        
    Raises:
        ValueError: If no valid document found
    """
    # Case 1: Array at top level
    if isinstance(raw_content, list):
        if len(raw_content) == 0:
            raise ValueError("Empty array (no documents)")
        first_item = raw_content[0]
        if not isinstance(first_item, dict):
            raise ValueError(f"First array item is not a dict: {type(first_item).__name__}")
        return normalize_to_wrapped_format(first_item)

    # Ensure it's a dictionary
    if not isinstance(raw_content, dict):
        raise ValueError(f"Expected dict or list at top level, got {type(raw_content).__name__}")

    # Case 2: Elasticsearch response format
    if "hits" in raw_content and isinstance(raw_content["hits"], dict):
        hits = raw_content["hits"].get("hits", [])
        if not hits:
            raise ValueError("Elasticsearch format: no documents in hits array")
        return hits[0]  # Already in wrapped format from ES

    # Case 3: Dictionary with values - try to find first valid dict value
    # Iterate through values until we find a dictionary
    for key, value in raw_content.items():
        if isinstance(value, dict):
            return normalize_to_wrapped_format(value)

    # Case 4: fallback — treat the entire dict as a single generic document
    # (a plain JSON object with no nested doc values and no article markers).
    if raw_content:
        logger.warning(
            "json_converter: no article/document markers found; indexing the "
            "whole JSON object as a single generic document (top-level keys: %s). "
            "An accidental upload (e.g. an API error payload) would still be indexed.",
            list(raw_content.keys())[:10],
        )
        return normalize_to_wrapped_format(raw_content)

    raise ValueError("No valid document found: empty JSON object")


def extract_all_documents(raw_content: Any) -> list[dict]:
    """
    Extract all valid documents from various JSON formats.
    
    Args:
        raw_content: Parsed JSON content
        
    Returns:
        List of documents in wrapped format
        
    Raises:
        ValueError: If no valid documents found
    """
    documents = []

    # Case 1: Array at top level
    if isinstance(raw_content, list):
        if len(raw_content) == 0:
            raise ValueError("Empty array (no documents)")
        for item in raw_content:
            if isinstance(item, dict):
                documents.append(normalize_to_wrapped_format(item))
        if not documents:
            raise ValueError("Array contains no dictionary items")
        return documents

    # Ensure it's a dictionary
    if not isinstance(raw_content, dict):
        raise ValueError(f"Expected dict or list, got {type(raw_content).__name__}")

    # Case 2: Elasticsearch response format
    if "hits" in raw_content and isinstance(raw_content["hits"], dict):
        hits = raw_content["hits"].get("hits", [])
        if not hits:
            raise ValueError("Elasticsearch format: no documents in hits array")
        return hits  # Already in wrapped format from ES

    # Case 3: Dictionary with numeric keys (sorted)
    if all(str(k).isdigit() for k in raw_content.keys()):
        sorted_keys = sorted(raw_content.keys(), key=lambda x: int(x))
        for key in sorted_keys:
            value = raw_content[key]
            if isinstance(value, dict):
                documents.append(normalize_to_wrapped_format(value))
        if not documents:
            raise ValueError("Numeric key format: no dictionary values found")
        return documents

    # Case 4: Dictionary with arbitrary keys - extract all dict values
    for key, value in raw_content.items():
        if isinstance(value, dict):
            documents.append(normalize_to_wrapped_format(value))

    if documents:
        return documents

    # Case 5: fallback — the entire dict is a single generic document
    if raw_content:
        logger.warning(
            "json_converter: no article/document markers found; indexing the "
            "whole JSON object as a single generic document (top-level keys: %s). "
            "An accidental upload (e.g. an API error payload) would still be indexed.",
            list(raw_content.keys())[:10],
        )
        return [normalize_to_wrapped_format(raw_content)]

    raise ValueError("No valid documents found: empty JSON object")


def combine_documents(docs_list: list[dict], source_path: str) -> dict:
    """
    Combine multiple documents into a single document.
    """
    if not docs_list:
        raise ValueError("Cannot combine empty document list")

    # If only one document, return it as-is
    if len(docs_list) == 1:
        return docs_list[0]

    # Create a combined DoclingDocument
    combined_doc = DoclingDocument(name=source_path)

    # Collect all metadata
    all_metadata = {
        "source": source_path,
        "document_count": len(docs_list),
        "combined": True,
        "sub_documents": []
    }

    # Combine all text from all documents
    for idx, doc_dict in enumerate(docs_list):
        docling_doc = doc_dict["document"]
        metadata = doc_dict["metadata"]

        # Add metadata reference
        all_metadata["sub_documents"].append({
            "index": idx,
            "id_article": metadata.get("id_article"),
            "id_element": metadata.get("id_element")
        })

        # Add all texts from this document
        for text_item in docling_doc.texts:
            # FIX: Access TextItem object attributes using dot notation, not dict syntax
            # Use the original label value as DocItemLabel is a strict enum
            combined_doc.add_text(
                text=text_item.text,  # Changed from text_item["text"]
                label=text_item.label
            )

    return {
        "document": combined_doc,
        "metadata": all_metadata
    }


def process_single_document(doc: dict, source_path: str) -> dict:
    """
    Process a single document.
    
    Args:
        doc: Document in wrapped format
        source_path: Path to source file
        
    Returns:
        Dict with DoclingDocument and metadata
    """
    metadata = build_metadata(doc)
    metadata["source"] = source_path

    # Create a DoclingDocument
    text_content = build_embedding_content(doc)
    docling_doc = DoclingDocument(name=source_path)

    # Split content into smaller paragraphs to help with chunking
    paragraphs = text_content.split('\n\n')

    for para in paragraphs:
        if para.strip():  # Only add non-empty paragraphs
            docling_doc.add_text(text=para.strip(), label="paragraph")

    rag_doc = {
        "document": docling_doc,
        "metadata": metadata,
    }
    return rag_doc


def special_json_jds(source: str) -> dict:
    """
    Process special JSON format for JDS documents (single document).
    
    Args:
        source: Path to JSON file
        
    Returns:
        Dict with document and metadata
    """
    # Check if file exists
    if not os.path.exists(source):
        raise FileNotFoundError(f"JSON file not found: {source}")

    # Check if file is empty
    if os.path.getsize(source) == 0:
        raise ValueError(f"JSON file is empty (0 bytes): {source}")

    # Parse JSON (NDJSON-aware: falls back to one object per line)
    raw_content = load_json_source(source)

    # Extract first document (this handles all the format variations)
    doc = extract_first_document(raw_content)

    # Process and return
    return process_single_document(doc, source)


def special_json_jds_multi(source: str) -> list[dict]:
    """
    Process special JSON format for JDS documents (multiple documents).
    
    Args:
        source: Path to JSON file
        
    Returns:
        List of dicts with document and metadata
    """
    # Check if file exists
    if not os.path.exists(source):
        raise FileNotFoundError(f"JSON file not found: {source}")

    # Check if file is empty
    if os.path.getsize(source) == 0:
        raise ValueError(f"JSON file is empty (0 bytes): {source}")

    # Parse JSON (NDJSON-aware: falls back to one object per line)
    raw_content = load_json_source(source)

    # Extract all documents
    documents = extract_all_documents(raw_content)

    # Process all documents
    results = []
    failed_count = 0

    for i, doc in enumerate(documents):
        try:
            results.append(process_single_document(doc, source))
        except Exception as e:
            # Log the error but continue processing other documents
            failed_count += 1
            print(f"Warning: Failed to process document {i+1}/{len(documents)}: {str(e)}")
            continue

    if not results:
        raise ValueError(
            f"All {len(documents)} document(s) failed to process. "
            f"Check document structure and required fields."
        )

    if failed_count > 0:
        print(f"Warning: {failed_count}/{len(documents)} document(s) failed to process")

    return results


def convert_json(
    source: str,
    special_format: str = "jds",
    multi_doc: bool = None
) -> dict:
    """
    Convert JSON file to document format.
    
    Args:
        source: Path to JSON file
        special_format: Format type (default: "jds")
        multi_doc: If True, process all documents and combine; if False, process first only;
                   if None (default), auto-detect based on file content
        
    Returns:
        Dict with document and metadata (always returns a single combined document)
        
    Raises:
        ValueError: If JSON format is invalid or file is empty
        FileNotFoundError: If source file doesn't exist
        json.JSONDecodeError: If JSON syntax is invalid
    """
    # Check file existence and size first
    if not os.path.exists(source):
        raise FileNotFoundError(f"JSON file not found: {source}")

    if os.path.getsize(source) == 0:
        raise ValueError(f"JSON file is empty (0 bytes): {source}")

    # Parse JSON (NDJSON-aware: falls back to one object per line)
    raw_content = load_json_source(source)

    # Auto-detect multi_doc if not specified
    if multi_doc is None:
        result = detect_multi_doc(raw_content)
        if result:  # result is either False or int > 1
            multi_doc = True
        else:
            multi_doc = False

    if special_format == "jds":
        if multi_doc:
            # Process multiple documents and combine into one
            docs_list = special_json_jds_multi(source)
            return combine_documents(docs_list, source)
        return special_json_jds(source)

    # Generic JSON handling (for future extensibility)
    if multi_doc:
        documents = extract_all_documents(raw_content)
        results = []
        for doc in documents:
            results.append(process_single_document(doc, source))
        return combine_documents(results, source)
    else:
        doc = extract_first_document(raw_content)
        return process_single_document(doc, source)
