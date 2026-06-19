from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from app.core.ptt_config import is_modifier

_SPECIAL = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Return: "Return",
    Qt.Key.Key_Enter: "KP_Enter",
    Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Insert: "Insert",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End",
    Qt.Key.Key_PageUp: "Prior",
    Qt.Key.Key_PageDown: "Next",
    Qt.Key.Key_Print: "Print",
    Qt.Key.Key_Menu: "Menu",
    Qt.Key.Key_Pause: "Pause",
    Qt.Key.Key_ScrollLock: "Scroll_Lock",
    Qt.Key.Key_CapsLock: "Caps_Lock",
    Qt.Key.Key_Backspace: "BackSpace",
    Qt.Key.Key_Escape: "Escape",
}

_MODIFIERS = {
    Qt.Key.Key_Alt: "Alt_L",
    Qt.Key.Key_Control: "Control_L",
    Qt.Key.Key_Shift: "Shift_L",
    Qt.Key.Key_Meta: "Super_L",
    Qt.Key.Key_Super_L: "Super_L",
    Qt.Key.Key_Super_R: "Super_R",
}

for _i in range(1, 25):
    _k = getattr(Qt.Key, f"Key_F{_i}", None)
    if _k is not None:
        _SPECIAL[_k] = f"F{_i}"


def qt_key_to_keysym(key: int, text: str = "") -> tuple[str | None, str, str]:
    """Map a Qt key code to (hyprland_keysym, display_name, caveat).

    keysym is None for keys we can't bind. caveat is a human warning ("" if none).
    """
    qk = Qt.Key(key) if not isinstance(key, Qt.Key) else key

    if qk in _MODIFIERS:
        keysym = _MODIFIERS[qk]
        return keysym, keysym, "модификатор — на Hyprland не отдаёт отпускание, ненадёжно"

    if qk in _SPECIAL:
        keysym = _SPECIAL[qk]
        caveat = "пробел будет печататься при наборе" if keysym == "space" else ""
        return keysym, keysym, caveat

    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        ch = chr(int(key)).lower()
        return ch, ch.upper(), "буква будет печататься при наборе текста"

    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        ch = chr(int(key))
        return ch, ch, "цифра будет печататься при наборе текста"

    display = QKeySequence(key).toString() or text
    return None, (display or "?"), "эту клавишу нельзя назначить"


class KeyCaptureDialog(QDialog):
    """Asks the user to press a key; remembers it as the push-to-talk key."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Клавиша рации")
        self.setMinimumWidth(360)
        self.keysym: str | None = None
        self.label_text: str = ""
        self.reset_requested: bool = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._prompt = QLabel("Нажмите клавишу, которая будет работать как рация…")
        self._prompt.setWordWrap(True)
        self._prompt.setStyleSheet("font-size: 14px;")
        self._caveat = QLabel("")
        self._caveat.setWordWrap(True)
        self._caveat.setStyleSheet("color: #B45309;")

        buttons = QHBoxLayout()
        self._apply = QPushButton("Применить")
        self._apply.setEnabled(False)
        self._apply.clicked.connect(self.accept)
        self._reset = QPushButton("Сбросить")
        self._reset.clicked.connect(self._on_reset)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(self._reset)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self._apply)

        layout.addWidget(self._prompt)
        layout.addWidget(self._caveat)
        layout.addLayout(buttons)

    def _on_reset(self) -> None:
        self.reset_requested = True
        self.accept()

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        keysym, display, caveat = qt_key_to_keysym(event.key(), event.text())
        self.label_text = display
        if keysym is None:
            self._prompt.setText(f"«{display}» — нельзя назначить, нажмите другую")
            self._caveat.setText(caveat)
            self._apply.setEnabled(False)
            self.keysym = None
            return
        self.keysym = keysym
        self._prompt.setText(f"Клавиша рации: {display}")
        self._caveat.setText(("⚠ " + caveat) if caveat else "")
        self._apply.setEnabled(True)
