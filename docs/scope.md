# Phạm vi BTL

Cập nhật 18/11/2026. Kế hoạch ưu tiên: [BTL_PLAN_VI.md](BTL_PLAN_VI.md).

- Mục tiêu: ứng dụng local chuyển lời nói tiếng Việt trong file audio/video thành văn bản.
- Thư mục: `/home/dev/tts`; repository `asr/ASR` chỉ tham khảo.
- Đầu vào mục tiêu: WAV, MP3, MP4 có audio, một người nói chính, thu rõ; tối đa 5 phút và 100 MiB cho giao diện BTL.
- Nội dung: tiếng Việt thông dụng, không giới hạn riêng bài giảng; đánh giá trên một tập nhỏ có reference.
- Model: bắt đầu với pretrained PhoWhisper-small hiện có trong code; cân nhắc base nếu không phù hợp phần cứng. Chọn một cấu hình chính cho demo.
- Giao diện đề xuất: một trang Streamlit, gọi trực tiếp lõi Python, hiển thị text và tải TXT.
- Bằng chứng: demo thật, WER và thời gian trên dữ liệu có bản chép đúng; không mặc định phải fine-tune, trừ yêu cầu môn học.
- CLI nhận WAV/MP3/MP4, giới hạn 600 giây và 100 MiB. Giao diện và bộ chấm là các hạng mục tiếp theo.
- Các mục ngoài bản BTL cơ sở: đăng nhập, database, dịch/TTS, realtime, diarization và nghiên cứu huấn luyện lớn.

Thông tin chưa được cung cấp: deadline, máy demo và tiêu chí cụ thể của giảng viên. Môi trường workspace không thay cho cấu hình máy của sinh viên.
