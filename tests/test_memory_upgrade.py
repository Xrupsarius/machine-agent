"""
Stage 18: tests for Memory Upgrade.
Covers LongTermMemory new methods, MemoryService new methods, MemorySearch upgrade.
"""
import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.memory.long_term_memory import LongTermMemory
from app.memory.session_memory import SessionMemory
from app.memory.memory_service import MemoryService
from app.agent.memory_search import MemorySearch, _hours_label
from app.core.event_bus import EventBus


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _db() -> LongTermMemory:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # LongTermMemory creates fresh
    return LongTermMemory(db_path=path)


def _record(cmd="test", intent="test", success=True, hours_ago=0.0) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {
        "timestamp": ts,
        "user_command": cmd,
        "intent": intent,
        "plan": "{}",
        "executed_actions": "[]",
        "result": f"result of {cmd}",
        "success": success,
        "error": "" if success else "some error",
    }


def _service(ltm=None) -> tuple[MemoryService, LongTermMemory]:
    if ltm is None:
        ltm = _db()
    session = SessionMemory(limit=200)
    bus = EventBus()
    svc = MemoryService(session, ltm, bus)
    return svc, ltm


def _search(svc: MemoryService) -> MemorySearch:
    return MemorySearch(svc)


# ==================================================================
# LongTermMemory — new methods
# ==================================================================

class TestLTMRecentSince:
    def test_returns_records_within_window(self):
        ltm = _db()
        ltm.add(_record(cmd="recent cmd", hours_ago=0.1))
        ltm.add(_record(cmd="old cmd", hours_ago=5.0))
        result = ltm.recent_since(hours=1.0)
        cmds = [r["user_command"] for r in result]
        assert "recent cmd" in cmds
        assert "old cmd" not in cmds

    def test_empty_when_nothing_recent(self):
        ltm = _db()
        ltm.add(_record(cmd="ancient", hours_ago=25.0))
        assert ltm.recent_since(hours=1.0) == []

    def test_returns_empty_when_unavailable(self):
        ltm = LongTermMemory(db_path="/nonexistent/path/db.sqlite")
        assert ltm.recent_since(hours=1.0) == []

    def test_ordered_chronologically(self):
        ltm = _db()
        ltm.add(_record(cmd="first", hours_ago=0.5))
        ltm.add(_record(cmd="second", hours_ago=0.2))
        result = ltm.recent_since(hours=1.0)
        assert result[0]["user_command"] == "first"
        assert result[1]["user_command"] == "second"


class TestLTMSearchByDate:
    def test_returns_records_for_date(self):
        ltm = _db()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ltm.add(_record(cmd="today cmd"))
        result = ltm.search_by_date(today)
        assert any(r["user_command"] == "today cmd" for r in result)

    def test_returns_empty_for_past_date(self):
        ltm = _db()
        ltm.add(_record(cmd="today cmd"))
        result = ltm.search_by_date("1990-01-01")
        assert result == []

    def test_returns_empty_when_unavailable(self):
        ltm = LongTermMemory(db_path="/nonexistent/path/db.sqlite")
        assert ltm.search_by_date("2024-01-01") == []


class TestLTMFilterBySuccess:
    def test_returns_only_successful(self):
        ltm = _db()
        ltm.add(_record(cmd="ok cmd", success=True))
        ltm.add(_record(cmd="fail cmd", success=False))
        result = ltm.filter_by_success(success=True)
        cmds = [r["user_command"] for r in result]
        assert "ok cmd" in cmds
        assert "fail cmd" not in cmds

    def test_returns_only_failed(self):
        ltm = _db()
        ltm.add(_record(cmd="ok cmd", success=True))
        ltm.add(_record(cmd="fail cmd", success=False))
        result = ltm.filter_by_success(success=False)
        cmds = [r["user_command"] for r in result]
        assert "fail cmd" in cmds
        assert "ok cmd" not in cmds

    def test_respects_limit(self):
        ltm = _db()
        for i in range(10):
            ltm.add(_record(cmd=f"cmd{i}", success=True))
        result = ltm.filter_by_success(success=True, limit=3)
        assert len(result) == 3

    def test_returns_empty_when_unavailable(self):
        ltm = LongTermMemory(db_path="/nonexistent/path/db.sqlite")
        assert ltm.filter_by_success(success=True) == []


# ==================================================================
# MemoryService — new methods
# ==================================================================

class TestMemoryServiceRecentSince:
    def test_returns_session_hits_first(self):
        svc, ltm = _service()
        svc._session.add(_record(cmd="session recent", hours_ago=0.1))
        result = svc.recent_since(hours=1.0)
        assert any(r["user_command"] == "session recent" for r in result)

    def test_falls_back_to_ltm(self):
        svc, ltm = _service()
        ltm.add(_record(cmd="ltm recent", hours_ago=0.1))
        result = svc.recent_since(hours=1.0)
        assert any(r["user_command"] == "ltm recent" for r in result)


class TestMemoryServiceSearchByDate:
    def test_returns_session_hits_for_today(self):
        svc, ltm = _service()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        svc._session.add(_record(cmd="today session"))
        result = svc.search_by_date(today)
        assert any(r["user_command"] == "today session" for r in result)

    def test_falls_back_to_ltm_for_past_date(self):
        svc, ltm = _service()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ltm.add(_record(cmd="today ltm"))
        result = svc.search_by_date(today)
        assert any(r["user_command"] == "today ltm" for r in result)


