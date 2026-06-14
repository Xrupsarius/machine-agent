"""Unit tests for VisionTool."""
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from app.tools.vision_tool import VisionTool, _take_screenshot
from app.vision.vision_service import VisionService


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _tool(available=True, response="Desktop with two windows"):
    svc = MagicMock(spec=VisionService)
    svc.model = "moondream"
    svc.is_available.return_value = available
    svc.analyze.return_value = response
    return VisionTool(svc), svc


def _tmp_img():
    fd, path = tempfile.mkstemp(suffix=".png")
    os.write(fd, b"\x89PNG\r\nFAKE")
    os.close(fd)
    return path


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

def test_name():
    tool, _ = _tool()
    assert tool.name == "vision"


def test_description():
    tool, _ = _tool()
    assert len(tool.description) > 5


def test_execute_sets_tool_name():
    tool, _ = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        result = tool.execute("describe_screen", {})
    assert result.tool_name == "vision"


def test_execute_sets_action():
    tool, _ = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        result = tool.execute("describe_screen", {})
    assert result.action == "describe_screen"


# ------------------------------------------------------------------
# describe_screen
# ------------------------------------------------------------------

def test_describe_screen_success():
    tool, svc = _tool(response="Three windows visible")
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        result = tool.execute("describe_screen", {})
    assert result.success
    assert "Three windows" in result.output


def test_describe_screen_calls_analyze():
    tool, svc = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        tool.execute("describe_screen", {})
    svc.analyze.assert_called_once()


def test_describe_screen_uses_custom_prompt():
    tool, svc = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        tool.execute("describe_screen", {"prompt": "Is there a browser open?"})
    call_args = svc.analyze.call_args
    assert "browser" in call_args.args[1].lower() or "browser" in call_args.kwargs.get("prompt", "").lower()


def test_describe_screen_screenshot_failed():
    tool, _ = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=False):
        result = tool.execute("describe_screen", {})
    assert not result.success
    assert "screenshot" in result.error.lower()


def test_describe_screen_vision_unavailable():
    tool, _ = _tool(available=False)
    result = tool.execute("describe_screen", {})
    assert not result.success
    assert "not available" in result.error.lower()


def test_describe_screen_cleans_up_tmp_on_success():
    paths_created = []
    original = tempfile.mkstemp

    def tracking(*args, **kwargs):
        fd, path = original(*args, **kwargs)
        paths_created.append(path)
        return fd, path

    tool, _ = _tool()
    with patch("app.tools.vision_tool.tempfile.mkstemp", side_effect=tracking):
        with patch("app.tools.vision_tool._take_screenshot", return_value=True):
            tool.execute("describe_screen", {})

    for p in paths_created:
        assert not os.path.exists(p)


def test_describe_screen_cleans_up_tmp_on_failure():
    paths_created = []
    original = tempfile.mkstemp

    def tracking(*args, **kwargs):
        fd, path = original(*args, **kwargs)
        paths_created.append(path)
        return fd, path

    tool, _ = _tool()
    with patch("app.tools.vision_tool.tempfile.mkstemp", side_effect=tracking):
        with patch("app.tools.vision_tool._take_screenshot", return_value=False):
            tool.execute("describe_screen", {})

    for p in paths_created:
        assert not os.path.exists(p)


# ------------------------------------------------------------------
# find_element
# ------------------------------------------------------------------

def test_find_element_success():
    tool, svc = _tool(response="Button 'Submit' is in the bottom right corner")
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        result = tool.execute("find_element", {"element": "Submit button"})
    assert result.success
    assert "Submit" in result.output


def test_find_element_includes_name_in_prompt():
    tool, svc = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=True):
        tool.execute("find_element", {"element": "Close button"})
    call_args = svc.analyze.call_args
    assert "Close button" in str(call_args)


def test_find_element_empty_name_fails():
    tool, _ = _tool()
    result = tool.execute("find_element", {"element": ""})
    assert not result.success
    assert "No element" in result.error


def test_find_element_no_element_param():
    tool, _ = _tool()
    result = tool.execute("find_element", {})
    assert not result.success


def test_find_element_screenshot_failed():
    tool, _ = _tool()
    with patch("app.tools.vision_tool._take_screenshot", return_value=False):
        result = tool.execute("find_element", {"element": "button"})
    assert not result.success


def test_find_element_vision_unavailable():
    tool, _ = _tool(available=False)
    result = tool.execute("find_element", {"element": "button"})
    assert not result.success


# ------------------------------------------------------------------
# analyze_image
# ------------------------------------------------------------------

def test_analyze_image_success():
    tool, svc = _tool(response="An image of a cat")
    tmp = _tmp_img()
    try:
        result = tool.execute("analyze_image", {"path": tmp, "prompt": "What is in the image?"})
        assert result.success
        assert "cat" in result.output
    finally:
        os.unlink(tmp)


def test_analyze_image_default_prompt():
    tool, svc = _tool()
    tmp = _tmp_img()
    try:
        tool.execute("analyze_image", {"path": tmp})
        call_args = svc.analyze.call_args
        assert len(call_args.args[1]) > 0  # prompt not empty
    finally:
        os.unlink(tmp)


def test_analyze_image_empty_path_fails():
    tool, _ = _tool()
    result = tool.execute("analyze_image", {"path": ""})
    assert not result.success
    assert "No image path" in result.error


def test_analyze_image_missing_file_fails():
    tool, _ = _tool()
    result = tool.execute("analyze_image", {"path": "/nonexistent/image.png"})
    assert not result.success
    assert "not found" in result.error.lower()


def test_analyze_image_vision_unavailable():
    tool, _ = _tool(available=False)
    tmp = _tmp_img()
    try:
        result = tool.execute("analyze_image", {"path": tmp})
        assert not result.success
    finally:
        os.unlink(tmp)


# ------------------------------------------------------------------
# unknown action
# ------------------------------------------------------------------

def test_unknown_action_fails():
    tool, _ = _tool()
    result = tool.execute("zoom_in", {})
    assert not result.success
    assert "zoom_in" in result.error


# ------------------------------------------------------------------
# _take_screenshot (unit)
# ------------------------------------------------------------------

def test_take_screenshot_uses_pil_when_available():
    mock_img = MagicMock()
    mock_img.width = 1920
    mock_img.height = 1080
    mock_img.resize.return_value = mock_img

    with patch("app.tools.vision_tool._PIL_OK", True):
        with patch("app.tools.vision_tool.ImageGrab") as mock_grab:
            mock_grab.grab.return_value = mock_img
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            try:
                _take_screenshot(path)
                mock_grab.grab.assert_called_once()
            finally:
                os.unlink(path) if os.path.exists(path) else None


def test_take_screenshot_returns_false_without_tools():
    with patch("app.tools.vision_tool._PIL_OK", False):
        with patch("app.tools.vision_tool.subprocess.run", side_effect=FileNotFoundError):
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            os.unlink(path)
            result = _take_screenshot(path)
            assert result is False
