import pytest
from app.agent.prompt_manager import PromptManager, PromptNotFoundError

EXPECTED_PROMPTS = [
    "intent_parser",
    "planner",
    "security_validator",
    "tool_selector",
    "tool_executor",
    "memory_writer",
    "memory_search",
    "desktop_agent",
    "accessibility_agent",
    "vision_agent",
    "terminal_agent",
    "browser_agent",
    "conversation_agent",
    "recovery_agent",
    "global_directive",
]


@pytest.fixture
def pm():
    return PromptManager()


def test_all_15_prompts_defined(pm):
    names = pm.names()
    for name in EXPECTED_PROMPTS:
        assert name in names, f"Missing prompt: '{name}'"


def test_get_returns_non_empty_string(pm):
    for name in EXPECTED_PROMPTS:
        text = pm.get(name)
        assert isinstance(text, str) and len(text) > 10, f"Prompt '{name}' too short"


def test_get_raises_for_unknown(pm):
    with pytest.raises(PromptNotFoundError):
        pm.get("nonexistent_prompt")


def test_intent_parser_prompt_mentions_json(pm):
    text = pm.get("intent_parser")
    assert "JSON" in text or "json" in text


def test_intent_parser_prompt_mentions_intent_field(pm):
    assert '"intent"' in pm.get("intent_parser")


def test_planner_prompt_mentions_steps(pm):
    assert "steps" in pm.get("planner")


def test_planner_prompt_mentions_intent_field(pm):
    assert '"intent"' in pm.get("planner")


def test_security_validator_mentions_sudo(pm):
    assert "sudo" in pm.get("security_validator")


def test_global_directive_mentions_safety(pm):
    text = pm.get("global_directive")
    assert "Safety" in text or "safety" in text


def test_names_returns_list(pm):
    assert isinstance(pm.names(), list)
    assert len(pm.names()) == 16
