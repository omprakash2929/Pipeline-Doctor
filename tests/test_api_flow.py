"""End-to-end API flow tests."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.services.factory import get_queue, get_store, reset_singletons

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_services(monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    reset_singletons()
    yield
    reset_singletons()


def test_api_end_to_end_flow():
    payload = {
        "repository": "octocat/Hello-World",
        "pipeline": "docker-ci",
        "status": "failed",
        "logs": "Step 4/6 : RUN npm run build\nThe command '/bin/sh -c npm run build' returned a non-zero code: 1\nfailed to build",
        "language": "english",
    }
    # 1. POST /api/analyze
    post_res = client.post("/api/analyze", json=payload)
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "queued"
    job_id = post_data["job_id"]
    assert job_id.startswith("pd-")

    # 2. GET /api/analysis/{job_id}
    # TestClient runs background tasks before completing the post response
    get_res = client.get(f"/api/analysis/{job_id}")
    assert get_res.status_code == 200
    analysis = get_res.json()

    assert analysis["job_id"] == job_id
    assert analysis["repository"] == "octocat/Hello-World"
    assert analysis["pipeline"] == "docker-ci"
    assert analysis["status"] == "done"
    assert analysis["category"] == "docker_build_error"
    assert analysis["severity"] == "high"
    assert len(analysis["evidence"]) > 0
    assert analysis["confidence"] > 0


def test_analysis_unknown_job_id_returns_404():
    res = client.get("/api/analysis/pd-unknown99")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_analyze_empty_logs_returns_422():
    # Empty string
    res = client.post(
        "/api/analyze",
        json={
            "repository": "octocat/Hello-World",
            "pipeline": "build",
            "status": "failed",
            "logs": "",
        },
    )
    assert res.status_code == 422

    # Whitespace-only string
    res_ws = client.post(
        "/api/analyze",
        json={
            "repository": "octocat/Hello-World",
            "pipeline": "build",
            "status": "failed",
            "logs": "   \n\t  \n  ",
        },
    )
    assert res_ws.status_code == 422


def test_factory_backend_aws_raises_not_implemented(monkeypatch):
    monkeypatch.setenv("BACKEND", "aws")
    reset_singletons()
    with pytest.raises(NotImplementedError):
        get_queue()
    with pytest.raises(NotImplementedError):
        get_store()
