from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from .audio import load_audio, write_wav, write_waveform
from .errors import ASRError
from .recognizer import DEFAULT_MODEL, WhisperRecognizer


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare_audio(source: Path, output_root: Path, *, max_duration: float = 600, max_size_mb: float = 100):
    started = time.perf_counter()
    audio = load_audio(source, max_duration=max_duration, max_size_mb=max_size_mb)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    output_dir = output_root.expanduser().resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    source_path = Path(audio.metadata["source_path"])
    with source_path.open("rb") as stream:
        audio.metadata["source_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    write_wav(output_dir / "normalized.wav", audio.samples)
    write_waveform(output_dir / "waveform.svg", audio.samples)
    save_json(output_dir / "audio.json", audio.metadata)
    elapsed = time.perf_counter() - started
    save_json(output_dir / "run.json", {"run_id": run_id, "status": "prepared", "prepare_seconds": elapsed})
    return audio, output_dir, elapsed


def transcribe_file(
    source: Path, output_root: Path, *, model_id: str = DEFAULT_MODEL,
    revision: str = "main", device: str = "auto", local_files_only: bool = False,
    threads: int = 4, max_duration: float = 600, max_size_mb: float = 100,
) -> tuple[dict, Path]:
    started = time.perf_counter()
    audio, output_dir, prepare_seconds = prepare_audio(source, output_root, max_duration=max_duration, max_size_mb=max_size_mb)
    run = {
        "run_id": output_dir.name, "status": "processing", "requested_model": model_id,
        "requested_revision": revision, "prepare_seconds": prepare_seconds,
    }
    save_json(output_dir / "run.json", run)
    try:
        if audio.metadata["digital_silence"]:
            result = {
                "text": "", "segments": [], "language_code": None,
                "duration_seconds": audio.metadata["duration_seconds"], "model": None,
                "timings": {"model_load_seconds": 0, "inference_seconds": 0},
                "warnings": ["digital_silence: all normalized samples are zero; model was not run"],
            }
        else:
            recognizer = WhisperRecognizer(model_id, revision=revision, device=device, local_files_only=local_files_only, threads=threads)
            result = recognizer.transcribe(audio)
        result["run_id"] = output_dir.name
        result["audio"] = audio.metadata
        result["timings"].update(prepare_seconds=prepare_seconds, total_seconds=time.perf_counter() - started)
        save_json(output_dir / "transcript.json", result)
        (output_dir / "transcript.txt").write_text(result["text"] + "\n", encoding="utf-8")
        run.update(status="ready", total_seconds=result["timings"]["total_seconds"])
        save_json(output_dir / "run.json", run)
        return result, output_dir
    except (ASRError, OSError) as exc:
        # A failed run must not retain something that looks like a successful transcript.
        for name in ("transcript.json", "transcript.txt"):
            (output_dir / name).unlink(missing_ok=True)
        run.update(status="failed", error=str(exc), total_seconds=time.perf_counter() - started)
        save_json(output_dir / "run.json", run)
        raise ASRError(f"{exc}\nChi tiết lần chạy: {output_dir / 'run.json'}") from exc
