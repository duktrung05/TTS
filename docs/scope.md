# Phạm vi milestone đầu

Xây lõi xử lý file trước khi làm ứng dụng upload.

- Thư mục: `/home/dev/tts`. Repository `asr/ASR` chỉ tham khảo.
- Đầu vào sản phẩm mục tiêu: WAV/MP3 tiếng Việt, một người nói, thu rõ, tối đa 600 giây và 100 MiB.
- Milestone này: CLI kiểm tra môi trường, đọc audio, chuẩn hóa mono 16 kHz, waveform, gọi model và ghi TXT/JSON.
- Mô hình khởi đầu: `vinai/PhoWhisper-small`; đối chứng dự kiến `openai/whisper-small`.
- Runtime đầu tiên: Transformers, native Whisper long-form; chưa thêm VAD/khử nhiễu.
- WAV chạy bằng NumPy/SciPy; MP3 cần ffmpeg executable.
- Mỗi lần chạy có ID và metadata riêng; model lỗi không được trả transcript thành công.
- Thử giọng nói thật cần checkpoint hợp lệ và bản ghi người nói; chưa hoàn tất trong môi trường hiện tại.
- Chưa triển khai: giao diện, API, database, fine-tune, bộ chấm WER/CER, phụ đề SRT.

Các thông tin chưa được cung cấp: deadline đồ án, máy triển khai cuối, yêu cầu fine-tune/đóng góp của giảng viên và lĩnh vực bài giảng được chốt. Môi trường workspace đang dùng CPU không thay cho cấu hình máy của sinh viên.
