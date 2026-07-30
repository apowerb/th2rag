from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from th2rag.models import Status


class KnowledgeBase(BaseModel):
    name: str
    description: str
    prompt: str | None = None


class Knowledge(KnowledgeBase):
    knowledge_id: int
    user_id: int
    knowledge_path: str
    status: Status
    callback_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class KnowledgeWithPaths(Knowledge):
    """Extended Knowledge schema that includes all file paths"""
    file_paths: list[str] = Field(description="List of all S3 file paths")
    file_names: list[str] = Field(description="List of original filenames")

    def get_file_path(self, index: int) -> str:
        """
        Get file path by index.
        """
        if 0 <= index < len(self.file_paths):
            return self.file_paths[index]
        raise IndexError(f"File index {index} out of range (0-{len(self.file_paths)-1})")

    def get_file_name(self, index: int) -> str:
        """
        Get filename by index.
        """
        if 0 <= index < len(self.file_names):
            return self.file_names[index]
        raise IndexError(f"File index {index} out of range (0-{len(self.file_names)-1})")

    @property
    def file_count(self) -> int:
        """Get the total number of files"""
        return len(self.file_paths)


class KnowledgeCreate(KnowledgeBase):
    pass

class FileProcessingInfo(BaseModel):
    """Information about individual file processing"""
    filename: str
    source: str
    chunk_count: int | None = None
    status: Literal["completed", "failed"] | None = "completed"


class ProcessingInfo(BaseModel):
    """Information about PDF processing status"""
    mode: Literal["sync", "async"] = Field(
        description="Processing mode: 'sync' (waited for completion) or 'async' (background)"
    )
    status: Literal["processing", "completed", "failed", "partial"] = Field(
        description="Current processing status"
    )
    total_files: int = Field(
        description="Total number of files being processed"
    )
    successful_files: int | None = Field(
        default=None,
        description="Number of files successfully processed"
    )
    failed_files: int | None = Field(
        default=None,
        description="Number of files that failed processing"
    )
    total_chunks: int | None = Field(
        default=None,
        description="Total number of chunks created across all files"
    )
    files: list[FileProcessingInfo] | None = Field(
        default=None,
        description="Individual file processing information"
    )
    method: Literal["mage", "background_task"] | None = Field(
        default=None,
        description="Processing method for async mode"
    )
    run_id: str | None = Field(
        default=None,
        description="Mage run ID (only for async with Mage)"
    )


class KnowledgeCreateResponse(BaseModel):
    """Response when creating a new knowledge document"""
    result: KnowledgeWithPaths = Field( description="The created knowledge document with file paths")
    processing: ProcessingInfo = Field(description="Processing information")
    message: str = Field(description="Human-readable message about the processing status")

    model_config = ConfigDict(from_attributes=True)
