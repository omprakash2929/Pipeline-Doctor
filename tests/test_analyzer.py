"""Tests for worker analyzer module."""

from unittest.mock import MagicMock, patch
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
        "language": "english",
    }
    store.save(job_id, job_data)

    result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["category"] == "dependency_error"
    assert result["severity"] == "high"
    assert result["source"] == "rules"
    assert len(result["evidence"]) > 0

    saved = store.get(job_id)
    assert saved is not None
    assert saved["status"] == "done"
    assert saved["category"] == "dependency_error"
    assert saved["source"] == "rules"


def test_process_job_known_error_skips_llm():
    store = InMemoryStore()
    job_id = "job-skip-llm-1"
    job_data = {
        "job_id": job_id,
        "repository": "org/repo",
        "pipeline": "build",
        "status": "queued",
        "logs": "npm ERR! code 1\nnpm ERR! path /app",
        "language": "english",
    }
    store.save(job_id, job_data)

    with patch("worker.analyzer.get_llm_client") as mock_get_client:
        result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["source"] == "rules"
    assert result["category"] == "dependency_error"
    mock_get_client.assert_not_called()


def test_process_job_unknown_error_calls_llm():
    store = InMemoryStore()
    job_id = "job-call-llm-1"
    job_data = {
        "job_id": job_id,
        "repository": "org/repo",
        "pipeline": "ci",
        "status": "queued",
        "logs": "A random unknown pipeline error occurred at step 9",
        "language": "english",
    }
    store.save(job_id, job_data)

    mock_llm_instance = MagicMock()
    mock_llm_instance.analyze.return_value = {
        "summary": "Unknown failure diagnosed by LLM",
        "category": "unknown",
        "severity": "medium",
        "likely_root_cause": "Misconfigured environment variable",
        "evidence": ["step 9 error"],
        "recommended_fix": ["Check environment variable setup"],
        "prevention": ["Add env linting"],
        "confidence": 0.82,
    }

    with patch("worker.analyzer.get_llm_client", return_value=mock_llm_instance):
        result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["source"] == "llm"
    assert result["confidence"] == 0.82
    assert "Misconfigured" in result["root_cause"]
    mock_llm_instance.analyze.assert_called_once_with(
        "A random unknown pipeline error occurred at step 9", language="english"
    )


def test_process_job_known_error_hinglish():
    store = InMemoryStore()
    job_id = "job-known-hinglish"
    job_data = {
        "job_id": job_id,
        "repository": "org/repo",
        "pipeline": "build",
        "status": "queued",
        "logs": "npm ERR! missing dependency",
        "language": "hinglish",
    }
    store.save(job_id, job_data)

    result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["source"] == "rules"
    assert result["category"] == "dependency_error"
    # Hinglish text in root cause and fix
    assert "dikkat hai" in result["root_cause"].lower()
    assert "check karein" in result["fix"].lower()


def test_process_job_unknown_error_hinglish():
    store = InMemoryStore()
    job_id = "job-unknown-hinglish"
    job_data = {
        "job_id": job_id,
        "repository": "org/repo",
        "pipeline": "ci",
        "status": "queued",
        "logs": "Unrecognized failure output 0x889",
        "language": "hinglish",
    }
    store.save(job_id, job_data)

    result = process_job(job_data, store)

    assert result["status"] == "done"
    assert result["source"] == "llm"
    assert "fail ho gaya" in result["root_cause"].lower() or any("karein" in str(f).lower() for f in result["fix"])


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
