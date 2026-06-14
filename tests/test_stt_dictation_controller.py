import time
from unittest.mock import MagicMock

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.stt.dictation_controller import (
    DictationController,
    EVENT_DICTATION_STARTED,
    EVENT_DICTATION_STOPPED,
    EVENT_DICTATION_COMMAND,
    _rms,
    _split_directive,
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


def test_split_directive_plain_text_has_no_command():
    body, local, agent = _split_directive("привет мир как дела")
    assert (local, agent) == (None, None)
    assert body == "привет мир как дела"


def test_split_directive_marker_extracts_submit():
    body, local, agent = _split_directive("привет мир омнис отправь")
    assert local == "submit" and agent is None
    assert body == "привет мир"


def test_split_directive_marker_only():
    body, local, agent = _split_directive("Омнис, отправь.")
    assert local == "submit" and agent is None
    assert body == ""


def test_split_directive_newline_and_delete():
    assert _split_directive("омнис новая строка")[1] == "newline"
    assert _split_directive("омнис сотри последнее")[1] == "delete_word"
    assert _split_directive("омнис стоп")[1] == "stop"


def test_split_directive_routes_unknown_to_agent():
    body, local, agent = _split_directive("заметка омнис открой браузер")
    assert local is None
    assert agent == "открой браузер"
    assert body == "заметка"


def test_split_directive_no_marker_keeps_word():
    body, local, agent = _split_directive("отправь письмо другу")
    assert (local, agent) == (None, None)
    assert body == "отправь письмо другу"


def test_commit_final_injects_body():
    typed = []
    ctrl, _, _, _, _, _ = _make_controller(inject_text=typed.append)
    ctrl._commit_final("привет мир")
    assert typed == ["привет мир"]


def test_commit_final_runs_submit_and_emits_command():
    typed = []
    keys = []
    commands = []
    ctrl, bus, _, _, _, _ = _make_controller(
        inject_text=typed.append, run_key=keys.append,
    )
    bus.subscribe(EVENT_DICTATION_COMMAND, lambda p: commands.append(p["command"]))
    ctrl._commit_final("сохрани заметку омнис отправь")
    assert typed == ["сохрани заметку"]
    assert keys == ["enter"]
    assert commands == ["submit"]


def test_commit_final_command_only_does_not_inject():
    typed = []
    keys = []
    ctrl, _, _, _, _, _ = _make_controller(
        inject_text=typed.append, run_key=keys.append,
    )
    ctrl._commit_final("омнис отправь")
    assert typed == []
    assert keys == ["enter"]


def test_commit_final_routes_agent_command():
    typed = []
    sent = []
    ctrl, _, _, _, _, _ = _make_controller(
        inject_text=typed.append, run_command=sent.append,
    )
    ctrl._commit_final("заметка омнис открой браузер")
    assert typed == ["заметка"]
    assert sent == ["открой браузер"]
