# Kế hoạch phát triển theo quy mô bài tập lớn

Cập nhật 18/11/2026 theo yêu cầu người dùng: dự án phục vụ một BTL. Tài liệu này là kế hoạch ưu tiên hiện tại; bản kế hoạch đồ án tốt nghiệp trước đó chỉ tham khảo cho hướng mở rộng.

## Mục tiêu và tên đề tài đề xuất

**Xây dựng ứng dụng nhận dạng tiếng nói tiếng Việt từ tệp âm thanh và video.**

Người dùng chọn một file, bấm nhận dạng, nghe lại audio, xem văn bản và tải TXT xuống. Dùng mô hình pretrained và có một phép đánh giá nhỏ trên các đoạn có transcript đúng. Mức đáp ứng yêu cầu môn học còn phụ thuộc tiêu chí giảng viên; nếu môn bắt buộc huấn luyện, cần điều chỉnh phạm vi riêng.

## Phạm vi vừa đủ

| Thành phần | Mục tiêu bản BTL |
|---|---|
| Đầu vào | WAV, MP3 và MP4 có track âm thanh |
| Nội dung | Tiếng Việt thông dụng: lời đọc, thuyết trình, ghi chú hoặc độc thoại |
| Điều kiện | Một người nói chính, nghe rõ; báo lỗi rõ với file không hợp lệ/không có audio |
| Thời lượng | Nhắm tới tối đa 5 phút/file cho giao diện BTL |
| Dung lượng | Tối đa 100 MiB/file |
| Model | Bắt đầu với PhoWhisper-small hiện có trong code; nếu quá chậm/thiếu tài nguyên thì thử PhoWhisper-base và ghi rõ lựa chọn |
| Giao diện | Một trang Streamlit chạy local, gọi trực tiếp lõi Python |
| Lưu kết quả | File local; TXT và JSON đã có nền tảng |
| Đánh giá | Một tập nhỏ có reference, báo WER và thời gian; CER là bổ sung |

Giao diện một trang giúp tập trung vào luồng hoàn chỉnh. Trong bản BTL cơ sở, các mục như đăng nhập, database, backend/frontend riêng, streaming, nhiều người nói, TTS, dịch, SRT và fine-tune không phải điều kiện hoàn thành. Chỉ thêm một tính năng mở rộng sau khi luồng chính và đánh giá đã xong.

CLI hỗ trợ WAV/MP3/MP4 và có giới hạn 600 giây. Có thể kiểm thử giới hạn 300 giây dự kiến cho giao diện Streamlit bằng `--max-duration 300`.

## Luồng cần hoàn thành

```text
Chọn WAV / MP3 / MP4
    → kiểm tra file
    → đọc audio hoặc tách track audio từ video
    → chuẩn hóa mono 16 kHz
    → mô hình ASR pretrained
    → hiển thị văn bản, nghe lại, tải TXT
```

## Bước 1 — Chạy nhận dạng giọng nói thật

Đây là việc ưu tiên trước khi làm giao diện.

- [x] Chuẩn bị checkpoint cục bộ `models/PhoWhisper-small`.
- [x] Dùng hai mẫu WAV FLEURS 14,94 và 31,98 giây có bản chép đối chiếu.
- [x] Chạy CLI bằng PhoWhisper-small, kiểm tra text và các file kết quả. Mẫu 31,98 giây có đoạn nhận dạng từ giây 30 đến hết file.
- [ ] Thử thêm một file 1–3 phút, nghe đối chiếu phần đầu/giữa/cuối.
- [x] Lưu cấu hình model, thiết bị, thời gian và transcript trong `outputs/`.

Đạt khi có transcript từ pretrained model trên bản ghi người thật, không phải kết quả từ test double/tín hiệu nhân tạo. Nếu small không phù hợp máy, thử base trước khi thay toàn bộ kiến trúc.

## Bước 2 — Hoàn thiện MP3 và bổ sung MP4

- [x] Cài hoặc cấu hình ffmpeg executable, kiểm tra từ môi trường chạy ứng dụng.
- [x] Chạy nhận dạng một MP3 thật.
- [x] Mở rộng kiểm tra định dạng và giải mã để nhận MP4 có audio.
- [x] Giữ khoảng trễ đầu track âm thanh và áp dụng giới hạn thời lượng sau giải mã.
- [x] Thử MP4 có lời nói, MP4 không có audio và file hỏng.

Đạt khi cả ba định dạng đi qua cùng lõi nhận dạng; file video không có track audio trả lỗi dễ hiểu. Chất lượng ASR phụ thuộc phần lời nói, không phụ thuộc hình ảnh hay chữ trên video.

