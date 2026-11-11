"""Decode local audio without trimming its timeline; normalize to mono 16 kHz."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd, isfinite
from pathlib import Path
import shutil
import subprocess
import warnings
import wave

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from .errors import ASRError

SAMPLE_RATE = 16_000


@dataclass
class AudioData:
    samples: np.ndarray
    metadata: dict


def _validate_source(path: Path, max_duration: float, max_size_mb: float) -> Path:
    if not isfinite(max_duration) or not 0 < max_duration <= 600:
        raise ASRError("max-duration phải lớn hơn 0 và không quá 600 giây.")
    if not isfinite(max_size_mb) or not 0 < max_size_mb <= 100:
        raise ASRError("max-size-mb phải lớn hơn 0 và không quá 100 MiB.")
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ASRError(f"Không tìm thấy file audio: {path}")
    if path.suffix.lower() not in {".wav", ".mp3"}:
        raise ASRError("Bản đầu chỉ nhận file WAV hoặc MP3.")
    size = path.stat().st_size
    if size == 0:
        raise ASRError("File audio rỗng.")
    if size > max_size_mb * 1024 * 1024:
        raise ASRError(f"File vượt giới hạn {max_size_mb:g} MiB.")
    return path


def _read_wav(path: Path) -> tuple[int, np.ndarray]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", wavfile.WavFileWarning)
            rate, values = wavfile.read(path)
        return rate, values
    except (ValueError, EOFError, OSError, wavfile.WavFileWarning) as exc:
        raise ASRError(f"Không đọc được WAV hợp lệ: {exc}") from exc


def _decode_with_ffmpeg(path: Path, max_duration: float) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ASRError(
            "Đọc MP3 cần ffmpeg trong PATH. Cài ffmpeg hoặc thử file WAV trước."
        )
    command = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-t", str(max_duration + 1),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1",
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ASRError(f"Không thể giải mã audio bằng ffmpeg: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise ASRError(f"ffmpeg không đọc được audio: {detail}")
    if len(result.stdout) % 2:
        raise ASRError("ffmpeg trả audio PCM không hợp lệ.")
    return np.frombuffer(result.stdout, dtype="<i2")


def load_audio(path: Path, *, max_duration: float = 600, max_size_mb: float = 100) -> AudioData:
    path = _validate_source(path, max_duration, max_size_mb)
    if path.suffix.lower() == ".wav":
        rate, raw = _read_wav(path)
        channels = 1 if raw.ndim == 1 else raw.shape[1] if raw.ndim == 2 else 0
        if channels == 0 or rate <= 0:
            raise ASRError("Audio có số kênh hoặc sample rate không hợp lệ.")
        original_rate, original_channels = rate, channels
        decoder = "scipy.io.wavfile"
    else:
        raw = _decode_with_ffmpeg(path, max_duration)
        rate, channels = SAMPLE_RATE, 1
        # ffmpeg normalizes directly; don't invent the source sample rate/channels.
        original_rate = original_channels = None
        decoder = "ffmpeg"
    if raw.size == 0:
        raise ASRError("File không có mẫu audio để xử lý.")
    duration = len(raw) / rate
    if duration > max_duration:
        raise ASRError(f"Audio dài {duration:.2f}s, vượt giới hạn {max_duration:g}s.")
    if raw.dtype == np.uint8:
        samples = (raw.astype(np.float32) - 128) / 128
    elif np.issubdtype(raw.dtype, np.signedinteger):
        samples = raw.astype(np.float32) / float(2 ** (raw.dtype.itemsize * 8 - 1))
    elif np.issubdtype(raw.dtype, np.floating):
        samples = raw.astype(np.float32)
    else:
        raise ASRError(f"Kiểu mẫu audio chưa được hỗ trợ: {raw.dtype}")
    if not np.isfinite(samples).all():
        raise ASRError("Audio có giá trị NaN/Infinity.")
    if channels > 1:
        samples = samples.mean(axis=1)
    notes = []
    if np.any(np.abs(samples) > 1):
        notes.append("source_amplitude_out_of_range_clipped")
        samples = np.clip(samples, -1, 1)
    if rate != SAMPLE_RATE:
        divisor = gcd(rate, SAMPLE_RATE)
        samples = resample_poly(samples, SAMPLE_RATE // divisor, rate // divisor)
    # The exact quantized signal used for inference is also saved to normalized.wav.
    pcm = np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2")
    samples = pcm.astype(np.float32) / 32768
    duration = len(samples) / SAMPLE_RATE
    metadata = {
        "source_path": str(path), "source_bytes": path.stat().st_size,
        "source_sample_rate": original_rate, "source_channels": original_channels,
        "decoder": decoder, "sample_rate": SAMPLE_RATE, "channels": 1,
        "duration_seconds": duration, "sample_count": len(samples),
        "peak": float(np.max(np.abs(samples))),
        "rms": float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))),
        "digital_silence": not bool(np.any(samples)),
        "warnings": notes,
    }
    return AudioData(samples=samples, metadata=metadata)


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())


def write_waveform(path: Path, samples: np.ndarray) -> None:
    """Small min/max SVG envelope; a click cannot disappear by downsampling points."""
    width, height = 1000, 220
    columns = min(width, len(samples))
    edges = np.linspace(0, len(samples), columns + 1, dtype=int)
    lines = []
    for i in range(columns):
        block = samples[edges[i]:edges[i + 1]]
        x = (i + 0.5) * width / columns
        top = height / 2 - float(block.max()) * 95
        bottom = height / 2 - float(block.min()) * 95
        lines.append(f'<path d="M{x:.2f},{top:.2f}V{bottom:.2f}"/>')
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"'
        ' role="img" aria-label="Audio waveform at mono 16 kHz">'
        '<rect width="100%" height="100%" fill="#0f172a"/>'
        f'<path d="M0,{height/2}H{width}" stroke="#475569"/>'
        '<g stroke="#38bdf8" stroke-width="1">' + "".join(lines) + '</g></svg>\n',
        encoding="utf-8",
    )
