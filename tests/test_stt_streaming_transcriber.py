import numpy as np

from app.stt.streaming_transcriber import LocalAgreement, StreamingTranscriber, _common_prefix


def test_common_prefix_basic():
    assert _common_prefix(["a", "b", "c"], ["a", "b", "x"]) == ["a", "b"]


def test_common_prefix_empty():
    assert _common_prefix([], ["a"]) == []


def test_first_hypothesis_is_all_interim():
    la = LocalAgreement()
    committed, interim = la.update(["привет", "мир"])
    assert committed == []
    assert interim == ["привет", "мир"]


def test_word_commits_after_two_agreements():
    la = LocalAgreement()
    la.update(["привет", "мир"])
    committed, interim = la.update(["привет", "мир"])
    assert committed == ["привет", "мир"]
    assert interim == []


def test_divergent_tail_stays_interim():
    la = LocalAgreement()
    la.update(["привет", "дорогой"])
    committed, interim = la.update(["привет", "мир"])
    assert committed == ["привет"]
    assert "мир" in interim


def test_committed_grows_monotonically():
    la = LocalAgreement()
    la.update(["цель"])
    la.update(["цель", "урока"])
    committed, _ = la.update(["цель", "урока"])
    assert committed[:2] == ["цель", "урока"]


def test_finalize_returns_latest_hypothesis_and_resets():
    la = LocalAgreement()
    la.update(["цель", "урока"])
    la.update(["цель", "урока", "химия"])
    final = la.finalize()
    assert final == "цель урока химия"
    assert la.committed == []


def test_finalize_empty():
    la = LocalAgreement()
    assert la.finalize() == ""


class _FakeWhisper:
    def __init__(self, outputs):
        self._outputs = list(outputs)

    def transcribe(self, audio, language="ru", vad_filter=True):
        return self._outputs.pop(0) if self._outputs else ""


def test_streaming_transcriber_feed_and_finalize():
    whisper = _FakeWhisper(["цель", "цель урока", "цель урока химия"])
    st = StreamingTranscriber(whisper)
    audio = np.zeros(1600, dtype=np.float32)

    st.feed(audio)
    committed, _ = st.feed(audio)
    assert "цель" in committed

    final = st.finalize(audio)
    assert final == "цель урока химия"


def test_streaming_transcriber_reset():
    whisper = _FakeWhisper(["раз", "раз"])
    st = StreamingTranscriber(whisper)
    audio = np.zeros(1600, dtype=np.float32)
    st.feed(audio)
    st.feed(audio)
    st.reset()
    assert st.finalize() == ""
