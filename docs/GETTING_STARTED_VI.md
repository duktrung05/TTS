# Bắt đầu sử dụng CLI ASR

## 1. Bạn đang ở bước nào?

CLI và giao diện Streamlit dùng chung backend. Xem [sơ đồ pipeline](ASR_PIPELINE_VI.md) để tìm module phụ trách mỗi bước.

Từ thư mục dự án trên máy demo, kích hoạt môi trường:

```bash
conda activate "$PWD/.cache/asr-env"
python -m asr_engine --help
python -m asr_engine doctor
```

`doctor` in phiên bản thư viện, CUDA có dùng được không và có ffmpeg không. Nó không tải model hay xác nhận model có sẵn.

## 2. Làm quen với audio trước khi chạy model

```bash
python -m asr_engine inspect data/media_smoke/sample.mp3
python -m asr_engine prepare data/media_smoke/sample.mp4
```

`inspect` giải mã file trong giới hạn để kiểm tra tín hiệu thực. Bạn sẽ thấy sample rate/kênh nguồn, thời lượng, sample rate đích, peak và RMS. FFmpeg giải mã MP3 và MP4 thẳng về mono 16 kHz, với kênh và sample rate nguồn để `null`. Với MP4, CLI lấy track âm thanh đầu tiên và giữ khoảng trễ đầu track trên timeline video.

`prepare` tạo một thư mục trong `outputs/`, đường dẫn được in trên terminal. Mở `waveform.svg` bằng trình duyệt và nghe `normalized.wav`. Tone có khoảng lặng chỉ giúp kiểm tra tín hiệu và timeline; âm tone không có nội dung để chép thành câu.

## 3. Thu file giọng nói thật

1. Dùng điện thoại hoặc micro thu khoảng 20–30 giây tiếng Việt trong nơi tương đối yên tĩnh.
2. Chép file vào `data/`, ví dụ `data/my_recording.wav`. Với MP3 và MP4, cài `ffmpeg` và đặt trong PATH.
3. Nghe lại toàn bộ và viết nội dung đúng vào một file riêng; đó là reference để đối chiếu sau.
4. Chạy `inspect`, rồi `prepare`; kiểm tra thời lượng đầu ra và nghe cả đầu/cuối.

Không đổi tên `.m4a` thành `.wav`; cần thực sự chuyển định dạng bằng công cụ audio. Bộ WAV nhân tạo trong dự án không thay cho bản ghi này.

## 4. Chạy nhận dạng

```bash
python -m asr_engine transcribe data/my_recording.wav --device cpu
```

Chương trình sẽ chuẩn hóa file, tải/load `vinai/PhoWhisper-small`, trích đặc trưng và nhận dạng bằng Whisper native long-form. Ngôn ngữ là tiếng Việt, tác vụ `transcribe`; kết quả được lưu trong thư mục run riêng và in text trên terminal.

Trọng số tải từ nguồn model; khi inference chạy local, audio được xử lý trên máy chạy lệnh. Lần đầu tải checkpoint cần kết nối mạng và mất thêm thời gian; thời gian load và inference được ghi riêng.

Nếu máy đã có checkpoint đầy đủ trong cache, thêm `--local-files-only`. Nếu có một thư mục model đã tải và chuyển từ máy khác, dùng:

```bash
python -m asr_engine transcribe data/my_recording.wav --model /duong/dan/checkpoint --local-files-only
```

Thư mục cần chứa đủ cấu hình, trọng số, feature extractor, tokenizer và generation config tương ứng. Chương trình không tải remote code tùy chỉnh. Ghi lại nguồn và revision của checkpoint chuyển tay; với model local không có `_commit_hash`, trường resolved revision có thể rỗng.

## 5. Đọc kết quả và đo thời gian

- `transcript.txt`: văn bản model sinh, chưa được người dùng sửa.
- `transcript.json`: text, segments và mốc theo audio gốc, model/revision, runtime/precision, cấu hình generation và timings.
- `audio.json`: nguồn và hash, thông tin audio sau chuẩn hóa.
- `run.json`: trạng thái hoàn tất hay lỗi.

So text với reference bằng cách nghe lại. Tốc độ được ghi ở `inference_rtf = inference_seconds / duration_seconds`; thời gian toàn bộ bao gồm chuẩn bị audio và load model. Chưa có bộ chấm WER/CER ở milestone đầu này.

Đổi cấu hình sẽ tạo run khác:

```bash
python -m asr_engine transcribe data/my_recording.wav --model openai/whisper-small --device cpu --threads 4
```

Giữ cùng file và thiết bị để bắt đầu đối chiếu. Hai lần chạy đầu tiên chưa đủ để kết luận mô hình nào tốt hơn.

## 6. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| Không tìm thấy audio | Kiểm tra đường dẫn và thư mục hiện tại |
| File rỗng/hỏng | Xuất lại audio hợp lệ, nghe lại bằng audio player |
| Vượt giới hạn | Dùng file trong giới hạn 600 giây/100 MiB |
| MP3/MP4 thiếu ffmpeg | Cài ffmpeg vào PATH hoặc thử WAV |
| MP4 không có track âm thanh | Xuất lại video có âm thanh hoặc cung cấp file audio riêng |
| Không load được checkpoint | Kiểm tra mạng và tên model; offline cần cache đầy đủ |
| CUDA không dùng được | Chạy `--device cpu`, kiểm tra driver riêng khi cần GPU |
| Thiếu bộ nhớ | Thử `vinai/PhoWhisper-base`; ghi rõ thay đổi model |
| Timestamp ngoài timeline | Run thất bại, giữ log và kiểm tra output model; không tự tạo mốc giả |

File im lặng số hoàn toàn được trả text rỗng mà không gọi model. Tín hiệu nhỏ/nhiễu không được mặc định là im lặng. Nhận dạng thật trên các tình huống này cần đánh giá ở giai đoạn pilot/VAD.

## 7. Các bước chưa hoàn thành

Theo phạm vi BTL, bước tiếp theo là kiểm chứng nhận dạng MP3 và MP4 trên máy có FFmpeg, làm giao diện Streamlit và đánh giá trên một tập nhỏ có bản chép đối chiếu. [Kế hoạch BTL](BTL_PLAN_VI.md)

Tài liệu API tham khảo khi triển khai: [PhoWhisper](https://huggingface.co/vinai/PhoWhisper-small), [Transformers Whisper generation](https://huggingface.co/docs/transformers/model_doc/whisper).
