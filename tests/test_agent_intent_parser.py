import json
import pytest
from unittest.mock import MagicMock

from app.agent.intent_parser import IntentParser, EVENT_INTENT_PARSED
from app.agent.llm_service import OllamaConnectionError
from app.agent.prompt_manager import PromptManager


def _make_parser(llm_response: str | Exception):
    llm = MagicMock()
    if isinstance(llm_response, Exception):
        llm.generate.side_effect = llm_response
    else:
        llm.generate.return_value = llm_response
    return IntentParser(llm, PromptManager())


def _json(intent: str, params: dict = None) -> str:
    return json.dumps({"intent": intent, "parameters": params or {}})


# --- happy path ---

def test_parse_returns_intent_and_parameters():
    parser = _make_parser(_json("open_terminal"))
    result = parser.parse("Открой терминал")
    assert result["intent"] == "open_terminal"
    assert result["parameters"] == {}


def test_parse_with_parameters():
    parser = _make_parser(_json("open_file", {"path": "/home/user/doc.txt"}))
    result = parser.parse("Открой файл")
    assert result["intent"] == "open_file"
    assert result["parameters"]["path"] == "/home/user/doc.txt"


def test_parse_strips_whitespace_from_intent():
    parser = _make_parser(json.dumps({"intent": "  open_terminal  ", "parameters": {}}))
    result = parser.parse("Открой терминал")
    assert result["intent"] == "open_terminal"


def test_parse_uses_json_output_mode():
    llm = MagicMock()
    llm.generate.return_value = _json("open_terminal")
    parser = IntentParser(llm, PromptManager())
    parser.parse("test")
    kwargs = llm.generate.call_args.kwargs
    assert kwargs.get("json_output") is True


def test_parse_uses_think_false():
    llm = MagicMock()
    llm.generate.return_value = _json("open_terminal")
    parser = IntentParser(llm, PromptManager())
    parser.parse("test")
    kwargs = llm.generate.call_args.kwargs
    assert kwargs.get("think") is False


def test_parse_passes_user_text_as_prompt():
    llm = MagicMock()
    llm.generate.return_value = _json("open_terminal")
    parser = IntentParser(llm, PromptManager())
    parser.parse("Открой терминал")
    assert llm.generate.call_args.kwargs["prompt"] == "Открой терминал"


# --- fallback behavior ---

def test_invalid_json_returns_unknown_intent():
    parser = _make_parser("not valid json at all")
    result = parser.parse("anything")
    assert result["intent"] == "unknown"
    assert result["parameters"] == {}


def test_missing_intent_field_returns_unknown():
    parser = _make_parser(json.dumps({"parameters": {}}))
    result = parser.parse("anything")
    assert result["intent"] == "unknown"


def test_empty_intent_returns_unknown():
    parser = _make_parser(json.dumps({"intent": "   ", "parameters": {}}))
    result = parser.parse("anything")
    assert result["intent"] == "unknown"


def test_non_dict_response_returns_unknown():
    parser = _make_parser(json.dumps(["not", "a", "dict"]))
    result = parser.parse("anything")
    assert result["intent"] == "unknown"


# --- error propagation ---

def test_ollama_connection_error_propagates():
    parser = _make_parser(OllamaConnectionError("connection refused"))
    with pytest.raises(OllamaConnectionError):
        parser.parse("anything")


# --- intent.parsed event constant ---

def test_event_constant_defined():
    assert isinstance(EVENT_INTENT_PARSED, str)
    assert EVENT_INTENT_PARSED == "intent.parsed"
