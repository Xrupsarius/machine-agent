from html import escape

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import Signal

from app.core.event_bus import EventBus

EVENT_CHAT_MESSAGE = "chat.message"  # {"role": "user"|"assistant", "text": str}

_ROLE_STYLE = {
    "user": ("Вы", "#2563EB"),
    "assistant": ("🤖 Собеседник", "#059669"),
}


class ChatWidget(QWidget):
    """Conversation panel for chat-mode replies (when input is not a command)."""

    _sig_message = Signal(str, str)

    def __init__(self, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._setup_ui()
        self._sig_message.connect(self._append)
        self._event_bus.subscribe(EVENT_CHAT_MESSAGE, self._on_message)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar_widget = QWidget()
        bar_widget.setFixedHeight(44)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(16, 6, 16, 6)
        header = QLabel("Чат")
        header.setStyleSheet("font-weight: bold;")
        bar.addWidget(header)
        bar.addStretch()

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("font-size: 14px; border: none;")

        layout.addWidget(bar_widget)
        layout.addWidget(self._text)

    def _on_message(self, data: dict) -> None:
        self._sig_message.emit(data.get("role", "assistant"), data.get("text", ""))

    def _append(self, role: str, text: str) -> None:
        if not text:
            return
        label, color = _ROLE_STYLE.get(role, _ROLE_STYLE["assistant"])
        self._text.append(
            f'<p style="margin:4px 0"><b style="color:{color}">{label}:</b> '
            f'<span style="color:#111827">{escape(text)}</span></p>'
        )
        cursor = self._text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._text.setTextCursor(cursor)

    @property
    def display_text(self) -> str:
        return self._text.toPlainText()
