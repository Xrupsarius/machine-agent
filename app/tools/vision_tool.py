import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.tools.base_tool import BaseTool, ToolResult
from app.vision.vision_service import VisionService

log = logging.getLogger(__name__)

# Screenshot resolution cap — large images slow down inference
_MAX_WIDTH = 1280

try:
    from PIL import ImageGrab, Image as _PILImage
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# Fallback CLI screenshot commands (tried in order if PIL not available)
_CLI_CMDS = [
    ["scrot", "{path}"],
    ["gnome-screenshot", "-f", "{path}"],
    ["spectacle", "-b", "-o", "{path}"],
    ["maim", "{path}"],
]


def _take_screenshot(path: str) -> bool:
    """Capture the full screen to *path*. Returns True on success."""
    if _PIL_OK:
        try:
            img = ImageGrab.grab()
            if img.width > _MAX_WIDTH:
                scale = _MAX_WIDTH / img.width
                img = img.resize(
                    (int(img.width * scale), int(img.height * scale)),
                    _PILImage.LANCZOS,
                )
            img.save(path)
            return True
        except Exception as e:
            log.warning(f"PIL ImageGrab failed: {e}")

    for cmd_template in _CLI_CMDS:
        cmd = [c.replace("{path}", path) for c in cmd_template]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and Path(path).exists() and Path(path).stat().st_size > 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return False


_DEFAULT_DESCRIBE_PROMPT = (
    "Describe what you see on the screen in detail. "
    "List all visible windows, applications, text, buttons, and UI elements."
)


class VisionTool(BaseTool):
    """
    Screen analysis via Moondream.
    ADR-005: Vision triggered only on explicit user request or when element not found.
    Actions: describe_screen, find_element, analyze_image.
    """

    def __init__(self, vision_service: VisionService) -> None:
        self._vision = vision_service

    @property
    def name(self) -> str:
        return "vision"

    @property
    def description(self) -> str:
        return (
            "Screen analysis via Moondream. "
            "Actions: describe_screen, find_element, analyze_image. "
            "ADR-005: use only on explicit user request."
        )

    def _run(self, action: str, parameters: dict) -> ToolResult:
        match action:
            case "describe_screen":
                return self._describe_screen(parameters.get("prompt", ""))
            case "find_element":
                return self._find_element(parameters.get("element", ""))
            case "analyze_image":
                return self._analyze_image(
                    parameters.get("path", ""),
                    parameters.get("prompt", ""),
                )
            case _:
                return ToolResult(
                    success=False,
                    error=(
                        f"Unknown action '{action}'. "
                        "Supported: describe_screen, find_element, analyze_image"
                    ),
                )

    # ------------------------------------------------------------------

    def _describe_screen(self, prompt: str) -> ToolResult:
        if not self._vision.is_available():
            return ToolResult(
                success=False,
                error=f"Vision model '{self._vision.model}' not available via Ollama",
            )
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            if not _take_screenshot(tmp):
                return ToolResult(
                    success=False,
                    error="Failed to take screenshot. Ensure Pillow or scrot is installed.",
                )
            p = prompt.strip() or _DEFAULT_DESCRIBE_PROMPT
            description = self._vision.analyze(tmp, p)
            return ToolResult(success=True, output=description)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _find_element(self, element: str) -> ToolResult:
        if not element.strip():
            return ToolResult(success=False, error="No element name specified")
        if not self._vision.is_available():
            return ToolResult(
                success=False,
                error=f"Vision model '{self._vision.model}' not available via Ollama",
            )
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            if not _take_screenshot(tmp):
                return ToolResult(success=False, error="Failed to take screenshot")
            prompt = (
                f"Find '{element}' on the screen. "
                "Describe its location, appearance, and how to interact with it. "
                "If not found, say so explicitly."
            )
            description = self._vision.analyze(tmp, prompt)
            return ToolResult(success=True, output=description)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _analyze_image(self, path: str, prompt: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No image path provided")
        if not Path(path).exists():
            return ToolResult(success=False, error=f"Image not found: {path!r}")
        if not self._vision.is_available():
            return ToolResult(
                success=False,
                error=f"Vision model '{self._vision.model}' not available via Ollama",
            )
        p = prompt.strip() or "Describe this image in detail."
        description = self._vision.analyze(path, p)
        return ToolResult(success=True, output=description)
