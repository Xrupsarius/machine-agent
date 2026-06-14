from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PySide6.QtGui import QColor

EVENT_ACTIVITY_LOG = "activity.log"

_LEVEL_COLORS = {
    "error":   "#EF4444",
    "warning": "#F97316",
    "success": "#10B981",
}


class ActivityLogWidget(QWidget):
    MAX_ENTRIES = 200

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("История действий")
        header.setStyleSheet("font-weight: bold; padding: 6px 16px; background: #F3F4F6;")

        self._list = QListWidget()
        self._list.setStyleSheet("font-size: 12px; border: none;")
        self._list.setAlternatingRowColors(True)

        layout.addWidget(header)
        layout.addWidget(self._list)

    def add_entry(self, text: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{ts}]  {text}")

        if level in _LEVEL_COLORS:
            item.setForeground(QColor(_LEVEL_COLORS[level]))

        if self._list.count() >= self.MAX_ENTRIES:
            self._list.takeItem(0)

        self._list.addItem(item)
        self._list.scrollToBottom()

    def clear(self) -> None:
        self._list.clear()

    def count(self) -> int:
        return self._list.count()

    def entry_text(self, index: int) -> str:
        item = self._list.item(index)
        return item.text() if item else ""
