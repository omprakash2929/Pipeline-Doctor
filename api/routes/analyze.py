"""Analyze route definition."""

from datetime import datetime, timezone
import os
import secrets
from typing import List
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from api.services.factory import get_queue, get_store
from models.schemas import AnalysisResponse, AnalyzeRequest, AnalyzeResponse
from worker.analyzer import process_job

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    job_id = f"pd-{secrets.token_hex(3)}"
    store = get_store()
    queue = get_queue()

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "job_id": job_id,
        "repository": request.repository,
        "pipeline": request.pipeline,
        "status": "queued",
        "logs": request.logs,
        "language": request.language,
        "created_at": now,
    }

    store.save(job_id, record)
    queue.enqueue(record)

    backend = os.getenv("BACKEND", "local").lower()
    if backend == "local":
        background_tasks.add_task(process_job, record, store)

    return AnalyzeResponse(job_id=job_id, status="queued")


@router.get("/analysis/{job_id}", response_model=AnalysisResponse)
def get_analysis(job_id: str) -> AnalysisResponse:
    store = get_store()
    record = store.get(job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job {job_id} not found",
        )
    return AnalysisResponse(**record)


@router.get("/analyses", response_model=List[AnalysisResponse])
def get_recent_analyses(limit: int = 10) -> List[AnalysisResponse]:
    store = get_store()
    records = store.list_recent(limit=limit)
    return [AnalysisResponse(**record) for record in records]
