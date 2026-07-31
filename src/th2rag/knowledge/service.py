from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.clients.storage.s3 import delete_file_from_s3, upload_file_to_s3
from th2rag.knowledge import exceptions, schemas
from th2rag.models import Knowledge, Status
from th2rag.pagination import PageParams, PageResponse, paginate
from th2rag.rag.retrieval.lancedb.lancedb_storage import LanceDBStorage
from th2rag.users import schemas as user_schemas
from th2rag.utils.logger import setup_logger
from th2rag.config import settings
from datetime import datetime, timezone
import os

logger = setup_logger(__name__)


async def get_all_knowledges(
    page_params: PageParams, current_user: user_schemas.User, db: AsyncSession
) -> PageResponse[schemas.Knowledge]:
    stmt = select(Knowledge)
    if current_user.role != "ADMIN":
        stmt = stmt.where(Knowledge.user_id == current_user.user_id)

    # First, check and auto-fail any timed out PENDING documents
    # Get all PENDING documents for this user
    pending_stmt = stmt.where(Knowledge.status == Status.PENDING)
    pending_result = await db.execute(pending_stmt)
    pending_docs = pending_result.scalars().all()

    # Check each PENDING document for timeout
    failed_count = 0
    timeout_threshold = settings.knowledge_pending_timeout_minutes

    for knowledge in pending_docs:
        if knowledge.created_at:
            # Handle both timezone-aware and timezone-naive datetimes
            created_at = knowledge.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age = datetime.now(timezone.utc) - created_at
            age_minutes = age.total_seconds() / 60

            if age_minutes > timeout_threshold:
                logger.warning(
                    f"Auto-failing knowledge {knowledge.knowledge_id} - "
                    f"exceeded timeout ({age_minutes:.1f} > {timeout_threshold} minutes)"
                )
                knowledge.status = Status.FAILED
                failed_count += 1

    # Commit all status updates
    if failed_count > 0:
        await db.commit()
        logger.info(f"Auto-failed {failed_count} knowledge document(s) in list view")

    # Now return paginated results, sorted by knowledge_id descending (newest first)
    stmt = stmt.order_by(Knowledge.knowledge_id.desc())
    return await paginate(db, stmt, page_params, schemas.Knowledge)


async def get_knowledge_by_id(knowledge_id: int, db: AsyncSession) -> schemas.Knowledge:
    stmt = select(Knowledge).where(Knowledge.knowledge_id == knowledge_id)
    result = await db.execute(stmt)
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise exceptions.KnowledgeNotFoundException("Knowledge not found")

    # Auto-fail logic: Check if PENDING and timed out
    if knowledge.status == Status.PENDING and knowledge.created_at:
        # Handle both timezone-aware and timezone-naive datetimes
        created_at = knowledge.created_at
        if created_at.tzinfo is None:
            # If created_at is naive, treat it as UTC
            created_at = created_at.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - created_at
        age_minutes = age.total_seconds() / 60
        timeout_threshold = settings.knowledge_pending_timeout_minutes

        if age_minutes > timeout_threshold:
            logger.warning(
                f"Auto-failing knowledge {knowledge_id} - "
                f"exceeded timeout ({age_minutes:.1f} > {timeout_threshold} minutes)"
            )
            knowledge.status = Status.FAILED
            await db.commit()
            await db.refresh(knowledge)

    return schemas.Knowledge.model_validate(knowledge)


# Single source of truth for the extensions accepted at upload time.
# EVERY extension listed here MUST be routable by convert_any_doc
# (permanent guardrail in test/knowledge/test_lot4_whitelist.py).
# Legacy formats (.doc/.ppt/.xls) require LibreOffice; without it,
# the upload is rejected with an explicit message.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    # Docling-native Office
    ".pdf",
    ".docx",
    ".pptx",
    # Legacy Office (through headless LibreOffice, if installed)
    ".doc",
    ".ppt",
    ".xls",
    # Spreadsheets
    ".csv",
    ".xlsx",
    # Structured data
    ".json",
    # Plain text
    ".txt",
    # Web / markup (Lot 2)
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".adoc",
    ".asciidoc",
    # Images OCR (Lot 2)
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
})

