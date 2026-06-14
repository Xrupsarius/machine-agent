import pytest
from app.core.state_manager import AppState
from app.ui.status_widget import StatusWidget, STATUS_LABELS, STATUS_COLORS


@pytest.fixture
def widget(qapp):
    w = StatusWidget()
    return w


def test_initial_state_is_idle(widget):
    assert widget.current_state == AppState.IDLE


def test_initial_label_is_idle(widget):
    assert widget.current_label() == STATUS_LABELS[AppState.IDLE]


def test_set_state_updates_label(widget):
    widget.set_state(AppState.LISTENING)
    assert widget.current_label() == STATUS_LABELS[AppState.LISTENING]


def test_set_state_updates_state_property(widget):
    widget.set_state(AppState.THINKING)
    assert widget.current_state == AppState.THINKING


def test_all_states_have_labels():
    for state in AppState:
        assert state in STATUS_LABELS, f"Missing label for {state}"


def test_all_states_have_colors():
    for state in AppState:
        assert state in STATUS_COLORS, f"Missing color for {state}"


def test_cycle_through_all_states(widget):
    for state in AppState:
        widget.set_state(state)
        assert widget.current_state == state
        assert widget.current_label() == STATUS_LABELS[state]


def test_set_error_state(widget):
    widget.set_state(AppState.ERROR)
    assert widget.current_state == AppState.ERROR


def test_set_waiting_confirmation(widget):
    widget.set_state(AppState.WAITING_CONFIRMATION)
    assert widget.current_label() == STATUS_LABELS[AppState.WAITING_CONFIRMATION]
