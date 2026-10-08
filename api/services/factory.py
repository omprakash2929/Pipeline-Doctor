"""Service factory providing singleton queue and store instances."""

import os
from typing import Optional
from api.services.queue import InMemoryQueue, JobQueue
from api.services.store import InMemoryStore, ResultStore

_queue_instance: Optional[JobQueue] = None
_store_instance: Optional[ResultStore] = None


def get_queue() -> JobQueue:
    """Return the configured singleton JobQueue instance."""
    global _queue_instance
    if _queue_instance is None:
        backend = os.getenv("BACKEND", "local").lower()
        if backend == "local":
            _queue_instance = InMemoryQueue()
        elif backend == "aws":
            raise NotImplementedError("AWS backend not implemented yet")
        else:
            raise ValueError(f"Unknown BACKEND: {backend}")
    return _queue_instance


def get_store() -> ResultStore:
    """Return the configured singleton ResultStore instance."""
    global _store_instance
    if _store_instance is None:
        backend = os.getenv("BACKEND", "local").lower()
        if backend == "local":
            _store_instance = InMemoryStore()
        elif backend == "aws":
            raise NotImplementedError("AWS backend not implemented yet")
        else:
            raise ValueError(f"Unknown BACKEND: {backend}")
    return _store_instance


def reset_singletons() -> None:
    """Reset singletons (useful for test isolation)."""
    global _queue_instance, _store_instance
    _queue_instance = None
    _store_instance = None
