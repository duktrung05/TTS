"""Download only Vietnamese FLEURS, then export embedded WAVs and references.

The downloader uses Python's standard library. Export additionally needs pyarrow.
Source sizes and SHA-256s are pinned to the dataset's Vietnamese Parquet commit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

REVISION = "840b885ab2155e7f69f185c62ca4c3526eb7ffd0"
BASE_URL = f"https://huggingface.co/datasets/google/fleurs/resolve/{REVISION}/vi_vn"
FILES = {
    "train": (2073226755, "6a754f3497f7b9b60549963372a7780bf2e60d2508030aec917da57a86af9251"),
    "validation": (274630187, "a6d7cf5fd0711ba5437e6f59f244e72207616aaa6b721f5f7bb2efb98eed1e20"),
    "test": (691128728, "65325be18bef84bb97b5bad1145958ae752919bb0b6696e7cfa8409ef5c46c77"),
}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, target: Path, expected_size: int, expected_sha: str) -> None:
    if target.exists():
        if target.stat().st_size == expected_size and sha256(target) == expected_sha:
            print(f"Đã có file hợp lệ: {target}", flush=True)
            return
        raise ValueError(f"File đã có nhưng sai kích thước/checksum: {target}. Chuyển file đó đi rồi chạy lại.")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    count = 0
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "viet-asr-btl/0.1"})
    print(f"Tải {target.name}: {expected_size / 1024**2:.1f} MiB", flush=True)
    try:
        with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as output:
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > expected_size:
                    raise ValueError("Máy chủ trả file lớn hơn snapshot đã chọn.")
                output.write(block)
                digest.update(block)
                if count // (64 * 1024**2) != (count - len(block)) // (64 * 1024**2):
                    print(f"  {count / expected_size:.0%}", flush=True)
        if count != expected_size or digest.hexdigest() != expected_sha:
            raise ValueError("File tải chưa đủ hoặc SHA-256 không đúng; chưa đánh dấu tải thành công.")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def export_split(source: Path, output_root: Path, split: str, limit: int | None) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Xuất WAV cần pyarrow. Chạy: uv pip install -e '.[data]' rồi chạy lại script.") from exc
    audio_dir = output_root / "audio" / split
    audio_dir.mkdir(parents=True, exist_ok=True)
    temporary_manifest = output_root / f"{split}.jsonl.part"
    count = 0
    try:
        with temporary_manifest.open("w", encoding="utf-8") as manifest:
            columns = ["id", "audio", "num_samples", "transcription", "raw_transcription"]
            for batch in pq.ParquetFile(source).iter_batches(batch_size=16, columns=columns):
                for row in batch.to_pylist():
                    if limit is not None and count >= limit:
                        break
                    payload = row["audio"]["bytes"]
                    if not payload or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
                        raise ValueError("Audio trong snapshot không phải WAV nhúng như dự kiến; chưa xuất manifest hoàn chỉnh.")
                    # Sentence IDs can repeat for different speakers; row index keeps names unique.
                    stem = f"{count:06d}_{row['id']}"
                    audio_path = audio_dir / f"{stem}.wav"
                    audio_path.write_bytes(payload)
                    audio_path.with_suffix(".txt").write_text(row["raw_transcription"] + "\n", encoding="utf-8")
                    record = {
                        "id": stem, "source_id": row["id"], "split": split,
                        "audio_path": str(audio_path.relative_to(output_root)),
                        "text": row["transcription"], "raw_transcription": row["raw_transcription"],
                        "num_samples": row["num_samples"], "sample_rate": 16000,
                        "dataset": "google/fleurs", "config": "vi_vn", "revision": REVISION,
                    }
                    manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1
                if limit is not None and count >= limit:
                    break
        if count == 0:
            raise ValueError(f"Không xuất được audio nào từ split {split}.")
        temporary_manifest.replace(output_root / f"{split}.jsonl")
    except Exception:
        temporary_manifest.unlink(missing_ok=True)
        raise
    print(f"Đã xuất {split}: {count} WAV kèm transcript.", flush=True)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tải FLEURS vi_vn từ Hugging Face; giữ audio và transcript.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/fleurs_vi"))
    parser.add_argument("--splits", nargs="+", choices=list(FILES), default=list(FILES))
    parser.add_argument("--download-only", action="store_true", help="Chỉ lấy Parquet chứa cả audio/text, chưa xuất WAV.")
    parser.add_argument("--max-samples", type=int, help="Số WAV xuất mỗi split; vẫn tải toàn bộ shard Parquet của split.")
    args = parser.parse_args(argv)
    if args.max_samples is not None and args.max_samples <= 0:
        parser.error("max-samples phải lớn hơn 0")
    root = args.output_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    splits = list(dict.fromkeys(args.splits))
    status = {
        "dataset": "google/fleurs", "config": "vi_vn", "revision": REVISION,
        "source": "https://huggingface.co/datasets/google/fleurs", "license": "CC-BY-4.0",
        "updated_at": datetime.now(timezone.utc).isoformat(), "status": "downloading",
        "requested_splits": splits, "downloaded_splits": [], "exported_samples": {},
    }
    write_json(root / "download_status.json", status)
    total_bytes = sum(FILES[split][0] for split in splits)
    print(f"FLEURS vi_vn: {', '.join(splits)}, {total_bytes / 1024**3:.2f} GiB Parquet.", flush=True)
    try:
        if shutil.disk_usage(root).free < total_bytes * 2:
            raise OSError("Cần dung lượng trống đủ cho Parquet và WAV xuất ra; hãy kiểm tra lại ổ đĩa.")
        for split in splits:
            filename = f"{split}-00000-of-00001.parquet"
            size, checksum = FILES[split]
            download(f"{BASE_URL}/{filename}", root / "parquet" / filename, size, checksum)
            status["downloaded_splits"].append(split)
            write_json(root / "download_status.json", status)
        status["status"] = "downloaded"
        write_json(root / "download_status.json", status)
        if not args.download_only:
            for split in splits:
                source = root / "parquet" / f"{split}-00000-of-00001.parquet"
                status["exported_samples"][split] = export_split(source, root, split, args.max_samples)
            status["status"] = "ready"
        write_json(root / "download_status.json", status)
        print(f"Hoàn tất: {root}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        status.update(status="failed", error=str(exc))
        write_json(root / "download_status.json", status)
        print(f"Chưa hoàn tất tải/xuất dữ liệu: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
