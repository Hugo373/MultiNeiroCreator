from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class DocumentResponse(BaseModel):
    id: str
    user_id: int
    project_id: int | None
    filename: str
    status: DocumentStatus
    size_bytes: int = Field(ge=0)
    file_hash: str | None
    chunks_count: int = Field(ge=0)
    error: str | None
    job_id: str | None
    created_at: str
    updated_at: str
    indexed_at: str | None


class DocumentMutationResponse(BaseModel):
    status: str
    message: str
    document: DocumentResponse
    job: "JobResponse | None" = None


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreateRequest(BaseModel):
    type: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    payload: dict[str, Any] = Field(default_factory=dict)
    project_id: int | None = None


class JobResponse(BaseModel):
    id: str
    type: str
    status: JobStatus
    user_id: int
    project_id: int | None
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    progress: int = Field(ge=0, le=100)
    progress_message: str | None
    attempts: int
    max_attempts: int
    cancel_requested: bool
    created_at: str
    started_at: str | None
    finished_at: str | None
