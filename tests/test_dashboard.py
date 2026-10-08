"""Tests for dashboard and recent analyses endpoints."""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.services.factory import get_store, reset_singletons

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_services(monkeypatch):
    monkeypatch.setenv("BACKEND", "local")
    reset_singletons()
    yield
    reset_singletons()


def test_root_serves_dashboard():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Pipeline Doctor" in response.text
    assert "AI-powered CI/CD troubleshooting" in response.text


def test_static_files_served():
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers.get("content-type", "")


def test_recent_analyses_empty():
    response = client.get("/api/analyses")
    assert response.status_code == 200
    assert response.json() == []


def test_recent_analyses_ordering():
    store = get_store()
    now = datetime.now(timezone.utc)

    # Insert 3 jobs with different timestamps
    job1 = {
        "job_id": "pd-old01",
        "repository": "repo/old",
        "pipeline": "ci",
        "status": "done",
        "language": "english",
        "created_at": (now - timedelta(minutes=10)).isoformat(),
    }
    job2 = {
        "job_id": "pd-mid02",
        "repository": "repo/mid",
        "pipeline": "ci",
        "status": "done",
        "language": "english",
        "created_at": (now - timedelta(minutes=5)).isoformat(),
    }
    job3 = {
        "job_id": "pd-new03",
        "repository": "repo/new",
        "pipeline": "ci",
        "status": "done",
        "language": "english",
        "created_at": now.isoformat(),
    }

    # Save in non-chronological order
    store.save("pd-mid02", job2)
    store.save("pd-old01", job1)
    store.save("pd-new03", job3)

    response = client.get("/api/analyses")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    # Newest first
    assert data[0]["job_id"] == "pd-new03"
    assert data[1]["job_id"] == "pd-mid02"
    assert data[2]["job_id"] == "pd-old01"


def test_recent_analyses_limit_ten():
    store = get_store()
    now = datetime.now(timezone.utc)

    # Insert 15 jobs
    for i in range(15):
        job_id = f"pd-{i:04d}"
        job = {
            "job_id": job_id,
            "repository": f"repo/{i}",
            "pipeline": "ci",
            "status": "done",
            "language": "english",
            "created_at": (now + timedelta(seconds=i)).isoformat(),
        }
        store.save(job_id, job)

    response = client.get("/api/analyses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    # Newest job should be pd-0014
    assert data[0]["job_id"] == "pd-0014"

    # Custom limit check
    res_custom = client.get("/api/analyses?limit=5")
    assert res_custom.status_code == 200
    assert len(res_custom.json()) == 5
