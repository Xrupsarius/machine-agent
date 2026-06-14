from html import escape

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel
from PySide6.QtCore import Signal

from app.core.event_bus import EventBus
from app.stt.dictation_controller import (
    EVENT_DICTATION_PARTIAL, EVENT_DICTATION_COMMITTED,
    EVENT_DICTATION_STARTED, EVENT_DICTATION_STOPPED,
    EVENT_DICTATION_COMMAND,
)

EVENT_DICTATION_TOGGLE = "dictation.toggle"


class DictationWidget(QWidget):
    _sig_partial = Signal(str, str)
    _sig_committed = Signal(str)
    _sig_running = Signal(bool)
    _sig_command = Signal(str)

    def __init__(self, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._finalized = ""
        self._committed = ""
        self._interim = ""
        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar_widget = QWidget()
        bar_widget.setFixedHeight(44)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(16, 6, 16, 6)
        self._header = QLabel("Диктовка")
        self._header.setStyleSheet("font-weight: bold;")
        self._button = QPushButton("Старт")
        self._button.setCheckable(True)
        self._button.clicked.connect(self._on_button)
        bar.addWidget(self._header)
        bar.addStretch()
        bar.addWidget(self._button)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("font-size: 14px; border: none;")

        layout.addWidget(bar_widget)
        layout.addWidget(self._text)

    def _subscribe_events(self) -> None:
        self._sig_partial.connect(self._apply_partial)
        self._sig_committed.connect(self._apply_committed)
        self._sig_running.connect(self._apply_running)
        self._sig_command.connect(self._apply_command)
        self._event_bus.subscribe(EVENT_DICTATION_PARTIAL, self._on_partial)
        self._event_bus.subscribe(EVENT_DICTATION_COMMITTED, self._on_committed)
        self._event_bus.subscribe(EVENT_DICTATION_COMMAND, self._on_command)
        self._event_bus.subscribe(EVENT_DICTATION_STARTED, lambda _: self._sig_running.emit(True))
        self._event_bus.subscribe(EVENT_DICTATION_STOPPED, lambda _: self._sig_running.emit(False))

    def _on_button(self) -> None:
        self._event_bus.publish(EVENT_DICTATION_TOGGLE, {})

    def _on_partial(self, data: dict) -> None:
        self._sig_partial.emit(data.get("committed", ""), data.get("interim", ""))

    def _on_committed(self, data: dict) -> None:
        self._sig_committed.emit(data.get("text", ""))

    def _on_command(self, data: dict) -> None:
        self._sig_command.emit(data.get("command", ""))

    def _apply_partial(self, committed: str, interim: str) -> None:
        self._committed = committed
        self._interim = interim
        self._render()

    def _apply_committed(self, text: str) -> None:
        if text:
            self._finalized = (self._finalized + " " + text).strip()
        self._committed = ""
        self._interim = ""
        self._render()

    def _apply_command(self, command: str) -> None:
        if command == "submit":
            self._finalized = (self._finalized + " ⏎").strip()
            self._committed = ""
            self._interim = ""
            self._render()

    def _apply_running(self, running: bool) -> None:
        self._button.setText("Стоп" if running else "Старт")
        self._button.setChecked(running)
        self._header.setText("🎙 Слушаю…" if running else "Диктовка")
        self._header.setStyleSheet(
            "font-weight: bold; color: #0EA5E9;" if running else "font-weight: bold;"
        )

    def _render(self) -> None:
        parts = []
        if self._finalized:
            parts.append(f'<span style="color:#111827">{escape(self._finalized)}</span>')
        if self._committed:
            parts.append(f'<span style="color:#111827">{escape(self._committed)}</span>')
        if self._interim:
            parts.append(f'<span style="color:#9CA3AF">{escape(self._interim)}</span>')
        self._text.setHtml(" ".join(parts))
        cursor = self._text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._text.setTextCursor(cursor)

    @property
    def display_text(self) -> str:
        return self._text.toPlainText()
