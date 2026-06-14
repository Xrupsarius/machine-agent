import logging
from enum import Enum

from app.core.event_bus import EventBus

log = logging.getLogger(__name__)

EVENT_STATE_CHANGED = "state.changed"


class AppState(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    ERROR = "ERROR"


class StateManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._state = AppState.IDLE
        self._event_bus = event_bus

    @property
    def state(self) -> AppState:
        return self._state

    def set_state(self, new_state: AppState) -> None:
        if new_state == self._state:
            return
        old_state = self._state
        self._state = new_state
        log.info(f"State: {old_state.value} → {new_state.value}")
        self._event_bus.publish(EVENT_STATE_CHANGED, {"old": old_state, "new": new_state})

    def is_state(self, state: AppState) -> bool:
        return self._state == state
