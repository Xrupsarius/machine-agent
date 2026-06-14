import logging
import os
import re
import subprocess

import numpy as np
import pyaudio

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1280   # 80 ms at 16 kHz — native frame size for openwakeword
FORMAT = pyaudio.paInt16


class MicrophoneService:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_size: int = CHUNK_SIZE,
        device_name: str = "",
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._device_name = device_name
        self._pa = pyaudio.PyAudio()
        self._stream = None

    def _list_sources(self) -> list[str]:
        try:
            out = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception as e:
            log.warning(f"pactl unavailable ({e}) — using system default source")
            return []
        names = []
        for line in out.splitlines():
            parts = line.split("\t")
            name = parts[1] if len(parts) > 1 else ""
            if name and not name.endswith(".monitor"):
                names.append(name)
        return names

    def _probe_source(self, name: str) -> float:
        os.environ["PULSE_SOURCE"] = name
        index = self._pulse_device_index()
        try:
            stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=self._sample_rate,
                input=True,
                input_device_index=index,
                frames_per_buffer=self._chunk_size,
            )
        except Exception as e:
            log.warning(f"Probe failed for '{name}': {e}")
            return -1.0
        try:
            peak = 0.0
            for _ in range(8):
                data = stream.read(self._chunk_size, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                peak = max(peak, float(np.sqrt(np.mean(audio ** 2))))
            return peak
        finally:
            stream.close()

    def _auto_select_source(self) -> bool:
        sources = self._list_sources()
        if not sources:
            return False
        scores = {name: self._probe_source(name) for name in sources}
        log.info(f"Microphone probe results: { {n: round(s, 1) for n, s in scores.items()} }")
        best, best_score = max(scores.items(), key=lambda kv: kv[1])
        if best_score < 1.0:
            os.environ.pop("PULSE_SOURCE", None)
            log.warning("All microphones are silent — using system default source")
            return False
        os.environ["PULSE_SOURCE"] = best
        log.info(f"Microphone auto-selected: {best} (RMS={best_score:.1f})")
        return True

    def _select_pulse_source(self) -> bool:
        if not self._device_name.strip():
            return False
        if self._device_name.strip().lower() == "auto":
            return self._auto_select_source()
        sources = self._list_sources()
        tokens = [t for t in re.split(r"[\s_\-.]+", self._device_name.lower()) if t]
        for name in sources:
            norm = re.sub(r"[\s_\-.]+", " ", name.lower())
            if all(t in norm for t in tokens):
                os.environ["PULSE_SOURCE"] = name
                log.info(f"Microphone source selected: {name}")
                return True
        log.warning(f"Microphone '{self._device_name}' not found — trying auto-detection")
        return self._auto_select_source()

    def _pulse_device_index(self) -> int | None:
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["name"] == "pulse" and info["maxInputChannels"] > 0:
                return i
        return None

    def open(self) -> None:
        if self._stream is not None:
            return
        index = self._pulse_device_index() if self._select_pulse_source() else None
        self._stream = self._pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=self._sample_rate,
            input=True,
            input_device_index=index,
            frames_per_buffer=self._chunk_size,
        )
        log.info("Microphone stream opened")

    def close(self) -> None:
        if self._stream is None:
            return
        self._stream.stop_stream()
        self._stream.close()
        self._stream = None
        log.info("Microphone stream closed")

    def read_chunk(self) -> bytes:
        if self._stream is None:
            raise RuntimeError("Microphone stream is not open")
        return self._stream.read(self._chunk_size, exception_on_overflow=False)

    def is_open(self) -> bool:
        return self._stream is not None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    def __del__(self) -> None:
        self.close()
        self._pa.terminate()