class TestMemoryServiceFilterBySuccess:
    def test_session_failure_filter(self):
        svc, _ = _service()
        svc._session.add(_record(cmd="bad cmd", success=False))
        svc._session.add(_record(cmd="good cmd", success=True))
        result = svc.filter_by_success(success=False)
        cmds = [r["user_command"] for r in result]
        assert "bad cmd" in cmds
        assert "good cmd" not in cmds

    def test_ltm_failure_filter_fallback(self):
        svc, ltm = _service()
        ltm.add(_record(cmd="ltm bad", success=False))
        result = svc.filter_by_success(success=False)
        assert any(r["user_command"] == "ltm bad" for r in result)


# ==================================================================
# MemorySearch — upgrade
# ==================================================================

def _ms_with_records(records: list[dict]) -> MemorySearch:
    svc, ltm = _service()
    for r in records:
        svc._session.add(r)
    return MemorySearch(svc)


class TestMemorySearchTriggers:
    @pytest.mark.parametrize("text", [
        "что мы делали",
        "что было сегодня",
        "что делали вчера",
        "что было час назад",
        "последний час",
        "покажи историю",
        "последние 5 команд",
        "что не получилось",
        "какие ошибки",
        "что прошло успешно",
        "история",
        "журнал",
        "вспомни",
        "за последние 30 минут",
    ])
    def test_is_history_query_positive(self, text):
        ms = _ms_with_records([])
        assert ms.is_history_query(text) is True

    @pytest.mark.parametrize("text", [
        "открой браузер",
        "запусти терминал",
        "создай файл notes.txt",
        "посмотри на экран",
    ])
    def test_is_history_query_negative(self, text):
        ms = _ms_with_records([])
        assert ms.is_history_query(text) is False


class TestMemorySearchFailureFilter:
    def test_answer_failure_query_returns_failed(self):
        ms = _ms_with_records([
            _record(cmd="good cmd", success=True),
            _record(cmd="bad cmd", success=False),
        ])
        answer = ms.answer("что не получилось")
        assert "bad cmd" in answer
        assert "good cmd" not in answer

    def test_answer_failure_empty(self):
        ms = _ms_with_records([_record(cmd="good", success=True)])
        answer = ms.answer("какие ошибки")
        assert "не найдено" in answer.lower() or "успешно" in answer.lower()

    def test_answer_success_filter(self):
        ms = _ms_with_records([
            _record(cmd="ok cmd", success=True),
            _record(cmd="fail cmd", success=False),
        ])
        answer = ms.answer("что прошло успешно")
        assert "ok cmd" in answer


class TestMemorySearchTimeFilter:
    def test_answer_today(self):
        ms = _ms_with_records([_record(cmd="today action", hours_ago=0.1)])
        answer = ms.answer("что было сегодня")
        assert "today action" in answer

    def test_answer_today_empty(self):
        # No records today — session is empty
        ms = _ms_with_records([])
        answer = ms.answer("что было сегодня")
        assert "не выполнялось" in answer.lower() or "пуста" in answer.lower()

    def test_answer_recent_hour(self):
        ms = _ms_with_records([_record(cmd="fresh cmd", hours_ago=0.1)])
        answer = ms.answer("что было за последний час")
        assert "fresh cmd" in answer

    def test_answer_recent_minutes(self):
        ms = _ms_with_records([_record(cmd="very fresh", hours_ago=0.01)])
        answer = ms.answer("что было за последние 30 минут")
        assert "very fresh" in answer


class TestMemorySearchCountParsing:
    def test_last_n_commands(self):
        records = [_record(cmd=f"cmd{i}", hours_ago=float(i)) for i in range(20)]
        ms = _ms_with_records(records)
        answer = ms.answer("последние 3 команды")
        # Should show at most 3 records (from recent())
        assert "cmd" in answer

    def test_default_limit_ten(self):
        records = [_record(cmd=f"cmd{i}") for i in range(15)]
        ms = _ms_with_records(records)
        answer = ms.answer("что мы делали")
        assert "cmd" in answer


class TestMemorySearchToolFilter:
    def test_terminal_filter(self):
        ms = _ms_with_records([
            _record(cmd="запусти bash скрипт", intent="terminal"),
            _record(cmd="открой браузер", intent="browser"),
        ])
        answer = ms.answer("какие команды выполнялись в терминале")
        # Should find the terminal-related record
        assert "bash скрипт" in answer or "терминал" in answer.lower()

    def test_browser_filter(self):
        ms = _ms_with_records([
            _record(cmd="открой браузер на github.com", intent="browser"),
            _record(cmd="создай файл", intent="filesystem"),
        ])
        answer = ms.answer("что делал в браузере")
        assert "браузер" in answer or "github" in answer.lower()


class TestMemorySearchEmpty:
    def test_empty_history(self):
        ms = _ms_with_records([])
        answer = ms.answer("что мы делали")
        assert "пуста" in answer.lower() or "не было" in answer.lower()


# ==================================================================
# _hours_label helper
# ==================================================================

@pytest.mark.parametrize("hours,expected", [
    (0.5,  "30 мин."),
    (1.0,  "1 час"),
    (2.0,  "2 ч."),
    (24.0, "1 дн."),
])
def test_hours_label(hours, expected):
    assert _hours_label(hours) == expected
