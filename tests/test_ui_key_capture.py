import pytest
from PySide6.QtCore import Qt

from app.ui.key_capture_dialog import qt_key_to_keysym


@pytest.fixture(scope="module")
def _qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app


def test_function_key_maps_cleanly(_qapp):
    keysym, display, caveat = qt_key_to_keysym(Qt.Key.Key_F8)
    assert keysym == "F8"
    assert display == "F8"
    assert caveat == ""


def test_letter_maps_lowercase_with_caveat(_qapp):
    keysym, display, caveat = qt_key_to_keysym(Qt.Key.Key_G)
    assert keysym == "g"
    assert display == "G"
    assert "печат" in caveat


def test_modifier_flagged_unreliable(_qapp):
    keysym, display, caveat = qt_key_to_keysym(Qt.Key.Key_Alt)
    assert keysym == "Alt_L"
    assert "отпуск" in caveat


def test_special_key_insert(_qapp):
    keysym, _, caveat = qt_key_to_keysym(Qt.Key.Key_Insert)
    assert keysym == "Insert"
    assert caveat == ""


def test_digit_maps_with_caveat(_qapp):
    keysym, display, caveat = qt_key_to_keysym(Qt.Key.Key_5)
    assert keysym == "5"
    assert display == "5"
    assert caveat
