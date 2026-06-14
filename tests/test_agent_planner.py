import json
import pytest
from unittest.mock import MagicMock

from app.agent.planner import Planner, EVENT_PLAN_CREATED
from app.agent.llm_service import OllamaConnectionError
from app.agent.prompt_manager import PromptManager


def _make_planner(llm_response: str | Exception):
    llm = MagicMock()
    if isinstance(llm_response, Exception):
        llm.generate.side_effect = llm_response
    else:
        llm.generate.return_value = llm_response
    return Planner(llm, PromptManager()), llm


def _plan_json(intent: str = "open_terminal", steps=None) -> str:
    if steps is None:
        steps = [{"tool": "desktop", "action": "open_terminal"}]
    return json.dumps({"intent": intent, "steps": steps})


# --- happy path ---

def test_plan_returns_intent_and_steps():
    planner, _ = _make_planner(_plan_json())
    result = planner.plan({"intent": "open_terminal", "parameters": {}})
    assert result["intent"] == "open_terminal"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["tool"] == "desktop"


def test_plan_preserves_extra_step_fields():
    raw = json.dumps({
        "intent": "open_file",
        "steps": [{"tool": "filesystem", "action": "read", "parameters": {"path": "/tmp/x"}}],
    })
    planner, _ = _make_planner(raw)
    result = planner.plan({"intent": "open_file", "parameters": {}})
    assert result["steps"][0]["parameters"]["path"] == "/tmp/x"


def test_plan_adds_intent_if_missing_from_llm():
    raw = json.dumps({"steps": [{"tool": "desktop", "action": "open_terminal"}]})
    planner, _ = _make_planner(raw)
    result = planner.plan({"intent": "open_terminal", "parameters": {}})
    assert result["intent"] == "open_terminal"


def test_plan_multiple_steps():
    raw = json.dumps({
        "intent": "complex",
        "steps": [
            {"tool": "terminal", "action": "open"},
            {"tool": "terminal", "action": "execute"},
        ],
    })
    planner, _ = _make_planner(raw)
    result = planner.plan({"intent": "complex", "parameters": {}})
    assert len(result["steps"]) == 2


def test_plan_calls_llm_with_json_output():
    planner, llm = _make_planner(_plan_json())
    planner.plan({"intent": "custom_intent", "parameters": {}})
    assert llm.generate.call_args.kwargs.get("json_output") is True


def test_plan_calls_llm_with_think_false():
    planner, llm = _make_planner(_plan_json())
    planner.plan({"intent": "custom_intent", "parameters": {}})
    assert llm.generate.call_args.kwargs.get("think") is False


def test_plan_passes_intent_as_prompt():
    planner, llm = _make_planner(_plan_json())
    intent = {"intent": "custom_intent", "parameters": {}}
    planner.plan(intent)
    prompt_str = llm.generate.call_args.kwargs.get("prompt", "")
    assert "custom_intent" in prompt_str


# --- fallback behavior ---

def test_invalid_json_returns_empty_plan():
    planner, _ = _make_planner("not valid json")
    result = planner.plan({"intent": "custom_intent", "parameters": {}})
    assert result["intent"] == "custom_intent"
    assert result["steps"] == []


def test_invalid_tool_returns_empty_plan():
    raw = json.dumps({"steps": [{"tool": "hacker_tool", "action": "do"}]})
    planner, _ = _make_planner(raw)
    result = planner.plan({"intent": "x", "parameters": {}})
    assert result["steps"] == []


def test_missing_steps_field_returns_empty_plan():
    raw = json.dumps({"intent": "x"})
    planner, _ = _make_planner(raw)
    result = planner.plan({"intent": "x", "parameters": {}})
    assert result["steps"] == []


def test_empty_plan_has_intent_from_input():
    planner, _ = _make_planner("bad json !!!")
    result = planner.plan({"intent": "my_intent", "parameters": {}})
    assert result["intent"] == "my_intent"


# --- error propagation ---

def test_ollama_error_propagates():
    planner, _ = _make_planner(OllamaConnectionError("down"))
    with pytest.raises(OllamaConnectionError):
        planner.plan({"intent": "x", "parameters": {}})


# --- constant ---

def test_event_constant_defined():
    assert EVENT_PLAN_CREATED == "plan.created"


def test_template_plan_skips_llm():
    planner, llm = _make_planner(_plan_json())
    result = planner.plan({"intent": "open_terminal", "parameters": {}})
    llm.generate.assert_not_called()
    assert result["steps"] == [{"tool": "desktop", "action": "open_terminal"}]


def test_template_plan_type_text():
    planner, llm = _make_planner(_plan_json())
    result = planner.plan({"intent": "type_text", "parameters": {"text": "hi"}})
    llm.generate.assert_not_called()
    assert result["steps"][0]["action"] == "type_text"
    assert result["steps"][0]["parameters"]["text"] == "hi"


def test_template_missing_required_param_falls_to_llm():
    planner, llm = _make_planner(_plan_json())
    planner.plan({"intent": "type_text", "parameters": {}})
    llm.generate.assert_called_once()
