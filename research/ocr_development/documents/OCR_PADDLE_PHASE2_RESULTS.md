# FINTECH OCR — Kết quả thử PaddleOCR CPU ngày 18/11/2026

## Cấu hình đã chạy

- Môi trường riêng nằm tại ocr_paddle_phase2/.venv, dùng CPython 3.12.16 x64 bản portable của Astral. Phiên bản và SHA-256 của archive đã đối chiếu với metadata phát hành. Bộ benchmark chạy cả ba nhánh trên môi trường này với giới hạn bốn luồng CPU. [CPython portable](http<LOCAL_PATH>
- PaddleOCR 3.3.1, PaddlePaddle CPU 3.3.0, PaddleX 3.3.13. pip check thành công. Smoke test xác minh phép tính tensor CPU và OCR thật trả 23 hộp chữ có tọa độ và điểm nhận dạng. [Wheel Windows CPU](http<LOCAL_PATH>
- Hai trọng số cục bộ là PP-OCRv5_mobile_det và latin_PP-OCRv5_mobile_rec. Đã lưu SHA-256 của archive và các file model trong báo cáo JSON. Pipeline tắt tải model phụ, kiểm tra kết nối model host, tự xoay và unwarp. So sánh nhận dạng có kiểm soát giữa hai nhánh layout dùng cùng ảnh, cùng assembler và parser. Nhánh Tesseract hiện hành giữ pipeline production gồm các lượt đọc bổ sung. PDF có lớp chữ và XML đi qua nhánh chung khi áp dụng.
- Các lần thử cài đặt gặp timeout khi tải wheel, lỗi quyền ghi cache mặc định và lỗi oneDNN không hỗ trợ PIR ArrayAttribute trong detector chạy CPU. Wheel được tải tiếp từ PyPI và kiểm tra SHA-256. Preflight chạy với quyền được duyệt để khởi tạo cache. Adapter benchmark tắt MKL-DNN cho cấu hình thử. Cảnh báo ccache và alias fitz không làm hỏng inference.

Các file vận hành nằm trong thư mục ocr_paddle_phase2 ở workspace, gồm paddle-cpu.lock.txt, model-archive-sha256.txt, paddle-wheel-sha256.txt, paddle_preflight.py, run_cohorts.ps1 và results. Thay đổi mã trong repository giới hạn ở công cụ benchmark ngoại tuyến và tài liệu. Backend hiện tại, API, Website và dữ liệu hóa đơn giữ nguyên.

## Tập tài liệu và quy tắc diễn giải

Tập test tổng hợp mới gồm năm tài liệu có nhãn khóa trước khi chạy. Bốn mẫu là chứng từ hóa đơn, bill hoặc bảng hàng, một mẫu là lịch bảo trì để kiểm tra loại unknown. Tập này có ảnh nghiêng, bill tiếng Việt không MST, PDF chữ hai trang và PDF scan song ngữ. Hai nhóm phát triển được giữ riêng gồm bảy fixture tổng hợp và bảy ảnh lịch sử HD-01–HD-07 đã dùng để phân tích lỗi. HD-01 có nhãn đầy đủ, HD-02 bị loại khỏi chấm điểm và HD-03–HD-07 chỉ chấm các trường đã xác minh.

Chỉ số khớp trường tính cả trường vắng có nhãn null xác nhận. Dòng hàng exact yêu cầu mô tả, số lượng, đơn giá và thành tiền đều đúng theo chuẩn của benchmark. Thời gian là mean/p95 của một lượt chạy tuần tự trên CPU. RAM là đỉnh working set quan sát theo mẫu của cây tiến trình, còn VRAM không áp dụng vì chạy CPU. Báo cáo từng hóa đơn và từng giá trị nằm ở results/summary.md và results/per-document.csv. JSON dự đoán giữ chữ OCR thô của nhánh baseline và các hộp chữ theo trang ở hai nhánh layout.

## Kết quả trên năm chứng từ tổng hợp mới

| Chỉ số | Tesseract hiện tại | Tesseract + bố cục | PaddleOCR + bố cục |
| --- | ---: | ---: | ---: |
| Nhà cung cấp exact | 3/5 | 2/5 | 2/5 |
| MST người bán exact | 5/5 | 5/5 | 4/5 |
| Số hóa đơn exact | 5/5 | 5/5 | 4/5 |
| Ngày lập exact | 5/5 | 5/5 | 3/5 |
| VAT amount exact | 5/5 | 5/5 | 4/5 |
| Tổng thanh toán exact | 5/5 | 5/5 | 3/5 |
| Dòng hàng khớp hết các ô | 2/7 | 2/7 | 2/7 |
| F1 dòng hàng | 0,364 | 0,400 | 0,400 |
| Mean / p95, giây mỗi file | 2,388 / 3,618 | 0,313 / 0,570 | 2,393 / 5,375 |
| RAM đỉnh lấy mẫu, MiB | 207,41 | 175,82 | 426,17 |

Hai nhánh layout cùng ghép đủ hai dòng của PDF nhiều trang bằng dữ liệu PyMuPDF. Trường hợp này đo lợi ích của lớp bố cục và gom trang. Ảnh VAT nghiêng khiến Paddle mất các nhãn như “Ngày lập” và “Mã số thuế”. Bill không MST giữ đúng giá trị MST trống trong cả ba nhánh, nhưng cả ba bỏ sót dòng hàng. Nhánh Paddle cũng bỏ sót tổng bill. Bản scan song ngữ khiến Paddle mất dấu ở tên người bán, người mua, ngày và mô tả dòng hàng. Mẫu ngoài phạm vi được giữ unknown và không sinh dòng hàng ở cả ba nhánh.

Đối chiếu inference.yml của đúng recognizer đã tải cho thấy bộ giải mã có 836 mục và thiếu ế, ệ, ị, ậ, ọ, ữ ở cả dạng ký tự dựng sẵn lẫn dạng tổ hợp. Một số nhãn bị mất chữ dù điểm nhận dạng của hộp cao. model-character-audit.json chứa checksum và các mã Unicode đã kiểm tra. Đây là giới hạn xác minh từ chính trọng số trong đợt thử.

## Kết quả trên hai tập phát triển

| Chỉ số | Tesseract hiện tại | Tesseract + bố cục | PaddleOCR + bố cục |
| --- | ---: | ---: | ---: |
| Tổng hợp — tên người bán exact | 7/7 | 7/7 | 5/7 |
| Tổng hợp — tổng thanh toán exact | 7/7 | 7/7 | 5/7 |
| Tổng hợp — dòng hàng khớp hết các ô | 9/10 | 9/10 | 8/10 |
| Tổng hợp — mean / p95, giây mỗi file | 1,836 / 2,895 | 0,379 / 0,504 | 3,815 / 4,856 |
| Tổng hợp — RAM đỉnh lấy mẫu, MiB | 216,87 | 178,94 | 383,33 |
| Lịch sử — tổng thanh toán exact trên 5 nhãn một phần | 2/5 | 1/5 | 1/5 |
| Lịch sử — dòng hàng của HD-01 | 0/4 | 0/4 | 0/4 |
| Lịch sử — mean / p95, giây mỗi file | 10,988 / 13,484 | 0,918 / 1,425 | 10,999 / 19,051 |
| Lịch sử — RAM đỉnh lấy mẫu, MiB | 198,09 | 204,21 | 536,23 |

Paddle đọc đúng tổng tiền của HD-01 ở bộ lịch sử, trong khi hai nhánh Tesseract sai trường này. Chưa có bằng chứng lặp lại trên bill mới. Cả ba nhánh xử lý xong 19 file mỗi nhánh. Chỉ số này phản ánh việc chương trình chạy hoàn tất, còn chất lượng trích xuất được báo trong bảng. Đã xác minh 57 dòng kết quả từng tài liệu trong CSV và chạy lại 19 bài kiểm thử benchmark/evaluator, tất cả đều đạt. SHA-256 của extraction.py vẫn là c878ec80cb32e1d2f8dada0329e70c6bf4eed708246dcef0ef1b108c094c3218.

## Quyết định tích hợp

Bằng chứng hiện tại chưa đạt điều kiện chuyển engine. Giữ Tesseract làm engine cho Website. Đợt tiếp theo nên dùng tập hóa đơn thật mới có nhãn xác minh, ưu tiên bố cục và nhà cung cấp chưa gặp, rồi chạy lại cả ba nhánh đã khóa. Nếu muốn thử Paddle tiếp trên tiếng Việt, kiểm tra bảng ký tự checkpoint trước, thử chung bước chỉnh nghiêng trên development và đánh giá lại trên một tập test khác. Chỉ đề xuất thử chạy song song trên UAT khi nhánh mới bổ sung được nhóm chứng từ cụ thể mà Tesseract còn thiếu và tỷ lệ sai trường trọng yếu đạt ngưỡng. Pipeline vẫn dựa vào OCR thật và lưu bằng chứng để người dùng xem lại. Cờ lựa chọn engine và luồng review, validation, approval tiếp tục là điều kiện triển khai.

**Khả năng tổng quát trên hóa đơn thật mới chưa được xác minh.** Tập test tổng hợp đã khóa chỉ chứng minh hành vi trên những tình huống được mô phỏng.
