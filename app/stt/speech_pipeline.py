import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.stt.microphone_service import MicrophoneService
from app.stt.whisper_service import WhisperService

if TYPE_CHECKING:
    from app.stt.wakeword_service import WakeWordService

log = logging.getLogger(__name__)

EVENT_SPEECH_RECOGNIZED = "speech.recognized"
EVENT_STT_ERROR = "stt.error"
EVENT_STT_EMPTY = "stt.empty"

# VAD — chunks of 80 ms at 16 kHz / 1280 samples
_SPEECH_CHUNKS_MIN = 3     # ~240 ms of sound to start recording
_SILENCE_CHUNKS_END = 12   # ~0.96 s of silence to stop recording
_PRE_SPEECH_BUFFER = 7     # ~0.56 s pre-roll
_WAKE_LISTEN_TIMEOUT = 75  # ~6 s: no speech after wake word → re-arm


def _rms(audio_bytes: bytes) -> float:
    if not audio_bytes:
        return 0.0
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(audio ** 2)))


def _bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    return audio / 32768.0


class SpeechPipeline:
    def __init__(
        self,
        mic: MicrophoneService,
        whisper: WhisperService,
        state_manager: StateManager,
        event_bus: EventBus,
        silence_threshold: float = 500.0,
        wakeword: "WakeWordService | None" = None,
    ) -> None:
        self._mic = mic
        self._whisper = whisper
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._silence_threshold = silence_threshold
        self._wakeword = wakeword
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        try:
            self._mic.open()
        except Exception as e:
            log.error(f"Microphone unavailable: {e}")
            self._event_bus.publish(EVENT_STT_ERROR, {"error": f"Microphone unavailable: {e}"})
            self._active = False
            return
        self._whisper.load()
        if self._wakeword is not None:
            self._wakeword.load()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SpeechPipeline")
        self._thread.start()
        log.info(
            f"SpeechPipeline started "
            f"(wake-word={'enabled' if self._wakeword else 'disabled'})"
        )

    def stop(self) -> None:
        self._stop_event.set()
        self._active = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._mic.close()
        log.info("SpeechPipeline stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        waiting_for_wakeword = self._wakeword is not None
        pre_buffer: list[bytes] = []
        speech_buffer: list[bytes] = []
        speech_streak = 0
        silence_streak = 0
        recording = False
        wake_idle_chunks = 0
        startup_chunks = 0
        startup_max_rms = 0.0

        while not self._stop_event.is_set():
            try:
                chunk = self._mic.read_chunk()
            except Exception as e:
                log.error(f"Microphone read error: {e}")
                self._event_bus.publish(EVENT_STT_ERROR, {"error": str(e)})
                self._active = False  # allow restart via start()
                break

            if startup_chunks <= 80:
                if startup_chunks < 80:
                    startup_max_rms = max(startup_max_rms, _rms(chunk))
                elif startup_max_rms < 5.0:
                    log.warning(f"Microphone delivers silence (max RMS={startup_max_rms:.1f} over first 5s)")
                    self._event_bus.publish(EVENT_STT_ERROR, {
                        "error": "Microphone delivers silence — check mic_device in config.yaml"
                    })
                startup_chunks += 1

            # ---- Phase 1: wait for wake word ----
            if waiting_for_wakeword:
                if self._wakeword.process_chunk(chunk):
                    waiting_for_wakeword = False
                    pre_buffer.clear()
                    speech_streak = 0
                    silence_streak = 0
                    wake_idle_chunks = 0
                    self._state_manager.set_state(AppState.LISTENING)
                    from app.stt.wakeword_service import EVENT_WAKE_WORD_DETECTED
                    self._event_bus.publish(EVENT_WAKE_WORD_DETECTED, {})
                    log.info("Wake word detected — now recording")
                continue

            # ---- Phase 2: VAD → record ----
            is_speech = _rms(chunk) > self._silence_threshold

            if not recording:
                pre_buffer.append(chunk)
                if len(pre_buffer) > _PRE_SPEECH_BUFFER:
                    pre_buffer.pop(0)

                speech_streak = (speech_streak + 1) if is_speech else max(0, speech_streak - 1)

                if speech_streak >= _SPEECH_CHUNKS_MIN:
                    recording = True
                    silence_streak = 0
                    speech_buffer = list(pre_buffer)
                    log.debug("Speech detected — recording")
                elif self._wakeword is not None:
                    wake_idle_chunks += 1
                    if wake_idle_chunks >= _WAKE_LISTEN_TIMEOUT:
                        log.info("No speech after wake word — re-arming")
                        pre_buffer.clear()
                        speech_streak = 0
                        self._wakeword.reset()
                        waiting_for_wakeword = True
                        self._state_manager.set_state(AppState.IDLE)
            else:
                speech_buffer.append(chunk)
                silence_streak = (silence_streak + 1) if not is_speech else 0

                if silence_streak >= _SILENCE_CHUNKS_END:
                    recording = False
                    speech_streak = 0
                    pre_buffer.clear()
                    self._state_manager.set_state(AppState.THINKING)
                    self._transcribe(speech_buffer)
                    speech_buffer = []

                    # Re-arm wake word gate for next command
                    if self._wakeword is not None:
                        self._wakeword.reset()
                        waiting_for_wakeword = True

        self._state_manager.set_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def _transcribe(self, audio_chunks: list[bytes]) -> None:
        try:
            audio_float = _bytes_to_float32(b"".join(audio_chunks))
            text = self._whisper.transcribe(audio_float)
            if text:
                log.info(f"Recognized: '{text}'")
                self._event_bus.publish(EVENT_SPEECH_RECOGNIZED, {"text": text})
            else:
                log.info("STT returned empty — nothing recognized")
                self._event_bus.publish(EVENT_STT_EMPTY, {})
        except Exception as e:
            log.error(f"Transcription error: {e}")
            self._event_bus.publish(EVENT_STT_ERROR, {"error": str(e)})
        finally:
            self._state_manager.set_state(AppState.IDLE)

    @property
    def is_active(self) -> bool:
        return self._active
