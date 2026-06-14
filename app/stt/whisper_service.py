import logging
import numpy as np
from faster_whisper import WhisperModel

log = logging.getLogger(__name__)


class WhisperService:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model: WhisperModel | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        log.info(f"Loading Whisper model '{self._model_name}' (device={self._device})")
        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )
        log.info("Whisper model loaded")

    def transcribe(self, audio: np.ndarray, language: str = "ru", vad_filter: bool = True) -> str:
        if self._model is None:
            raise RuntimeError("WhisperService not loaded — call load() first")
        segments, info = self._model.transcribe(
            audio, language=language, vad_filter=vad_filter, beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.debug(
            f"Transcribed: '{text}' "
            f"(lang={info.language}, prob={info.language_probability:.2f})"
        )
        return text

    def is_loaded(self) -> bool:
        return self._model is not None
