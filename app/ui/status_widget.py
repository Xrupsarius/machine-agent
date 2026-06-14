from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame

from app.core.state_manager import AppState

STATUS_COLORS = {
    AppState.IDLE:                  "#6B7280",
    AppState.LISTENING:             "#3B82F6",
    AppState.THINKING:              "#F59E0B",
    AppState.PLANNING:              "#8B5CF6",
    AppState.EXECUTING:             "#10B981",
    AppState.WAITING_CONFIRMATION:  "#F97316",
    AppState.ERROR:                 "#EF4444",
}

STATUS_LABELS = {
    AppState.IDLE:                  "Ожидание",
    AppState.LISTENING:             "Слушаю...",
    AppState.THINKING:              "Думаю...",
    AppState.PLANNING:              "Планирую...",
    AppState.EXECUTING:             "Выполняю...",
    AppState.WAITING_CONFIRMATION:  "Требуется подтверждение",
    AppState.ERROR:                 "Ошибка",
}


class StatusWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.set_state(AppState.IDLE)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self._indicator = QFrame()
        self._indicator.setFixedSize(14, 14)

        self._label = QLabel()
        self._label.setStyleSheet("font-size: 14px; font-weight: bold;")

        layout.addWidget(self._indicator)
        layout.addSpacing(8)
        layout.addWidget(self._label)
        layout.addStretch()

    def set_state(self, state: AppState) -> None:
        color = STATUS_COLORS.get(state, "#6B7280")
        self._indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 7px;"
        )
        self._label.setText(STATUS_LABELS.get(state, state.value))
        self._label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {color};"
        )
        self._current_state = state

    @property
    def current_state(self) -> AppState:
        return self._current_state

    def current_label(self) -> str:
        return self._label.text()
