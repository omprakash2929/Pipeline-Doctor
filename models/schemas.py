"""Pydantic schemas for request and response validation."""

from typing import Literal
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


class Diagnosis(BaseModel):
    category: str = Field(..., description="Detected error category or 'unknown'")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Severity level")
    root_cause: str = Field(..., description="Identified root cause explanation")
    fix: str = Field(..., description="Recommended fix or troubleshooting action")
    evidence: list[str] = Field(default_factory=list, description="Matching log lines providing evidence (max 5)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence between 0.0 and 1.0")

