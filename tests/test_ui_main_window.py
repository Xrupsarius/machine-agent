import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QCloseEvent

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState, EVENT_STATE_CHANGED
from app.ui.activity_log_widget import EVENT_ACTIVITY_LOG
from app.ui.main_window import MainWindow


@pytest.fixture
def core(qapp):
    bus = EventBus()
    sm = StateManager(bus)
    return bus, sm


@pytest.fixture
def window(qapp, core):
    bus, sm = core
    w = MainWindow(sm, bus)
    return w, bus, sm


def test_window_title(window):
    w, _, _ = window
    assert w.windowTitle() == "Machine Agent"


def test_close_hides_not_destroys(window):
    w, _, _ = window
    w.show()
    assert w.isVisible()
    event = QCloseEvent()
    w.closeEvent(event)
    assert event.isAccepted() is False
    assert not w.isVisible()


def test_state_change_updates_status_widget(window):
    w, bus, sm = window
    sm.set_state(AppState.LISTENING)
    assert w.status_widget.current_state == AppState.LISTENING


def test_state_change_adds_activity_log_entry(window):
    w, bus, sm = window
    w.activity_log.clear()
    sm.set_state(AppState.THINKING)
    assert w.activity_log.count() > 0
    assert "Распознаю" in w.activity_log.entry_text(0)


def test_activity_log_event(window):
    w, bus, _ = window
    w.activity_log.clear()
    bus.publish(EVENT_ACTIVITY_LOG, {"text": "Custom log entry", "level": "info"})
    assert w.activity_log.count() == 1
    assert "Custom log entry" in w.activity_log.entry_text(0)


def test_all_states_update_status_widget(window):
    w, bus, sm = window
    for state in AppState:
        sm.set_state(state)
        assert w.status_widget.current_state == state


def test_minimum_size(window):
    w, _, _ = window
    assert w.minimumWidth() >= 400
    assert w.minimumHeight() >= 500
