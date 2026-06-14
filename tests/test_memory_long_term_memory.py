import pytest
from app.memory.long_term_memory import LongTermMemory


@pytest.fixture
def ltm(tmp_path):
    return LongTermMemory(db_path=str(tmp_path / "test.db"))


def _record(**kw) -> dict:
    base = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "user_command": "test command",
        "intent": "test_intent",
        "plan": '{"steps":[]}',
        "executed_actions": "[]",
        "result": "ok",
        "success": True,
        "error": "",
    }
    base.update(kw)
    return base


# --- availability ---

def test_available_after_init(ltm):
    assert ltm.is_available


def test_unavailable_on_bad_path():
    ltm = LongTermMemory(db_path="/root/no_permission/x/y/z.db")
    assert not ltm.is_available


# --- add ---

def test_add_returns_id(ltm):
    row_id = ltm.add(_record())
    assert row_id == 1


def test_add_increments_id(ltm):
    id1 = ltm.add(_record())
    id2 = ltm.add(_record())
    assert id2 == id1 + 1


def test_add_increases_count(ltm):
    ltm.add(_record())
    assert ltm.count() == 1


def test_add_multiple(ltm):
    for _ in range(5):
        ltm.add(_record())
    assert ltm.count() == 5


def test_add_returns_none_when_unavailable(tmp_path):
    ltm = LongTermMemory(db_path="/root/no_permission/x.db")
    result = ltm.add(_record())
    assert result is None


# --- recent ---

def test_recent_returns_records(ltm):
    ltm.add(_record(user_command="cmd1"))
    ltm.add(_record(user_command="cmd2"))
    result = ltm.recent(10)
    assert len(result) == 2


def test_recent_ordered_oldest_first(ltm):
    ltm.add(_record(user_command="first"))
    ltm.add(_record(user_command="second"))
    result = ltm.recent(10)
    assert result[0]["user_command"] == "first"
    assert result[1]["user_command"] == "second"


def test_recent_respects_limit(ltm):
    for i in range(10):
        ltm.add(_record(user_command=f"cmd{i}"))
    result = ltm.recent(3)
    assert len(result) == 3


def test_recent_empty(ltm):
    assert ltm.recent() == []


def test_recent_returns_empty_when_unavailable(tmp_path):
    ltm = LongTermMemory(db_path="/root/no_permission/x.db")
    assert ltm.recent() == []


# --- search ---

def test_search_finds_by_user_command(ltm):
    ltm.add(_record(user_command="открой браузер"))
    ltm.add(_record(user_command="создай файл"))
    result = ltm.search("браузер")
    assert len(result) == 1
    assert result[0]["user_command"] == "открой браузер"


def test_search_finds_by_intent(ltm):
    ltm.add(_record(intent="open_browser"))
    ltm.add(_record(intent="create_file"))
    result = ltm.search("open_browser")
    assert len(result) == 1


def test_search_finds_by_result(ltm):
    ltm.add(_record(result="file created at /tmp/x.txt"))
    result = ltm.search("/tmp/x.txt")
    assert len(result) == 1


def test_search_case_insensitive(ltm):
    ltm.add(_record(user_command="Открой БРАУЗЕР"))
    result = ltm.search("браузер")
    assert len(result) == 1


def test_search_no_match(ltm):
    ltm.add(_record(user_command="something"))
    result = ltm.search("xyz_not_found")
    assert result == []


def test_search_returns_empty_when_unavailable(tmp_path):
    ltm = LongTermMemory(db_path="/root/no_permission/x.db")
    assert ltm.search("anything") == []


# --- count ---

def test_count_zero_initially(ltm):
    assert ltm.count() == 0


def test_count_after_adds(ltm):
    ltm.add(_record())
    ltm.add(_record())
    assert ltm.count() == 2


def test_count_zero_when_unavailable(tmp_path):
    ltm = LongTermMemory(db_path="/root/no_permission/x.db")
    assert ltm.count() == 0


# --- persistence ---

def test_persists_across_instances(tmp_path):
    db = str(tmp_path / "persist.db")
    ltm1 = LongTermMemory(db_path=db)
    ltm1.add(_record(user_command="remembered"))

    ltm2 = LongTermMemory(db_path=db)
    result = ltm2.recent()
    assert any(r["user_command"] == "remembered" for r in result)
