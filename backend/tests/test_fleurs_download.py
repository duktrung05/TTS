from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import urllib.error
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_fleurs_vi.py"
spec = importlib.util.spec_from_file_location("download_fleurs_vi", SCRIPT)
downloader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downloader)


class FleursDownloadTests(unittest.TestCase):
    def test_verified_file_is_reused_without_network(self):
        data = b"fixture parquet bytes"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "sample.parquet"
            with patch.object(downloader.urllib.request, "urlopen", return_value=io.BytesIO(data)) as request:
                downloader.download("https://example.invalid/sample", target, len(data), digest)
                self.assertEqual(target.read_bytes(), data)
                downloader.download("https://example.invalid/sample", target, len(data), digest)
                self.assertEqual(request.call_count, 1)

    def test_incomplete_or_wrong_content_never_becomes_completed_file(self):
        expected = b"expected fixture"
        for received in [b"short", b"x" * len(expected)]:
            with self.subTest(received=received), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / "sample.parquet"
                with patch.object(downloader.urllib.request, "urlopen", return_value=io.BytesIO(received)):
                    with self.assertRaises(ValueError):
                        downloader.download("https://example.invalid/sample", target, len(expected), hashlib.sha256(expected).hexdigest())
                self.assertFalse(target.exists())
                self.assertFalse(target.with_suffix(".parquet.part").exists())

    def test_dns_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(downloader, "download", side_effect=urllib.error.URLError("DNS unavailable")):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = downloader.main(["--output-dir", temporary, "--download-only"])
            status = json.loads((Path(temporary) / "download_status.json").read_text())
            self.assertEqual(code, 2)
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["downloaded_splits"], [])
            self.assertEqual(status["exported_samples"], {})

    def test_export_keeps_duplicate_sentence_recordings_and_references(self):
        # Mock only the Parquet reader, not online download or actual ASR inference.
        payload = b"RIFFxxxxWAVEfixture"
        rows = [{"id": 7, "audio": {"bytes": payload}, "num_samples": 16000,
                 "transcription": "xin chào", "raw_transcription": "Xin chào."}] * 2
        class Batch:
            def to_pylist(self):
                return rows
        class Parquet:
            def iter_batches(self, **kwargs):
                yield Batch()
        parent = ModuleType("pyarrow")
        parent.__path__ = []
        parquet = ModuleType("pyarrow.parquet")
        parquet.ParquetFile = lambda source: Parquet()
        parent.parquet = parquet
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(sys.modules, {"pyarrow": parent, "pyarrow.parquet": parquet}):
                count = downloader.export_split(root / "fixture.parquet", root, "test", None)
            records = [json.loads(line) for line in (root / "test.jsonl").read_text().splitlines()]
            self.assertEqual(count, 2)
            self.assertNotEqual(records[0]["audio_path"], records[1]["audio_path"])
            self.assertEqual(records[0]["text"], "xin chào")
            self.assertEqual(records[0]["raw_transcription"], "Xin chào.")
            for item in records:
                self.assertEqual((root / item["audio_path"]).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
