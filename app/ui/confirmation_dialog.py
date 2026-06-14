from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Qt


class ConfirmationDialog(QDialog):
    """
    Modal dialog shown when SecurityValidator requires confirmation.
    ADR-013: dangerous commands cannot execute without user approval.
    """

    def __init__(self, reason: str, plan: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Требуется подтверждение")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Warning header
        header = QLabel("⚠  Опасная операция")
        header.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Reason
        reason_label = QLabel(reason)
        reason_label.setWordWrap(True)
        layout.addWidget(reason_label)

        # Plan steps
        steps = plan.get("steps", [])
        if steps:
            layout.addWidget(QLabel("Шаги плана:"))
            details = QPlainTextEdit()
            details.setReadOnly(True)
            details.setMaximumHeight(120)
            lines = []
            for i, step in enumerate(steps, 1):
                cmd = step.get("parameters", {}).get("command", "")
                suffix = f": {cmd}" if cmd else ""
                lines.append(
                    f"{i}. [{step.get('tool', '?')}] {step.get('action', '?')}{suffix}"
                )
            details.setPlainText("\n".join(lines))
            layout.addWidget(details)

        # Divider label
        note = QLabel("Вы уверены, что хотите выполнить это действие?")
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_cancel = QPushButton("Отмена")
        self._btn_cancel.setStyleSheet("padding: 7px 22px;")
        self._btn_confirm = QPushButton("Подтвердить")
        self._btn_confirm.setStyleSheet(
            "background: #e74c3c; color: white; padding: 7px 22px; font-weight: bold;"
        )
        btn_layout.addWidget(self._btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_confirm)
        layout.addLayout(btn_layout)

        self._btn_confirm.clicked.connect(self.accept)
        self._btn_cancel.clicked.connect(self.reject)

    # Public accessors for testing
    def confirm_button(self) -> QPushButton:
        return self._btn_confirm

    def cancel_button(self) -> QPushButton:
        return self._btn_cancel
