"""Unit tests for FastAPI endpoints."""

import re
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_endpoint_success():
    payload = {
        "repository": "octocat/Hello-World",
        "pipeline": "build-and-test",
        "status": "failed",
        "logs": "npm ERR! Missing script: 'test'\nnpm ERR! A complete log can be found in...",
        "language": "english",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert re.match(r"^pd-[0-9a-f]{6}$", data["job_id"]) is not None


def test_analyze_endpoint_default_language():
    payload = {
        "repository": "octocat/Hello-World",
        "pipeline": "build-and-test",
        "status": "failed",
        "logs": "Traceback (most recent call last):\n  File 'app.py', line 1, in <module>\nModuleNotFoundError",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert re.match(r"^pd-[0-9a-f]{6}$", data["job_id"]) is not None


def test_analyze_endpoint_validation_error():
    # Missing required 'logs' and 'repository'
    payload = {
        "pipeline": "build-and-test",
        "status": "failed",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 422
