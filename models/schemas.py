"""Pydantic schemas for request and response validation."""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    repository: str = Field(..., description="Repository name or slug (e.g. org/repo)")
    pipeline: str = Field(..., description="Pipeline or workflow name")
    status: str = Field(..., description="Pipeline execution status (e.g. failed)")
    logs: str = Field(..., description="Pipeline execution logs")
    language: str = Field(default="english", description="Explanation language ('english' or 'hinglish')")


class AnalyzeResponse(BaseModel):
    job_id: str = Field(..., description="Unique job ID for the analysis request (format: pd-xxxxxx)")
    status: str = Field(default="queued", description="Initial job status")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Service health status")