## Bước 3 — Làm một trang Streamlit

- [x] Khu vực chọn file, hiện định dạng/giới hạn và nút nhận dạng.
- [x] Trình phát audio gốc hoặc audio đã tách để nghe kiểm tra.
- [ ] Trạng thái đang xử lý; chặn bấm lặp gây nhiều inference đồng thời.
- [x] Vùng hiển thị transcript, thời gian xử lý, nút tải TXT.
- [ ] Thông báo rõ khi thiếu model, thiếu ffmpeg, file hỏng hoặc quá giới hạn.
- [ ] Load và dùng lại model trong phiên chạy ứng dụng thay vì load lại mỗi lần bấm.

Đạt khi một người khác có thể chạy local và hoàn thành chọn file → nhận text → tải TXT. Giao diện chỉ gọi lõi Python; chưa cần một HTTP API độc lập.

Streamlit có sẵn [file uploader](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader) và [audio player](https://docs.streamlit.io/develop/api-reference/media/st.audio). Đây là lựa chọn đề xuất để triển khai giao diện nhỏ, chưa phải dependency đã cài của dự án.

## Bước 4 — Đánh giá nhỏ, đủ giải thích kết quả

- [ ] Chuẩn bị khoảng 20–30 đoạn tiếng Việt, mỗi đoạn khoảng 10–60 giây, từ nhiều người.
- [ ] Có các nhóm lời đọc, giải thích/thuyết trình, lời nói tự nhiên; thêm một ít nhiễu nhẹ.
- [ ] Nghe và kiểm tra reference toàn bộ, giữ dấu tiếng Việt.
- [ ] Tách một phần development nếu chỉnh cấu hình; giữ riêng phần đánh giá cuối. Ghi rõ số người và giới hạn của tập nhỏ.
- [ ] Viết script tính WER với quy tắc chuẩn hóa cố định và báo cách tách theo khoảng trắng; đo thời gian/RTF trên cùng máy.
- [ ] Lưu các ví dụ đúng/sai: sai dấu, tên riêng, thuật ngữ, bỏ hoặc thêm từ.
- [ ] Thử thêm file dài 3–5 phút để kiểm tra vận hành; không dùng một file dài thay cho sự đa dạng người nói.

Đây là dữ liệu đánh giá ứng dụng pretrained, chưa phải dữ liệu train. Có thể tự thu có sự đồng ý hoặc chọn dữ liệu công khai có điều kiện sử dụng phù hợp; nếu có thể trùng với dữ liệu model đã học thì cần ghi rõ.

Không cần tải hàng trăm giờ hay tự huấn luyện từ đầu để hoàn thành phương án BTL này. Nếu giảng viên yêu cầu so sánh, có thể chạy thêm một model trên cùng tập; đó là hạng mục bổ sung có giới hạn.

## Bước 5 — Hoàn thiện báo cáo và demo

- [ ] Giải thích bài toán, model pretrained và pipeline xử lý.
- [ ] Trình bày phần mã tự xây: chuẩn hóa, tích hợp model, video, giao diện, xuất kết quả và đánh giá.
- [ ] Có bảng WER/thời gian thực đo và ví dụ lỗi, không đặt trước một mức chính xác chưa đo.
- [ ] Chuẩn bị một WAV, một MP3, một MP4 và một file lỗi để demo.
- [ ] Viết hướng dẫn cài/chạy, bảo đảm checkpoint sẵn sàng trước buổi demo.
- [ ] Kiểm tra lại từ một phiên chạy mới để phát hiện dependency hoặc đường dẫn thiếu.

Đạt khi có mã nguồn, ứng dụng local, phép đánh giá nhỏ và báo cáo tái hiện được luồng xử lý. Không cần triển khai public để chứng minh chức năng BTL.

## Thứ tự và tiêu chí dừng

Làm lần lượt: nhận dạng thật → audio/video → giao diện → đánh giá → báo cáo. Có thể thu và gán reference trong lúc xây giao diện.

Khi năm bước đạt tiêu chí, ưu tiên sửa lỗi, hoàn thiện tài liệu và tập demo. Nếu còn thời gian và muốn thêm chức năng, chọn một mục nhỏ như sửa/copy transcript hoặc so hai cỡ model; không mở nhiều nhánh đồng thời.

## Tình trạng hiện tại

CLI và demo Streamlit đã chạy với PhoWhisper và FFmpeg trên máy demo. Giao diện nằm trong `frontend/`, lõi nhận dạng nằm trong `backend/asr_engine/`. Bộ đánh giá nhiều bản ghi là bước tiếp theo. Xem [pipeline hiện tại](ASR_PIPELINE_VI.md).
