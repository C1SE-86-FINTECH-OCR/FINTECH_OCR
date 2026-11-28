# Giai đoạn 3 — Kế hoạch trích xuất bảng hàng hóa FINTECH OCR

> Cập nhật 18/11/2026: kế hoạch đã được phê duyệt và prototype offline đã được tiếp tục kiểm thử. Xem [kết quả Giai đoạn 3.1–3.4 và checkpoint](OCR_PHASE3_TABLE_EXTRACTION_RESULTS.md). Nội dung bên dưới giữ lại bằng chứng và kế hoạch trước triển khai; trạng thái mới nhất nằm trong báo cáo kết quả. Parser chưa tích hợp API/Website.

## 1. Kết quả đã xác minh

Số **2/7** là số **dòng hàng** khớp đủ bốn trường mô tả, số lượng, đơn giá và thành tiền trong năm chứng từ tổng hợp đã khóa nhãn. Các engine không nhất thiết đúng cùng hai dòng.

| Chỉ số | Tesseract hiện tại | Tesseract + bố cục | PaddleOCR + bố cục |
| --- | ---: | ---: | ---: |
| Dòng kỳ vọng khớp đúng | 2/7 | 2/7 | 2/7 |
| Dòng dự đoán sai hoặc thừa | 2 | 1 | 1 |
| F1 dòng hàng | 0,364 | 0,400 | 0,400 |
| Khớp toàn bộ danh sách, tính cả mẫu không có hàng | 1/5 | 2/5 | 2/5 |
| Khớp toàn bộ trên bốn chứng từ có hàng | 0/4 | 1/4 | 1/4 |

Mẫu đối chứng NEW-UNKNOWN có bảng rỗng, cả ba nhánh xử lý đúng. Hai nhánh layout đọc PDF nhiều trang qua lớp chữ PyMuPDF, nên thành công của chúng ở ca này phản ánh việc gom bảng theo trang, chưa cho biết chất lượng của engine OCR raster. [Kết quả từng chứng từ](../../ocr_paddle_phase2/results/summary.md) · [Nhãn và kết quả dự đoán](../../ocr_paddle_phase2/results/per-document.csv)

## 2. Nguyên nhân theo từng chứng từ

| Chứng từ | Bằng chứng trong kết quả đã lưu | Nguyên nhân |
| --- | --- | --- |
| NEW-VAT, ảnh nghiêng, tiêu đề lệch | Tesseract hiện tại xuất hai dòng và đúng toàn bộ số. Một mô tả đọc “nối” thành “nói”. Với Tesseract layout, hộp tiêu đề “Tên” ở y=560, “Đơn” ở y=493 và “Thành” ở y=487 trên ảnh benchmark. Chiều cao hộp trung vị 27 px, vùng tìm phía trên tiêu đề mô tả chỉ khoảng 43 px. Paddle còn đọc sai nhãn cột. | Hai tầng độc lập. OCR nhầm chữ làm mất điểm exact ở baseline. Ở nhánh layout, tiêu đề chữ và các cột tiền không nằm cùng hàng hoặc dải tìm cố định. |
| NEW-BILL, bill nhiệt không MST | Văn bản lưu của Tesseract chứa đúng cả hai dòng và giá. Phân loại trả bill nhưng parser bảng trả rỗng. Gọi riêng reader bill trên cùng văn bản lưu trả đủ hai dòng 42.000 và 16.000, giữ trống số lượng/đơn giá. | Điều kiện mở nhánh bill dùng một danh sách nhãn riêng, bỏ sót trường hợp đã phân loại thành bill. Tầng dựng dòng nhận được dữ liệu khi chạy đúng nhánh. |
| NEW-TWO-PAGE, PDF có lớp chữ | Baseline trả đúng dòng ở trang 1 và thiếu dòng ở trang 2. Hai nhánh layout đều trả đúng hai dòng. | Nhánh bảng PDF hiện tại trả về ngay khi tìm được bảng đầu tiên. Nhánh đọc văn bản xét tối đa 12 trang, còn nhánh bảng chỉ xét tối đa 10 và có thể dừng sớm hơn. |
| NEW-BILINGUAL, PDF scan không kẻ bảng | Hai nhánh Tesseract đọc “đo” thành “do” và số lượng 1 thành 4. Hai ô đơn giá và thành tiền vẫn là 582.000. Paddle đọc đúng số lượng và giá, nhưng sai tên có dấu. | Hộp và hàng đã được nhận. Lỗi ở chữ và ô số cần đọc lại. Phép đối chiếu số lượng × đơn giá nhận ra mâu thuẫn ở kết quả Tesseract. ITEM-SUM hiện chỉ so tổng dòng với subtotal nên không phát hiện số lượng sai của mẫu này. |

