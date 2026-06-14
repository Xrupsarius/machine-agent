import glob
import logging
import os
from pathlib import Path

import numpy as np
import openwakeword
from openwakeword.model import Model

log = logging.getLogger(__name__)

EVENT_WAKE_WORD_DETECTED = "wakeword.detected"

# After a detection, ignore the next N chunks to avoid re-triggering.
# 50 chunks × 64 ms = ~3.2 s cooldown.
_COOLDOWN_CHUNKS = 50


class WakeWordService:
    """
    Wraps OpenWakeWord. Loads custom ONNX models from model_dir if present,
    otherwise falls back to OpenWakeWord built-in models.

    Place trained Russian wake-word models (брат.onnx, etc.) in
    config/wakeword_models/ to activate them.
    """

    def __init__(
        self,
        model_dir: str = "config/wakeword_models",
        threshold: float = 0.5,
        cooldown_chunks: int = _COOLDOWN_CHUNKS,
    ) -> None:
        self._model_dir = Path(model_dir)
        self._threshold = threshold
        self._cooldown_chunks = cooldown_chunks
        self._model: Model | None = None
        self._cooldown_remaining = 0

    def load(self) -> None:
        if self._model is not None:
            return

        model_paths = sorted(self._model_dir.glob("*.onnx"))

        if model_paths:
            paths_str = [str(p) for p in model_paths]
            log.info(f"Loading custom wake-word models: {[p.name for p in model_paths]}")
            self._model = Model(wakeword_model_paths=paths_str)
        else:
            # No custom models — load built-in hey_jarvis / hey_mycroft / hey_marvin.
            # Model(wakeword_model_paths=[]) creates an EMPTY model (no detections ever).
            builtin_dir = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
            builtin = sorted(glob.glob(os.path.join(builtin_dir, "hey_*.onnx")))
            if builtin:
                names = [os.path.basename(p) for p in builtin]
                log.warning(
                    f"No custom models in '{self._model_dir}'. "
                    f"Using built-in models: {names}. "
                    "Say 'hey jarvis', 'hey mycroft', or 'hey marvin' to activate. "
                    "Train Russian models and place .onnx files in config/wakeword_models/ for production."
                )
                self._model = Model(wakeword_model_paths=builtin)
            else:
                log.error("No wake-word models found at all. Wake word detection disabled.")
                self._model = Model(wakeword_model_paths=[])

        log.info(f"WakeWordService loaded. Active models: {self.active_models}")

    def process_chunk(self, audio_bytes: bytes) -> bool:
        """Return True if a wake word was detected in this audio chunk."""
        if self._model is None:
            raise RuntimeError("WakeWordService not loaded — call load() first")

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return False

        audio = np.frombuffer(audio_bytes, dtype=np.int16)
        scores: dict[str, float] = self._model.predict(audio)

        detected = any(score >= self._threshold for score in scores.values())
        if detected:
            triggered = [name for name, score in scores.items() if score >= self._threshold]
            log.info(f"Wake word detected: {triggered} (scores={scores})")
            self._cooldown_remaining = self._cooldown_chunks
        elif scores:
            best_name, best_score = max(scores.items(), key=lambda kv: kv[1])
            if best_score >= self._threshold * 0.5:
                log.info(
                    f"Wake word near-miss: '{best_name}' score={best_score:.2f} "
                    f"(threshold={self._threshold})"
                )

        return detected

    def reset(self) -> None:
        self._cooldown_remaining = 0
        if self._model is not None:
            silence = np.zeros(1280, dtype=np.int16)
            for _ in range(30):
                self._model.predict(silence)
            self._model.reset()

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def active_models(self) -> list[str]:
        if self._model is None:
            return []
        return list(self._model.models.keys())
