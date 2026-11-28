# Benchmark OCR ngoại tuyến — Giai đoạn 2

Bộ công cụ ở backend/tools/ocr_benchmark. Chạy bằng Python từ thư mục backend. Các nhánh đọc file trực tiếp và gọi parser hiện có, độc lập với FastAPI, SQLite/PostgreSQL và Website.

## Các nhánh thực nghiệm

| Nhánh | Mục đích |
| --- | --- |
| tesseract-current | Baseline gọi đúng text_from_file, extract_fields và extract_line_items của luồng upload hiện tại. |
| tesseract-layout | Tesseract vie+eng trả chữ và hộp từ. PDF có lớp chữ dùng hộp của PyMuPDF. Các trang có cùng định dạng đầu ra cho bước phân tích bố cục. |
| paddle-layout | Cùng đường đọc PDF, cùng ảnh raster, cùng bộ phân tích bố cục và parser như tesseract-layout. Adapter nhận polygon và điểm nhận dạng từ PP-OCRv5. Chạy cần môi trường Paddle riêng và hai thư mục trọng số cục bộ. |

JSON dự đoán của hai nhánh layout lưu tọa độ, thứ tự đọc, loại nguồn, bảng và dòng hàng theo từng trang. Bảng tìm theo cột, có nhánh xử lý tiêu đề lệch hàng và fallback từ text. Chỉ giữ polygon thật mà engine trả về. Tọa độ là pixel của ảnh đưa vào OCR sau EXIF hoặc điểm trang PDF. Hai engine có thể khác độ chi tiết của hộp chữ. Việc ghép một dòng bị ngắt sang trang tiếp theo, phân vùng bảng bằng mô hình chuyên biệt và phủ chuỗi nhãn song ngữ phức tạp vẫn cần thử thêm. Nhánh XML dùng cùng parser cấu trúc cho tất cả engine nên không đo năng lực OCR raster.

## Dữ liệu và cách chạy

Manifest CSV lưu document_id,file,split,origin,supplier_group,layout_family,duplicate_group và language nếu có. file là đường dẫn tương đối bên dưới dataset-root. split nhận development, validation hoặc test. origin nhận real hoặc synthetic. Tool kiểm tra ID, đường dẫn, định dạng, kích thước và chặn cùng SHA-256 hoặc nhóm nhà cung cấp/bố cục/gần trùng xuất hiện ở hai tập. Nhóm gần trùng cần được đội dữ liệu xác định trước. Giữ cùng các trang của một hóa đơn trong một file.

Nhãn là JSON hoặc JSONL. Mỗi dòng có document_id, review_status và expected. Trường đã xác nhận không tồn tại ghi null. Bỏ key khi chưa xác minh. Các tài liệu xác minh một phần dùng partial và chỉ đưa các trường đã xác nhận vào expected. Nhãn approved và partial được báo riêng, excluded không tính điểm. Chỉ ghi items khi có thể xác nhận cả bảng. Mỗi dòng có description, quantity, unit_price và amount. Số hóa đơn, ký hiệu và MST luôn là chuỗi. Số tiền chuẩn dùng giá trị số không có dấu phân cách. Công cụ lưu dự đoán trước khi mở nhãn.

Ví dụ lệnh dùng cùng file cho hai nhánh. Mỗi thư mục đầu ra phải chưa tồn tại.

```powershell
Set-Location '<LOCAL_PATH>
$common = @('--manifest','<LOCAL_PATH>
            '--split','development','--labels','<LOCAL_PATH>
& '.\.venv\Scripts\python.exe' -m tools.ocr_benchmark run --engine tesseract-current @common --output '<LOCAL_PATH>
& '.\.venv\Scripts\python.exe' -m tools.ocr_benchmark run --engine tesseract-layout @common --output '<LOCAL_PATH>
& '.\.venv\Scripts\python.exe' -m tools.ocr_benchmark compare '<LOCAL_PATH>
```

Sau phê duyệt, chạy paddle-layout bằng Python venv riêng với cùng manifest, nhãn, số luồng và max-pages. Dùng thêm --det-model và --rec-model, trỏ tới thư mục model đã giải nén. Công cụ dừng trước khi khởi tạo Paddle nếu thiếu file trọng số hoặc đồ thị. Khởi động với CPU.

report.json có Exact Match, Precision/Recall/F1 theo trường và ô, F1 dòng hàng, khớp toàn bảng, kết quả validation, tỷ lệ review theo cảnh báo, thời gian khởi tạo, mean/p50/p95 trên tài liệu xử lý thành công và bộ nhớ. So sánh kiểm tra SHA-256 của tài liệu, manifest, nhãn, parser và công cụ. Exact giữ dấu tiếng Việt, số 0 đầu, và coi dạng số tương đương như 1000 với 1000.00 là cùng giá trị. So khớp dòng hàng đếm đúng số bản sao, cho phép đổi thứ tự. Các dòng chỉ khớp tên được ghép để đo từng ô. Khi không có nhãn, chỉ số độ đúng trả null.

RAM là đỉnh working set của cây tiến trình đo theo mẫu 0,1 giây trên Windows, gồm tiến trình Tesseract khi quan sát được. Giá trị có thể bỏ lỡ đỉnh xảy ra giữa hai lần lấy mẫu. VRAM để N/A khi CPU; tùy chọn GPU ghi VRAM của PID qua nvidia-smi nếu driver cung cấp số liệu. Các kết quả thời gian là lượt chạy tuần tự một lần trên từng bộ dữ liệu với giới hạn bốn luồng, chưa phải kết quả tải Website hoặc phân tích cold/warm lặp lại.