Chỉ số exact hiện hành giữ dấu tiếng Việt và ghép dòng theo toàn bộ bốn trường. Số dòng đúng thấp đồng thời phản ánh thiếu dòng, đọc sai nội dung và ghép ô chưa chắc chắn. Cần đo riêng các nguyên nhân này để biết thay đổi nào có tác dụng. [Nhận diện tiêu đề lệch hàng](../backend/app/extraction.py#L444) · [Nhánh bảng PDF](../backend/app/extraction.py#L559) · [Điều kiện đọc bill](../backend/app/extraction.py#L683) · [Cách chấm dòng](../backend/tools/ocr_benchmark/scoring.py#L60)

## 3. Kiến trúc đề xuất

**Giữ Tesseract làm mặc định, giữ PaddleOCR và benchmark làm nhánh thử nghiệm.** Phiên bản đầu phát triển offline cạnh công cụ benchmark. Phần chọn tên nhà cung cấp, số hóa đơn, MST, ngày và tổng ở pipeline hiện tại được đối chiếu nguyên trạng để cô lập tác động của thay đổi bảng.

| Tầng | Thiết kế đề xuất |
| --- | --- |
| Đọc tài liệu | Dùng context theo trang gồm văn bản, polygon, điểm OCR, nguồn đọc và phép đổi tọa độ về trang gốc. Chỉnh nghiêng trước khi dùng hình học. Dùng chữ PDF khi có lớp chữ đủ tin cậy và OCR thật cho vùng scan. Lượt thử Tesseract và Paddle nhận cùng ảnh trong phép so sánh đối chứng. |
| Phát hiện vùng bảng | Kết hợp dải tiêu đề một hoặc nhiều dòng, đường kẻ nếu có, mật độ hàng và dãy giá thẳng cột. Ước lượng độ lệch cục bộ và khoảng cách theo cỡ chữ. Với bill đã phân loại, tìm vùng mô tả–giá ở giữa phần thông tin và dòng tổng, đồng thời loại tiền khách đưa, tiền thừa và thông tin liên hệ. |
| Suy ra cột và ghép ô | Tìm các đường biên từ vị trí tiêu đề, dải trống và căn lề của dữ liệu. Gắn vai trò mô tả, số lượng, đơn vị, đơn giá, thành tiền, thuế hoặc giảm giá khi có bằng chứng. Ghép theo giao nhau với vùng cột, khoảng cách theo baseline và kiểu dữ liệu. Khi cột mơ hồ, giữ ứng viên kèm lý do và đưa vào review. |
| Dựng hàng và nối trang | Neo hàng bằng cụm ô số, dấu vết hàng kẻ hoặc số thứ tự nếu đáng tin. Ghép mô tả xuống dòng khi nằm trong cột mô tả, đủ gần và không có dấu hiệu mở hàng mới. Gom bảng theo thứ tự trang, loại tiêu đề trùng và nhận phần tiếp trang không có tiêu đề khi cấu trúc phù hợp. Giữ hai dòng hàng giống nhau nếu chúng ở hai vị trí thật khác nhau. |
| Kiểm tra và đọc lại có mục tiêu | Dùng phép tính số lượng × đơn giá khi các cột thể hiện cùng ngữ nghĩa và đủ dữ liệu. Kiểm tra subtotal, từng nhóm VAT và tổng thanh toán độc lập. Nếu xung đột, OCR lại đúng vùng số hoặc mô tả, rồi giữ null/cảnh báo nếu vẫn mơ hồ. Phép tính dùng để phát hiện hoặc xếp hạng ứng viên có bằng chứng OCR. |

Đầu ra nội bộ của bảng cần giữ page_id, table_id, row_id, vai trò cột, hộp chữ gốc, giá trị chuẩn, điểm tin cậy và lý do cần review. So sánh cấu trúc theo nhãn hàng/cột để một chữ sai dấu không che mất kết quả phân tích bố cục. Vẫn giữ điểm exact toàn dòng làm chỉ số nghiệm thu.

Với nhiều mức thuế, giữ riêng VAT của từng hàng và các nhóm thuế trong kết quả thử nghiệm. Phân biệt 0%, miễn/không chịu thuế, bảng không có thông tin, cột tiền trước thuế và tiền sau thuế. Mô hình hiện tại chỉ có một vat_rate cấp hóa đơn và không có VAT cấp dòng. Phiên bản offline giữ dữ liệu mở rộng trong báo cáo, tránh gán một mức cho cả hóa đơn hay sửa quy tắc validation hiện hành. Việc lưu và hiển thị từng mức thuế cần đề xuất riêng nếu kết quả thử nghiệm cho thấy cần thiết. [Mô hình hóa đơn](../backend/app/models.py#L37) · [Validation](../backend/app/extraction.py#L1815)

Chỉ đánh giá mô hình học máy nhận diện bảng khi thí nghiệm cho thấy vùng bảng hoặc cấu trúc ô vẫn là lỗi chính. PP-Structure/Table Structure Recognition hoặc Table Transformer có thể là nhánh đối chứng hình học, với chữ vẫn lấy từ Tesseract hoặc nguồn chữ phù hợp. Xác minh quyền sử dụng, độ tương thích và chi phí trước khi tải hoặc cài. [PaddleOCR Table Structure Recognition](http<LOCAL_PATH>

## 4. Kế hoạch dữ liệu và phép đo

- Dùng các ca đang phân tích làm ca hồi quy. Khởi động bằng 30–50 chứng từ thực có quyền sử dụng, gồm e-invoice, bill nhiệt, PDF có chữ/scan/hỗn hợp và bản song ngữ. Phủ bảng không viền, mô tả dài, số model giống giá, nhiều VAT, giảm giá, các dòng lặp thật và bảng tiếp nhiều trang. Giữ tài liệu âm có bảng hoặc số tiền nhưng không phải hóa đơn.
- Gán nhãn từ ảnh gốc trước khi xem đầu ra OCR. Hai người kiểm tra độc lập các trường tài chính, dòng hàng và vị trí bảng/ô. Điều hòa khác biệt bằng chứng từ gốc. Phân biệt absent, unreadable và unverified để không chấm dữ liệu chưa xác nhận.
- Giữ manifest, nhãn và SHA-256 riêng. Chia theo nhà cung cấp, họ bố cục và nhóm chứng từ gần trùng, giữ các trang cùng hóa đơn trong một tập. Đóng băng tập test mới trước khi chỉnh thuật toán. Báo cáo riêng dữ liệu tổng hợp, development và hóa đơn thật mới.
- Đo Exact Match và Precision/Recall/F1 từng trường, F1 dòng đúng toàn bộ ô, tỷ lệ bảng đủ dòng và chỉ số xác định đúng hàng/cột. Báo thêm trường bị bỏ sót, dòng thừa, lỗi theo loại tài liệu, p95, tỷ lệ review và kết quả từng hóa đơn. Giữ chính sách chấm exact hiện có và bổ sung điểm theo nguyên nhân bằng phép ghép dòng dựa vào vị trí hoặc nhãn đã xác minh.

## 5. Trình tự thực hiện sau phê duyệt

1. Khóa baseline, quy trình gán nhãn và tiêu chí so sánh. Phân loại lỗi từng tầng ngay trong benchmark.
2. Tạo prototype dựng bảng offline, lần lượt thử chỉnh nghiêng chung, vùng bảng và ghép ô, đọc bill theo kết quả phân loại, ghép trang và kiểm tra từng hàng. Chỉ điều chỉnh trên development.
3. Chạy ba cấu hình trên cùng tập test khóa. Mục tiêu thí điểm là tăng F1 dòng hàng và tỷ lệ bảng đầy đủ trên các nhóm khó, không giảm độ đúng của tổng tiền, VAT, MST, số và ngày hóa đơn ở các nhóm đã qua. Đo cả số liệu theo nhóm và các ca hồi quy cụ thể trước khi đề xuất ngưỡng tích hợp.
4. Sau kết quả offline, xin phê duyệt riêng cho thử nghiệm song song trên UAT. Đối chiếu các trường đã đúng, review/edit, validation và approval. Giữ Tesseract hiện tại có thể khôi phục bằng cấu hình.

Lượt này chỉ phân tích bằng chứng đã lưu và thêm tài liệu. Chưa có tập nhãn mới, chưa chạy benchmark Giai đoạn 3 và chưa thay đổi pipeline, API, Website hay database.
