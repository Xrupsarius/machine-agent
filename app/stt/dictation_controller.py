import logging
import threading
import time
from typing import Callable

import numpy as np

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.stt.command_set import CommandSet
from app.stt.microphone_service import MicrophoneService
from app.stt.streaming_transcriber import StreamingTranscriber
from app.stt.whisper_service import WhisperService

log = logging.getLogger(__name__)

EVENT_DICTATION_PARTIAL = "dictation.partial"
EVENT_DICTATION_COMMITTED = "dictation.committed"
EVENT_DICTATION_STARTED = "dictation.started"
EVENT_DICTATION_STOPPED = "dictation.stopped"
EVENT_DICTATION_COMMAND = "dictation.command"


def _rms(audio_bytes: bytes) -> float:
    if not audio_bytes:
        return 0.0
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(audio ** 2)))


def _to_float32(audio_bytes: bytes) -> np.ndarray:
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    return audio / 32768.0


class DictationController:
    """
    Live dictation session (Phase 1): streams microphone audio through the
    StreamingTranscriber and emits committed/interim text as the user speaks.

    Owns the microphone for the duration of the session; the command pipeline
    is paused via the injected callbacks so only one consumer reads the mic.
    """

    def __init__(
        self,
        mic: MicrophoneService,
        whisper: WhisperService,
        state_manager: StateManager,
        event_bus: EventBus,
        pause_listening: Callable[[], None],
        resume_listening: Callable[[], None],
        inject_text: Callable[[str], None] | None = None,
        run_key: Callable[[str], None] | None = None,
        run_command: Callable[[str], None] | None = None,
        command_set: CommandSet | None = None,
        silence_threshold: float = 500.0,
        chunk_seconds: float = 0.7,
        silence_seconds: float = 1.0,
        max_segment_seconds: float = 15.0,
        noise_factor: float = 1.4,
        calibration_seconds: float = 0.5,
    ) -> None:
        self._mic = mic
        self._whisper = whisper
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._pause_listening = pause_listening
        self._resume_listening = resume_listening
        self._inject_text = inject_text
        self._run_key = run_key
        self._run_command = run_command
        self._command_set = command_set or CommandSet.from_config("ru")
        self._configured_threshold = silence_threshold
        self._silence_threshold = silence_threshold
        self._chunk_seconds = chunk_seconds
        self._noise_factor = noise_factor

        chunk_duration = mic.chunk_size / mic.sample_rate
        self._silence_chunks = max(1, int(silence_seconds / chunk_duration))
        self._calibration_chunks = max(1, int(calibration_seconds / chunk_duration))
        self._min_bytes = int(0.3 * mic.sample_rate) * 2
        self._max_bytes = int(max_segment_seconds * mic.sample_rate) * 2

        self._transcriber = StreamingTranscriber(whisper, language=self._command_set.language)
        self._lock = threading.Lock()
        self._segment = bytearray()
        self._silence_streak = 0
        self._has_speech = False
        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._decode_thread: threading.Thread | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        if self._active:
            return
        self._pause_listening()
        try:
            self._mic.open()
        except Exception as e:
            log.error(f"Dictation: microphone unavailable: {e}")
            self._resume_listening()
            return
        self._whisper.load()
        self._transcriber.reset()
        self._silence_threshold = self._configured_threshold
        with self._lock:
            self._segment = bytearray()
            self._silence_streak = 0
            self._has_speech = False
        self._stop_event.clear()
        self._active = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name="DictationCapture")
        self._decode_thread = threading.Thread(target=self._decode_loop, daemon=True, name="DictationDecode")
        self._capture_thread.start()
        self._decode_thread.start()
        self._state_manager.set_state(AppState.DICTATING)
        self._event_bus.publish(EVENT_DICTATION_STARTED, {})
        log.info("Dictation started")

    def stop(self) -> None:
        if not self._active:
            return
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=3)
            self._capture_thread = None
        if self._decode_thread:
            self._decode_thread.join(timeout=5)
            self._decode_thread = None
        with self._lock:
            tail = bytes(self._segment)
            self._segment = bytearray()
        if len(tail) >= self._min_bytes:
            final = self._transcriber.finalize(_to_float32(tail))
            self._commit_final(final)
        self._active = False
        self._mic.close()
        self._event_bus.publish(EVENT_DICTATION_STOPPED, {})
        self._state_manager.set_state(AppState.IDLE)
        self._resume_listening()
        log.info("Dictation stopped")

    def toggle(self) -> None:
        if self._active:
            self.stop()
        else:
            self.start()

    def _calibrate(self) -> None:
        samples: list[float] = []
        for _ in range(self._calibration_chunks):
            if self._stop_event.is_set():
                return
            try:
                chunk = self._mic.read_chunk()
            except Exception as e:
                log.error(f"Dictation calibration error: {e}")
                return
            samples.append(_rms(chunk))
            with self._lock:
                self._segment.extend(chunk)
        if samples:
            floor = float(np.median(samples))
            self._silence_threshold = max(self._configured_threshold, floor * self._noise_factor)
            log.info(
                f"Dictation: silence threshold {self._silence_threshold:.0f} "
                f"(noise floor {floor:.0f}, configured {self._configured_threshold:.0f})"
            )

    def _capture_loop(self) -> None:
        self._calibrate()
        while not self._stop_event.is_set():
            try:
                chunk = self._mic.read_chunk()
            except Exception as e:
                log.error(f"Dictation capture error: {e}")
                break
            speech = _rms(chunk) > self._silence_threshold
            with self._lock:
                self._segment.extend(chunk)
                if speech:
                    self._silence_streak = 0
                    self._has_speech = True
                else:
                    self._silence_streak += 1

    def _decode_loop(self) -> None:
        last_decode = 0.0
        while not self._stop_event.is_set():
            time.sleep(0.15)
            with self._lock:
                snapshot = bytes(self._segment)
                silence = self._silence_streak
                has_speech = self._has_speech
            if not has_speech or len(snapshot) < self._min_bytes:
                continue

            now = time.monotonic()
            if silence >= self._silence_chunks or len(snapshot) >= self._max_bytes:
                self._finalize_segment(snapshot)
                last_decode = now
            elif now - last_decode >= self._chunk_seconds:
                self._emit_partial(snapshot)
                last_decode = now

    def _emit_partial(self, snapshot: bytes) -> None:
        try:
            committed, interim = self._transcriber.feed(_to_float32(snapshot))
            self._event_bus.publish(
                EVENT_DICTATION_PARTIAL, {"committed": committed, "interim": interim}
            )
        except Exception as e:
            log.error(f"Dictation decode error: {e}")

    def _finalize_segment(self, snapshot: bytes) -> None:
        try:
            final = self._transcriber.finalize(_to_float32(snapshot))
        except Exception as e:
            log.error(f"Dictation finalize error: {e}")
            final = ""
        with self._lock:
            self._segment = bytearray()
            self._silence_streak = 0
            self._has_speech = False
        self._commit_final(final)

    def _commit_final(self, final: str) -> None:
        if not final:
            return
        body, local_command, agent_command = self._command_set.parse(final)
        if body:
            self._event_bus.publish(EVENT_DICTATION_COMMITTED, {"text": body})
            if self._inject_text is not None:
                try:
                    self._inject_text(body)
                except Exception as e:
                    log.error(f"Dictation inject error: {e}")
        if local_command:
            self._run_local(local_command)
            self._event_bus.publish(EVENT_DICTATION_COMMAND, {"command": local_command})
        elif agent_command:
            if self._run_command is not None:
                try:
                    self._run_command(agent_command)
                except Exception as e:
                    log.error(f"Dictation command error: {e}")
            self._event_bus.publish(
                EVENT_DICTATION_COMMAND, {"command": "agent", "text": agent_command}
            )

    _KEY_FOR_COMMAND = {"submit": "enter", "newline": "newline", "delete_word": "delete_word"}

    def _run_local(self, name: str) -> None:
        if name == "stop":
            threading.Thread(target=self.stop, daemon=True, name="DictationStop").start()
            return
        key = self._KEY_FOR_COMMAND.get(name)
        if key and self._run_key is not None:
            try:
                self._run_key(key)
            except Exception as e:
                log.error(f"Dictation key '{key}' error: {e}")
