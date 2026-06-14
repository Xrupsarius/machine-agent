import time
from unittest.mock import MagicMock

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.stt.dictation_controller import (
    DictationController,
    EVENT_DICTATION_STARTED,
    EVENT_DICTATION_STOPPED,
    _rms,
    _to_float32,
)

import numpy as np

from app.stt.dictation_controller import EVENT_DICTATION_COMMITTED

_SILENT_CHUNK = b"\x00" * 2560
_LOUD_CHUNK = np.full(1280, 2000, dtype=np.int16).tobytes()


def _make_mic(chunk=_SILENT_CHUNK):
    mic = MagicMock()
    mic.chunk_size = 1280
    mic.sample_rate = 16000
    mic.read_chunk.return_value = chunk
    return mic


def _make_controller(mic=None, whisper=None, **kwargs):
    bus = EventBus()
    sm = StateManager(bus)
    mic = mic or _make_mic()
    whisper = whisper or MagicMock()
    calls = {"paused": 0, "resumed": 0}
    params = dict(silence_threshold=500, chunk_seconds=0.7, silence_seconds=1.0)
    params.update(kwargs)
    ctrl = DictationController(
        mic, whisper, sm, bus,
        pause_listening=lambda: calls.__setitem__("paused", calls["paused"] + 1),
        resume_listening=lambda: calls.__setitem__("resumed", calls["resumed"] + 1),
        **params,
    )
    return ctrl, bus, sm, mic, whisper, calls


def test_rms_silent():
    assert _rms(_SILENT_CHUNK) == 0.0


def test_to_float32_range():
    arr = _to_float32(_SILENT_CHUNK)
    assert arr.dtype.name == "float32"
    assert arr.max() <= 1.0


def test_start_sets_state_and_pauses_listening():
    ctrl, bus, sm, mic, whisper, calls = _make_controller()
    started = []
    bus.subscribe(EVENT_DICTATION_STARTED, lambda _: started.append(1))

    ctrl.start()
    try:
        assert ctrl.is_active
        assert calls["paused"] == 1
        assert sm.state == AppState.DICTATING
        assert started == [1]
        mic.open.assert_called_once()
        whisper.load.assert_called_once()
    finally:
        ctrl.stop()


def test_stop_resumes_listening_and_resets_state():
    ctrl, bus, sm, mic, whisper, calls = _make_controller()
    stopped = []
    bus.subscribe(EVENT_DICTATION_STOPPED, lambda _: stopped.append(1))

    ctrl.start()
    time.sleep(0.05)
    ctrl.stop()

    assert not ctrl.is_active
    assert calls["resumed"] == 1
    assert sm.state == AppState.IDLE
    assert stopped == [1]
    mic.close.assert_called_once()


def test_start_twice_is_noop():
    ctrl, _, _, _, _, calls = _make_controller()
    ctrl.start()
    try:
        ctrl.start()
        assert calls["paused"] == 1
    finally:
        ctrl.stop()


def test_stop_when_inactive_is_noop():
    ctrl, _, _, _, _, calls = _make_controller()
    ctrl.stop()
    assert calls["resumed"] == 0


def test_toggle_flips_active():
    ctrl, _, _, _, _, _ = _make_controller()
    ctrl.toggle()
    assert ctrl.is_active
    ctrl.toggle()
    assert not ctrl.is_active


def test_mic_open_failure_resumes_listening():
    mic = _make_mic()
    mic.open.side_effect = OSError("no mic")
    ctrl, _, sm, _, _, calls = _make_controller(mic=mic)

    ctrl.start()
    assert not ctrl.is_active
    assert calls["paused"] == 1
    assert calls["resumed"] == 1


def test_hard_cap_finalizes_without_silence():
    whisper = MagicMock()
    whisper.transcribe.return_value = "привет мир"
    mic = _make_mic(_LOUD_CHUNK)
    ctrl, bus, _, _, _, _ = _make_controller(
        mic=mic, whisper=whisper, max_segment_seconds=0.5,
        calibration_seconds=0.0, noise_factor=0.0,
    )
    committed = []
    bus.subscribe(EVENT_DICTATION_COMMITTED, lambda p: committed.append(p["text"]))

    ctrl.start()
    time.sleep(0.6)
    ctrl.stop()

    assert committed, "segment should force-finalize once it exceeds the cap"


def test_calibration_raises_threshold_for_noisy_mic():
    mic = _make_mic(_LOUD_CHUNK)
    ctrl, _, _, _, _, _ = _make_controller(
        mic=mic, silence_threshold=500, noise_factor=1.4, calibration_seconds=0.3,
    )
    ctrl.start()
    time.sleep(0.1)
    threshold = ctrl._silence_threshold
    ctrl.stop()

    assert threshold > 500


def test_calibration_keeps_floor_for_quiet_mic():
    ctrl, _, _, _, _, _ = _make_controller(silence_threshold=500, calibration_seconds=0.3)
    ctrl.start()
    time.sleep(0.1)
    threshold = ctrl._silence_threshold
    ctrl.stop()

    assert threshold == 500
