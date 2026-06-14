import struct
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.stt.wakeword_service import WakeWordService


_SILENT = b"\x00" * 2048


def _mock_model(scores: dict) -> MagicMock:
    m = MagicMock()
    m.predict.return_value = scores
    m.prediction_buffer = scores
    m.models = scores
    return m


@pytest.fixture
def svc(tmp_path):
    return WakeWordService(model_dir=str(tmp_path), threshold=0.5)


# --- load ---

def test_not_loaded_initially(svc):
    assert not svc.is_loaded()


def test_load_with_no_custom_models_uses_builtin(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"hey_jarvis_v0.1": 0.0})
        svc.load()
        assert svc.is_loaded()
        # Should pass built-in hey_*.onnx paths, NOT an empty list
        call_paths = MockModel.call_args.kwargs.get("wakeword_model_paths", [])
        assert len(call_paths) > 0, "Expected built-in models to be loaded, got empty list"
        assert all("hey_" in p for p in call_paths), f"Expected hey_* models, got: {call_paths}"


def test_load_with_custom_models_passes_paths(tmp_path):
    onnx = tmp_path / "брат.onnx"
    onnx.write_bytes(b"fake")
    svc = WakeWordService(model_dir=str(tmp_path))
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"брат": 0.0})
        svc.load()
        call_paths = MockModel.call_args.kwargs["wakeword_model_paths"]
        assert str(onnx) in call_paths


def test_load_is_idempotent(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.0})
        svc.load()
        svc.load()
        assert MockModel.call_count == 1


def test_process_chunk_raises_if_not_loaded(svc):
    with pytest.raises(RuntimeError, match="not loaded"):
        svc.process_chunk(_SILENT)


# --- detect ---

def test_no_detection_below_threshold(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.3})
        svc.load()
        assert svc.process_chunk(_SILENT) is False


def test_detection_at_threshold(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.5})
        svc.load()
        assert svc.process_chunk(_SILENT) is True


def test_detection_above_threshold(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.95})
        svc.load()
        assert svc.process_chunk(_SILENT) is True


def test_any_model_above_threshold_triggers(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.1, "hey_jarvis": 0.8})
        svc.load()
        assert svc.process_chunk(_SILENT) is True


# --- cooldown ---

def test_cooldown_prevents_immediate_re_detection(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.9})
        svc.load()
        assert svc.process_chunk(_SILENT) is True   # detected
        assert svc.process_chunk(_SILENT) is False  # cooldown active


def test_cooldown_expires(tmp_path):
    svc = WakeWordService(model_dir=str(tmp_path), threshold=0.5, cooldown_chunks=2)
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.9})
        svc.load()
        svc.process_chunk(_SILENT)    # detected, cooldown=2
        svc.process_chunk(_SILENT)    # cooldown=1, False
        svc.process_chunk(_SILENT)    # cooldown=0, False
        assert svc.process_chunk(_SILENT) is True  # cooldown expired


def test_reset_clears_cooldown(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.9})
        svc.load()
        svc.process_chunk(_SILENT)  # triggers cooldown
        svc.reset()
        assert svc.process_chunk(_SILENT) is True  # cooldown cleared


# --- active_models ---

def test_active_models_empty_before_load(svc):
    assert svc.active_models == []


def test_active_models_after_load(svc):
    with patch("app.stt.wakeword_service.Model") as MockModel:
        MockModel.return_value = _mock_model({"alexa": 0.0, "hey_jarvis": 0.0})
        svc.load()
        models = svc.active_models
        assert "alexa" in models
        assert "hey_jarvis" in models
