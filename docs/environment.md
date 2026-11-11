# Môi trường và kiểm chứng milestone đầu

Cập nhật: 11/11/2026. Chạy trong `/home/dev/tts/.venv`, không thay đổi môi trường Python hệ thống.

## Môi trường thực tế

```json
{
  "python": "3.12.3",
  "executable": "/home/dev/tts/.venv/bin/python",
  "platform": "Linux-5.15.0-139-generic-x86_64-with-glibc2.39",
  "packages": {
    "numpy": "2.5.4",
    "scipy": "1.18.1",
    "torch": "2.11.0+cu130",
    "transformers": "5.10.4"
  },
  "ffmpeg": null,
  "ffprobe": null,
  "cuda_available": false,
  "torch_error": null,
  "default_device": "cpu",
  "default_model": "vinai/PhoWhisper-small",
  "notes": [
    "WAV inspection/preparation works without ffmpeg; MP3 needs ffmpeg in PATH.",
    "This checks libraries and hardware, not pretrained weights or recognition accuracy."
  ]
}
```

Môi trường này chưa phân giải được các tên miền PyPI, Hugging Face và download.pytorch.org khi kiểm tra bằng Python. Cài đặt từ các distribution đã có trong cache local; không tải được checkpoint pretrained. Cache có PyTorch bản CUDA, nhưng CUDA không khả dụng nên các kiểm tra dùng CPU. Đây không phải lý do phải cài CUDA trên máy mới.

[Snapshot phiên bản đã cài](environment-packages.txt) phục vụ truy vết môi trường kiểm tra. Nó có các bản prerelease từ cache và dependency CUDA; hướng dẫn cài CPU trên máy mới nằm trong README, không mặc định dùng snapshot CUDA này cho mọi máy. Chưa tạo universal lockfile hay xác nhận cài sạch trên hệ điều hành khác.

## Đã kiểm tra

- Cài package editable và chạy entrypoint `viet-asr --help`.
- `python -m pytest`: **25 passed**; có xử lý audio thật từ tín hiệu nhân tạo, các trường hợp lỗi, giữ phần cuối file 35,2 giây, waveform và lưu kết quả tiếng Việt/provenance với model thay thế trong test.
- Feature extractor thật nhận tín hiệu trên 30 giây, không truncate còn 30 giây.
- Whisper native generation thật trên model tí hon khởi tạo ngẫu nhiên/token ép sẵn trả hai đoạn `[0,30]`, `[30,35]`; đây là kiểm tra API/window advancement, không phải nhận dạng lời nói.
- `uv pip check`: 58 package tương thích với dependency metadata trong môi trường này.
- `python -m compileall -q asr_engine scripts tests`: thành công.
- CLI `prepare` chạy trên tone stereo 48 kHz, tạo WAV mono 16 kHz, SVG và metadata; khoảng lặng nằm đúng timeline.
- CLI trên im lặng số trả text rỗng, ghi model chưa chạy.
- CLI với tone và `--local-files-only` khi không có checkpoint trả exit code 2, lưu `failed`, không tạo transcript thành công.

Các kết quả local minh họa nằm trong `outputs/`; chúng bị Git ignore và không phải số liệu benchmark.

## Chưa xác minh

- Load và nhận dạng lời nói thật bằng pretrained PhoWhisper-small/Whisper-small.
- WER/CER, tốc độ inference của pretrained model, chất lượng mốc thời gian.
- MP3 end-to-end: máy chưa có ffmpeg; đã kiểm tra thông báo thiếu ffmpeg và giới hạn sau giải mã bằng test thay decoder.
- Chạy GPU, file bài giảng thật 10 phút, cài sạch qua Internet trên máy mới.
- API/frontend/database và fine-tune, thuộc giai đoạn tiếp theo.

## Để tiếp tục

Có checkpoint đầy đủ trong cache hoặc thư mục local, chuẩn bị một file WAV giọng nói thật có reference và chạy lệnh transcribe theo [hướng dẫn](GETTING_STARTED_VI.md). Kiểm tra đầu/giữa/cuối file rồi mới mở rộng dữ liệu pilot và đo chất lượng.