_ALLOWED_EXTENSIONS_STR: str = ", ".join(sorted(ALLOWED_EXTENSIONS))


def validate_upload_extension(ext: str) -> None:
    """
    Validate that a file extension is supported for upload.
    Raises ValueError with a clear message when it is not.
    Call it BEFORE creating the knowledge to avoid a late FAILED status.

    Args:
        ext: Extension including the dot, e.g. '.pdf', '.xyz'

    Raises:
        ValueError: If the extension is not in ALLOWED_EXTENSIONS.
    """
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Format {ext} is not supported. "
            f"Supported formats: {_ALLOWED_EXTENSIONS_STR}"
        )


async def create_knowledge_with_multiple_files(
    name: str,
    description: str,
    prompt: str,
    files_data: list[dict],
    user_id: int,
    db: AsyncSession,
    callback_url: str | None = None,
) -> schemas.KnowledgeWithPaths:
    """
    Create knowledge with one or more files.

    This function handles both single and multiple file uploads uniformly.
    Files are uploaded to S3 and stored in the database.

    Args:
        name: Knowledge name
        description: Knowledge description
        prompt: Chatbot prompt
        files_data: List of file dictionaries with 'filename' and 'bytes'
        user_id: User ID
        db: Database session

    Returns:
        KnowledgeWithPaths object with all file information
    """
    if not files_data:
        raise ValueError("At least one file is required")

    # Validate that no files are empty (zero bytes)
    for file_data in files_data:
        file_size = len(file_data["bytes"])
        if file_size == 0:
            raise ValueError(
                f"File '{file_data['filename']}' is empty (0 bytes) and cannot be uploaded"
            )

    # Create knowledge record first to get the ID
    new_knowledge = Knowledge(
        name=name,
        description=description,
        knowledge_path="",
        knowledge_paths=[],
        filenames=[file_data["filename"] for file_data in files_data],
        prompt=prompt,
        user_id=user_id,
        status=Status.PENDING,
        callback_url=callback_url,
    )
    db.add(new_knowledge)
    await db.commit()
    await db.refresh(new_knowledge)

    # Upload all files to S3 and collect their URLs
    s3_urls = []
    filenames = []
    logger.info("[Indexing] Started Upload files to  storage: s3")

    try:
        for file_data in files_data:
            s3_url = upload_file_to_s3(
                file_data["bytes"], file_data["filename"], new_knowledge.knowledge_id
            )
            s3_urls.append(s3_url)
            filenames.append(file_data["filename"])
            logger.info(f"Uploaded '{file_data['filename']}' to S3: {s3_url}")
        logger.info("[Indexing] finished Upload files to  storage: s3")

        # Update knowledge with S3 URLs
        new_knowledge.knowledge_path = s3_urls[0]
        new_knowledge.knowledge_paths = s3_urls
        await db.commit()
        await db.refresh(new_knowledge)

    except Exception as e:
        # If upload fails, delete the knowledge record
        logger.error(
            f"Failed to upload files for knowledge {new_knowledge.knowledge_id}: {e}"
        )
        await db.delete(new_knowledge)
        await db.commit()
        raise

    # Return enhanced schema with paths
    logger.info(
        f"Created knowledge {new_knowledge.knowledge_id} with {len(s3_urls)} file(s)"
    )

    return schemas.KnowledgeWithPaths(
        **schemas.Knowledge.model_validate(new_knowledge).model_dump(),
        file_paths=s3_urls,
        file_names=filenames,
    )


