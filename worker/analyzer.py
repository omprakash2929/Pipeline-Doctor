"""Worker analyzer component to process pipeline jobs."""

import logging
from typing import Any, Dict
from api.services.store import ResultStore
from worker.llm import get_llm_client
from worker.log_parser import detect_error
from worker.translations import get_hinglish_diagnosis

logger = logging.getLogger(__name__)


def process_job(job: Dict[str, Any], store: ResultStore) -> Dict[str, Any]:
    """Process a pipeline analysis job using rules first and falling back to LLM.

    Args:
        job: Dictionary containing job details including 'job_id', 'logs', and 'language'.
        store: ResultStore instance to persist status and analysis results.

    Returns:
        Updated job record dictionary from the store.
    """
    job_id = job.get("job_id", "")
    language = str(job.get("language", "english")).lower()
    logs = job.get("logs", "")

    try:
        store.update_status(job_id, "processing")

        # 1. Run rule-based parser first
        rule_diagnosis = detect_error(logs)

        if rule_diagnosis.get("category") != "unknown":
            # Known error detected via rules
            root_cause = rule_diagnosis.get("root_cause", "")
            fix = rule_diagnosis.get("fix", "")

            if language == "hinglish":
                root_cause, fix = get_hinglish_diagnosis(
                    rule_diagnosis["category"], root_cause, fix
                )

            final_result = {
                "category": rule_diagnosis["category"],
                "severity": rule_diagnosis["severity"],
                "root_cause": root_cause,
                "fix": fix,
                "evidence": rule_diagnosis.get("evidence", []),
                "prevention": [],
                "confidence": rule_diagnosis.get("confidence", 0.9),
                "source": "rules",
                "language": language,
            }
        else:
            # 2. Fall back to LLM for unknown errors
            llm_client = get_llm_client()
            llm_result = llm_client.analyze(logs, language=language)

            final_result = {
                "category": llm_result.get("category", "unknown"),
                "severity": llm_result.get("severity", "medium"),
                "root_cause": llm_result.get("likely_root_cause") or llm_result.get("summary") or "Unknown error",
                "fix": llm_result.get("recommended_fix", ["Inspect pipeline logs manually."]),
                "evidence": llm_result.get("evidence", []),
                "prevention": llm_result.get("prevention", []),
                "confidence": llm_result.get("confidence", 0.0),
                "source": "llm",
                "language": language,
            }

        store.update_status(job_id, "done", **final_result)
        record = store.get(job_id)
        return record or {"job_id": job_id, "status": "done", **final_result}

    except Exception as exc:
        logger.exception("Failed to process job %s: %s", job_id, exc)
        error_msg = str(exc)
        store.update_status(job_id, "failed", error=error_msg)
        record = store.get(job_id)
        return record or {"job_id": job_id, "status": "failed", "error": error_msg}
