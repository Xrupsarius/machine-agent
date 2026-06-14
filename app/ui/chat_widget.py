from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer

from app.core.event_bus import EventBus

EVENT_CHAT_MESSAGE = "chat.message"  # {"role": "user"|"assistant", "text": str}

_STYLE = {
    "user": {"name": "Вы", "bg": "#2563EB", "fg": "#FFFFFF"},
    "assistant": {"name": "Omnis", "bg": "#EEF2F7", "fg": "#111827"},
}
_BUBBLE_MAX_WIDTH = 300


class ChatWidget(QWidget):
    """Conversation panel with chat bubbles for chat-mode replies."""

    _sig_message = Signal(str, str)

    def __init__(self, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._messages: list[str] = []
        self._setup_ui()
        self._sig_message.connect(self._append)
        self._event_bus.subscribe(EVENT_CHAT_MESSAGE, self._on_message)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(44)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 6, 16, 6)
        title = QLabel("Чат")
        title.setStyleSheet("font-weight: bold;")
        bar_layout.addWidget(title)
        bar_layout.addStretch()
        outer.addWidget(bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self._vbox = QVBoxLayout(container)
        self._vbox.setContentsMargins(12, 8, 12, 8)
        self._vbox.setSpacing(10)
        self._vbox.addStretch()
        self._scroll.setWidget(container)
        outer.addWidget(self._scroll)

    def _on_message(self, data: dict) -> None:
        self._sig_message.emit(data.get("role", "assistant"), data.get("text", ""))

    def _append(self, role: str, text: str) -> None:
        if not text:
            return
        style = _STYLE.get(role, _STYLE["assistant"])
        self._messages.append(f"{style['name']}: {text}")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        column = QVBoxLayout()
        column.setSpacing(2)
        name = QLabel(style["name"])
        name.setStyleSheet("color: #9CA3AF; font-size: 10px;")
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(_BUBBLE_MAX_WIDTH)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setStyleSheet(
            f"background: {style['bg']}; color: {style['fg']}; "
            "border-radius: 12px; padding: 8px 12px; font-size: 14px;"
        )
        column.addWidget(name)
        column.addWidget(bubble)

        if role == "user":
            name.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addStretch()
            row.addLayout(column)
        else:
            name.setAlignment(Qt.AlignmentFlag.AlignLeft)
            row.addLayout(column)
            row.addStretch()

        holder = QWidget()
        holder.setLayout(row)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._vbox.insertWidget(self._vbox.count() - 1, holder)

        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    @property
    def display_text(self) -> str:
        return "\n".join(self._messages)
