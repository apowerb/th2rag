import asyncio
import re
import os
import tempfile
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from th2rag.clients.storage.s3 import download_file_from_s3
from sqlalchemy import select

from th2rag.config import settings
from th2rag.knowledge.service import update_knowledge_status
from th2rag.models import Knowledge, Status
from th2rag.rag.chunkers.hybrid_chunker import HybridTextChunker
from th2rag.rag.converters.documents_converter import convert_any_doc
from th2rag.rag.embeddings.sentence_transformer import SentenceTransformerEmbedding
from th2rag.rag.retrieval.lancedb.lancedb_storage import LanceDBStorage
from th2rag.utils.logger import setup_logger
from th2rag.webhooks.sender import build_webhook_payload, send_webhook

logger = setup_logger(__name__)
dotenv_path = os.getenv("WORK_DIR", default=os.getcwd()) + "/.env"
load_dotenv(dotenv_path)


def _build_partial_error_message(
    failed_file_records: list[dict[str, Any]],
    total: int,
) -> str:
    """Build a human-readable summary for partial-success cases.

    Args:
        failed_file_records: List of dicts with keys 'source' and 'error'.
        total: Total number of files attempted.

    Returns:
        A summary string suitable for the error_message column (≤ 2000 chars
        before the service-layer truncation).
    """
    count = len(failed_file_records)
    lines = [f"{count}/{total} file(s) skipped during indexing:"]
    for rec in failed_file_records:
        source = rec.get("source", "?")
        filename = os.path.basename(source)
        error = _strip_urls_from_error(rec.get("error", "unknown reason"))
        lines.append(f"  - {filename}: {error[:200]}")
    return "\n".join(lines)


def _strip_urls_from_error(error_msg: str) -> str:
    """Remove URLs (https:// and s3://) from error messages before storing in DB."""
    return re.sub(r"(https?://|s3://)\S+", lambda m: os.path.basename(m.group(0).rstrip("/:,")), error_msg)


