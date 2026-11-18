"""Generate clearly labeled synthetic fixtures for audio plumbing, never ASR evaluation."""

import argparse
from array import array
from math import pi, sin
from pathlib import Path
import sys
import wave


def write(path: Path, *, seconds: int, silence: bool) -> None:
    rate = 48_000
    samples = array("h")
    for index in range(seconds * rate):
        # Tone, pause, tone; this is NOT a person speaking.
        quiet = silence or 2 <= index / rate < 4
        value = 0 if quiet else round(8_000 * sin(2 * pi * 440 * index / rate))
        samples.extend((value, value // 2))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples.tobytes())


def main():
    parser = argparse.ArgumentParser(description="Tạo WAV nhân tạo để thử chuẩn hóa; không phải dữ liệu lời nói.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, seconds, silence in [("tone_pause.wav", 6, False), ("digital_silence.wav", 2, True), ("long_tone.wav", 35, False)]:
        target = args.output_dir / name
        if target.exists():
            parser.error(f"File đã tồn tại: {target}. Chọn thư mục khác để giữ dữ liệu cũ.")
        write(target, seconds=seconds, silence=silence)
        print(target)


if __name__ == "__main__":
    main()
