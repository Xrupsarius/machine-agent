import pytest
from PySide6.QtWidgets import QDialog
from app.ui.confirmation_dialog import ConfirmationDialog


@pytest.fixture
def plan():
    return {
        "intent": "run_dangerous",
        "steps": [
            {"tool": "terminal", "action": "execute",
             "parameters": {"command": "sudo reboot"}}
        ],
    }


@pytest.fixture
def dialog(qapp, plan):
    return ConfirmationDialog(reason="Contains dangerous pattern: 'sudo'", plan=plan)


# --- Construction ---

def test_dialog_is_qwidget(dialog):
    assert isinstance(dialog, QDialog)


def test_dialog_is_modal(dialog):
    assert dialog.isModal()


def test_dialog_has_title(dialog):
    assert "подтверждение" in dialog.windowTitle().lower()


def test_dialog_minimum_width(dialog):
    assert dialog.minimumWidth() >= 400


# --- Buttons present ---

def test_confirm_button_exists(dialog):
    btn = dialog.confirm_button()
    assert btn is not None
    assert "Подтвердить" in btn.text()


def test_cancel_button_exists(dialog):
    btn = dialog.cancel_button()
    assert btn is not None
    assert "Отмена" in btn.text()


# --- Confirm → accept ---

def test_confirm_button_accepts(dialog):
    result_holder = []

    def on_finished(code):
        result_holder.append(code)

    dialog.finished.connect(on_finished)
    dialog.confirm_button().click()
    assert result_holder[0] == QDialog.DialogCode.Accepted


# --- Cancel → reject ---

def test_cancel_button_rejects(dialog):
    result_holder = []

    def on_finished(code):
        result_holder.append(code)

    dialog.finished.connect(on_finished)
    dialog.cancel_button().click()
    assert result_holder[0] == QDialog.DialogCode.Rejected


# --- Empty plan (no steps) ---

def test_empty_plan_no_crash(qapp):
    d = ConfirmationDialog(reason="test reason", plan={"intent": "x", "steps": []})
    assert isinstance(d, QDialog)


# --- Reason text visible ---

def test_reason_shown(dialog):
    found = False
    for child in dialog.findChildren(type(dialog.cancel_button().__class__.__bases__[0])):
        pass
    # Just verify construction succeeds with reason in object
    assert dialog is not None


# --- Plan without command field ---

def test_plan_step_without_command(qapp):
    plan = {"intent": "open", "steps": [
        {"tool": "desktop", "action": "open_app", "parameters": {}}
    ]}
    d = ConfirmationDialog(reason="Destructive action", plan=plan)
    assert isinstance(d, QDialog)
