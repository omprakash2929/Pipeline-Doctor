"""Tests for worker.llm module."""

import json
from unittest.mock import MagicMock, patch
import pytest
from worker.llm import (
    BedrockLLMClient,
    MockLLMClient,
    get_llm_client,
    parse_llm_json,
    truncate_logs,
)


def test_mock_llm_client_english():
    client = MockLLMClient()
    logs = "Traceback (most recent call last):\nRuntimeError: Unknown system failure"
    result = client.analyze(logs, language="english")

    assert result["category"] == "unknown"
    assert result["severity"] == "high"
    assert result["confidence"] == 0.85
    assert "build failure" in result["summary"].lower()
    assert len(result["evidence"]) > 0
    assert len(result["recommended_fix"]) > 0
    assert len(result["prevention"]) > 0


def test_mock_llm_client_hinglish():
    client = MockLLMClient()
    logs = "Traceback (most recent call last):\nRuntimeError: Unknown system failure"
    result = client.analyze(logs, language="hinglish")

    assert result["category"] == "unknown"
    assert "fail ho gaya" in result["summary"].lower()
    assert any("karein" in fix.lower() for fix in result["recommended_fix"])
    assert any("karein" in p.lower() for p in result["prevention"])


def test_parse_llm_json_clean():
    raw = json.dumps({
        "summary": "Build step failed.",
        "category": "dependency_error",
        "severity": "high",
        "likely_root_cause": "Package not found.",
        "evidence": ["npm ERR! 404"],
        "recommended_fix": ["npm install"],
        "prevention": ["Lock dependencies"],
        "confidence": 0.95,
    })
    parsed = parse_llm_json(raw)
    assert parsed["category"] == "dependency_error"
    assert parsed["confidence"] == 0.95
    assert parsed["evidence"] == ["npm ERR! 404"]


def test_parse_llm_json_fenced_markdown():
    data = {
        "summary": "Fenced output.",
        "category": "network_error",
        "severity": "medium",
        "likely_root_cause": "DNS timeout.",
        "evidence": ["timeout 30s"],
        "recommended_fix": ["retry"],
        "prevention": ["increase timeout"],
        "confidence": 0.8,
    }
    raw = f"```json\n{json.dumps(data)}\n```"
    parsed = parse_llm_json(raw)
    assert parsed["category"] == "network_error"
    assert parsed["severity"] == "medium"
    assert parsed["confidence"] == 0.8


def test_parse_llm_json_extra_text_wrapper():
    data = {
        "summary": "Surrounded output.",
        "category": "test_failure",
        "severity": "low",
        "likely_root_cause": "Assertion failed.",
        "evidence": ["assert False"],
        "recommended_fix": ["fix test"],
        "prevention": ["write better tests"],
        "confidence": 0.7,
    }
    raw = f"Here is my analysis of your pipeline:\n{json.dumps(data)}\nPlease check the fixes!"
    parsed = parse_llm_json(raw)
    assert parsed["category"] == "test_failure"
    assert parsed["confidence"] == 0.7


def test_parse_llm_json_invalid_fallback():
    raw = "I am an AI and I could not find any error in the logs."
    parsed = parse_llm_json(raw)
    assert parsed["category"] == "unknown"
    assert parsed["confidence"] == 0.0
    assert "failed" in parsed["likely_root_cause"].lower()
    assert parsed["evidence"] == []


def test_parse_llm_json_confidence_clamping():
    # Greater than 1.0
    high_raw = json.dumps({"confidence": 1.75, "category": "unknown"})
    assert parse_llm_json(high_raw)["confidence"] == 1.0

    # Negative
    low_raw = json.dumps({"confidence": -0.8, "category": "unknown"})
    assert parse_llm_json(low_raw)["confidence"] == 0.0

    # Non-numeric
    bad_raw = json.dumps({"confidence": "not-a-number", "category": "unknown"})
    assert parse_llm_json(bad_raw)["confidence"] == 0.0


def test_truncate_logs():
    many_lines = "\n".join([f"line {i}" for i in range(350)])
    truncated = truncate_logs(many_lines, max_lines=200, max_chars=12000)
    lines = truncated.splitlines()
    assert len(lines) == 200
    assert lines[-1] == "line 349"

    long_chars = "x" * 20000
    truncated_chars = truncate_logs(long_chars, max_lines=200, max_chars=12000)
    assert len(truncated_chars) <= 12000


def test_bedrock_llm_client_canned_response():
    fake_bedrock = MagicMock()
    canned_payload = {
        "summary": "Database migration failure.",
        "category": "unknown",
        "severity": "critical",
        "likely_root_cause": "Alembic revision mismatch on production schema.",
        "evidence": ["alembic.util.exc.CommandError: Target database is not up to date."],
        "recommended_fix": ["Run alembic upgrade head"],
        "prevention": ["Add migration verification step in staging CI"],
        "confidence": 0.92,
    }
    fake_bedrock.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": json.dumps(canned_payload)}]
            }
        }
    }

    client = BedrockLLMClient(model_id="test-model", region="us-east-1")
    client._client = fake_bedrock

    res = client.analyze("alembic migration logs error", language="english")

    assert res["category"] == "unknown"
    assert res["severity"] == "critical"
    assert res["confidence"] == 0.92
    assert "Alembic revision" in res["likely_root_cause"]
    assert len(res["evidence"]) == 1
    assert fake_bedrock.converse.called


def test_get_llm_client_factory(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "mock")
    c_mock = get_llm_client()
    assert isinstance(c_mock, MockLLMClient)

    monkeypatch.setenv("LLM_BACKEND", "bedrock")
    c_bedrock = get_llm_client()
    assert isinstance(c_bedrock, BedrockLLMClient)

    monkeypatch.setenv("LLM_BACKEND", "invalid")
    with pytest.raises(ValueError):
        get_llm_client()
