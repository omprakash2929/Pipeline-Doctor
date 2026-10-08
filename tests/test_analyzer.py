"""Tests for worker analyzer module."""

from unittest.mock import patch
from api.services.store import InMemoryStore
from worker.analyzer import process_job


def test_process_job_success():
    store = InMemoryStore()
    job_id = "job-success-1"
    job_data = {
        "job_id": job_id,
        "repository": "org/repo",
        "pipeline": "build",
        "status": "queued",
        "logs": "npm ERR! Missing script: 'test'\nnpm ERR! A complete log can be found in...",
    }
    store.save(job_id, job_data)

    result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["category"] == "dependency_error"
    assert result["severity"] == "high"
    assert len(result["evidence"]) > 0

    saved = store.get(job_id)
    assert saved is not None
    assert saved["status"] == "done"
    assert saved["category"] == "dependency_error"


def test_process_job_failure():
    store = InMemoryStore()
    job_id = "job-fail-1"
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "logs": "some logs",
    }
    store.save(job_id, job_data)

    with patch("worker.analyzer.detect_error", side_effect=RuntimeError("Simulated analyzer crash")):
        result = process_job(job_data, store)

    assert result["status"] == "failed"
    assert "Simulated analyzer crash" in result["error"]

    saved = store.get(job_id)
    assert saved is not None
    assert saved["status"] == "failed"
    assert "Simulated analyzer crash" in saved["error"]
