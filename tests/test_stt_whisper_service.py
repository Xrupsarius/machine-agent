import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from app.stt.whisper_service import WhisperService


def _make_mock_model(text: str = "Привет мир") -> MagicMock:
    seg = MagicMock()
    seg.text = text
    model = MagicMock()
    model.transcribe.return_value = (
        [seg],
        MagicMock(language="ru", language_probability=0.99),
    )
    return model


def test_not_loaded_initially():
    ws = WhisperService()
    assert not ws.is_loaded()


def test_load_sets_loaded():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        Mock.return_value = MagicMock()
        ws = WhisperService("small")
        ws.load()
        assert ws.is_loaded()


def test_load_uses_correct_model_name():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        Mock.return_value = MagicMock()
        ws = WhisperService("medium")
        ws.load()
        Mock.assert_called_once_with("medium", device="cpu", compute_type="int8")


def test_load_is_idempotent():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        Mock.return_value = MagicMock()
        ws = WhisperService()
        ws.load()
        ws.load()
        assert Mock.call_count == 1


def test_transcribe_raises_when_not_loaded():
    ws = WhisperService()
    with pytest.raises(RuntimeError, match="not loaded"):
        ws.transcribe(np.zeros(1600, dtype=np.float32))


def test_transcribe_returns_text():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        Mock.return_value = _make_mock_model("открой терминал")
        ws = WhisperService()
        ws.load()
        result = ws.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "открой терминал"


def test_transcribe_joins_multiple_segments():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        seg1, seg2 = MagicMock(), MagicMock()
        seg1.text = "  Первый  "
        seg2.text = "  Второй  "
        m = MagicMock()
        m.transcribe.return_value = (
            [seg1, seg2],
            MagicMock(language="ru", language_probability=0.9),
        )
        Mock.return_value = m
        ws = WhisperService()
        ws.load()
        result = ws.transcribe(np.zeros(100, dtype=np.float32))
        assert "Первый" in result
        assert "Второй" in result


def test_transcribe_strips_whitespace():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        Mock.return_value = _make_mock_model("  текст  ")
        ws = WhisperService()
        ws.load()
        result = ws.transcribe(np.zeros(100, dtype=np.float32))
        assert result == "текст"


def test_transcribe_passes_language():
    with patch("app.stt.whisper_service.WhisperModel") as Mock:
        mock_model = _make_mock_model("test")
        Mock.return_value = mock_model
        ws = WhisperService()
        ws.load()
        ws.transcribe(np.zeros(100, dtype=np.float32), language="en")
        call_kwargs = mock_model.transcribe.call_args.kwargs
        assert call_kwargs.get("language") == "en"
