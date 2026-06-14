"""Unit tests for VisionService."""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from app.vision.vision_service import VisionService


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _service_with_mock_client(response_text="A desktop screen"):
    svc = VisionService(model="moondream")
    client = MagicMock()
    resp = MagicMock()
    resp.response = response_text
    client.generate.return_value = resp
    client.list.return_value = MagicMock(models=[MagicMock(model="moondream:latest")])
    svc._client = client
    return svc, client


def _tmp_png(content=b"PNG"):
    fd, path = tempfile.mkstemp(suffix=".png")
    os.write(fd, content)
    os.close(fd)
    return path


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

def test_model_property():
    svc = VisionService(model="moondream")
    assert svc.model == "moondream"


def test_model_default():
    svc = VisionService()
    assert svc.model == "moondream"


# ------------------------------------------------------------------
# is_available
# ------------------------------------------------------------------

def test_is_available_when_model_present():
    svc, _ = _service_with_mock_client()
    assert svc.is_available() is True


def test_is_available_false_when_model_missing():
    svc = VisionService(model="moondream")
    client = MagicMock()
    client.list.return_value = MagicMock(models=[MagicMock(model="llama3")])
    svc._client = client
    assert svc.is_available() is False


def test_is_available_false_when_ollama_raises():
    svc = VisionService()
    client = MagicMock()
    client.list.side_effect = Exception("connection refused")
    svc._client = client
    assert svc.is_available() is False


def test_is_available_false_without_ollama():
    with patch("app.vision.vision_service._OLLAMA_OK", False):
        svc = VisionService()
        assert svc.is_available() is False


# ------------------------------------------------------------------
# analyze
# ------------------------------------------------------------------

def test_analyze_returns_description():
    svc, client = _service_with_mock_client("Three windows visible")
    tmp = _tmp_png()
    try:
        result = svc.analyze(tmp, "Describe the screen")
        assert "Three windows" in result
    finally:
        os.unlink(tmp)


def test_analyze_calls_generate_with_model():
    svc, client = _service_with_mock_client()
    tmp = _tmp_png()
    try:
        svc.analyze(tmp, "What is this?")
        client.generate.assert_called_once()
        call_kwargs = client.generate.call_args.kwargs
        assert call_kwargs["model"] == "moondream"
        assert "What is this?" == call_kwargs["prompt"]
    finally:
        os.unlink(tmp)


def test_analyze_sends_image_bytes():
    svc, client = _service_with_mock_client()
    content = b"\x89PNG\r\nFAKEDATA"
    tmp = _tmp_png(content)
    try:
        svc.analyze(tmp, "Describe")
        call_kwargs = client.generate.call_args.kwargs
        assert call_kwargs["images"][0] == content
    finally:
        os.unlink(tmp)


def test_analyze_missing_file():
    svc, _ = _service_with_mock_client()
    result = svc.analyze("/nonexistent/path.png", "Describe")
    assert "not found" in result.lower()


def test_analyze_generate_exception():
    svc, client = _service_with_mock_client()
    client.generate.side_effect = Exception("model error")
    tmp = _tmp_png()
    try:
        result = svc.analyze(tmp, "Describe")
        assert "error" in result.lower()
    finally:
        os.unlink(tmp)


def test_analyze_without_ollama():
    with patch("app.vision.vision_service._OLLAMA_OK", False):
        svc = VisionService()
        result = svc.analyze("/tmp/fake.png", "Describe")
        assert "not available" in result.lower()


# ------------------------------------------------------------------
# analyze_bytes
# ------------------------------------------------------------------

def test_analyze_bytes_writes_tmp_and_calls_analyze():
    svc, client = _service_with_mock_client("Some screen")
    img_bytes = b"\x89PNG\r\nFAKE"
    result = svc.analyze_bytes(img_bytes, "Describe")
    assert "Some screen" in result
    client.generate.assert_called_once()


def test_analyze_bytes_cleans_up_tmp():
    """Temp file should be deleted after analyze_bytes."""
    created_paths = []
    svc, client = _service_with_mock_client()

    original_mkstemp = tempfile.mkstemp

    def tracking_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        created_paths.append(path)
        return fd, path

    with patch("app.vision.vision_service.tempfile.mkstemp", side_effect=tracking_mkstemp):
        svc.analyze_bytes(b"\x89PNG", "Describe")

    for path in created_paths:
        assert not os.path.exists(path), f"Temp file not cleaned up: {path}"
