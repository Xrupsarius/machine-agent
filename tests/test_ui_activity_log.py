import pytest
from app.ui.activity_log_widget import ActivityLogWidget


@pytest.fixture
def widget(qapp):
    return ActivityLogWidget()


def test_initially_empty(widget):
    assert widget.count() == 0


def test_add_entry_increases_count(widget):
    widget.add_entry("Test message")
    assert widget.count() == 1


def test_add_entry_text_contains_message(widget):
    widget.add_entry("Hello world")
    assert "Hello world" in widget.entry_text(0)


def test_add_entry_includes_timestamp(widget):
    widget.add_entry("msg")
    text = widget.entry_text(0)
    assert "[" in text and "]" in text


def test_clear_resets_count(widget):
    widget.add_entry("a")
    widget.add_entry("b")
    widget.clear()
    assert widget.count() == 0


def test_max_entries_not_exceeded(widget):
    for i in range(ActivityLogWidget.MAX_ENTRIES + 10):
        widget.add_entry(f"entry {i}")
    assert widget.count() == ActivityLogWidget.MAX_ENTRIES


def test_oldest_entry_dropped_when_full(widget):
    widget.clear()
    for i in range(ActivityLogWidget.MAX_ENTRIES):
        widget.add_entry(f"entry {i}")
    widget.add_entry("new entry")
    assert "entry 0" not in widget.entry_text(0)
    assert "new entry" in widget.entry_text(widget.count() - 1)


def test_multiple_entries_ordered(widget):
    widget.clear()
    widget.add_entry("first")
    widget.add_entry("second")
    assert "first" in widget.entry_text(0)
    assert "second" in widget.entry_text(1)
