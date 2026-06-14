import pytest
from app.agent.security_validator import (
    SecurityValidator,
    SecurityCheckResult,
    EVENT_SECURITY_VALIDATED,
    EVENT_SECURITY_BLOCKED,
)


@pytest.fixture
def sv():
    return SecurityValidator()


# --- SecurityCheckResult ---

def test_result_safe_defaults():
    r = SecurityCheckResult(safe=True, requires_confirmation=False)
    assert r.reason == ""


def test_result_to_dict():
    r = SecurityCheckResult(safe=False, requires_confirmation=True, reason="sudo found")
    d = r.to_dict()
    assert d["safe"] is False
    assert d["requires_confirmation"] is True
    assert d["reason"] == "sudo found"


# --- validate_plan: safe commands ---

def test_empty_plan_is_safe(sv):
    result = sv.validate_plan({"intent": "x", "steps": []})
    assert result.safe


def test_safe_step_is_safe(sv):
    plan = {"steps": [{"tool": "desktop", "action": "open_terminal", "parameters": {}}]}
    result = sv.validate_plan(plan)
    assert result.safe
    assert not result.requires_confirmation


def test_echo_command_is_safe(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "echo hello"}}]}
    assert sv.validate_plan(plan).safe


def test_ls_command_is_safe(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "ls -la"}}]}
    assert sv.validate_plan(plan).safe


def test_cat_command_is_safe(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "cat /etc/hostname"}}]}
    assert sv.validate_plan(plan).safe


# --- validate_plan: dangerous commands ---

def test_sudo_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "sudo apt update"}}]}
    result = sv.validate_plan(plan)
    assert not result.safe
    assert result.requires_confirmation
    assert "sudo" in result.reason


def test_rm_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "rm -rf /tmp/test"}}]}
    result = sv.validate_plan(plan)
    assert not result.safe
    assert result.requires_confirmation


def test_mkfs_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "mkfs.ext4 /dev/sdb"}}]}
    assert not sv.validate_plan(plan).safe


def test_chmod_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "chmod 777 /etc/passwd"}}]}
    assert not sv.validate_plan(plan).safe


def test_chown_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "chown root /tmp/x"}}]}
    assert not sv.validate_plan(plan).safe


def test_systemctl_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "systemctl stop nginx"}}]}
    assert not sv.validate_plan(plan).safe


def test_dd_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "dd if=/dev/zero of=/dev/sda"}}]}
    assert not sv.validate_plan(plan).safe


def test_apt_remove_requires_confirmation(sv):
    plan = {"steps": [{"tool": "terminal", "action": "execute",
                        "parameters": {"command": "apt remove python3"}}]}
    assert not sv.validate_plan(plan).safe


def test_stops_at_first_dangerous_step(sv):
    plan = {
        "steps": [
            {"tool": "terminal", "action": "execute",
             "parameters": {"command": "echo safe"}},
            {"tool": "terminal", "action": "execute",
             "parameters": {"command": "sudo reboot"}},
        ]
    }
    result = sv.validate_plan(plan)
    assert not result.safe


# --- validate_command ---

def test_validate_command_safe(sv):
    assert sv.validate_command("echo hello").safe


def test_validate_command_dangerous(sv):
    result = sv.validate_command("sudo reboot")
    assert not result.safe
    assert result.requires_confirmation


def test_validate_command_case_insensitive(sv):
    assert not sv.validate_command("SUDO rm -rf /").safe


# --- event constants ---

def test_event_constants_defined():
    assert isinstance(EVENT_SECURITY_VALIDATED, str)
    assert isinstance(EVENT_SECURITY_BLOCKED, str)