## Phạm vi phê duyệt PaddleOCR

Đề xuất môi trường Python 3.12 x64 riêng. Kiểm tra Python tương thích trước, sau đó chỉ cài bản CPU PaddlePaddle 3.3.0 và PaddleOCR 3.3.1, cùng thư viện đọc ảnh/PDF và adapter cần dùng. Cần hai model PP-OCRv5_mobile_det và latin_PP-OCRv5_mobile_rec từ kho chính thức. Không cần GPU wheel, CUDA, mô hình bảng lớn hoặc API ngoài cho lần thử này. Kích thước phục vụ cài framework và các dependency lớn hơn kích thước hai trọng số, cần ghi nhận sau khi được phép kiểm tra tải. [PaddlePaddle trên Windows](http<LOCAL_PATH>

Sau khi có kết quả so sánh cùng pipeline layout, bổ sung tập test thực mới có nhà cung cấp và bố cục tách khỏi tập phát triển. Xác nhận độ đúng theo từng nhóm rủi ro và độ trễ trước khi đề xuất adapter FastAPI phía UAT. Khi đó chỉ ánh xạ đầu ra đã qua kiểm tra vào contract hiện tại và duy trì cờ quay lại engine cũ.

## Kết quả chạy

Đã chạy 19 bài kiểm thử benchmark và evaluator. Có kiểm tra giữ polygon/độ tin cậy Paddle từ một payload hợp lệ giả lập, ghép bảng PDF hai trang, chặn trùng giữa các tập, chấm giá trị có số 0 đầu và từ chối so sánh hai bộ khác nhau. Lệnh Paddle thực tế dừng ở kiểm tra hai thư mục trọng số cục bộ, trước khi import model. Inference của PaddleOCR vẫn chưa được thử.

| Tập development và chỉ số | Tesseract hiện tại | Tesseract + layout |
| --- | ---: | ---: |
| 7 tài liệu tổng hợp — từng trường loại, số hóa đơn, ngày, người bán/mua, MST hai bên, subtotal, VAT rate, VAT và tổng | 7/7 mỗi trường | 7/7 mỗi trường |
| 7 tài liệu tổng hợp — ký hiệu có nhãn | 2/2 | 2/2 |
| 7 tài liệu tổng hợp — dòng hàng đúng cả 4 ô, F1 | 9/10, 0,90 | 9/10, 0,90 |
| 7 tài liệu tổng hợp — mean / p95, giây/tài liệu | 1,845 / 2,870 | 0,365 / 0,459 |
| 7 tài liệu tổng hợp — RAM đỉnh theo mẫu, MiB | 177,61 | 140,27 |
| 7 ảnh lịch sử — mean / p95, giây/tài liệu | 10,856 / 13,349 | 0,922 / 1,374 |
| 7 ảnh lịch sử — RAM đỉnh theo mẫu, MiB | 155,42 | 165,65 |
| 5 ảnh lịch sử có nhãn một phần — trường xác minh đúng | 2/9 | 1/9 |
| 5 ảnh lịch sử có nhãn một phần — tổng thanh toán, kể cả nhãn null đã xác minh | 2/5 | 1/5 |
| HD-01 — dòng hàng có nhãn khớp cả 4 ô | 0/4 | 0/4 |

Trên tập tổng hợp, cả hai nhánh nhận đúng giá, lượng và thành tiền của dòng trong bản scan song ngữ, nhưng đọc sai dấu tiếng Việt trong tên hàng. Mẫu thiếu bảng sinh 0 dòng và đi vào review như mong đợi. Trên ảnh lịch sử, HD-01 là tài liệu duy nhất có nhãn approved và là trường hợp bill không MST. Cả hai giữ MST trống, nhưng sai loại, tên người bán, ngày, số hóa đơn, tổng và dòng hàng. Năm ảnh còn lại chỉ chấm các trường đã xác minh. HD-02 không tính độ đúng do chứng từ mẫu bị che/cắt. Thời gian và RAM của bộ lịch sử tính trên cả 7 lần xử lý. Các file HD-01–HD-07 từng dùng để chẩn đoán lỗi và nằm trong development.

Tốc độ của nhánh layout cao hơn trong các lần chạy này vì nhánh thử chỉ chạy một lượt nhận dạng cho mỗi trang ảnh. Nhánh hiện tại còn gọi các lượt đọc lại theo ngữ cảnh. Chênh lệch này là đo hai pipeline Tesseract, chưa phải so sánh engine OCR khác nhau. Nhánh layout nhanh hơn nhưng bỏ sót một tổng thanh toán đã nhận đúng ở nhánh hiện hành trên ảnh lịch sử. CPU không sử dụng VRAM trong các lượt trên.

Bằng chứng tại thư mục workspace ocr_benchmark_pilot gồm manifest và labels của từng tập, report/predictions theo nhánh, **layout-comparison.json** và **historical-comparison.json**. Báo cáo JSON có kết quả từng trường, từng ô, từng tài liệu và nhóm ngôn ngữ. Các file này có thể chứa dữ liệu hóa đơn nên giữ cục bộ.

**Trạng thái**. Benchmark offline và hai nhánh Tesseract đã chạy. PaddleOCR và tập test thực chưa từng xem chưa có kết quả. Chưa thể kết luận PaddleOCR cải thiện độ chính xác hoặc hiệu năng so với Tesseract.