class PDFProcessor:
    """Reusable PDF processor that loads models once and processes multiple files."""

    def __init__(self):
        self.chunker = None
        self.embedding_model = None
        self.storage = None
        self._initialized = False

    def _initialize_models(self):
        """Initialize models once - called on first use."""
        if self._initialized:
            return

        logger.info("Initializing PDF processor models...")
        self.chunker = HybridTextChunker()
        self.embedding_model = SentenceTransformerEmbedding()
        self.storage = LanceDBStorage()
        self._initialized = True
        logger.info("PDF processor models initialized successfully")

    async def process_single_file(
        self,
        doc_id: int,
        source: str,
        file_index: int,
        total_files: int
    ) -> dict[str, Any]:
        """
        Process a single PDF file.

        Args:
            doc_id: Document ID
            source: S3 URL or local file path
            file_index: Current file index (1-based for logging)
            total_files: Total number of files being processed

        Returns:
            Dict with processing results
        """
        # Ensure models are loaded
        self._initialize_models()

        temp_file_path = None

        try:
            logger.info(
                f"[Doc {doc_id}] Processing file {file_index}/{total_files}: {source}"
            )
            local_source = source

            # Download from S3 if needed
            if source.startswith("https://"):
                try:
                    logger.info(f"[Doc {doc_id}] [{file_index}/{total_files}] Downloading from S3...")
                    file_bytes = download_file_from_s3(source)
                    # Get the correct extension from the source URL
                    parsed_url=urlparse(source)
                    original_filename = os.path.basename(parsed_url.path)
                    file_ext = os.path.splitext(original_filename)[1] or ".pdf"
                    fd, temp_file_path = tempfile.mkstemp(suffix=file_ext)
                    with os.fdopen(fd, "wb") as tmp:
                        tmp.write(file_bytes)
                    local_source = temp_file_path
                    logger.info(
                        f"[Doc {doc_id}] [{file_index}/{total_files}] "
                        f"Downloaded to: {local_source} (extension: {file_ext})"
                    )
                except Exception as e:
                    logger.error(
                        f"[Doc {doc_id}] [{file_index}/{total_files}] "
                        f"Error downloading from S3: {e}"
                    )
                    raise Exception(f"Failed to download file from S3: {str(e)}")

            # Convert document (PDF or JSON)
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] Converting document..."
            )
            file_ext = os.path.splitext(local_source)[1]
            doc_result = convert_any_doc(local_source, doc_id=doc_id)
            document = doc_result["document"]
            metadata = doc_result.get("metadata", {})
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] {file_ext} converted"
            )

            # Chunk the document
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] Chunking document..."
            )
            chunks = self.chunker.chunk_document(document)
            chunk_count = len(chunks)
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Created {chunk_count} chunks"
            )

            if chunk_count == 0:
                logger.warning(
                    f"[Doc {doc_id}] [{file_index}/{total_files}] "
                    f"Document converted but no extractable text (0 chunks) — "
                    f"indexing aborted for {os.path.basename(source)}"
                )
                raise ValueError(
                    f"Document converted but no extractable text (0 chunks): {os.path.basename(source)}"
                )

            # Generate embeddings
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Generating embeddings for {chunk_count} chunks..."
            )

            processed_chunks = []
            for idx, chunk in enumerate(chunks):
                text = chunk.text
                vector = self.embedding_model.encode(text)

                chunk_metadata = {
                    "filename": metadata.get("source", source),
                    "page_numbers": None,
                    "title": None,
                }
                processed_chunks.append({
                    "doc_id": doc_id,
                    "text": text,
                    "vector": vector,
                    "metadata": chunk_metadata,
                })

                if (idx + 1) % 10 == 0:
                    logger.info(
                        f"[Doc {doc_id}] [{file_index}/{total_files}] "
                        f"Embedded {idx + 1}/{chunk_count} chunks"
                    )

            # Store in LanceDB
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Storing {len(processed_chunks)} chunks in vector database..."
            )
            self.storage.add_chunks(processed_chunks)
            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Chunks stored successfully"
            )

            result = {
                "doc_id": doc_id,
                "source": source,
                "chunk_count": chunk_count,
                "status": "completed",
                "message": f"Successfully processed document into {chunk_count} chunks"
            }

            logger.info(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Processing complete: {chunk_count} chunks"
            )
            return result

        except Exception as e:
            logger.error(
                f"[Doc {doc_id}] [{file_index}/{total_files}] "
                f"Error processing document: {e}",
                exc_info=True
            )
            raise Exception(f"Document processing failed for {os.path.basename(source)}: {str(e)}")

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(
                        f"[Doc {doc_id}] [{file_index}/{total_files}] "
                        f"Cleaned up temporary file"
                    )
                except Exception as e:
                    logger.warning(
                        f"[Doc {doc_id}] [{file_index}/{total_files}] "
                        f"Failed to clean up temporary file: {e}"
                    )


