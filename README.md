# Dự án ASR tiếng Việt

Chuyển file ghi âm tiếng Việt thành văn bản. Thư mục làm việc là `tts`; mục tiêu là ASR/STT.

**Bước đầu đã triển khai:** CLI đọc WAV/MP3, chuẩn hóa audio về mono 16 kHz, tạo waveform SVG, gọi Whisper/PhoWhisper và xuất TXT/JSON. Model mặc định là `vinai/PhoWhisper-small`, chạy bằng Transformers; thiết bị `auto` chọn CPU khi CUDA không dùng được.

Mã dự án mới được viết trong thư mục này; `/home/dev/asr/ASR` là nguồn tham khảo. Hiện chưa có giao diện upload hoặc HTTP API.

## Chạy ngay trong workspace hiện tại

Môi trường `.venv` đã được tạo. Từ thư mục `/home/dev/tts`:

```bash
source .venv/bin/activate
python -m asr_engine doctor
python -m asr_engine inspect data/synthetic/tone_pause.wav
python -m asr_engine prepare data/synthetic/long_tone.wav
```

Các file `data/synthetic/` đã được tạo để kiểm tra xử lý tín hiệu: tiếng tone, khoảng lặng và im lặng số. **Đây không phải file giọng nói hay dữ liệu đo độ chính xác ASR.** Muốn tự tạo ở một thư mục mới:

```bash
python scripts/create_test_audio.py --output-dir data/synthetic-new
```

Chép file ghi âm thật vào `data/my_recording.wav`, sau đó chạy:

```bash
python -m asr_engine transcribe data/my_recording.wav --device cpu
```

Lần đầu cần mạng để tải checkpoint từ Hugging Face. Workspace hiện chưa tải được checkpoint vì kết nối DNS không hoạt động; do đó **chưa xác minh nhận dạng giọng nói thật bằng PhoWhisper**. Lệnh trên sẽ chỉ hoàn tất khi có checkpoint hợp lệ trong cache hoặc có mạng tải model.

Nếu checkpoint đã có đầy đủ trong cache:

```bash
python -m asr_engine transcribe data/my_recording.wav --device cpu --local-files-only
```

Có thể truyền thư mục checkpoint có sẵn qua `--model /duong/dan/checkpoint`. Chỉ hỗ trợ kiến trúc Whisper/PhoWhisper ở bước này.

## Cài trên máy mới có kết nối mạng

Cần Python 3.11–3.13 và `uv`. Các lệnh dưới dùng môi trường riêng trong dự án:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e '.[model]'
python -m asr_engine doctor
```

Lệnh PyTorch trên dành cho CPU. Khi triển khai GPU, chọn bản PyTorch/driver tương thích với máy rồi kiểm tra lại `doctor`; số đo trong workspace không đại diện cho máy của bạn. Trên Windows, kích hoạt bằng `.venv\Scripts\Activate.ps1` trong PowerShell.

WAV được đọc và resample bằng SciPy, không cần `ffmpeg` executable. MP3 cần cài `ffmpeg` và để trong PATH. Ví dụ trên Ubuntu: `sudo apt install ffmpeg`; trên máy khác dùng cách cài phù hợp hệ điều hành.

## Kết quả và cấu hình mỗi lần chạy

```text
outputs/<run_id>/
├── normalized.wav       # Tín hiệu mono 16 kHz thực sự đưa vào model
├── waveform.svg         # Mở bằng trình duyệt để xem tín hiệu
├── audio.json           # Thời lượng, kênh, sample rate, SHA-256 nguồn
├── run.json             # prepared / processing / ready / failed
├── transcript.txt       # Chỉ có khi nhận dạng hoàn tất
└── transcript.json      # Text, segments, model/revision, cấu hình, thời gian
```

Mỗi lần chạy tạo một thư mục riêng. Thất bại khi load/nhận dạng model được lưu `failed` và không sinh transcript giả. Với tín hiệu có **toàn bộ mẫu chuẩn hóa bằng 0**, chương trình trả text rỗng, ghi rõ model chưa chạy; đây chưa phải VAD hay khả năng nhận diện mọi loại nhiễu.

Whisper dùng đường sinh long-form, giữ toàn bộ audio thay vì cắt lấy 30 giây đầu. Timestamp theo đoạn là ước lượng từ model, chưa được đánh giá alignment; vì vậy hiện xuất TXT/JSON, chưa xuất SRT.

Giới hạn: WAV/MP3, tối đa 100 MiB và 600 giây. Có thể hạ giới hạn bằng `--max-size-mb` và `--max-duration`. Dùng `--model openai/whisper-small` để thử mô hình đối chứng; `--revision` chọn commit/tag, `--threads` giới hạn thread CPU, `--output-dir` chọn thư mục kết quả.

## Kiểm chứng

```bash
python -m pytest
```

Các kiểm thử kiểm tra audio hỏng, resample, tín hiệu ở phần cuối file dài, timestamp, lưu lỗi và không ghi đè kết quả. Có kiểm tra feature extractor thật và native generation của Whisper với model tí hon khởi tạo ngẫu nhiên/token ép sẵn để kiểm chứng chạy qua 30 giây; chúng **không chứng minh độ chính xác nhận dạng lời nói** và không tải pretrained model.

## Tài liệu và việc tiếp theo

- [Hướng dẫn từng bước cho người mới](docs/GETTING_STARTED_VI.md).
- [Môi trường và kết quả kiểm chứng hiện tại](docs/environment.md).
- [Pipeline và sơ đồ luồng dự án](docs/ASR_PIPELINE_VI.md).
- [Kế hoạch chi tiết](docs/ASR_PROJECT_PLAN_VI.md).

Bước tiếp theo: chuẩn bị file giọng nói có reference, tải/check checkpoint, chạy thử thật và bắt đầu bộ dữ liệu pilot để đo WER/CER. Sau đó mới nối engine với API và giao diện upload.
