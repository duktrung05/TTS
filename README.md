# Dự án ASR tiếng Việt

Chuyển file ghi âm tiếng Việt thành văn bản. Thư mục làm việc là `tts`; mục tiêu là ASR/STT.

**Phạm vi hiện tại:Hướng phát triển ưu tiên là một trang nhận WAV/MP3/MP4, hiển thị và tải transcript, kèm đánh giá nhỏ bằng model pretrained. Kế hoạch đồ án tốt nghiệp cũ dùng để tham khảo mở rộng. [Kế hoạch BTL](docs/BTL_PLAN_VI.md)

CLI đọc WAV/MP3/MP4, chuẩn hóa audio về mono 16 kHz, tạo waveform SVG, gọi Whisper/PhoWhisper và xuất TXT/JSON. Model mặc định là `vinai/PhoWhisper-small`. Transformers chạy trên CUDA nếu có, với CPU là phương án dự phòng khi dùng `--device auto`.

## Cấu trúc dự án

| Thư mục | Tìm gì ở đây |
|---|---|
| `frontend/` | Giao diện Streamlit, chọn file, nghe lại, xem và tải bản chép |
| `backend/asr_engine/` | CLI và lõi Python xử lý âm thanh, gọi model, lưu kết quả |
| `backend/scripts/`, `backend/tests/` | Chuẩn bị dữ liệu và kiểm thử backend |
| `data/` | Các bản ghi đầu vào |
| `models/`, `outputs/` | Checkpoint và kết quả theo từng lần chạy |
| `docs/` | Sơ đồ pipeline và hướng dẫn |

Khi sửa luồng nhận dạng, bắt đầu ở [pipeline.py](backend/asr_engine/app/pipeline.py). Khi sửa giao diện, mở [app.py](frontend/app.py). Xem [sơ đồ và thứ tự gọi hàm](docs/ASR_PIPELINE_VI.md).

## Demo trên trình duyệt

Từ thư mục dự án, chạy lệnh sau rồi mở http://127.0.0.1:8501 trên cùng máy.

```bash
.cache/asr-env/bin/python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501 --server.maxUploadSize 100
```

Chọn **Dùng mẫu** hoặc **Tải tệp lên**, rồi bấm **Nhận dạng**. Giao diện dùng checkpoint cục bộ `models/PhoWhisper-small-clean` và lưu kết quả trong `outputs/demo/`. Khi cài ở môi trường khác, dùng `python -m pip install -e '.[demo,model]'` và chạy lệnh Streamlit bằng Python của môi trường đó.

## Chạy ngay trong workspace hiện tại

Từ thư mục gốc của dự án trên máy demo, dùng môi trường đã cài và mẫu MP3 có sẵn:

```bash
conda activate "$PWD/.cache/asr-env"
python -m asr_engine doctor
python -m asr_engine inspect data/media_smoke/sample.mp3
python -m asr_engine transcribe data/media_smoke/sample.mp3 \
  --model models/PhoWhisper-small-clean --local-files-only
```

Chép file ghi âm thật vào `data/my_recording.wav`, sau đó chạy:

```bash
python -m asr_engine transcribe data/my_recording.wav --device cpu
```

Lần đầu cần mạng để tải checkpoint từ Hugging Face. Trong workspace này đã chạy nhận dạng WAV tiếng Việt bằng checkpoint cục bộ `models/PhoWhisper-small-clean`.

Nếu checkpoint đã có đầy đủ trong cache:

```bash
python -m asr_engine transcribe data/my_recording.wav --device cpu --local-files-only
```

Có thể truyền thư mục checkpoint Whisper/PhoWhisper có sẵn qua `--model`. Ví dụ, lệnh sau dùng checkpoint cục bộ để chép lời từ video.

```bash
python -m asr_engine transcribe data/my_recording.mp4 \
  --model models/PhoWhisper-small-clean --local-files-only
```

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

SciPy đọc và resample WAV. MP3 và MP4 cần `ffmpeg` trong PATH. Trên Ubuntu có thể cài bằng `sudo apt install ffmpeg`. Với MP4, CLI dùng track âm thanh đầu tiên và giữ khoảng trễ đầu track để timestamp khớp với timeline video.

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

CLI nhận WAV/MP3/MP4 tối đa 100 MiB và 600 giây audio sau giải mã. Có thể hạ giới hạn bằng `--max-size-mb` và `--max-duration`. Dùng `--model openai/whisper-small` để thử mô hình đối chứng. `--revision` chọn commit/tag, `--threads` giới hạn thread CPU và `--output-dir` chọn thư mục kết quả.

## Kiểm chứng

```bash
python -m pytest
```

Các kiểm thử kiểm tra audio hỏng, resample, tín hiệu ở phần cuối file dài, timestamp, lưu lỗi và không ghi đè kết quả. Có kiểm tra feature extractor thật và native generation của Whisper với model tí hon khởi tạo ngẫu nhiên/token ép sẵn để kiểm chứng chạy qua 30 giây; chúng **không chứng minh độ chính xác nhận dạng lời nói** và không tải pretrained model.

## Tài liệu và việc tiếp theo

- [Tải FLEURS tiếng Việt: audio và transcript](docs/FLEURS_VI.md).
- [Kế hoạch phát triển BTL — ưu tiên hiện tại](docs/BTL_PLAN_VI.md).
- [Hướng dẫn từng bước cho người mới](docs/GETTING_STARTED_VI.md).
- [Môi trường và kết quả kiểm chứng hiện tại](docs/environment.md).
- [Pipeline và sơ đồ luồng dự án](docs/ASR_PIPELINE_VI.md).
- [Kế hoạch chi tiết](docs/ASR_PROJECT_PLAN_VI.md).

Các bước tiếp theo trong kế hoạch BTL là đánh giá chất lượng nhận dạng trên nhiều bản ghi và hoàn thiện báo cáo.