async def process_pdfs_sync(
    doc_id: int,
    sources: list[str],
    db: AsyncSession,
    callback_url: str | None = None,
) -> dict[str, Any]:
    """
    Synchronously process one or more PDFs (waits for completion).
    Models are loaded once for all files.

    Args:
        doc_id: Document ID
        sources: List of S3 URLs or local file paths
        db: Database session
        callback_url: Optional URL to notify via webhook when processing completes

    Returns:
        Dict with processing results for all files
    """
    logger.info(
        f"[Doc {doc_id}] Starting SYNCHRONOUS processing of {len(sources)} file(s) "
        f"(timeout: {settings.pdf_processing_timeout}s)"
    )

    # Create a single processor instance for all files
    processor = PDFProcessor()

    async def _process_all():
        total_chunks = 0
        processed_files = []
        failed_files = []

        for idx, source in enumerate(sources, 1):
            try:
                result = await processor.process_single_file(
                    doc_id,
                    source,
                    file_index=idx,
                    total_files=len(sources)
                )
                chunk_count = result.get("chunk_count", 0)
                total_chunks += chunk_count
                processed_files.append({
                    "source": source,
                    "chunk_count": chunk_count,
                    "status": "completed"
                })
                logger.info(
                    f"[Doc {doc_id}] File {idx}/{len(sources)} completed: "
                    f"{chunk_count} chunks"
                )
            except Exception as e:
                logger.error(
                    f"[Doc {doc_id}] File {idx}/{len(sources)} failed: {e}"
                )
                failed_files.append({
                    "source": source,
                    "status": "failed",
                    "error": str(e)
                })

        # Update status based on results
        if failed_files and not processed_files:
            # All files failed — use first error as representative message
            first_error = _strip_urls_from_error(
                failed_files[0].get("error", "unknown reason") if failed_files else ""
            )
            all_failed_msg = (
                f"{len(sources)}/{len(sources)} file(s) failed. "
                f"First error: {first_error[:500]}"
            )
            await update_knowledge_status(
                doc_id, Status.FAILED, db, error_message=all_failed_msg
            )
            raise Exception(f"All {len(sources)} file(s) failed to process")
        elif failed_files:
            # Partial success
            partial_msg = _build_partial_error_message(failed_files, total=len(sources))
            await update_knowledge_status(
                doc_id, Status.COMPLETED, db, error_message=partial_msg
            )
            logger.warning(
                f"[Doc {doc_id}] Partial success: {len(processed_files)} succeeded, "
                f"{len(failed_files)} failed"
            )
        else:
            # All succeeded
            await update_knowledge_status(doc_id, Status.COMPLETED, db)

        return {
            "doc_id": doc_id,
            "total_files": len(sources),
            "successful_files": len(processed_files),
            "failed_files": len(failed_files),
            "total_chunks": total_chunks,
            "files": processed_files + failed_files,
            "status": "completed" if not failed_files else "partial"
        }

    try:
        # Process with timeout
        result = await asyncio.wait_for(
            _process_all(),
            timeout=settings.pdf_processing_timeout
        )
        logger.info(
            f"[Doc {doc_id}] Synchronous processing completed: "
            f"{result['successful_files']}/{result['total_files']} files, "
            f"{result['total_chunks']} total chunks"
        )

        # Send webhook notification if callback_url was provided
        if callback_url:
            webhook_payload = build_webhook_payload(
                knowledge_id=doc_id,
                status=result.get("status", "completed").upper(),
                total_files=result["total_files"],
                successful_files=result["successful_files"],
                failed_files=result["failed_files"],
            )
            await send_webhook(callback_url, webhook_payload)

        return result

    except TimeoutError:
        logger.error(
            f"[Doc {doc_id}] Processing timed out after "
            f"{settings.pdf_processing_timeout}s"
        )
        try:
            await update_knowledge_status(doc_id, Status.FAILED, db)
        except Exception as e:
            logger.error(
                f"[Doc {doc_id}] Failed to update status after timeout: {e}"
            )

        raise TimeoutError(
            f"Document processing exceeded timeout of {settings.pdf_processing_timeout} seconds. "
            f"Consider using async mode for large files."
        )

    except Exception as e:
        logger.error(f"[Doc {doc_id}] Synchronous processing failed: {e}")
        try:
            await update_knowledge_status(doc_id, Status.FAILED, db)
        except Exception as status_error:
            logger.error(
                f"[Doc {doc_id}] Failed to update status to FAILED: {status_error}"
            )
        raise


