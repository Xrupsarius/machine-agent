import logging

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy, QFrame
from PySide6.QtGui import QCloseEvent
from PySide6.QtCore import Qt, Signal

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState, EVENT_STATE_CHANGED
from app.ui.status_widget import StatusWidget
from app.ui.activity_log_widget import ActivityLogWidget, EVENT_ACTIVITY_LOG
from app.ui.dictation_widget import DictationWidget
from app.ui.chat_widget import ChatWidget

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    _sig_state = Signal(object)
    _sig_activity = Signal(str, str)

    def __init__(self, state_manager: StateManager, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._state_manager = state_manager
        self._event_bus = event_bus

        self._setup_ui()
        self._subscribe_events()
        log.info("MainWindow initialized")

    def _setup_ui(self) -> None:
        self.setWindowTitle("Machine Agent")
        self.setMinimumSize(680, 540)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._status_widget = StatusWidget()
        self._chat_widget = ChatWidget(self._event_bus)
        self._dictation_widget = DictationWidget(self._event_bus)
        for w in (self._chat_widget, self._dictation_widget):
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._activity_log = ActivityLogWidget()
        self._activity_log.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #D1D5DB;")

        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        split.addWidget(self._chat_widget, 1)
        split.addWidget(separator)
        split.addWidget(self._dictation_widget, 1)

        layout.addWidget(self._status_widget)
        layout.addLayout(split, 1)
        layout.addWidget(self._activity_log)

    def _subscribe_events(self) -> None:
        self._sig_state.connect(self._apply_state)
        self._sig_activity.connect(self._apply_activity)
        self._event_bus.subscribe(EVENT_STATE_CHANGED, self._on_state_changed)
        self._event_bus.subscribe(EVENT_ACTIVITY_LOG, self._on_activity_log)

    _STATE_LABELS = {
        AppState.IDLE: "Ожидание — жду wake word",
        AppState.LISTENING: "Слушаю команду…",
        AppState.THINKING: "Распознаю и анализирую…",
        AppState.PLANNING: "Составляю план…",
        AppState.EXECUTING: "Выполняю…",
        AppState.WAITING_CONFIRMATION: "Жду подтверждения",
        AppState.DICTATING: "Диктовка — говорите",
        AppState.ERROR: "Ошибка",
    }

    def _on_state_changed(self, data: dict) -> None:
        self._sig_state.emit(data["new"])

    def _on_activity_log(self, data: dict) -> None:
        self._sig_activity.emit(data.get("text", ""), data.get("level", "info"))

    def _apply_state(self, new_state: AppState) -> None:
        self._status_widget.set_state(new_state)
        label = self._STATE_LABELS.get(new_state, new_state.value)
        self._activity_log.add_entry(f"Статус: {label}")

    def _apply_activity(self, text: str, level: str) -> None:
        self._activity_log.add_entry(text, level)

    def closeEvent(self, event: QCloseEvent) -> None:
        # ADR-019: close hides the window, process stays alive
        event.ignore()
        self.hide()
        log.info("Window hidden — use tray to quit")

    @property
    def status_widget(self) -> StatusWidget:
        return self._status_widget

    @property
    def activity_log(self) -> ActivityLogWidget:
        return self._activity_log

    @property
    def dictation_widget(self) -> DictationWidget:
        return self._dictation_widget

    @property
    def chat_widget(self) -> ChatWidget:
        return self._chat_widget
