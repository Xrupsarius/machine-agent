import pytest
from unittest.mock import MagicMock, patch
from app.memory.session_memory import SessionMemory
from app.memory.long_term_memory import LongTermMemory
from app.memory.memory_service import MemoryService, EVENT_MEMORY_SAVED
from app.core.event_bus import EventBus
from app.tools.base_tool import ToolResult


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def service(tmp_path, bus):
    session = SessionMemory(limit=200)
    ltm = LongTermMemory(db_path=str(tmp_path / "test.db"))
    return MemoryService(session, ltm, bus)


def _results(output: str = "ok", success: bool = True) -> list[ToolResult]:
    return [ToolResult(success=success, output=output, tool_name="terminal", action="execute")]


# --- save ---

def test_save_increments_session_count(service):
    service.save("cmd", "intent", {}, _results(), True)
    assert service.session_count() == 1


def test_save_increments_total_count(service):
    service.save("cmd", "intent", {}, _results(), True)
    assert service.total_count() == 1


def test_save_stores_user_command(service):
    service.save("открой браузер", "open_browser", {}, _results(), True)
    records = service.recent()
    assert records[-1]["user_command"] == "открой браузер"


def test_save_stores_intent(service):
    service.save("cmd", "create_file", {}, _results(), True)
    records = service.recent()
    assert records[-1]["intent"] == "create_file"


def test_save_stores_success_flag(service):
    service.save("cmd", "intent", {}, _results(success=False), False)
    records = service.recent()
    # SQLite stores 0/1
    assert not records[-1]["success"]


def test_save_stores_result_output(service):
    service.save("cmd", "intent", {}, _results(output="created file"), True)
    records = service.recent()
    assert records[-1]["result"] == "created file"


def test_save_publishes_event(service, bus):
    received = []
    bus.subscribe(EVENT_MEMORY_SAVED, received.append)
    service.save("cmd", "intent", {}, _results(), True)
    assert len(received) == 1
    assert received[0]["user_command"] == "cmd"


def test_save_with_dict_results(service):
    results = [{"success": True, "output": "done", "error": "", "tool_name": "t", "action": "a"}]
    service.save("cmd", "intent", {}, results, True)
    assert service.session_count() == 1


def test_save_empty_results(service):
    service.save("cmd", "intent", {}, [], True)
    assert service.session_count() == 1


def test_save_with_error(service):
    service.save("cmd", "intent", {}, _results(success=False), False, error="timeout")
    records = service.recent()
    assert records[-1]["error"] == "timeout"


# --- search ---

def test_search_finds_in_session(service):
    service.save("открой браузер", "open_browser", {}, _results(), True)
    results = service.search("браузер")
    assert len(results) == 1
    assert results[0]["user_command"] == "открой браузер"


def test_search_finds_by_intent(service):
    service.save("cmd", "create_file", {}, _results(), True)
    results = service.search("create_file")
    assert len(results) >= 1


def test_search_no_match(service):
    service.save("something", "intent", {}, _results(), True)
    results = service.search("xyz_not_found_xyz")
    assert results == []


def test_search_session_priority(service, tmp_path, bus):
    # Manually add to LTM only (not in session)
    session = SessionMemory()
    ltm = LongTermMemory(db_path=str(tmp_path / "prio.db"))
    svc = MemoryService(session, ltm, bus)

    from datetime import datetime, timezone
    import json
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_command": "only_in_ltm",
        "intent": "test",
        "plan": "{}",
        "executed_actions": "[]",
        "result": "ok",
        "success": True,
        "error": "",
    }
    ltm.add(record)

    # Session is empty, so LTM should be searched
    results = svc.search("only_in_ltm")
    assert len(results) == 1


# --- recent ---

def test_recent_returns_records(service):
    service.save("cmd1", "i1", {}, _results(), True)
    service.save("cmd2", "i2", {}, _results(), True)
    result = service.recent(10)
    assert len(result) == 2


def test_recent_limit(service):
    for i in range(10):
        service.save(f"cmd{i}", "intent", {}, _results(), True)
    result = service.recent(3)
    assert len(result) == 3


# --- counts ---

def test_session_count_reflects_saves(service):
    service.save("a", "i", {}, [], True)
    service.save("b", "i", {}, [], True)
    assert service.session_count() == 2


def test_total_count_reflects_saves(service):
    service.save("a", "i", {}, [], True)
    service.save("b", "i", {}, [], True)
    assert service.total_count() == 2
