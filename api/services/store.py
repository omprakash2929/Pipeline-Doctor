"""Store interfaces and implementations for Pipeline Doctor."""

from abc import ABC, abstractmethod
import threading
from typing import Any, Dict, List, Optional


class ResultStore(ABC):
    """Abstract interface for pipeline analysis result storage."""

    @abstractmethod
    def save(self, job_id: str, data: Dict[str, Any]) -> None:
        """Save analysis record for the given job_id."""
        pass

    @abstractmethod
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve analysis record by job_id, or None if not found."""
        pass

    @abstractmethod
    def update_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Update job status and any additional fields."""
        pass

    @abstractmethod
    def list_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List most recent analysis records, newest first."""
        pass


class InMemoryStore(ResultStore):
    """Thread-safe in-memory result store using dict and threading.Lock."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, job_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._store[job_id] = dict(data)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._store.get(job_id)
            return dict(record) if record is not None else None

    def update_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id]["status"] = status
                self._store[job_id].update(kwargs)

    def list_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._store.values())
            records_sorted = sorted(
                records,
                key=lambda r: r.get("created_at") or "",
                reverse=True,
            )
            return [dict(r) for r in records_sorted[:limit]]
