from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt


class LanguageDialog(QDialog):
    """First-run dialog: pick the language the assistant listens in."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Language / Язык")
        self.setModal(True)
        self._choice = "ru"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        label = QLabel("На каком языке мне работать?\nWhich language should I work in?")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)

        buttons = QHBoxLayout()
        ru = QPushButton("🇷🇺 Русский")
        en = QPushButton("🇬🇧 English")
        for b in (ru, en):
            b.setMinimumHeight(40)
            b.setStyleSheet("font-size: 14px; font-weight: bold;")
        ru.clicked.connect(lambda: self._pick("ru"))
        en.clicked.connect(lambda: self._pick("en"))
        buttons.addWidget(ru)
        buttons.addWidget(en)
        layout.addLayout(buttons)

    def _pick(self, lang: str) -> None:
        self._choice = lang
        self.accept()

    @property
    def choice(self) -> str:
        return self._choice

    @staticmethod
    def choose() -> str:
        dialog = LanguageDialog()
        dialog.exec()
        return dialog.choice
