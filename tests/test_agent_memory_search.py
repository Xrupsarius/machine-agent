import pytest
from app.agent.memory_search import MemorySearch, EVENT_HISTORY_ANSWERED
from app.memory.session_memory import SessionMemory
from app.memory.long_term_memory import LongTermMemory
from app.memory.memory_service import MemoryService
from app.core.event_bus import EventBus
from app.tools.base_tool import ToolResult


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def svc(tmp_path, bus):
    session = SessionMemory()
    ltm = LongTermMemory(db_path=str(tmp_path / "test.db"))
    return MemoryService(session, ltm, bus)


@pytest.fixture
def ms(svc):
    return MemorySearch(svc)


def _save(svc, cmd, intent="test", success=True, result="ok"):
    svc.save(
        user_command=cmd,
        intent=intent,
        plan={},
        results=[ToolResult(success=success, output=result, tool_name="t", action="a")],
        success=success,
    )


# --- is_history_query ---

@pytest.mark.parametrize("text", [
    "что мы делали",
    "Что мы делали?",
    "что было в терминале",
    "какие команды запускались",
    "какие файлы создавались",
    "какие приложения запускались",
    "какие программы открывались",
    "когда открывался браузер",
    "покажи историю",
    "вспомни что делали",
    "история действий",
    "покажи лог",
    "что я делал",
    "что происходило",
    "что открывал",
    "что создавал",
    "журнал",
])
def test_is_history_query_true(ms, text):
    assert ms.is_history_query(text)


@pytest.mark.parametrize("text", [
    "открой браузер",
    "создай файл test.txt",
    "запусти терминал",
    "выключи компьютер",
    "привет",
    "echo hello",
])
def test_is_history_query_false(ms, text):
    assert not ms.is_history_query(text)


def test_is_history_query_case_insensitive(ms):
    assert ms.is_history_query("ЧТО МЫ ДЕЛАЛИ?")
    assert ms.is_history_query("ИСТОРИЯ")


# --- answer: empty memory ---

def test_answer_empty_memory(ms):
    result = ms.answer("что мы делали?")
    assert "пуста" in result.lower() or "не было" in result.lower()


# --- answer: general recent ---

def test_answer_returns_recent_records(ms, svc):
    _save(svc, "открой браузер", intent="open_browser", result="Opened firefox")
    _save(svc, "создай файл", intent="create_file", result="Created /tmp/f.txt")
    result = ms.answer("что мы делали?")
    assert "открой браузер" in result
    assert "создай файл" in result


def test_answer_includes_success_marker(ms, svc):
    _save(svc, "echo hi", success=True)
    result = ms.answer("что делали?")
    assert "✓" in result


def test_answer_includes_failure_marker(ms, svc):
    _save(svc, "bad command", success=False)
    result = ms.answer("что делали?")
    assert "✗" in result


def test_answer_includes_timestamp(ms, svc):
    _save(svc, "команда")
    result = ms.answer("история")
    assert "202" in result  # year prefix


def test_answer_includes_result(ms, svc):
    _save(svc, "echo hello", result="hello world")
    result = ms.answer("что делали?")
    assert "hello world" in result


# --- answer: tool-specific filtering ---

def test_answer_terminal_filter(ms, svc):
    _save(svc, "открой браузер", intent="open_browser")
    _save(svc, "запусти ls", intent="terminal", result="file1.txt")
    result = ms.answer("что было в терминале?")
    assert "запусти ls" in result


def test_answer_filesystem_filter(ms, svc):
    _save(svc, "открой браузер", intent="open_browser")
    _save(svc, "создай файл notes.txt", intent="filesystem")
    result = ms.answer("какие файлы создавались?")
    assert "создай файл" in result


def test_answer_browser_filter(ms, svc):
    _save(svc, "создай файл", intent="filesystem")
    _save(svc, "открой сайт google.com", intent="browser")
    result = ms.answer("когда открывался браузер?")
    assert "google.com" in result


def test_answer_desktop_filter(ms, svc):
    _save(svc, "создай файл", intent="filesystem")
    _save(svc, "открой приложение gedit", intent="desktop")
    result = ms.answer("какие приложения запускались?")
    assert "gedit" in result


# --- answer: max 10 records shown ---

def test_answer_limits_to_10_records(ms, svc):
    for i in range(15):
        _save(svc, f"cmd{i}")
    result = ms.answer("что делали?")
    # Should show up to 10 records
    count = result.count("✓") + result.count("✗")
    assert count <= 10


# --- event constant ---

def test_event_constant_defined():
    assert isinstance(EVENT_HISTORY_ANSWERED, str)
    assert len(EVENT_HISTORY_ANSWERED) > 0
