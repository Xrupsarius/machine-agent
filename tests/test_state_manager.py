import pytest
from app.core.event_bus import EventBus
from app.core.state_manager import AppState, StateManager, EVENT_STATE_CHANGED


def make_manager():
    return StateManager(EventBus())


def test_initial_state_is_idle():
    sm = make_manager()
    assert sm.state == AppState.IDLE


def test_set_state_changes_state():
    sm = make_manager()
    sm.set_state(AppState.LISTENING)
    assert sm.state == AppState.LISTENING


def test_state_change_publishes_event():
    bus = EventBus()
    sm = StateManager(bus)
    events = []
    bus.subscribe(EVENT_STATE_CHANGED, lambda d: events.append(d))
    sm.set_state(AppState.THINKING)
    assert len(events) == 1
    assert events[0]["old"] == AppState.IDLE
    assert events[0]["new"] == AppState.THINKING


def test_same_state_no_event():
    bus = EventBus()
    sm = StateManager(bus)
    events = []
    bus.subscribe(EVENT_STATE_CHANGED, lambda d: events.append(d))
    sm.set_state(AppState.IDLE)
    assert events == []


def test_is_state():
    sm = make_manager()
    assert sm.is_state(AppState.IDLE)
    sm.set_state(AppState.ERROR)
    assert sm.is_state(AppState.ERROR)
    assert not sm.is_state(AppState.IDLE)


def test_all_states_reachable():
    sm = make_manager()
    for state in AppState:
        sm.set_state(state)
        assert sm.state == state
