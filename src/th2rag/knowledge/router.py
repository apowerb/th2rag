import asyncio
import ipaddress
import os
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from th2rag.config import settings
from th2rag.database import get_db
from th2rag.dependencies import get_current_user
from th2rag.knowledge import dependencies, schemas, service
from th2rag.knowledge.mage_client import process_knowledge_upload_batch
from th2rag.pagination import PageParams, PageResponse
from th2rag.rag.tasks.process_pdf import process_pdfs_background, process_pdfs_sync
from th2rag.users import schemas as user_schemas
from th2rag.utils.logger import setup_logger

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = setup_logger(__name__)


def _validate_callback_url(url: str | None) -> None:
    """Validate callback_url to prevent SSRF attacks."""
    if url is None:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="callback_url must use http or https")
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise HTTPException(status_code=400, detail="callback_url cannot point to localhost")
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise HTTPException(status_code=400, detail="callback_url cannot point to a private network")
    except ValueError:
        pass  # hostname is a DNS name, not an IP — OK


@router.get("/", response_model=PageResponse[schemas.Knowledge])
async def get_all_knowledges(
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    """
    Get all knowledge documents for the current user.
    Admin users can see all documents.
    """
    return await service.get_all_knowledges(page_params, current_user, db)


@router.get("/upload-ui", response_class=HTMLResponse)
async def upload_ui():
    """
    Serve a custom HTML interface for multi-file upload with drag & drop.
    This provides a better user experience than Swagger UI for selecting multiple files.

    Note: Swagger UI has limitations rendering multiple file inputs properly.
    Use this UI or test via cURL/Postman for better multi-file selection.

    This endpoint does not require authentication to serve the HTML page,
    but the upload endpoint itself requires authentication.
    """
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Knowledge - Multi-File Selector</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #013DFF 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            width: 100%;
            padding: 40px;
        }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .form-group { margin-bottom: 24px; }
        label {
            display: block;
            color: #333;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }
        input[type="text"], textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus, textarea:focus {
            outline: none;
            border-color: #013DFF
;
        }
        textarea { resize: vertical; min-height: 80px; }
        .file-drop-area {
            border: 3px dashed #013DFF
;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: #f8f9ff;
        }
        .file-drop-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }
        .file-drop-area.dragover {
            background: #e8ebff;
            border-color: #764ba2;
            transform: scale(1.02);
        }
        .file-icon { font-size: 48px; margin-bottom: 16px; }
        .file-label {
            font-size: 16px;
            color: #013DFF
;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .file-hint { font-size: 13px; color: #999; }
        #fileInput { display: none; }
        .file-list { margin-top: 20px; }
        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .file-info { display: flex; align-items: center; gap: 12px; }
        .file-name { font-weight: 500; color: #333; }
        .file-size { color: #999; font-size: 13px; }
        .remove-btn {
            background: #ff4444;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.3s;
        }
        .remove-btn:hover { background: #cc0000; }
        .submit-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #013DFF
 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
            margin-top: 24px;
        }
        .submit-btn:hover:not(:disabled) { transform: translateY(-2px); }
        .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .status-message {
            margin-top: 20px;
            padding: 16px;
            border-radius: 8px;
            display: none;
        }
        .status-message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status-message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .status-message.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #e0e0e0;
            border-radius: 2px;
            overflow: hidden;
            margin-top: 16px;
            display: none;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #013DFF
 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Create Knowledge Base</h1>
        <p class="subtitle">Upload multiple documents (PDF, DOCX, PPTX, CSV, XLSX) at once...</p>

        <form id="uploadForm">
            <div class="form-group">
                <label for="name">Knowledge Name *</label>
                <input type="text" id="name" name="name" required placeholder="e.g., Company Policies">
            </div>

            <div class="form-group">
                <label for="description">Description *</label>
                <textarea id="description" name="description" required placeholder="Describe what this knowledge base contains..."></textarea>
            </div>

            <div class="form-group">
                <label for="prompt">ChatBot Prompt *</label>
                <textarea id="prompt" name="prompt" required placeholder="Enter the system prompt for the chatbot..."></textarea>
            </div>

            <div class="form-group">
                <label>Supported formats: PDF, DOCX, PPTX, DOC, PPT, XLS, CSV, XLSX, JSON, TXT, HTML, MD, ADOC, PNG, JPG, TIFF, BMP (select multiple)</label>
                <div class="file-drop-area" id="dropArea">
                    <div class="file-icon">📄</div>
                    <div class="file-label">Click to select files or drag & drop</div>
                    <div class="file-hint">Select multiple PDFs or JSON files using Ctrl+Click (Cmd+Click on Mac)</div>
                </div>
                <input type="file" id="fileInput" multiple accept=".pdf,.docx,.pptx,.doc,.ppt,.xls,.csv,.xlsx,.json,.txt,.html,.htm,.md,.markdown,.adoc,.asciidoc,.png,.jpg,.jpeg,.tiff,.tif,.bmp">
                <div class="file-list" id="fileList"></div>
            </div>

            <button type="submit" class="submit-btn" id="submitBtn">
                Upload & Create Knowledge Base
            </button>

            <div class="progress-bar" id="progressBar">
                <div class="progress-fill" id="progressFill"></div>
            </div>

            <div class="status-message" id="statusMessage"></div>
        </form>
    </div>

    <script>
        const dropArea = document.getElementById('dropArea');
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const form = document.getElementById('uploadForm');
        const submitBtn = document.getElementById('submitBtn');
        const statusMessage = document.getElementById('statusMessage');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        let selectedFiles = [];

        dropArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'));
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'));
        });

        dropArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            handleFiles(files);
        });

        const ALLOWED_EXTS = new Set([
            '.pdf', '.docx', '.pptx', '.doc', '.ppt', '.xls',
            '.csv', '.xlsx', '.json', '.txt',
            '.html', '.htm', '.md', '.markdown', '.adoc', '.asciidoc',
            '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'
        ]);

        function handleFiles(files) {
            const validFiles = Array.from(files).filter(file => {
                const ext = '.' + file.name.toLowerCase().split('.').pop();
                return ALLOWED_EXTS.has(ext);
            });
            if (validFiles.length === 0) {
                const exts = Array.from(ALLOWED_EXTS).join(', ');
                showStatus('Please select a supported file. Supported formats: ' + exts, 'error');
                return;
            }
            selectedFiles = [...selectedFiles, ...validFiles];
            displayFiles();
            hideStatus();
        }

        function displayFiles() {
            fileList.innerHTML = '';
            selectedFiles.forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
                fileItem.innerHTML = `
                    <div class="file-info">
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">(${sizeInMB} MB)</span>
                    </div>
                    <button type="button" class="remove-btn" onclick="removeFile(${index})">Remove</button>
                `;
                fileList.appendChild(fileItem);
            });
        }

        function removeFile(index) {
            selectedFiles.splice(index, 1);
            displayFiles();
        }

        function showStatus(message, type) {
            statusMessage.textContent = message;
            statusMessage.className = `status-message ${type}`;
            statusMessage.style.display = 'block';
        }

        function hideStatus() { statusMessage.style.display = 'none'; }

        function showProgress(percent) {
            progressBar.style.display = 'block';
            progressFill.style.width = percent + '%';
        }

        function hideProgress() {
            progressBar.style.display = 'none';
            progressFill.style.width = '0%';
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (selectedFiles.length === 0) {
                showStatus('Please select at least one PDF or JSON file', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('name', document.getElementById('name').value);
            formData.append('description', document.getElementById('description').value);
            formData.append('prompt', document.getElementById('prompt').value);
            selectedFiles.forEach(file => formData.append('files', file));

            submitBtn.disabled = true;
            showStatus('Uploading files...', 'info');
            showProgress(30);

            try {
                const response = await fetch('/knowledge/', {
                    method: 'POST',
                    body: formData,
                    credentials: 'include', // Include cookies for authentication
                });

                showProgress(100);

                if (response.ok) {
                    const result = await response.json();
                    showStatus(
                        `✅ Success! Created knowledge base with ID ${result.result.knowledge_id}. ${result.message}`,
                        'success'
                    );
                    setTimeout(() => {
                        form.reset();
                        selectedFiles = [];
                        displayFiles();
                        hideProgress();
                    }, 3000);
                } else {
                    const error = await response.json();
                    showStatus(`❌ Error: ${error.detail || 'Upload failed'}`, 'error');
                    hideProgress();
                }
            } catch (error) {
                showStatus(`❌ Network error: ${error.message}`, 'error');
                hideProgress();
            } finally {
                submitBtn.disabled = false;
            }
        });

        window.removeFile = removeFile;
    </script>
</body>
</html>
    """


@router.get("/{knowledge_id}", response_model=schemas.Knowledge)
async def get_knowledge_by_id(
    knowledge: schemas.Knowledge = Depends(dependencies.require_knowledge_owner_or_admin),
):
    """
    Get a specific knowledge document by ID.
    Only the owner or admin can access it.
    """
    return knowledge


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    background_tasks: BackgroundTasks,
    name: str = Form(..., description="The name of the knowledge"),
    description: str = Form(..., description="The description of the knowledge"),
    prompt: str = Form(..., description="The prompt of the ChatBot"),
    files: list[UploadFile] = File(..., description="PDF files to upload (use /knowledge/upload-ui for better multi-select experience)"),
    callback_url: str | None = Form(None, description="Optional webhook URL to notify when indexation completes"),
    db: AsyncSession = Depends(get_db),
    current_user: user_schemas.User = Depends(get_current_user),
):
    """
    Upload PDF files to create a knowledge base.
    """
    _validate_callback_url(callback_url)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file must be provided."
        )

    # Read and validate all files
    file_data_list = []
    total_size_bytes = 0

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        try:
            service.validate_upload_extension(ext)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        try:
            file_bytes = await file.read()
            file_size_bytes = len(file_bytes)
            
            # Reject empty files (zero bytes)
            if file_size_bytes == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{file.filename}' is empty and cannot be uploaded."
                )
            
            total_size_bytes += file_size_bytes

            file_data_list.append({
                "filename": file.filename,
                "bytes": file_bytes,
                "size_bytes": file_size_bytes,
                "size_mb": file_size_bytes / (1024 * 1024)
            })
            logger.info(f"Read file: {file.filename} ({file_data_list[-1]['size_mb']:.2f} MB)")

        except HTTPException:
            # Re-raise HTTPException as-is
            raise
        except Exception as e:
            logger.error(f"Error reading file '{file.filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reading file '{file.filename}'."
            )

    total_size_mb = total_size_bytes / (1024 * 1024)
    logger.info(
        f"Total upload size: {total_size_mb:.2f} MB across {len(files)} file(s)"
    )

    # Check total size against max limit
    if total_size_mb > settings.pdf_max_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Total file size too large. Maximum is {settings.pdf_max_file_size_mb} MB. "
                   f"Your total is {total_size_mb:.2f} MB."
        )

    # Create ONE knowledge record with all files
    try:
        knowledge = await service.create_knowledge_with_multiple_files(
            name=name,
            description=description,
            prompt=prompt,
            files_data=file_data_list,
            user_id=current_user.user_id,
            db=db,
            callback_url=callback_url,
        )
        logger.info(
            f"Created knowledge record: ID={knowledge.knowledge_id} "
            f"with {len(file_data_list)} file(s)"
        )

    except Exception as e:
        logger.error(f"Failed to create knowledge record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create knowledge record: {str(e)}"
        )

    # Collect all sources for processing
    sources = knowledge.file_paths  # Use file_paths directly
    filenames = knowledge.file_names  # Use file_names directly

    # Determine processing mode based on TOTAL size
    processing_mode = settings.get_pdf_processing_mode(total_size_mb)
    processing_mode = "async"

    logger.info(
        f"Processing mode: {processing_mode} for knowledge {knowledge.knowledge_id} "
        f"with {len(sources)} file(s) "
        f"(total size: {total_size_mb:.2f} MB, threshold: {settings.pdf_auto_async_threshold_mb} MB)"
    )

    if processing_mode == "sync":
        # Process all files synchronously - user waits for completion
        try:
            logger.info(
                f"Starting synchronous processing for knowledge {knowledge.knowledge_id} "
                f"with {len(sources)} file(s)"
            )

            # Process all files and wait for results
            result = await process_pdfs_sync(
                doc_id=knowledge.knowledge_id,
                sources=sources,
                db=db,
                callback_url=callback_url,
            )

            # Build response with file details
            processed_files = []
            for idx, file_result in enumerate(result.get("files", [])):
                processed_files.append({
                    "filename": filenames[idx] if idx < len(filenames) else file_result.get("source"),
                    "source": file_result.get("source"),
                    "chunk_count": file_result.get("chunk_count"),
                    "status": file_result.get("status")
                })

            logger.info(
                f"Synchronous processing completed for knowledge {knowledge.knowledge_id}: "
                f"{result['total_chunks']} total chunks from {result['successful_files']} file(s)"
            )

            return {
                "result": knowledge,
                "processing": {
                    "mode": "sync",
                    "status": "completed",
                    "total_files": len(sources),
                    "successful_files": result.get("successful_files", 0),
                    "failed_files": result.get("failed_files", 0),
                    "total_chunks": result.get("total_chunks", 0),
                    "files": processed_files
                },
                "message": (
                    f"Successfully processed {result['successful_files']}/{len(sources)} file(s) "
                    f"with {result['total_chunks']} total chunks."
                )
            }

        except asyncio.TimeoutError:
            logger.warning(
                f"Synchronous processing timed out for knowledge {knowledge.knowledge_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"PDF processing exceeded timeout of {settings.pdf_processing_timeout}s."
            )
        except Exception as e:
            logger.error(f"Synchronous processing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF processing failed: {str(e)}"
            )

    else:
        # Process all files asynchronously - immediate response
        logger.info(
            f"Starting asynchronous processing for knowledge {knowledge.knowledge_id} "
            f"with {len(sources)} file(s)"
        )

        # Prepare file info for response
        file_sources = [
            {
                "filename": filenames[idx],
                "source": sources[idx],
                "size_mb": file_data_list[idx]["size_mb"]
            }
            for idx in range(len(sources))
        ]

        try:
            # Try Mage AI pipeline first
            mage_result = process_knowledge_upload_batch(
                doc_id=str(knowledge.knowledge_id),
                sources=sources
            )

            if mage_result:
                run_id = mage_result.get('run_id')
                logger.info(
                    f"Mage AI pipeline triggered for knowledge {knowledge.knowledge_id}. "
                    f"Run ID: {run_id}"
                )
                processing_info = {
                    "method": "mage",
                    "run_id": run_id,
                    "files": file_sources
                }
            else:
                logger.warning(
                    f"Mage trigger failed for knowledge {knowledge.knowledge_id}, "
                    f"using background task"
                )
                # Fallback to background task
                background_tasks.add_task(
                    process_pdfs_background,
                    doc_id=knowledge.knowledge_id,
                    sources=sources,
                    callback_url=callback_url,
                )
                processing_info = {
                    "method": "background_task",
                    "files": file_sources
                }

        except Exception as mage_error:
            logger.error(
                f"Error triggering Mage AI for knowledge {knowledge.knowledge_id}: {mage_error}"
            )
            # Fallback to background task
            background_tasks.add_task(
                process_pdfs_background,
                doc_id=knowledge.knowledge_id,
                sources=sources,
                callback_url=callback_url,
            )
            processing_info = {
                "method": "background_task",
                "files": file_sources
            }

        return {
            "result": knowledge,
            "processing": {
                "mode": "async",
                "status": "processing",
                "total_files": len(sources),
                **processing_info
            },
            "message": (
                f"Your {len(sources)} file(s) {'is' if len(sources) == 1 else 'are'} being processed "
                f"in the background under knowledge ID {knowledge.knowledge_id}."
            )
        }


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    knowledge: schemas.Knowledge = Depends(dependencies.require_knowledge_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a knowledge document and all its associated data.
    This includes all S3 files and vector database entries.
    """
    await service.delete_knowledge(knowledge.knowledge_id, db)