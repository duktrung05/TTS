from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import wave

import numpy as np
import pytest
from scipy.io import wavfile

from asr_engine.app.audio import load_audio, write_wav
from asr_engine.app.errors import ASRError
from asr_engine.app.pipeline import prepare_audio


def make_wav(path: Path, seconds=1.0, rate=48_000, channels=1):
    t = np.arange(round(seconds * rate)) / rate
    signal = (np.sin(2 * np.pi * 440 * t) * 8_000).astype(np.int16)
    if channels == 2:
        signal = np.column_stack((signal, signal // 2))
    wavfile.write(path, rate, signal)
    return path


def test_resample_stereo_long_audio_retains_end_and_duration(tmp_path):
    source = make_wav(tmp_path / "long.wav", seconds=35.2, channels=2)
    audio, output, _ = prepare_audio(source, tmp_path / "outputs")
    assert audio.samples.dtype == np.float32
    assert len(audio.samples) == round(35.2 * 16_000)
    assert np.max(np.abs(audio.samples[-16_000:])) > 0.05
    assert audio.metadata["source_sample_rate"] == 48_000
    assert audio.metadata["source_channels"] == 2
    with wave.open(str(output / "normalized.wav")) as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getframerate() == 16_000
        assert normalized.getnframes() == len(audio.samples)
    assert (output / "waveform.svg").read_text().startswith('<svg')
    assert len(audio.metadata["source_sha256"]) == 64


def test_normalized_wav_round_trip_matches_inference_signal(tmp_path):
    audio = load_audio(make_wav(tmp_path / "source.wav"))
    write_wav(tmp_path / "normalized.wav", audio.samples)
    reread = load_audio(tmp_path / "normalized.wav")
    np.testing.assert_array_equal(reread.samples, audio.samples)


@pytest.mark.parametrize("rate", [8_000, 16_000, 44_100, 48_000])
def test_resampling_keeps_duration_for_common_rates(tmp_path, rate):
    audio = load_audio(make_wav(tmp_path / "source.wav", seconds=0.75, rate=rate))
    assert audio.metadata["duration_seconds"] == pytest.approx(0.75, abs=1 / 16_000)


def test_rejects_bad_input_and_limits_before_model(tmp_path):
    with pytest.raises(ASRError, match="Không tìm thấy"):
        load_audio(tmp_path / "missing.wav")
    empty = tmp_path / "empty.wav"
    empty.touch()
    with pytest.raises(ASRError, match="rỗng"):
        load_audio(empty)
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not a wave file")
    with pytest.raises(ASRError, match="Không đọc được"):
        load_audio(corrupt)
    valid = make_wav(tmp_path / "valid.wav")
    with pytest.raises(ASRError, match="vượt giới hạn"):
        load_audio(valid, max_duration=0.5)
    with pytest.raises(ASRError, match="vượt giới hạn"):
        load_audio(valid, max_size_mb=0.001)
    for limit in [0, -1, float("nan"), float("inf"), 601]:
        with pytest.raises(ASRError, match="max-duration"):
            load_audio(valid, max_duration=limit)


def test_nonfinite_audio_cannot_reach_model(tmp_path):
    path = tmp_path / "nan.wav"
    wavfile.write(path, 16_000, np.array([0, float("nan"), 0], dtype=np.float32))
    with pytest.raises(ASRError, match="NaN"):
        load_audio(path)


def test_truncated_wav_cannot_be_reported_as_complete(tmp_path):
    path = make_wav(tmp_path / "truncated.wav")
    path.write_bytes(path.read_bytes()[:100])
    with pytest.raises(ASRError):
        load_audio(path)


@pytest.mark.parametrize("suffix", [".mp3", ".MP4"])
def test_media_reports_missing_ffmpeg(tmp_path, monkeypatch, suffix):
    path = tmp_path / f"source{suffix}"
    path.write_bytes(b"some media bytes")
    monkeypatch.setattr("asr_engine.app.audio.shutil.which", lambda _: None)
    with pytest.raises(ASRError, match="Cài ffmpeg"):
        load_audio(path)


@pytest.mark.parametrize("suffix", [".mp3", ".mp4"])
def test_ffmpeg_duration_guard_detects_decoded_limit(tmp_path, monkeypatch, suffix):
    path = tmp_path / f"source{suffix}"
    path.write_bytes(b"fake fixture, decoder is replaced below")
    monkeypatch.setattr("asr_engine.app.audio.shutil.which", lambda _: "/test/ffmpeg")
    monkeypatch.setattr(
        "asr_engine.app.audio.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"\0\0" * 32_000, stderr=b""),
    )
    with pytest.raises(ASRError, match="vượt giới hạn"):
        load_audio(path, max_duration=1)


@pytest.mark.parametrize(("stderr", "message"), [
    (b"Stream map '0:a:0' matches no streams.", "MP4 không có track âm thanh"),
    (b"moov atom not found", "ffmpeg không đọc được audio: moov atom not found"),
])
def test_mp4_distinguishes_missing_audio_from_corruption(tmp_path, monkeypatch, stderr, message):
    path = tmp_path / "source.mp4"
    path.write_bytes(b"decoder is replaced below")
    monkeypatch.setattr("asr_engine.app.audio.shutil.which", lambda _: "/test/ffmpeg")
    monkeypatch.setattr(
        "asr_engine.app.audio.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b"", stderr=stderr),
    )
    with pytest.raises(ASRError, match=message):
        load_audio(path)


def test_real_mp4_keeps_audio_offset_on_video_timeline(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg executable is required")

    video_only = tmp_path / "video_only.mp4"
    subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=32x32:d=2",
        "-c:v", "mpeg4", str(video_only),
    ], check=True, timeout=30)
    with pytest.raises(ASRError, match="MP4 không có track âm thanh"):
        load_audio(video_only)

    source = make_wav(tmp_path / "source.wav", channels=2)
    mp4 = tmp_path / "delayed.mp4"
    subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-i", str(video_only),
        "-itsoffset", "0.75", "-i", str(source), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", str(mp4),
    ], check=True, timeout=30)
    audio, output, _ = prepare_audio(mp4, tmp_path / "outputs")
    assert audio.metadata["duration_seconds"] == pytest.approx(1.75, abs=0.05)
    assert np.max(np.abs(audio.samples[:10_400])) < 0.001
    assert np.max(np.abs(audio.samples[14_400:])) > 0.05
    with wave.open(str(output / "normalized.wav")) as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getframerate() == 16_000
        assert normalized.getnframes() == len(audio.samples)
    with pytest.raises(ASRError, match="vượt giới hạn"):
        load_audio(mp4, max_duration=1)
