import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS actions (
    id               INTEGER PRIMARY KEY,
    timestamp        TEXT NOT NULL,
    user_command     TEXT NOT NULL,
    intent           TEXT NOT NULL,
    plan             TEXT NOT NULL,
    executed_actions TEXT,
    result           TEXT,
    success          INTEGER NOT NULL DEFAULT 0,
    error            TEXT
);
"""


class LongTermMemory:
    """
    SQLite-backed action log.
    ADR-006: Long-Term Memory = SQLite.
    ADR-012: SQLite as primary storage; PostgreSQL forbidden in MVP.
    Falls back gracefully when SQLite is unavailable (log warning only).
    """

    def __init__(self, db_path: str = "data/memory.db") -> None:
        self._path = db_path
        self._available = False
        self._init_db()

    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        try:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(_DDL)
            self._available = True
            log.debug(f"LongTermMemory: SQLite ready at {self._path}")
        except Exception as e:
            log.warning(f"SQLite unavailable ({e}). Working with Session Memory only.")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        # SQLite built-in LOWER() is ASCII-only; override with Python's Unicode-aware str.lower.
        conn.create_function("LOWER", 1, str.lower)
        return conn

    # ------------------------------------------------------------------

    def add(self, record: dict) -> int | None:
        if not self._available:
            return None
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """INSERT INTO actions
                       (timestamp, user_command, intent, plan,
                        executed_actions, result, success, error)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.get("timestamp", ""),
                        record.get("user_command", ""),
                        record.get("intent", ""),
                        record.get("plan", ""),
                        record.get("executed_actions", ""),
                        record.get("result", ""),
                        1 if record.get("success") else 0,
                        record.get("error", ""),
                    ),
                )
                return cur.lastrowid
        except Exception as e:
            log.error(f"LongTermMemory.add failed: {e}")
            return None

    def recent(self, limit: int = 20) -> list[dict]:
        if not self._available:
            return []
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in reversed(rows)]
        except Exception as e:
            log.error(f"LongTermMemory.recent failed: {e}")
            return []

    def search(self, query: str) -> list[dict]:
        if not self._available:
            return []
        # LOWER() covers ASCII; for Cyrillic we also lower the query so both sides match.
        pattern = f"%{query.lower()}%"
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT * FROM actions
                       WHERE LOWER(user_command) LIKE ?
                          OR LOWER(intent) LIKE ?
                          OR LOWER(result) LIKE ?
                       ORDER BY id DESC LIMIT 50""",
                    (pattern, pattern, pattern),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"LongTermMemory.search failed: {e}")
            return []

    def recent_since(self, hours: float) -> list[dict]:
        """Records created in the last *hours* hours (UTC)."""
        if not self._available:
            return []
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM actions WHERE timestamp >= ? ORDER BY id ASC",
                    (since,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"LongTermMemory.recent_since failed: {e}")
            return []

    def search_by_date(self, date_str: str) -> list[dict]:
        """Records whose timestamp starts with *date_str* (e.g. '2024-01-15')."""
        if not self._available:
            return []
        pattern = f"{date_str}%"
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM actions WHERE timestamp LIKE ? ORDER BY id ASC",
                    (pattern,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"LongTermMemory.search_by_date failed: {e}")
            return []

    def filter_by_success(self, success: bool, limit: int = 20) -> list[dict]:
        """Records filtered by success flag (most recent first, then reversed)."""
        if not self._available:
            return []
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM actions WHERE success = ? ORDER BY id DESC LIMIT ?",
                    (1 if success else 0, limit),
                ).fetchall()
            return [dict(r) for r in reversed(rows)]
        except Exception as e:
            log.error(f"LongTermMemory.filter_by_success failed: {e}")
            return []

    def count(self) -> int:
        if not self._available:
            return 0
        try:
            with self._connect() as conn:
                return conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        except Exception:
            return 0

    @property
    def is_available(self) -> bool:
        return self._available
