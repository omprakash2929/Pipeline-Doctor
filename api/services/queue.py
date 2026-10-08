"""Queue interfaces and implementations for Pipeline Doctor."""

from abc import ABC, abstractmethod
from collections import deque
import threading
from typing import Any, Dict, Optional


class JobQueue(ABC):
    """Abstract interface for pipeline job queues."""

    @abstractmethod
    def enqueue(self, job: Dict[str, Any]) -> None:
        """Enqueue a job payload into the queue."""
        pass

    @abstractmethod
    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue the next job payload from the queue, or None if empty."""
        pass


class InMemoryQueue(JobQueue):
    """Thread-safe in-memory job queue using collections.deque and threading.Lock."""

    def __init__(self) -> None:
        self._queue: deque[Dict[str, Any]] = deque()
        self._lock = threading.Lock()

    def enqueue(self, job: Dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(job)

    def dequeue(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def size(self) -> int:
        """Return the current number of jobs in the queue."""
        with self._lock:
            return len(self._queue)
