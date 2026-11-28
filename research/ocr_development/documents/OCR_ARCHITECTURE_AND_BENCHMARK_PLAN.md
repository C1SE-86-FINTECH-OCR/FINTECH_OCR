# FINTECH OCR C1SE.86 — Khảo sát và kế hoạch nâng cấp OCR

## 1. Kiến trúc hiện tại

FastAPI cung cấp upload PDF, JPG, PNG và XML cho Employee. Route giới hạn dung lượng mặc định 20 MB, kiểm tra chữ ký tệp PDF/JPG/PNG, lưu tệp gốc kèm SHA-256 và gọi ba bước đọc văn bản, trích xuất trường và trích xuất dòng hàng. JPEG được parser xử lý nhưng đuôi .jpeg chưa nằm trong danh sách upload của API. OCR chạy trực tiếp trong request upload, nên thời gian OCR và các lần đọc lại ảnh ảnh hưởng đến thời gian trả HTTP. [Route upload](../backend/app/main.py#L363) · [Cấu hình](../backend/app/core.py#L14)

| Đầu vào | Cách đọc hiện tại | Phạm vi và giới hạn |
| --- | --- | --- |
| JPG, PNG | Pillow chỉnh EXIF, độ tương phản và nghiêng nhẹ. Tesseract cục bộ chạy vie+eng, PSM 11/6, OSD khi thiếu trường, có lượt đọc lại vùng tài chính hoặc tên công ty. | Góc nghiêng nhẹ được xử lý trong khoảng ±5°. Ảnh chói, mờ, nhăn hoặc méo phối cảnh vẫn cần đo riêng. |
| PDF có lớp chữ | PyMuPDF lấy văn bản nếu trang có hơn 40 ký tự sau khi bỏ khoảng trắng. Có thể đọc tọa độ chữ cho bảng. | Một lớp chữ lỗi hoặc một ít chữ sẵn trên trang scan có thể khiến OCR toàn vùng ảnh bị bỏ qua. |
| PDF scan hoặc hỗn hợp | Render trang thiếu text và gọi nhánh OCR ảnh. | Nhánh văn bản đọc tối đa 12 trang và cắt còn 60.000 ký tự. Nhánh bảng tọa độ xét tối đa 10 trang và trả ngay bảng đầu tiên đọc được. Hai nhánh có thể xử lý các trang khác nhau. |
| XML | Đọc cấu trúc HDon/DLHDon, NBan/NMua và HHDVu theo tên thẻ, sau đó dùng parser trường và ánh xạ dòng hàng. | Đây là dữ liệu có cấu trúc. Hóa đơn XML của hệ thống khác cần kiểm tra schema riêng. Nhánh HHDVu hiện trả null cho đơn vị, số lượng và đơn giá. |
| Song ngữ Việt–Anh | Tesseract có vie/eng. Parser nhận một số nhãn Anh–Việt. | Tài liệu có hai bộ nhãn, dấu số theo hai quy ước hoặc nhiều giá trị cạnh nhau chưa có benchmark phân nhóm. |

[Đọc tài liệu](../backend/app/extraction.py#L1303) · [Trích xuất dòng](../backend/app/extraction.py#L803) · [Nhánh bảng PDF](../backend/app/extraction.py#L559) · [Tiền xử lý ảnh](../backend/app/extraction.py#L904)

Phân loại einvoice, bill, unknown hiện dựa vào nhãn và dấu hiệu cấu trúc như MST, số hóa đơn, ngày và VAT. Sau đó parser đọc các trường từ chuỗi văn bản. Tọa độ từ PyMuPDF hoặc Tesseract được dùng ở một số nhánh bảng và khôi phục số liệu, nhưng chưa có lớp bố cục chung cho toàn bộ tài liệu. Hàm lấy hộp chữ Tesseract giữ tọa độ và văn bản, chưa đưa độ tin cậy từng từ vào hàm chọn trường. [Phân loại](../backend/app/extraction.py#L1337) · [Hộp chữ OCR](../backend/app/extraction.py#L593)

Kết quả được lưu vào invoices, invoice_items và extraction_runs, gồm văn bản OCR, JSON và trạng thái lượt trích xuất. validation_results lưu kết quả theo lần kiểm tra. GET chi tiết đọc dữ liệu đã lưu và áp dụng quyền truy cập. Web có file gốc, bảng dòng hàng, cảnh báo và form chỉnh sửa cho Employee có quyền ở draft/rejected. Thao tác sửa ghi invoice_corrections và kiểm tra lại. Validation, Approval và Lookup có trạng thái riêng. [Lưu dữ liệu và API](../backend/app/main.py#L363) · [Mô hình dữ liệu](../backend/app/models.py#L25) · [Lưu chỉnh sửa](../backend/app/main.py#L432) · [Trang chi tiết](../web/src/InvoiceDetailPage.jsx)

## 2. Các điểm làm giảm khả năng tổng quát hóa

| Nhóm | Quy tắc hiện tại và hậu quả cần đo |
| --- | --- |
| Người bán, người mua, MST | Tìm nhãn, vùng đầu văn bản, số dòng lân cận và dấu hiệu loại hình doanh nghiệp. Khi OCR đảo thứ tự đọc, tên và MST dễ thuộc hai khối khác nhau. Nhãn vai trò ở chữ ký có thể cạnh tranh với nhãn ở phần thông tin nếu OCR làm mất ranh giới. |
| Số hóa đơn, ký hiệu, ngày | Regex quét khoảng 20 dòng đầu cho số, 24 cho ngày và 35 cho ký hiệu. Nhãn song ngữ, nhãn xuống dòng, ngày ký và mã đơn hàng làm tăng nhập nhằng. |
| VAT và số tiền | Nhãn tổng thanh toán được xếp ưu tiên, nhiều giá trị ưu tiên bằng nhau có thể dẫn đến bỏ trống. Một số lượt đọc lại dùng cửa sổ ảnh cố định theo tỷ lệ trang. Quy tắc dấu chấm/phẩy và một thuế suất chưa bao phủ đầy đủ chứng từ đa tiền tệ, nhiều thuế suất, giảm giá, phụ phí hoặc hóa đơn điều chỉnh. |
| Bảng hàng hóa | Parser thử cột phân tách, bảng có tiêu đề và dòng đánh số, bố cục theo tọa độ, hoặc dòng bill có giá ở cuối. Các ngưỡng và tên cột vẫn giả định bố cục quen thuộc. Dòng dài, ô ghép, thiếu tiêu đề, bảng tiếp trang và nhiều bảng có thể làm mất hoặc đếm trùng dòng. Một kết quả có vài dòng có thể khiến nhánh khác không được gọi. |
| Trường thiếu và điểm tin cậy | confidence_score là tỷ lệ điền nhóm trường chính. Điểm 1.0 vẫn có thể xảy ra khi điền sai hoặc thiếu bảng. Validation phát hiện nhiều lỗi số học nhưng số liệu cộng khớp vẫn có thể bắt nguồn từ cột sai. |
| Giới hạn và vận hành | Các lượt OCR bổ sung mở lại ảnh/PDF và chạy engine nhiều lần. OCR đồng bộ trong request có thể giữ tài nguyên xử lý khi nhiều người upload. Giới hạn trang hiện tại cần thông báo khi kết quả bị cắt. |

[Quy tắc số và ngày](../backend/app/extraction.py#L1383) · [Các khối người bán/người mua](../backend/app/extraction.py#L1429) · [Số tiền và VAT](../backend/app/extraction.py#L1567) · [Validation](../backend/app/extraction.py#L1815)

Trong các đường xử lý đã khảo sát, rủi ro chính đến từ giả định theo nhãn, tọa độ và thứ tự đọc. Tên nhà cung cấp, MST và số tiền của ca FPT xuất hiện dưới dạng dữ liệu kỳ vọng trong kiểm thử, còn parser làm việc trên văn bản và vị trí nhận được. Ca PNG mục tiêu và 5 chứng từ tổng hợp đã qua Chrome UAT biệt lập ở lượt trước. Bộ 7 ảnh HD-01–HD-07 đã được xem để phân tích lỗi, nên chỉ dùng cho phát triển hoặc hồi quy. Chưa có benchmark mới của bản hiện tại trên hóa đơn thực tế chưa từng được xem. [Bằng chứng UAT](../../ocr_uat_evidence_00012345/REPORT.md) · [Ghi chú tập HD-01–HD-07](OCR_REAL_DOCUMENT_EVALUATION.md)

## 3. Pipeline đề xuất

1. **Tiếp nhận và tiền xử lý.** Giữ nguyên bytes và SHA-256 của tệp gốc. Xử lý theo trang, ghi biến đổi xoay/nghiêng để ánh xạ tọa độ về ảnh gốc. Kiểm tra tính hữu dụng của lớp văn bản theo trang/vùng, ghép OCR với text có sẵn khi cần. Giữ lối đi XML theo schema. Ghi rõ trang đã xử lý, trang bị cắt và lý do.
2. **Nhận dạng chữ và bố cục.** Mỗi trang trả văn bản, polygon, thứ tự đọc, điểm nhận dạng và mã nguồn đọc như pdf-text, raster OCR hoặc XML. Phát hiện khối thông tin, bảng, tổng kết, chữ ký và footer. Dùng cùng một biểu diễn trang cho các tầng sau để giảm OCR lặp.
3. **Phân loại và trích xuất trường.** Dùng tín hiệu từ chữ và bố cục để phân loại einvoice/bill/unknown. Ưu tiên ứng viên có liên kết nhãn–giá trị và cùng khối nghiệp vụ. Lưu ứng viên và bằng chứng theo trang/vùng khi cần phân xử. Bắt đầu bằng bộ xếp hạng đơn giản dựa trên vị trí, nhãn và kiểu dữ liệu, rồi thử mô hình gán nhãn nếu benchmark cho thấy đây là điểm nghẽn.
4. **Dòng hàng.** Phát hiện vùng bảng và vai trò cột, dựng hàng theo ô và vị trí. Nối dòng móc sang hàng trước khi hình học ủng hộ, loại tiêu đề lặp khi nối trang, giữ số model trong mô tả. Loại tổng phụ, VAT và phần thanh toán khỏi bảng. Bảng không có khung và bill nhiệt được chấm riêng.
5. **Chuẩn hóa và kiểm tra.** Lưu dữ liệu gốc và dạng chuẩn. Dùng Decimal hoặc số nguyên theo đơn vị nhỏ nhất, ngày ISO, số hóa đơn/MST dạng chuỗi giữ số 0 đầu. Phân biệt tiền phải trả, tiền khách đưa và tiền thừa. Dữ liệu vắng mặt hoặc mâu thuẫn để null hay đưa vào review. Giữ nguyên ITEM-SUM hiện tại ở lần so sánh đầu để kết quả có thể đối chiếu công bằng. Nếu cần xác nhận quy tắc giảm giá hoặc nhiều VAT, đây là thay đổi nghiệp vụ cần duyệt riêng.
6. **Độ tin cậy và người kiểm tra.** Tách độ đầy đủ, điểm nhận dạng chữ, mức chắc chắn gán trường và nhất quán số học. Hiệu chỉnh ngưỡng theo validation có ground truth, theo dõi cả tỷ lệ chấp nhận nhầm và tỷ lệ cần review. Trường trọng yếu mơ hồ, thiếu trang hoặc xung đột giá trị đi vào review. Lưu vị trí vùng nghi vấn để người dùng đối chiếu trên bản gốc. Giữ quyền chỉnh sửa hiện tại và lịch sử correction. Một hóa đơn qua kiểm tra số học vẫn nằm trong quy trình phê duyệt hiện có.

Giao diện giữa các tầng nên có một đối tượng kết quả nội bộ gồm loại chứng từ, danh sách trang, fields, items, diagnostics và phiên bản engine/config. FastAPI chuyển đối tượng này sang contract hiện tại. Thông tin chẩn đoán có thể thử với JSON của extraction_runs hoặc file trong thư mục benchmark cô lập, tùy giới hạn lưu trữ và quyền đọc. Chỉ lưu thông tin cần thiết, tránh in hóa đơn hoặc token vào log vận hành.

## 4. Công nghệ và tài nguyên

Máy Windows 11 đã kiểm tra có Core i5-12450HX, 8 lõi/12 luồng, 15,7 GiB RAM, RTX 2050 4.096 MiB VRAM với khoảng 3.883 MiB trống khi khảo sát. Ổ C còn khoảng 35,5 GiB và D còn 163,8 GiB. Driver NVIDIA nhận GPU. Chưa xác nhận bộ thư viện CUDA hoạt động qua framework vì môi trường hiện tại chưa có framework AI.

Backend đang dùng Python 3.14.7, Tesseract 5.5.3.20260724 với eng/vie/osd, pytesseract 0.3.13, Pillow 12.3.0 và PyMuPDF 1.28.2. Chưa có PaddleOCR, PaddlePaddle, torch, transformers, ONNX Runtime hay OpenCV trong venv được kiểm tra. Tài liệu PaddlePaddle Windows đã tra cứu liệt kê Python 3.9–3.13, chưa liệt kê 3.14. Nếu chọn Paddle, ưu tiên một môi trường Python 3.11 hoặc 3.12 riêng tương thích với wheel đã chọn. [Cài đặt PaddlePaddle Windows](http<LOCAL_PATH>

| Ứng viên | Điểm mạnh | Giới hạn và thứ tự thử |
| --- | --- | --- |
| Tesseract/PyMuPDF hiện tại | Baseline cục bộ đã chạy. Dễ giữ đường tương thích và đối chiếu lỗi. | Đo lại trên data mới. Dùng ứng viên Tesseract với cùng lớp bố cục/trích xuất mới để biết phần cải thiện đến từ parser hay engine. |
| PaddleOCR PP-OCRv5 Latin hoặc PP-OCRv6 tiny/small | Có hỗ trợ tiếng Việt và đầu ra hộp chữ. Có lựa chọn nhẹ để thử trên CPU trước. PP-OCRv5 Latin có cả Anh/Việt trong tài liệu triển khai. | Nhận dạng chữ chỉ là một tầng. Đo riêng Việt–Anh, dấu và chuỗi số trên hóa đơn. Khóa phiên bản và cấu hình. [PP-OCRv5 Latin](http<LOCAL_PATH>|
| PP-StructureV3 tùy chọn nhẹ | Tách vùng bố cục và bảng, có thể ghép với OCR tiếng Việt. Tài liệu chính thức hỗ trợ CPU. | Cấu hình đầy đủ tốn bộ nhớ. Bắt đầu với detector/bảng cần thiết và tắt công thức/biểu đồ. Đo batch 1 trên máy nhóm. Số benchmark từ Xeon/V100/A100 của nhà cung cấp không dự báo tốc độ máy này. [PP-StructureV3](http<LOCAL_PATH>|
| LayoutLMv3 / LayoutXLM | Dùng chữ, tọa độ và ảnh để gán vai trò như tên người bán hay MST người mua. LayoutXLM là ứng viên đa ngôn ngữ. | Cần OCR đầu vào, nhãn vùng/token và dữ liệu tiếng Việt để fine-tune. Bảng và quan hệ giữa các ô vẫn cần thiết kế. Checkpoint base đã xem có CC BY-NC-SA 4.0, cần rà soát giấy phép cho mục đích triển khai. [LayoutLMv3](http<LOCAL_PATH>|
| Donut | Mô hình ảnh sang chuỗi, hữu ích để so sánh ở một tập khó vì tránh lệ thuộc vào chữ OCR đầu vào. | Cần nhãn ảnh–đầu ra để học schema. Giá trị sinh ra cần đối chiếu bằng chứng và kiểm tra số học. Dữ liệu tiếng Việt và bộ nhớ là rủi ro lớn hơn. Xếp sau thí nghiệm OCR/bố cục. [Bài báo Donut](http<LOCAL_PATH>|

Đề xuất chạy baseline và ứng viên CPU với một tiến trình OCR, một trang mỗi batch. Thử 4 luồng CPU trước để chừa tài nguyên cho FastAPI và Vite. Lấy 6 GiB RAM đỉnh cho tiến trình OCR làm ngân sách thử trên máy 16 GiB và đo lại khi chạy cùng ứng dụng. So sánh GPU 4 GiB với cùng cấu hình nhẹ khi runtime đã được xác nhận, theo dõi RAM và VRAM đỉnh, lỗi hết bộ nhớ, thời gian tải model và thời gian xử lý ổn định. Với fine-tuning, thử đóng băng encoder hoặc kỹ thuật tiết kiệm bộ nhớ sau khi đủ nhãn. Nếu vẫn vượt 4 GiB, cân nhắc máy được cấp phép có GPU 8–16 GiB để thử nghiệm. Đây là ngân sách dự kiến, chưa phải yêu cầu tối thiểu hoặc số đo dự án. Đặt quota dung lượng model/cache và artifacts sau khi chốt cấu hình. Kiểm tra giấy phép tài liệu, thư viện và từng model weight trước khi dùng.

## 5. Dataset, nhãn và cách đo

Giữ manifest và ground truth riêng như công cụ hiện nay. Manifest mở rộng gồm document_id, đường dẫn tương đối, SHA-256, supplier_group, template_family, duplicate_group, loại chứng từ, định dạng, ngôn ngữ, số trang, mức chất lượng và nguồn/điều kiện sử dụng. JSONL nhãn có version, trạng thái duyệt và các trường chuẩn, gồm số, ký hiệu, ngày, người bán/mua và MST tương ứng, currency, tiền trước thuế, VAT, các khoản điều chỉnh, tổng phải trả, danh sách dòng, số lượng, đơn vị, đơn giá, thành tiền. Trường cần học bố cục có page_id và bbox/polygon. Mỗi trường phân biệt present, absent, unreadable và unverified. Chỉ dùng giá trị đã được người gán nhãn xác nhận để chấm chính thức. Số 0 khác null. Duyệt chéo các trường trọng yếu, các trường mơ hồ và một mẫu ngẫu nhiên đã gán nhãn.

- **Pilot**: 30–50 tài liệu thực được phép dùng. Phủ hóa đơn điện tử, bill không MST, tài liệu ngoài phạm vi, Việt/Anh/song ngữ, PDF text/scan/hỗn hợp, JPEG/PNG, nhiều trang, bảng không viền, hóa đơn nhiều dòng và ảnh kém. Báo cáo thiếu nhóm và số mẫu. Pilot dùng để tìm lỗi và đo tài nguyên.
- **Nghiệm thu**: đóng băng test mới trước khi phát triển. Mục tiêu thu tối thiểu 100 chứng từ test thực cho các nhóm chính, ưu tiên đủ mẫu ở các nhóm khó. Đây là quy mô lập kế hoạch, chưa có sẵn và không thay thế phân tích khoảng tin cậy.
- **Chia tập**: sau khi có đủ nhóm, có thể bắt đầu 70/15/15 cho train/validation/test, điều chỉnh để test đạt quy mô trên. Chia theo nhóm nhà cung cấp, họ mẫu, cùng số chứng từ và các bản gần trùng, thay vì chia ngẫu nhiên theo file. Dùng SHA-256 cho trùng byte, fingerprint hình ảnh và rà thủ công cho ảnh chụp lại, cắt hoặc PDF và ảnh của cùng tài liệu. Tất cả trang của một hóa đơn ở một tập. Báo cáo riêng nhóm nhà cung cấp/mẫu chưa từng gặp và cùng mẫu nhưng chứng từ mới.
- **Fine-tuning**: thu nhãn theo lỗi chi phối. Lỗi nhận dạng cần ảnh crop và chữ chuẩn. Lỗi gán trường cần bbox/token và nhãn vai trò. Lỗi bảng cần ô, hàng/cột và liên kết dòng tiếp trang. Có thể lập pilot fine-tune với vài trăm chứng từ train đã duyệt nếu thu được đủ nhóm, theo dõi đường học trên validation. Giữ test chính thức riêng với người phụ trách chấm. Dữ liệu tổng hợp có thể dùng phát triển, hồi quy và bổ trợ train, báo cáo riêng với chất lượng hóa đơn thực.

Công cụ hiện tại đã xuất dự đoán trước khi đọc nhãn, hỗ trợ nhãn đã duyệt/xác minh một phần, exact/normalized và phân nhóm. Công cụ chấm dòng theo thứ tự, danh sách trường chưa có ký hiệu, người mua, MST người mua, VAT rate và currency, đồng thời chưa có Precision/Recall/F1, phép đo thời gian, độ tin cậy, chia nhóm chống rò rỉ và XML. Nên mở rộng công cụ sau phê duyệt, giữ output cũ cho khả năng đối chiếu. [Evaluator](../backend/tools/evaluate_ocr_dataset.py)

| Chỉ số | Cách đo dự kiến |
| --- | --- |
| Exact Match và F1 trường | Exact theo giá trị chuẩn, giữ dấu tiếng Việt và số 0 đầu ở mã. Đo normalized bổ sung theo quy tắc công bố. Với trường có mặt, dự đoán đúng là TP, giá trị sai là FP và FN, bỏ sót là FN, sinh giá trị cho trường vắng là FP. Báo micro/macro và mẫu số từng trường. Không tính trường chưa xác minh là sai hay đúng. |
| Phân loại | Macro F1 và ma trận nhầm lẫn 3 lớp, cùng độ chính xác/chấp nhận đúng cho từng loại. |
| Dòng hàng | Ghép một đối một theo nhận dạng hàng và thứ tự/vị trí khi có, rồi tính Precision/Recall/F1 dòng và Exact Match từng ô. Dòng thiếu/thừa và dòng trùng được phạt. Báo tỷ lệ hóa đơn có tất cả dòng đúng. |
| Số học | Tỷ lệ các kiểm tra chạy được và tỷ lệ nhất quán trên các chứng từ đủ dữ liệu, gồm subtotal, VAT, tổng và ITEM-SUM. Báo riêng tỷ lệ nhất quán nhưng khác ground truth. |
| Review và calibration | Tỷ lệ đưa vào review, tỷ lệ bỏ lọt lỗi trọng yếu ngoài review, tỷ lệ review quá mức. Vẽ đường coverage so với tỷ lệ lỗi theo ngưỡng và chốt ngưỡng trên validation. |
| Hiệu năng và tích hợp | Mean/p50/p95 theo trang và tài liệu, tách cold/warm và lần thất bại. Ghi RAM/VRAM đỉnh, tỷ lệ timeout, upload/lưu/read-back; báo offline và HTTP/browser riêng. |

**Mục tiêu thí điểm đề xuất**: macro F1 phân loại và trường trọng yếu ≥90%, Exact Match tổng phải trả ≥95%, F1 dòng hàng ≥85%, lỗi trọng yếu bị bỏ qua review ≤2% trong nhóm kết quả được chấp nhận. Ban đầu theo dõi tỷ lệ review, chưa đặt mục tiêu hạ bằng cách giảm cảnh báo. Lấy p95 ≤15 giây cho một trang khi chạy tuần tự ở chế độ warm làm mốc thử khả năng phục vụ, rồi chốt ngưỡng vận hành sau baseline và đo tải. Tất cả là mục tiêu dự kiến và cần công bố số lượng mẫu cùng khoảng tin cậy. Mẫu ít không đủ chứng minh mức lỗi 2%.

## 6. Lộ trình triển khai và kiểm thử

| Bước | Công việc và điều kiện qua bước |
| --- | --- |
| 1. Đóng băng benchmark | Chốt nhãn, chia tập và tiêu chí. Chạy pipeline hiện tại offline, lưu checksum nguồn/config, phiên bản engine, tham số, kết quả và lỗi. |
| 2. Thử pipeline mới ngoại tuyến | So sánh Tesseract gốc, Tesseract với cùng parser bố cục mới, Paddle OCR nhẹ với cùng parser, sau đó thêm mô-đun bảng nếu có ích. Tách phần đóng góp của mỗi thay đổi. Dùng development/validation để chọn cấu hình và ngưỡng. |
| 3. Đo cùng bộ test | Chạy baseline và ứng viên đã khóa trên cùng tài liệu, cùng quyền sử dụng và phần cứng. So sánh theo cặp, theo nhóm và kèm khoảng tin cậy theo nhóm chứng từ. Chạy chính thức sau khi chốt; nếu nhóm phát triển dùng lỗi test để chỉnh tiếp, dành một test mới. |
| 4. Fine-tuning nếu cần | Chỉ thực hiện khi đã chỉ ra nhóm lỗi, đủ nhãn được duyệt, chi phí và giấy phép phù hợp. Đánh giá lại theo cùng quy trình, giữ bài toán bảng, trường và OCR riêng để dễ chẩn đoán. |
| 5. Tích hợp FastAPI có thể rollback | Thêm adapter và cờ chọn engine, mặc định giữ engine hiện hành. Đầu tiên chạy ứng viên bên ngoài hoặc trên bản sao được phép. Sau phê duyệt dùng UAT cô lập, ánh xạ sang API hiện có, kiểm thử quyền và Review/Edit. Hạn chế CPU/GPU, giới hạn trang và timeout. Chỉ chuyển qua worker nếu đo tải cho thấy cần thiết. |
| 6. Nghiệm thu và chuyển có kiểm soát | Với file mới, xác minh Chrome upload, JSON API, tệp gốc và checksum, bảng lưu và mở lại sau restart, sửa thủ công, validation và audit. Chạy toàn bộ backend tests, web build và hồi quy browser/RBAC. Bật dần dựa trên tiêu chí đã duyệt. Khi cần rollback, chuyển cờ về engine cũ cho lượt upload mới, giữ kết quả cũ và lịch sử. |

Các nhóm hồi quy bắt buộc gồm PDF có lớp chữ lỗi, PDF scan hỗn hợp và bảng qua trang, bill không MST, hóa đơn hai ngôn ngữ, dấu tiền tệ, ngày ký cạnh ngày lập, MST gần khối chữ ký, mã model giống số tiền, ô trống, giảm giá/đa VAT, cảnh báo ITEM-SUM, file quá cỡ hoặc quá nhiều trang, timeout/OOM và hai upload đồng thời.

| Rủi ro | Kiểm tra và cách giảm thiểu |
| --- | --- |
| Kết quả đẹp do mẫu hoặc nhà cung cấp lặp lại | Kiểm tra nhóm trùng trước khi chia tập, khóa test và báo riêng nhóm mẫu/nhà cung cấp mới. |
| Giá trị tự sinh hoặc chọn nhầm cột dù tổng vẫn khớp | Yêu cầu bằng chứng theo trang cho trường trọng yếu, kiểm tra với ground truth và đo lỗi nằm ngoài nhóm review. Kiểm thử riêng tài liệu thiếu hoặc mâu thuẫn. |
| Tắc upload hoặc hết bộ nhớ | Đo nhiều trang và tải đồng thời, giới hạn độ phân giải/số trang/timeout, theo dõi p95 và khả năng phục hồi. |
| Lộ dữ liệu hoặc mất lịch sử chỉnh sửa | Giữ tài liệu và mẫu thử cục bộ, kiểm tra log và các API file gốc theo RBAC. So sánh checksum, API và dữ liệu sau restart. Tách nhãn chuẩn khỏi correction của người dùng. |
| Cấu hình mới làm giảm chất lượng một nhóm quan trọng | So sánh theo từng loại và bố cục, ưu tiên nhóm trọng yếu. Giữ cờ rollback và kiểm tra cả hai đường đi API trên UAT. |

**Đề xuất phê duyệt trước**: đồng ý bước 1 và thống nhất nhóm người gán nhãn hoặc cung cấp 30–50 tài liệu pilot được phép dùng. Sau khi có baseline và đo tài nguyên, chọn cấu hình ứng viên và phạm vi cài đặt trong một lượt phê duyệt riêng.
