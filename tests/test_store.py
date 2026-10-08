"""Tests for result store implementations."""

import threading
from api.services.store import InMemoryStore


def test_in_memory_store_save_and_get():
    store = InMemoryStore()
    assert store.get("non-existent") is None

    data = {"job_id": "job-100", "status": "queued", "repository": "test/repo"}
    store.save("job-100", data)

    retrieved = store.get("job-100")
    assert retrieved is not None
    assert retrieved["job_id"] == "job-100"
    assert retrieved["status"] == "queued"
    assert retrieved["repository"] == "test/repo"


def test_in_memory_store_update_status():
    store = InMemoryStore()
    data = {"job_id": "job-200", "status": "queued"}
    store.save("job-200", data)

    store.update_status("job-200", "processing")
    record = store.get("job-200")
    assert record["status"] == "processing"

    store.update_status("job-200", "done", category="dependency_error", confidence=0.95)
    record = store.get("job-200")
    assert record["status"] == "done"
    assert record["category"] == "dependency_error"
    assert record["confidence"] == 0.95


def test_in_memory_store_thread_safety():
    store = InMemoryStore()
    num_threads = 20

    def writer(idx: int):
        job_id = f"job-{idx}"
        store.save(job_id, {"job_id": job_id, "status": "queued"})
        store.update_status(job_id, "processing")
        store.update_status(job_id, "done", index=idx)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(num_threads):
        rec = store.get(f"job-{i}")
        assert rec is not None
        assert rec["status"] == "done"
        assert rec["index"] == i
