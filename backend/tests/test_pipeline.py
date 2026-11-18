import json

import numpy as np
import pytest
from scipy.io import wavfile

from asr_engine.app.errors import ASRError
from asr_engine.app.pipeline import transcribe_file
from asr_engine.app.recognizer import validate_segments
from asr_engine.cli import main


def test_digital_silence_does_not_download_or_claim_model_inference(tmp_path, monkeypatch):
    source = tmp_path / "silence.wav"
    wavfile.write(source, 16_000, np.zeros(16_000, dtype=np.int16))
    def must_not_load(*args, **kwargs):
        raise AssertionError("Digital silence should not load a model")
    monkeypatch.setattr("asr_engine.app.pipeline.WhisperRecognizer", must_not_load)
    result, output = transcribe_file(source, tmp_path / "outputs")
    assert result["text"] == ""
    assert result["segments"] == []
    assert result["model"] is None
    assert result["timings"]["inference_seconds"] == 0
    assert json.loads((output / "run.json").read_text())["status"] == "ready"


def test_model_failure_is_saved_and_never_creates_successful_transcript(tmp_path, monkeypatch):
    source = tmp_path / "source.wav"
    wavfile.write(source, 16_000, np.full(16_000, 2000, dtype=np.int16))
    def unavailable(*args, **kwargs):
        raise ASRError("checkpoint unavailable")
    monkeypatch.setattr("asr_engine.app.pipeline.WhisperRecognizer", unavailable)
    with pytest.raises(ASRError, match="checkpoint unavailable"):
        transcribe_file(source, tmp_path / "outputs", local_files_only=True)
    output = next((tmp_path / "outputs").iterdir())
    assert json.loads((output / "run.json").read_text())["status"] == "failed"
    assert not (output / "transcript.json").exists()
    assert not (output / "transcript.txt").exists()
    assert (output / "normalized.wav").exists()


def test_repeated_runs_keep_previous_results(tmp_path):
    source = tmp_path / "source.wav"
    wavfile.write(source, 16_000, np.zeros(16_000, dtype=np.int16))
    _, first = transcribe_file(source, tmp_path / "outputs")
    original = (first / "transcript.json").read_bytes()
    _, second = transcribe_file(source, tmp_path / "outputs")
    assert first != second
    assert (first / "transcript.json").read_bytes() == original


def test_successful_model_result_preserves_vietnamese_and_provenance(tmp_path, monkeypatch):
    source = tmp_path / "source.wav"
    wavfile.write(source, 16_000, np.full(16_000, 2000, dtype=np.int16))

    class ModelDouble:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio):
            return {
                "text": "Hôm nay học trí tuệ nhân tạo.",
                "segments": [{"segment_id": 1, "start": 0, "end": 1, "text": "Hôm nay học trí tuệ nhân tạo."}],
                "model": {"id": "explicit-test-double", "resolved_revision": "test-revision"},
                "timings": {"model_load_seconds": 0, "inference_seconds": 0.1},
            }

    monkeypatch.setattr("asr_engine.app.pipeline.WhisperRecognizer", ModelDouble)
    result, output = transcribe_file(source, tmp_path / "outputs")
    saved = json.loads((output / "transcript.json").read_text(encoding="utf-8"))
    assert saved["text"] == result["text"]
    assert (output / "transcript.txt").read_text(encoding="utf-8").strip() == result["text"]
    assert saved["model"]["resolved_revision"] == "test-revision"
    assert len(saved["audio"]["source_sha256"]) == 64
    assert saved["segments"][0]["end"] == 1
    assert json.loads((output / "run.json").read_text())["status"] == "ready"


@pytest.mark.parametrize("start,end", [(float("nan"), 1), (0, float("inf")), (-1, 1), (1, 0), (0, 10)])
def test_invalid_timestamps_are_rejected(start, end):
    with pytest.raises(ASRError):
        validate_segments([{"text": "xin chào", "start": start, "end": end}], 2)


def test_model_quantization_overhang_is_bounded():
    result = validate_segments([{"text": "xin chào", "start": 0.4, "end": 2.1}], 2)
    assert result[0]["end"] == 2


def test_cli_bad_path_is_actionable_and_returns_nonzero(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "missing.wav")]) == 2
    captured = capsys.readouterr()
    assert "Không tìm thấy" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_cli_prepare_and_silence_output_are_machine_readable(tmp_path, capsys):
    source = tmp_path / "source.wav"
    wavfile.write(source, 16_000, np.zeros(8000, dtype=np.int16))
    assert main(["prepare", str(source), "--output-dir", str(tmp_path / "outputs")]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["status"] == "prepared"
    assert main(["transcribe", str(source), "--local-files-only", "--output-dir", str(tmp_path / "outputs")]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["status"] == "ready"
    assert info["text"] == ""
