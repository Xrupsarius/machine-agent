import ctypes
import glob
import logging
import os

import numpy as np
from faster_whisper import WhisperModel

log = logging.getLogger(__name__)

# Where CTranslate2 can find CUDA cuBLAS (libcublas.so.12). Ollama bundles it,
# so a GPU build works without a system-wide CUDA toolkit.
_CUDA_LIB_DIRS = (
    "/usr/local/lib/ollama/cuda_v12",
    os.path.expanduser("~/.local/lib/ollama/cuda_v12"),
    "/opt/cuda/lib64",
)


def _preload_cuda(lib_dir: str = "") -> bool:
    """Preload cuBLAS so CTranslate2's dlopen finds it without LD_LIBRARY_PATH."""
    candidates = [lib_dir] if lib_dir else []
    candidates += list(_CUDA_LIB_DIRS)
    for d in candidates:
        cublas = os.path.join(d, "libcublas.so.12")
        if not (d and os.path.exists(cublas)):
            continue
        try:
            for lt in glob.glob(os.path.join(d, "libcublasLt.so.12")):
                ctypes.CDLL(lt, mode=ctypes.RTLD_GLOBAL)
            ctypes.CDLL(cublas, mode=ctypes.RTLD_GLOBAL)
            log.info(f"Preloaded CUDA cuBLAS from {d}")
            return True
        except OSError as e:
            log.warning(f"CUDA preload from {d} failed: {e}")
    return False


class WhisperService:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 1,
        cuda_lib_dir: str = "",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._beam_size = beam_size
        self._cuda_lib_dir = cuda_lib_dir
        self._model: WhisperModel | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        if self._device.startswith("cuda"):
            _preload_cuda(self._cuda_lib_dir)
        log.info(
            f"Loading Whisper model '{self._model_name}' "
            f"(device={self._device}, compute={self._compute_type}, beam={self._beam_size})"
        )
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
            audio, language=language, vad_filter=vad_filter, beam_size=self._beam_size,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.debug(
            f"Transcribed: '{text}' "
            f"(lang={info.language}, prob={info.language_probability:.2f})"
        )
        return text

    def is_loaded(self) -> bool:
        return self._model is not None