async def update_knowledge_status(
    knowledge_id: int,
    new_status: Status,
    db: AsyncSession,
    error_message: str | None = None,
) -> None:
    """Update the processing status of a knowledge document.

    Args:
        knowledge_id: ID of the knowledge document.
        new_status: Target status.
        db: Database session.
        error_message: Optional reason for FAILED status or partial-success summary.
            If provided, it is written to the error_message column (truncated to 2000 chars).
            If None, the existing value in error_message is left untouched.
    """
    stmt = select(Knowledge).where(Knowledge.knowledge_id == knowledge_id)
    result = await db.execute(stmt)
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise exceptions.KnowledgeNotFoundException("Knowledge not found")

    knowledge.status = new_status
    if error_message is not None:
        knowledge.error_message = error_message[:2000]
    await db.commit()
    logger.info(f"Updated knowledge {knowledge_id} status to {new_status.value}")


async def check_and_fail_if_timeout(knowledge_id: int, db: AsyncSession) -> bool:
    """
    Check if a knowledge document has exceeded the timeout threshold.
    If it has and is still PENDING, update it to FAILED.

    Args:
        knowledge_id: ID of the knowledge document
        db: Database session

    Returns:
        True if the document was auto-failed, False otherwise
    """
    stmt = select(Knowledge).where(Knowledge.knowledge_id == knowledge_id)
    result = await db.execute(stmt)
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise exceptions.KnowledgeNotFoundException("Knowledge not found")

    # Only check if status is PENDING
    if knowledge.status != Status.PENDING:
        return False

    # Check if created_at exists and calculate age
    if not knowledge.created_at:
        logger.warning(f"Knowledge {knowledge_id} has no created_at timestamp")
        return False

    # Calculate age in minutes
    age = datetime.now(timezone.utc) - knowledge.created_at
    age_minutes = age.total_seconds() / 60

    timeout_threshold = settings.knowledge_pending_timeout_minutes

    # If exceeded timeout, mark as FAILED
    if age_minutes > timeout_threshold:
        logger.warning(
            f"Auto-failing knowledge {knowledge_id} - "
            f"exceeded timeout ({age_minutes:.1f} > {timeout_threshold} minutes)"
        )
        knowledge.status = Status.FAILED
        await db.commit()
        return True

    return False


async def delete_knowledge(knowledge_id: int, db: AsyncSession) -> None:
    """
    Delete a knowledge document and all associated resources.

    This includes:
    - All S3 files (primary and additional)
    - All vector database chunks
    - The database record
    """
    stmt = select(Knowledge).where(Knowledge.knowledge_id == knowledge_id)
    result = await db.execute(stmt)
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise exceptions.KnowledgeNotFoundException("Knowledge not found")

    # Delete all associated files from S3
    deleted_files = 0
    failed_deletions = []

    try:
        # Get all file paths (primary + additional)
        all_paths = set()
        all_paths.add(knowledge.knowledge_path)

        # JSONB fields are already lists, no need to parse JSON
        if hasattr(knowledge, "knowledge_paths") and knowledge.knowledge_paths:
            if isinstance(knowledge.knowledge_paths, list):
                all_paths.update(knowledge.knowledge_paths)
            else:
                logger.warning(
                    f"knowledge_paths is not a list: {type(knowledge.knowledge_paths)}"
                )

        # Delete each file from S3
        for path in all_paths:
            try:
                delete_file_from_s3(path)
                deleted_files += 1
                logger.info(f"Deleted S3 file: {path}")
            except Exception as e:
                failed_deletions.append(path)
                logger.warning(f"Could not delete S3 object {path}: {e}")

        logger.info(
            f"Deleted {deleted_files} file(s) from S3 for knowledge {knowledge_id}"
        )
        if failed_deletions:
            logger.warning(
                f"Failed to delete {len(failed_deletions)} file(s): {failed_deletions}"
            )

    except Exception as e:
        logger.error(f"Error during S3 cleanup for knowledge {knowledge_id}: {e}")

    # Delete from database
    await db.delete(knowledge)
    await db.commit()
    logger.info(f"Deleted knowledge {knowledge_id} from database")

    # Delete from vector database
    try:
        lancedb_storage = LanceDBStorage()
        lancedb_storage.delete_chunks(doc_id=knowledge_id)
        logger.info(f"Deleted chunks for knowledge {knowledge_id} from vector database")
    except Exception as e:
        logger.error(f"Error deleting chunks from vector database: {e}")
