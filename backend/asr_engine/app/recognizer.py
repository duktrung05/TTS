"""Whisper native long-form generation; model imports are lazy for audio-only use."""

from __future__ import annotations

from importlib.metadata import version
import math
from pathlib import Path
import time

from .audio import AudioData, SAMPLE_RATE
from .errors import ASRError

DEFAULT_MODEL = "vinai/PhoWhisper-small"


def validate_segments(segments: list[dict], duration: float) -> list[dict]:
    cleaned = []
    previous_start = 0.0
    for raw in segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        try:
            start, end = float(raw["start"]), float(raw["end"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ASRError("Model trả segment thiếu mốc thời gian hợp lệ.") from exc
        if not math.isfinite(start) or not math.isfinite(end):
            raise ASRError("Model trả timestamp NaN/Infinity.")
        # Whisper timestamp quantization may extend a little past the last sample.
        if start < 0 or end > duration + 0.5 or end <= start or start < previous_start:
            raise ASRError(f"Model trả timestamp ngoài timeline: {start:g}–{end:g}s.")
        end = min(end, duration)
        if end <= start:
            raise ASRError("Segment nằm sau điểm kết thúc audio.")
        cleaned.append({"segment_id": len(cleaned) + 1, "start": start, "end": end, "text": text})
        previous_start = start
    return cleaned


class WhisperRecognizer:
    def __init__(
        self, model_id: str = DEFAULT_MODEL, *, revision: str = "main",
        device: str = "auto", local_files_only: bool = False, threads: int = 4,
    ) -> None:
        try:
            import torch
            from transformers import AutoConfig, AutoProcessor, AutoModelForSpeechSeq2Seq
        except (ImportError, OSError) as exc:
            raise ASRError("Thiếu hoặc lỗi thư viện model. Cài optional dependencies: uv pip install -e '.[model]'.") from exc
        if device == "cuda" and not torch.cuda.is_available():
            raise ASRError("CUDA chưa dùng được. Chọn --device cpu hoặc kiểm tra driver/PyTorch.")
        self.torch = torch
        self.device = "cuda" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        torch.set_num_threads(threads)
        started = time.perf_counter()
        try:
            config = AutoConfig.from_pretrained(model_id, revision=revision, local_files_only=local_files_only, trust_remote_code=False)
            if config.model_type != "whisper":
                raise ASRError("Bản đầu chỉ hỗ trợ checkpoint kiến trúc Whisper/PhoWhisper.")
            self.resolved_revision = getattr(config, "_commit_hash", None)
            source_revision = self.resolved_revision or revision
            self.processor = AutoProcessor.from_pretrained(model_id, revision=source_revision, local_files_only=local_files_only, trust_remote_code=False)
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id, revision=source_revision, local_files_only=local_files_only,
                trust_remote_code=False, dtype=self.dtype,
            ).to(self.device).eval()
        except ASRError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            raise ASRError(
                f"Không load được model {model_id}. Lần đầu cần kết nối Hugging Face để tải checkpoint; "
                "--local-files-only chỉ dùng cache đã đủ. Kiểm tra mạng, tên model và bộ nhớ. "
                f"Chi tiết: {exc}"
            ) from exc
        self.load_seconds = time.perf_counter() - started
        self.model_id = model_id
        self.requested_revision = revision
        self.threads = threads

    def transcribe(self, audio: AudioData) -> dict:
        torch = self.torch
        if self.device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        try:
            # No 30-second truncation. Native Whisper generation advances over the full file.
            inputs = self.processor(
                audio.samples, sampling_rate=SAMPLE_RATE, return_tensors="pt",
                truncation=False, padding="longest", return_attention_mask=True,
            )
            features = inputs.input_features.to(device=self.device, dtype=self.dtype)
            attention_mask = inputs.attention_mask.to(self.device)
            with torch.inference_mode():
                output = self.model.generate(
                    input_features=features, attention_mask=attention_mask,
                    language="vi", task="transcribe", return_timestamps=True,
                    return_segments=True, condition_on_prev_tokens=False,
                    num_beams=1, do_sample=False, max_new_tokens=440,
                )
            if self.device == "cuda":
                torch.cuda.synchronize()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise ASRError(f"Nhận dạng thất bại: {exc}") from exc
        inference_seconds = time.perf_counter() - started
        try:
            raw_segments = [
                {"start": float(item["start"]), "end": float(item["end"]),
                 "text": self.processor.decode(item["tokens"], skip_special_tokens=True)}
                for item in output["segments"][0]
            ]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ASRError("Model không trả schema segments mong đợi; chưa ghi transcript thành công.") from exc
        segments = validate_segments(raw_segments, audio.metadata["duration_seconds"])
        decoded_text = self.processor.batch_decode(output["sequences"], skip_special_tokens=True)[0].strip()
        if decoded_text and not segments:
            raise ASRError("Model có text nhưng không có segment hợp lệ; cần kiểm tra cấu hình timestamps.")
        if segments and not decoded_text:
            raise ASRError("Model trả text toàn file rỗng nhưng segments có nội dung; cần kiểm tra decoder.")
        return {
            "text": decoded_text, "segments": segments, "language_code": "vi",
            "duration_seconds": audio.metadata["duration_seconds"],
            "model": {
                "id": self.model_id, "requested_revision": self.requested_revision,
                "resolved_revision": self.resolved_revision,
                "local_checkpoint": str(Path(self.model_id).resolve()) if Path(self.model_id).is_dir() else None,
                "runtime": "transformers", "device": self.device, "dtype": str(self.dtype),
                "torch_version": version("torch"), "transformers_version": version("transformers"),
            },
            "generation": {
                "language": "vi", "task": "transcribe", "long_form": "whisper_native",
                "return_timestamps": True, "condition_on_prev_tokens": False,
                "num_beams": 1, "do_sample": False, "max_new_tokens": 440, "threads": self.threads,
                "vad": False,
            },
            "timings": {
                "model_load_seconds": self.load_seconds,
                "inference_seconds": inference_seconds,
                "inference_rtf": inference_seconds / audio.metadata["duration_seconds"],
            },
            "warnings": ["Model timestamps are estimates; alignment has not been evaluated."],
        }
