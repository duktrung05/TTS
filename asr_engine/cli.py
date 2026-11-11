from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys

from . import __version__
from .app.errors import ASRError
from .app.recognizer import DEFAULT_MODEL


def doctor() -> dict:
    packages = {}
    for name in ("numpy", "scipy", "torch", "transformers"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    cuda = False
    torch_error = None
    if importlib.util.find_spec("torch"):
        try:
            import torch
            cuda = torch.cuda.is_available()
        except (ImportError, OSError, RuntimeError) as exc:
            torch_error = str(exc)
    return {
        "python": platform.python_version(), "executable": sys.executable,
        "platform": platform.platform(), "packages": packages,
        "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
        "cuda_available": cuda, "torch_error": torch_error,
        "default_device": "cuda" if cuda else "cpu", "default_model": DEFAULT_MODEL,
        "notes": [
            "WAV inspection/preparation works without ffmpeg; MP3 needs ffmpeg in PATH.",
            "This checks libraries and hardware, not pretrained weights or recognition accuracy.",
        ],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="ASR tiếng Việt: đọc audio, chuẩn hóa và chép thành văn bản.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Kiểm tra môi trường; không tải model.")
    for name, help_text in (
        ("inspect", "Đọc và kiểm tra audio, in metadata JSON."),
        ("prepare", "Lưu WAV 16 kHz, waveform SVG và metadata."),
        ("transcribe", "Chạy Whisper/PhoWhisper và xuất TXT/JSON."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("audio", type=Path, help="Đường dẫn WAV/MP3 trên máy.")
        command.add_argument("--max-duration", type=float, default=600, help="Giới hạn giây, tối đa 600.")
        command.add_argument("--max-size-mb", type=float, default=100, help="Giới hạn MiB, tối đa 100.")
        if name != "inspect":
            command.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Thư mục cha; mỗi lần tạo thư mục run riêng.")
        if name == "transcribe":
            command.add_argument("--model", default=DEFAULT_MODEL)
            command.add_argument("--revision", default="main", help="Commit/tag/branch nguồn; commit đã resolve được ghi vào JSON.")
            command.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
            command.add_argument("--threads", type=int, default=4, help="Số thread PyTorch, 1–64.")
            command.add_argument("--local-files-only", action="store_true", help="Chỉ dùng checkpoint có sẵn, không tải từ mạng.")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        else:
            from .app.audio import load_audio
            from .app.pipeline import prepare_audio, transcribe_file
            limits = {"max_duration": args.max_duration, "max_size_mb": args.max_size_mb}
            if args.command == "inspect":
                result = load_audio(args.audio, **limits).metadata
            elif args.command == "prepare":
                audio, output, _ = prepare_audio(args.audio, args.output_dir, **limits)
                result = {"status": "prepared", "output_dir": str(output), "audio": audio.metadata}
            else:
                if not 1 <= args.threads <= 64:
                    raise ASRError("threads phải nằm trong khoảng 1–64.")
                transcript, output = transcribe_file(
                    args.audio, args.output_dir, model_id=args.model, revision=args.revision,
                    device=args.device, local_files_only=args.local_files_only,
                    threads=args.threads, **limits,
                )
                result = {"status": "ready", "output_dir": str(output), "text": transcript["text"], "timings": transcript["timings"]}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ASRError, OSError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"Thiếu thư viện: {exc}. Cài môi trường theo README.md.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
