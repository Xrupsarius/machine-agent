import pytest
from unittest.mock import MagicMock, patch
from app.agent.llm_service import LLMService, OllamaConnectionError


def _make_generate_resp(text: str) -> MagicMock:
    r = MagicMock()
    r.response = text
    return r


def _make_chat_resp(text: str) -> MagicMock:
    r = MagicMock()
    r.message.content = text
    return r


@pytest.fixture
def svc():
    with patch("app.agent.llm_service.ollama.Client") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield LLMService("qwen3:8b", "http://localhost:11434"), client


def test_model_property(svc):
    llm, _ = svc
    assert llm.model == "qwen3:8b"


def test_generate_returns_text(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("hello")
    assert llm.generate("test") == "hello"


def test_generate_passes_prompt(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("ok")
    llm.generate("my prompt")
    kwargs = client.generate.call_args.kwargs
    assert kwargs["prompt"] == "my prompt"


def test_generate_passes_system(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("ok")
    llm.generate("p", system="sys")
    kwargs = client.generate.call_args.kwargs
    assert kwargs["system"] == "sys"


def test_generate_empty_system_passes_none(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("ok")
    llm.generate("p", system="")
    kwargs = client.generate.call_args.kwargs
    assert kwargs["system"] is None


def test_generate_json_output_sets_format(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("{}")
    llm.generate("p", json_output=True)
    kwargs = client.generate.call_args.kwargs
    assert kwargs["format"] == "json"


def test_generate_no_json_sets_format_none(svc):
    llm, client = svc
    client.generate.return_value = _make_generate_resp("text")
    llm.generate("p")
    kwargs = client.generate.call_args.kwargs
    assert kwargs["format"] is None


def test_generate_raises_on_connection_error(svc):
    llm, client = svc
    client.generate.side_effect = ConnectionRefusedError("refused")
    with pytest.raises(OllamaConnectionError):
        llm.generate("p")


def test_chat_returns_text(svc):
    llm, client = svc
    client.chat.return_value = _make_chat_resp("answer")
    assert llm.chat([{"role": "user", "content": "hi"}]) == "answer"


def test_chat_passes_messages(svc):
    llm, client = svc
    client.chat.return_value = _make_chat_resp("ok")
    msgs = [{"role": "user", "content": "hello"}]
    llm.chat(msgs)
    assert client.chat.call_args.kwargs["messages"] == msgs


def test_chat_raises_on_connection_error(svc):
    llm, client = svc
    client.chat.side_effect = OSError("timeout")
    with pytest.raises(OllamaConnectionError):
        llm.chat([])


def test_is_available_true_when_list_succeeds(svc):
    llm, client = svc
    client.list.return_value = MagicMock()
    assert llm.is_available() is True


def test_is_available_false_when_list_fails(svc):
    llm, client = svc
    client.list.side_effect = ConnectionRefusedError()
    assert llm.is_available() is False
