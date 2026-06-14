import logging
from collections import deque
from threading import Lock

log = logging.getLogger(__name__)


class SessionMemory:
    """
    In-process action log. Max `limit` records; evicts oldest when full.
    ADR-006: Session Memory = in-process, 200 records.
    Thread-safe.
    """

    def __init__(self, limit: int = 200) -> None:
        self._records: deque[dict] = deque(maxlen=limit)
        self._limit = limit
        self._lock = Lock()

    def add(self, record: dict) -> None:
        with self._lock:
            self._records.append(record)

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._records)

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            records = list(self._records)
        return records[-limit:]

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    @property
    def limit(self) -> int:
        return self._limit
