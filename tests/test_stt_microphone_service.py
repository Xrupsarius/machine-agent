import pytest
from unittest.mock import MagicMock, patch
from app.stt.microphone_service import MicrophoneService, SAMPLE_RATE, CHUNK_SIZE


@pytest.fixture
def mock_pa():
    with patch("app.stt.microphone_service.pyaudio.PyAudio") as MockPA:
        pa = MagicMock()
        stream = MagicMock()
        stream.read.return_value = b"\x00" * (CHUNK_SIZE * 2)
        pa.open.return_value = stream
        MockPA.return_value = pa
        yield pa, stream


def test_not_open_initially(mock_pa):
    svc = MicrophoneService()
    assert not svc.is_open()


def test_open_creates_stream(mock_pa):
    pa, _ = mock_pa
    svc = MicrophoneService()
    svc.open()
    assert svc.is_open()
    pa.open.assert_called_once()


def test_open_is_idempotent(mock_pa):
    pa, _ = mock_pa
    svc = MicrophoneService()
    svc.open()
    svc.open()
    assert pa.open.call_count == 1


def test_close_closes_stream(mock_pa):
    _, stream = mock_pa
    svc = MicrophoneService()
    svc.open()
    svc.close()
    assert not svc.is_open()
    stream.close.assert_called_once()


def test_close_when_not_open_does_nothing(mock_pa):
    svc = MicrophoneService()
    svc.close()   # should not raise


def test_read_chunk_returns_bytes(mock_pa):
    svc = MicrophoneService()
    svc.open()
    data = svc.read_chunk()
    assert isinstance(data, bytes)
    assert len(data) == CHUNK_SIZE * 2


def test_read_chunk_raises_when_not_open(mock_pa):
    svc = MicrophoneService()
    with pytest.raises(RuntimeError, match="not open"):
        svc.read_chunk()


def test_sample_rate_property(mock_pa):
    svc = MicrophoneService(sample_rate=16000)
    assert svc.sample_rate == 16000


def test_chunk_size_property(mock_pa):
    svc = MicrophoneService(chunk_size=512)
    assert svc.chunk_size == 512


def test_open_uses_correct_sample_rate(mock_pa):
    pa, _ = mock_pa
    svc = MicrophoneService(sample_rate=22050)
    svc.open()
    call_kwargs = pa.open.call_args.kwargs
    assert call_kwargs["rate"] == 22050
