import logging

import numpy as np

from app.stt.whisper_service import WhisperService

log = logging.getLogger(__name__)


def _common_prefix(a: list[str], b: list[str]) -> list[str]:
    out: list[str] = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out


class LocalAgreement:
    """
    LocalAgreement-2 stabilization for streaming ASR.

    Each hypothesis is the full transcript of the current audio segment.
    A word is committed once two consecutive hypotheses agree on it; the
    unstable tail is returned as interim text and may still change.
    """

    def __init__(self) -> None:
        self._committed: list[str] = []
        self._prev: list[str] = []

    def update(self, hypothesis: list[str]) -> tuple[list[str], list[str]]:
        n = len(self._committed)
        if len(hypothesis) < n or _common_prefix(hypothesis[:n], self._committed) != self._committed:
            self._prev = hypothesis
            return list(self._committed), hypothesis[n:]
        agreed = _common_prefix(self._prev[n:], hypothesis[n:])
        self._committed.extend(agreed)
        self._prev = hypothesis
        return list(self._committed), hypothesis[len(self._committed):]

    def finalize(self) -> str:
        text = " ".join(self._prev if len(self._prev) >= len(self._committed) else self._committed)
        self.reset()
        return text.strip()

    def reset(self) -> None:
        self._committed = []
        self._prev = []

    @property
    def committed(self) -> list[str]:
        return list(self._committed)


class StreamingTranscriber:
    """Decodes a growing audio segment into stabilized committed/interim text."""

    def __init__(self, whisper: WhisperService, language: str = "ru") -> None:
        self._whisper = whisper
        self._language = language
        self._agreement = LocalAgreement()

    def feed(self, audio: np.ndarray) -> tuple[str, str]:
        text = self._whisper.transcribe(audio, language=self._language, vad_filter=False)
        words = text.split()
        committed, interim = self._agreement.update(words)
        return " ".join(committed), " ".join(interim)

    def finalize(self, audio: np.ndarray | None = None) -> str:
        if audio is not None and audio.size > 0:
            text = self._whisper.transcribe(audio, language=self._language, vad_filter=False)
            self._agreement.update(text.split())
        return self._agreement.finalize()

    def reset(self) -> None:
        self._agreement.reset()
