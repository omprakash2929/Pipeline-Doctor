"""Pydantic schemas for request and response validation."""

from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    repository: str = Field(..., description="Repository name or slug (e.g. org/repo)")
    pipeline: str = Field(..., description="Pipeline or workflow name")
    status: str = Field(..., description="Pipeline execution status (e.g. failed)")
    logs: str = Field(..., description="Pipeline execution logs")
    language: str = Field(default="english", description="Explanation language ('english' or 'hinglish')")

    @field_validator("logs")
    @classmethod
    def validate_logs(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Logs cannot be empty or whitespace only")
        return v


class AnalyzeResponse(BaseModel):
    job_id: str = Field(..., description="Unique job ID for the analysis request (format: pd-xxxxxx)")
    status: str = Field(default="queued", description="Initial job status")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Service health status")


class Diagnosis(BaseModel):
    category: str = Field(..., description="Detected error category or 'unknown'")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Severity level")
    root_cause: str = Field(..., description="Identified root cause explanation")
    fix: Union[str, List[str]] = Field(..., description="Recommended fix or troubleshooting action")
    evidence: list[str] = Field(default_factory=list, description="Matching log lines providing evidence (max 5)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence between 0.0 and 1.0")
    source: Optional[Literal["rules", "llm"]] = Field(default="rules", description="Source of diagnosis")
    prevention: Optional[Union[List[str], str]] = Field(default_factory=list, description="Prevention steps")


class AnalysisResponse(BaseModel):
    job_id: str = Field(..., description="Unique job ID")
    repository: str = Field(..., description="Repository name")
    pipeline: str = Field(..., description="Pipeline name")
    status: str = Field(..., description="Job execution status ('queued', 'processing', 'done', 'failed')")
    language: str = Field(default="english", description="Explanation language")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    category: Optional[str] = Field(default=None, description="Detected error category")
    severity: Optional[str] = Field(default=None, description="Detected severity level")
    root_cause: Optional[str] = Field(default=None, description="Identified root cause")
    fix: Optional[Union[str, List[str]]] = Field(default=None, description="Recommended fix")
    evidence: Optional[list[str]] = Field(default=None, description="Matching evidence lines")
    confidence: Optional[float] = Field(default=None, description="Detection confidence")
    error: Optional[str] = Field(default=None, description="Failure error details")
    source: Optional[str] = Field(default=None, description="Source of diagnosis ('rules' or 'llm')")
    prevention: Optional[Union[List[str], str]] = Field(default=None, description="Prevention steps")
