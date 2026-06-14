import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

try:
    import ollama as _ollama_mod
    _OLLAMA_OK = True
except ImportError:
    _OLLAMA_OK = False
    log.warning("ollama package not installed — VisionService unavailable")


class VisionService:
    """
    Wraps Moondream via Ollama for image analysis.
    ADR-005: Vision on demand only — never called continuously.
    """

    def __init__(self, model: str = "moondream", host: str = "http://localhost:11434") -> None:
        self._model = model
        self._host = host
        self._client: Optional[object] = None

    def _get_client(self):
        if not _OLLAMA_OK:
            return None
        if self._client is None:
            self._client = _ollama_mod.Client(host=self._host)
        return self._client

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            result = client.list()
            return any(self._model in m.model for m in result.models)
        except Exception as e:
            log.debug(f"VisionService.is_available check failed: {e}")
            return False

    def analyze(self, image_path: str, prompt: str) -> str:
        """Analyze an image file. Returns Moondream's description."""
        client = self._get_client()
        if client is None:
            return "Vision not available: ollama not installed"
        if not Path(image_path).exists():
            return f"Image not found: {image_path}"
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            response = client.generate(
                model=self._model,
                prompt=prompt,
                images=[image_data],
            )
            return response.response.strip()
        except Exception as e:
            log.error(f"VisionService.analyze error: {e}")
            return f"Vision error: {e}"

    def analyze_bytes(self, image_bytes: bytes, prompt: str) -> str:
        """Analyze image given as raw bytes."""
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, image_bytes)
            os.close(fd)
            return self.analyze(tmp_path, prompt)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
