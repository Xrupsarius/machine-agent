import json
import pytest
from unittest.mock import MagicMock, patch
from app.agent.security_validator import SecurityValidator, SecurityCheckResult


@pytest.fixture
def sv():
    return SecurityValidator()


def _plan(command: str) -> dict:
    return {"intent": "x", "steps": [
        {"tool": "terminal", "action": "execute", "parameters": {"command": command}}
    ]}


# --- Phase 1: pattern matching unchanged ---

def test_sudo_still_blocked(sv):
    assert not sv.validate_plan(_plan("sudo reboot")).safe


def test_rm_dash_blocked(sv):
    assert not sv.validate_plan(_plan("rm -rf /tmp")).safe


def test_safe_echo_passes(sv):
    assert sv.validate_plan(_plan("echo hi")).safe


# --- Destructive filesystem actions ---

def test_delete_file_requires_confirmation(sv):
    plan = {"intent": "del", "steps": [
        {"tool": "filesystem", "action": "delete_file", "parameters": {"path": "/tmp/x"}}
    ]}
    result = sv.validate_plan(plan)
    assert not result.safe
    assert result.requires_confirmation
    assert "delete_file" in result.reason


def test_safe_create_file_passes(sv):
    plan = {"intent": "create", "steps": [
        {"tool": "filesystem", "action": "create_file", "parameters": {"path": "/tmp/x"}}
    ]}
    assert sv.validate_plan(plan).safe


def test_safe_read_file_passes(sv):
    plan = {"intent": "read", "steps": [
        {"tool": "filesystem", "action": "read_file", "parameters": {"path": "/tmp/x"}}
    ]}
    assert sv.validate_plan(plan).safe


# --- LLM layer: not called when patterns catch it ---

def test_llm_not_called_when_pattern_blocks():
    llm = MagicMock()
    llm.is_available.return_value = True
    prompts = MagicMock()
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    sv.validate_plan(_plan("sudo reboot"))
    llm.generate.assert_not_called()


# --- LLM layer: called when patterns pass ---

def test_llm_called_when_patterns_safe():
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate.return_value = json.dumps(
        {"safe": True, "requires_confirmation": False, "reason": ""}
    )
    prompts = MagicMock()
    prompts.get.return_value = "system prompt"
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    sv.validate_plan(_plan("echo hello"))
    llm.generate.assert_called_once()


def test_llm_skipped_when_unavailable():
    llm = MagicMock()
    llm.is_available.return_value = False
    prompts = MagicMock()
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    result = sv.validate_plan(_plan("echo hello"))
    assert result.safe
    llm.generate.assert_not_called()


def test_llm_skipped_when_no_llm():
    sv = SecurityValidator()
    result = sv.validate_plan(_plan("echo hello"))
    assert result.safe


# --- LLM result parsing ---

def test_llm_says_dangerous():
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate.return_value = json.dumps(
        {"safe": False, "requires_confirmation": True, "reason": "Suspicious command"}
    )
    prompts = MagicMock()
    prompts.get.return_value = "system"
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    result = sv.validate_plan(_plan("cat /etc/shadow"))
    assert not result.safe
    assert result.requires_confirmation
    assert "Suspicious" in result.reason


def test_llm_confirms_safe():
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate.return_value = json.dumps(
        {"safe": True, "requires_confirmation": False, "reason": ""}
    )
    prompts = MagicMock()
    prompts.get.return_value = "system"
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    result = sv.validate_plan(_plan("ls -la"))
    assert result.safe


def test_llm_invalid_json_falls_back_to_safe():
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate.return_value = "not valid json at all"
    prompts = MagicMock()
    prompts.get.return_value = "system"
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    result = sv.validate_plan(_plan("ls"))
    assert result.safe


def test_llm_exception_falls_back_to_safe():
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.generate.side_effect = Exception("timeout")
    prompts = MagicMock()
    prompts.get.return_value = "system"
    sv = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    result = sv.validate_plan(_plan("ls"))
    assert result.safe


# --- Plan serialization ---

def test_serialize_plan_includes_intent():
    sv = SecurityValidator()
    plan = {"intent": "run_cmd", "steps": [
        {"tool": "terminal", "action": "execute", "parameters": {"command": "ls"}}
    ]}
    text = sv._serialize_plan(plan)
    assert "run_cmd" in text
    assert "ls" in text


def test_serialize_empty_plan():
    sv = SecurityValidator()
    text = sv._serialize_plan({"intent": "x", "steps": []})
    assert "x" in text


# --- validate_command unchanged ---

def test_validate_command_safe(sv):
    assert sv.validate_command("echo hello").safe


def test_validate_command_dangerous(sv):
    assert not sv.validate_command("sudo shutdown").safe


# --- Constructor backward-compat (no args) ---

def test_no_args_constructor():
    sv = SecurityValidator()
    assert sv.validate_plan({"steps": []}).safe
