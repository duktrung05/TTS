# Tải FLEURS tiếng Việt

Script `backend/scripts/download_fleurs_vi.py` chỉ tải cấu hình `vi_vn` từ `google/fleurs`, giữ audio và transcript. Snapshot được pin theo commit của Hugging Face và kiểm tra kích thước/SHA-256 của mỗi file Parquet.

## Tải và xuất WAV

```bash
conda activate "$PWD/.cache/asr-env"
uv pip install -e '.[data]'
python backend/scripts/download_fleurs_vi.py
```

Mặc định lấy cả `train`, `validation`, `test`, khoảng 2,83 GiB Parquet; cần thêm dung lượng cho WAV xuất ra. Script tải bằng thư viện chuẩn Python, chỉ bước đọc Parquet/xuất WAV cần `pyarrow`.

Với BTL dùng model pretrained, có thể chỉ lấy hai split phục vụ chạy thử và đánh giá:

```bash
python backend/scripts/download_fleurs_vi.py --splits validation test --max-samples 100
```

`--max-samples` giới hạn số WAV xuất mỗi split, không giảm dung lượng shard Parquet phải tải. `--download-only` chỉ tải Parquet, chưa cần pyarrow. Chạy lại sẽ kiểm tra và dùng lại file Parquet đã tải đủ, không tải lại file hợp lệ. File đang tải dở không được đánh dấu thành công.

## Kết quả dự kiến

```text
data/fleurs_vi/
├── download_status.json
├── parquet/
│   ├── train-00000-of-00001.parquet
│   ├── validation-00000-of-00001.parquet
│   └── test-00000-of-00001.parquet
├── audio/<split>/
│   ├── <row_index>_<sentence_id>.wav
│   └── <row_index>_<sentence_id>.txt
├── train.jsonl
├── validation.jsonl
└── test.jsonl
```

Manifest giữ `text` (transcription chuẩn hóa), `raw_transcription`, đường dẫn audio tương đối với `data/fleurs_vi/`, split và nguồn/revision. File TXT cạnh WAV giữ raw transcription. Một sentence ID có thể có nhiều bản thu, nên tên file có thêm chỉ số dòng.

Sau khi `download_status.json` là `ready`, chọn một WAV có thật trong thư mục `audio/validation/` để chạy `python -m asr_engine inspect ...`, rồi `transcribe`. Audio/reference dùng cho kiểm thử, không tự động được đưa vào huấn luyện. Giữ test riêng nếu đang chỉnh cấu hình trên validation.

## Nguồn và quyền sử dụng

- Dataset: [google/fleurs](https://huggingface.co/datasets/google/fleurs), cấu hình tiếng Việt `vi_vn`.
- Snapshot: [commit bổ sung Parquet vi_vn](https://huggingface.co/datasets/google/fleurs/commit/840b885ab2155e7f69f185c62ca4c3526eb7ffd0), gồm kích thước và SHA-256 đã dùng trong script.
- Dataset card công bố CC BY 4.0; ghi nguồn và trích dẫn FLEURS trong báo cáo.

Nếu DNS/kết nối đến Hugging Face lỗi, script ghi `failed` và nguyên nhân trong `download_status.json`. Trạng thái đó không có nghĩa audio đã được tải. Có thể chạy cùng lệnh trên máy có mạng rồi chuyển thư mục dữ liệu sang máy chạy dự án. Bản script chưa được kiểm chứng tải/xuất online thành công trong workspace bị lỗi DNS.
