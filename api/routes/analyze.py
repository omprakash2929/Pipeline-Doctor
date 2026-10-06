"""Analyze route definition."""

import secrets
from fastapi import APIRouter
from models.schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    job_id = f"pd-{secrets.token_hex(3)}"
    return AnalyzeResponse(job_id=job_id, status="queued")
