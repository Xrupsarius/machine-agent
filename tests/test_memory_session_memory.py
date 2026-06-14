import pytest
from app.memory.session_memory import SessionMemory


@pytest.fixture
def mem():
    return SessionMemory(limit=5)


# --- add / count ---

def test_empty_initially(mem):
    assert mem.count() == 0


def test_add_increases_count(mem):
    mem.add({"x": 1})
    assert mem.count() == 1


def test_add_multiple(mem):
    for i in range(3):
        mem.add({"i": i})
    assert mem.count() == 3


# --- limit eviction ---

def test_evicts_oldest_when_full(mem):
    for i in range(6):
        mem.add({"i": i})
    assert mem.count() == 5
    records = mem.all()
    assert records[0]["i"] == 1   # oldest evicted: 0
    assert records[-1]["i"] == 5


def test_limit_property(mem):
    assert mem.limit == 5


# --- all ---

def test_all_returns_list(mem):
    mem.add({"a": 1})
    result = mem.all()
    assert isinstance(result, list)
    assert result[0]["a"] == 1


def test_all_is_copy(mem):
    mem.add({"a": 1})
    result = mem.all()
    result.append({"injected": True})
    assert mem.count() == 1


# --- recent ---

def test_recent_returns_last_n(mem):
    for i in range(5):
        mem.add({"i": i})
    result = mem.recent(3)
    assert len(result) == 3
    assert result[-1]["i"] == 4


def test_recent_when_fewer_than_limit(mem):
    mem.add({"a": 1})
    result = mem.recent(10)
    assert len(result) == 1


def test_recent_empty(mem):
    assert mem.recent(5) == []


# --- clear ---

def test_clear_resets_count(mem):
    mem.add({"x": 1})
    mem.clear()
    assert mem.count() == 0


def test_clear_all_returns_empty(mem):
    mem.add({"x": 1})
    mem.clear()
    assert mem.all() == []


# --- thread safety (smoke) ---

def test_concurrent_writes():
    import threading
    m = SessionMemory(limit=1000)
    threads = [
        threading.Thread(target=lambda: m.add({"t": i}))
        for i in range(100)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert m.count() == 100
