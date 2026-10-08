"""Tests for job queue implementations."""

import threading
from api.services.queue import InMemoryQueue


def test_in_memory_queue_basic_fifo():
    queue = InMemoryQueue()
    assert queue.dequeue() is None
    assert queue.size() == 0

    job1 = {"job_id": "job-1", "pipeline": "build"}
    job2 = {"job_id": "job-2", "pipeline": "test"}

    queue.enqueue(job1)
    queue.enqueue(job2)
    assert queue.size() == 2

    assert queue.dequeue() == job1
    assert queue.size() == 1
    assert queue.dequeue() == job2
    assert queue.size() == 0
    assert queue.dequeue() is None


def test_in_memory_queue_thread_safety():
    queue = InMemoryQueue()
    num_threads = 10
    items_per_thread = 50

    def producer(thread_id: int):
        for i in range(items_per_thread):
            queue.enqueue({"thread": thread_id, "index": i})

    threads = [threading.Thread(target=producer, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert queue.size() == num_threads * items_per_thread

    consumed = []
    def consumer():
        while True:
            item = queue.dequeue()
            if item is None:
                break
            consumed.append(item)

    c_threads = [threading.Thread(target=consumer) for _ in range(5)]
    for ct in c_threads:
        ct.start()
    for ct in c_threads:
        ct.join()

    assert len(consumed) == num_threads * items_per_thread
    assert queue.size() == 0