def process_pdfs_background(
    doc_id: int,
    sources: list[str],
    callback_url: str | None = None,
) -> None:
    """
    Background task for asynchronous processing of one or more PDFs.
    Models are loaded once for all files.

    This function creates its own event loop and database connection,
    making it safe to call from FastAPI background tasks or Mage AI.

    Args:
        doc_id: Document ID
        sources: List of S3 URLs or local file paths
        callback_url: Optional URL to notify via webhook when processing completes
    """
    logger.info(
        f"[Doc {doc_id}] Starting BACKGROUND processing of {len(sources)} file(s)"
    )

    async def _runner():
        # Create a fresh AsyncEngine on this loop
        engine = create_async_engine(
            settings.database_url,
            connect_args={"server_settings": {"jit": "off"}},
            echo=settings.echo_sql,
        )

        async_session_maker = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create a single processor instance for all files
        processor = PDFProcessor()

        total_chunks = 0
        successful_files = 0
        failed_files = 0
        failed_file_records: list[dict[str, Any]] = []

        # Process each file sequentially
        try:
            async with async_session_maker() as db_session:
                for idx, source in enumerate(sources, 1):
                    try:
                        result = await processor.process_single_file(
                            doc_id,
                            source,
                            file_index=idx,
                            total_files=len(sources)
                        )
                        total_chunks += result.get("chunk_count", 0)
                        successful_files += 1
                        logger.info(
                            f"[Doc {doc_id}] Successfully processed file "
                            f"{idx}/{len(sources)}: {result.get('chunk_count', 0)} chunks"
                        )
                    except Exception as e:
                        failed_files += 1
                        failed_file_records.append({"source": source, "error": str(e)})
                        logger.error(
                            f"[Doc {doc_id}] Failed to process file "
                            f"{idx}/{len(sources)}: {e}"
                        )

                # Update final status and determine webhook status string
                final_status: str = "failed"  # safe default
                if failed_files == 0:
                    final_status = "completed"
                    await update_knowledge_status(doc_id, Status.COMPLETED, db_session)
                    logger.info(
                        f"[Doc {doc_id}] All {len(sources)} file(s) processed "
                        f"successfully: {total_chunks} total chunks"
                    )
                elif successful_files > 0:
                    # Partial success - still mark as completed but log warning
                    final_status = "completed"
                    partial_msg = _build_partial_error_message(
                        failed_file_records, total=len(sources)
                    )
                    await update_knowledge_status(
                        doc_id, Status.COMPLETED, db_session, error_message=partial_msg
                    )
                    logger.warning(
                        f"[Doc {doc_id}] Partial success: "
                        f"{successful_files}/{len(sources)} succeeded, "
                        f"{total_chunks} total chunks"
                    )
                else:
                    # All files failed
                    final_status = "failed"
                    first_error = _strip_urls_from_error(
                        failed_file_records[0].get("error", "") if failed_file_records else ""
                    )
                    all_failed_msg = (
                        f"{len(sources)}/{len(sources)} file(s) failed. "
                        f"First error: {first_error[:500]}"
                    )
                    await update_knowledge_status(
                        doc_id, Status.FAILED, db_session, error_message=all_failed_msg
                    )
                    logger.error(
                        f"[Doc {doc_id}] All {len(sources)} file(s) failed to process"
                    )

                # Send webhook notification — use param if provided, else read from DB
                effective_callback_url = callback_url
                if not effective_callback_url:
                    try:
                        row = await db_session.execute(
                            select(Knowledge.callback_url).where(Knowledge.knowledge_id == doc_id)
                        )
                        effective_callback_url = row.scalar_one_or_none()
                    except Exception:
                        pass

                if effective_callback_url:
                    try:
                        webhook_payload = build_webhook_payload(
                            knowledge_id=doc_id,
                            status=final_status,
                            processing={
                                "total_files": len(sources),
                                "successful_files": successful_files,
                                "failed_files": failed_files,
                                "total_chunks": total_chunks,
                            },
                        )
                        await send_webhook(effective_callback_url, webhook_payload)
                    except Exception as wh_err:
                        logger.error(f"[Doc {doc_id}] Webhook delivery failed: {wh_err}")
                else:
                    logger.info(f"[Doc {doc_id}] No callback_url — skipping webhook")

        except Exception as e:
            logger.error(
                f"[Doc {doc_id}] Background processing failed: {e}",
                exc_info=True
            )
            # Bug fix 1: use a separate variable name to avoid UnboundLocalError
            # (callback_url is the outer-scope parameter; we must not shadow it here)
            error_callback_url: str | None = callback_url
            try:
                async with async_session_maker() as db_session:
                    await update_knowledge_status(doc_id, Status.FAILED, db_session)
                    # Fall back to DB value if not provided as parameter
                    if not error_callback_url:
                        row = await db_session.execute(
                            select(Knowledge.callback_url).where(Knowledge.knowledge_id == doc_id)
                        )
                        error_callback_url = row.scalar_one_or_none()
            except Exception as status_error:
                logger.error(
                    f"[Doc {doc_id}] Failed to update status: {status_error}"
                )
            # Bug fix 2+3: send_webhook is async — use await directly (not asyncio.to_thread),
            # and build_webhook_payload expects processing=dict, not top-level kwargs
            if error_callback_url:
                try:
                    webhook_payload = build_webhook_payload(
                        knowledge_id=doc_id,
                        status="failed",
                        processing={
                            "total_files": len(sources),
                            "successful_files": 0,
                            "failed_files": len(sources),
                        },
                    )
                    await send_webhook(error_callback_url, webhook_payload)
                except Exception as wh_err:
                    logger.error(f"[WEBHOOK] Failed to send failure webhook: {wh_err}")
        finally:
            # Dispose the engine when we're done
            await engine.dispose()
            logger.info(
                f"[Doc {doc_id}] Background processing completed: "
                f"{successful_files}/{len(sources)} succeeded, "
                f"{total_chunks} total chunks"
            )

    # Run our async runner on its own loop
    try:
        asyncio.run(_runner())
    except Exception as e:
        logger.error(
            f"[Doc {doc_id}] Background processing failed: {e}",
            exc_info=True
        )