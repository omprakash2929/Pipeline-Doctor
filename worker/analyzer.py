"""Worker analyzer component to process pipeline jobs."""

import logging
from typing import Any, Dict
from api.services.store import ResultStore
from worker.log_parser import detect_error

logger = logging.getLogger(__name__)


def process_job(job: Dict[str, Any], store: ResultStore) -> Dict[str, Any]:
    """Process a pipeline analysis job using the rule-based log parser and update store.

    Args:
        job: Dictionary containing job details including 'job_id' and 'logs'.
        store: ResultStore instance to persist status and analysis results.

    Returns:
        Updated job record dictionary from the store.
    """
    job_id = job.get("job_id", "")
    try:
        store.update_status(job_id, "processing")
        logs = job.get("logs", "")
        diagnosis = detect_error(logs)

        store.update_status(job_id, "done", **diagnosis)
        record = store.get(job_id)
        return record or {"job_id": job_id, "status": "done", **diagnosis}
    except Exception as exc:
        logger.exception("Failed to process job %s: %s", job_id, exc)
        error_msg = str(exc)
        store.update_status(job_id, "failed", error=error_msg)
        record = store.get(job_id)
        return record or {"job_id": job_id, "status": "failed", "error": error_msg}
