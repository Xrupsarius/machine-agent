import json
import logging
from datetime import datetime, timezone

from app.core.event_bus import EventBus
from app.memory.long_term_memory import LongTermMemory
from app.memory.session_memory import SessionMemory

log = logging.getLogger(__name__)
actions_log = logging.getLogger("actions")

EVENT_MEMORY_SAVED = "memory.saved"


class MemoryService:
    """
    Unified memory facade: writes to SessionMemory + SQLite simultaneously.
    ADR-006: Session first, then SQLite.
    ADR-007: Every action is logged — no silent failures.
    ADR-018: Memory System is mandatory; cannot be removed.
    """

    def __init__(
        self,
        session: SessionMemory,
        ltm: LongTermMemory,
        event_bus: EventBus,
    ) -> None:
        self._session = session
        self._ltm = ltm
        self._bus = event_bus

    # ------------------------------------------------------------------

    def save(
        self,
        user_command: str,
        intent: str,
        plan: dict,
        results: list,
        success: bool,
        error: str = "",
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()

        executed_actions = json.dumps(
            [_to_dict(r) for r in results],
            ensure_ascii=False,
        )

        result_str = ""
        if results:
            last = _to_dict(results[-1])
            result_str = last.get("output") or last.get("error") or ""

        record = {
            "timestamp": timestamp,
            "user_command": user_command,
            "intent": intent,
            "plan": json.dumps(plan, ensure_ascii=False),
            "executed_actions": executed_actions,
            "result": result_str,
            "success": success,
            "error": error,
        }

        self._session.add(record)
        self._ltm.add(record)

        actions_log.info(
            f"[{timestamp}] cmd={user_command!r} intent={intent} success={success}"
        )
        self._bus.publish(EVENT_MEMORY_SAVED, record)

    def search(self, query: str) -> list[dict]:
        """Search Session Memory first; fall back to SQLite (ADR-006)."""
        q = query.lower()
        session_hits = [
            r for r in self._session.all()
            if q in (
                r.get("user_command", "")
                + r.get("intent", "")
                + r.get("result", "")
            ).lower()
        ]
        if session_hits:
            return session_hits
        return self._ltm.search(query)

    def recent(self, limit: int = 20) -> list[dict]:
        session = self._session.recent(limit)
        if session:
            return session
        return self._ltm.recent(limit)

    def recent_since(self, hours: float) -> list[dict]:
        """Records from the last *hours* hours. Session memory first, then SQLite."""
        from datetime import timedelta
        since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        session_hits = [
            r for r in self._session.all()
            if r.get("timestamp", "") >= since_iso
        ]
        if session_hits:
            return session_hits
        return self._ltm.recent_since(hours)

    def search_by_date(self, date_str: str) -> list[dict]:
        """Records from a specific date (YYYY-MM-DD). Session first, then SQLite."""
        session_hits = [
            r for r in self._session.all()
            if r.get("timestamp", "").startswith(date_str)
        ]
        if session_hits:
            return session_hits
        return self._ltm.search_by_date(date_str)

    def filter_by_success(self, success: bool, limit: int = 20) -> list[dict]:
        """Records filtered by success flag. Session first, then SQLite."""
        session_hits = [
            r for r in self._session.all()
            if r.get("success") == success
        ]
        if session_hits:
            return session_hits[-limit:]
        return self._ltm.filter_by_success(success, limit)

    def session_count(self) -> int:
        return self._session.count()

    def total_count(self) -> int:
        return self._ltm.count()


# ------------------------------------------------------------------

def _to_dict(result) -> dict:
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return {"output": str(result)}
