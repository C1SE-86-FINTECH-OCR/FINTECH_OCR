# Giai đoạn 6 — Kế hoạch nghiệm thu OCR độc lập

Ngày 18/11/2026. Đây là kế hoạch, chưa có bộ mới được duyệt hoặc kết quả nghiệm thu.

## 1. Dữ liệu và phân tách

Dùng thư mục mới **ngoài repository**: `<LOCAL_PATH>`. Chưa tự tạo nhãn hoặc chạy OCR trong thư mục này. Giữ riêng `ocr_phase35_acceptance` và 10 ảnh đã dùng phát triển; không đổi tên rồi gọi chúng là held-out.

Đề xuất tiếp nhận 30–50 chứng từ thật được phép sử dụng, đa nhà cung cấp/mẫu: VAT PDF text, VAT JPG/PNG, PDF scan nhiều trang, bill nhiệt không MST, nhiều dòng và tên xuống dòng, nhiều VAT, bảng khác nhau, Việt–Anh. Các nhóm có thể giao nhau; báo số mẫu mỗi nhóm, không dùng một tài liệu đại diện để khẳng định mọi loại. Chuẩn bị nhóm ảnh khó riêng để tách chất lượng nguồn khỏi chất lượng parser.

Danh mục loại trừ đã chuẩn bị: [known_documents_development.json](../../ocr_phase6_development/known_documents_development.json), **35 hash** gồm dữ liệu cũ và toàn bộ 10 ảnh hiện tại. Kiểm tra SHA-256, ảnh gần trùng, trang PDF, mẫu và nhóm nhà cung cấp bằng mắt. Các trường supplier_group/layout_family/duplicate_group phải phản ánh mẫu thực; không đổi nhóm để vượt chặn leakage. Gate hiện tại chặn cả nhóm trùng, là chính sách bảo thủ cần giữ cho phép đo độc lập.

## 2. Nhãn trước inference

Người A đọc ảnh/PDF gốc để ghi nhãn, người B kiểm tra độc lập. Hai định danh khác nhau, ngày xác minh, hash ảnh, quyền sử dụng và xác nhận chưa dùng phát triển/chưa xem prediction phải là bằng chứng thực. Không tự điền A/B hoặc approved từ chatbot.

- Lưu loại, seller/buyer/MST, số/ký hiệu/ngày, tiền hàng, VAT và tổng khi được in rõ. Định danh là chuỗi để giữ số 0 đầu, tiền là số hữu hạn.
- Mỗi dòng có description, unit, quantity, unit_price, amount và page; VAT từng dòng nếu có. Phân biệt 0/null. Không suy số lượng hoặc đơn giá từ phép chia.
- Không xuất hiện: chỉ đặt null khi người kiểm thử đã xác minh thực sự vắng. Không đọc được/chưa chắc: bỏ key khỏi expected, ghi source_issues và giữ partial/draft. Items chưa đọc đủ thì bỏ key items; không dùng [] thay nhãn đầy đủ.
- Ghi rõ chính sách giảm giá/phụ phí/quà/vé và phạm vi subtotal theo chứng từ. Không cộng/trừ lại khoản đã nằm trong tổng.
- Chép transcription đầy đủ từng trang bằng người kiểm thử nếu muốn CER/WER; không lấy raw OCR làm ground truth. Nếu chưa có thì CER/WER NOT TESTED.

## 3. Công cụ và PowerShell

Chạy từ `FINTECH_OCR_GitHub\backend`; các lệnh sau chỉ dành cho thư mục bộ mới, không ghi database:

```powershell
$python = '.\.venv\Scripts\python.exe'
$dataset = '<LOCAL_PATH>
& $python -X utf8 -m tools.ocr_benchmark.acceptance init --dataset-root $dataset
```

Chỉ chạy init một lần khi chưa có thư mục. Chép file được phép vào documents, rồi điền documents.csv với header công cụ vừa tạo: document_id,file,split,origin,supplier_group,layout_family,duplicate_group,language,categories. Dùng split=test, origin=real, đường dẫn tương đối documents/..., nhóm chính xác và category theo danh sách công cụ. Không điền file/nhãn mẫu để giả bộ có dữ liệu.

```powershell
& $python -X utf8 -m tools.ocr_benchmark.acceptance prepare --dataset-root $dataset
```

Prepare chỉ tạo draft metadata/hash/pages, không tự trích xuất đáp án. A/B hoàn tất ground_truth.json theo quy tắc trên. Khóa source và cấu hình trước khi freeze:

```powershell
$known = '<LOCAL_PATH>
$tag = [DateTimeOffset]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff')
$frozen = Join-Path $dataset "frozen_$tag"
& $python -X utf8 -m tools.ocr_benchmark.acceptance freeze --dataset-root $dataset --known-documents $known --output $frozen
if ($LASTEXITCODE -ne 0) { throw 'Chưa đủ điều kiện xác minh; không chạy inference' }
```

Sau freeze thành công mới chạy bốn nhánh trên cùng snapshot. Không dùng script cũ cố định table-v3 để gọi đó là Hybrid.

```powershell
$env:PYTHONHASHSEED = '0'
foreach ($ocrEngine in @('tesseract-current','tesseract-context-v4','tesseract-region-v5','tesseract-hybrid-v6')) {
    $runPath = Join-Path $dataset "$ocrEngine`_$tag"
    & $python -X utf8 -m tools.ocr_benchmark run --engine $ocrEngine --manifest "$frozen\documents.csv" --dataset-root $dataset --split test --labels "$frozen\labels.json" --cpu-threads 1 --output $runPath
    if ($LASTEXITCODE -ne 0) { throw "Inference lỗi: $ocrEngine; giữ log, không chấm PASS" }
    & $python -X utf8 -m tools.ocr_benchmark.acceptance evaluate --frozen $frozen --run $runPath --output "$runPath`_acceptance"
    if ($LASTEXITCODE -ne 0) { throw "Evidence/scoring lỗi: $ocrEngine" }
}
```

CLI lưu predictions trước khi mở labels. Chọn thư mục output mới; không ghi đè kết quả. Compare các report bằng `python -m tools.ocr_benchmark compare <baseline/report.json> <candidate/report.json> --output <new.json>` để kiểm tra hash/host/thread/source đồng nhất. Không tự sửa nhãn sau khi xem prediction; nếu phát hiện nhãn lỗi, lập biên bản, phiên bản mới, A/B duyệt lại và báo ảnh hưởng.

## 4. Phạm vi scorer/evidence cần kiểm tra trước đo chính thức

Công cụ acceptance hiện hỗ trợ partial/approved, page/unit/VAT, CER/WER và chặn leakage, nhưng schema evidence của các prototype không đồng nhất. Hybrid xuất pages V4 full-page thực cùng enhanced_pages/crop/field evidence; CER trang phản ánh full-page pass, không trộn lặp text các crop thành transcript. V5 giữ read vùng trong pages.reads; Current có thể chỉ có raw toàn tài liệu, không có page boxes. Vì vậy phải kiểm tra đầu ra đánh giá: thiếu page/transcription thì NOT TESTED/PARTIAL, không báo CER hay table detection PASS từ dữ liệu rỗng.

Nếu cần adapter evidence cho Current/V5, triển khai riêng và kiểm thử trước khi freeze chính thức; giữ prediction gốc, hash và log phép chuyển, không thay field/item. Bộ đo phát triển Giai đoạn 6 chỉ chấm field/4 ô dòng và timing; không tự coi đã chứng minh unit/page/table polygon.

## 5. Tiêu chí cần người dùng/PO chốt trước đo

Báo exact từng trường, Precision/Recall/F1 có xử lý giá trị vắng, exact bốn ô và đầy đủ unit/page/VAT khi có nhãn, bảng exact, sai lệch số học, tỷ lệ xử lý thành công, tỷ lệ phải review và khả năng gắn cờ trường sai. Dùng người kiểm thử gán nguyên nhân OCR/parser/table/source, không phán từ mismatch đơn thuần.

Đề xuất điều kiện tối thiểu để **xem xét** tích hợp, chưa phải ngưỡng đã được phê duyệt: không có hồi quy trên trường/dòng baseline đang đúng; không phát sinh trường bịa; báo riêng mọi tổng tiền/MST sai; không che lỗi bằng confidence hoặc arithmetic repair. Mục tiêu chất lượng theo ngành/field và latency p95 phải được thống nhất trước đo, không đặt sau khi thấy điểm. Báo khoảng tin cậy và cỡ mẫu; tập nhỏ không chứng minh độ chính xác 100%.

Đo cold/warm, ít nhất ba lượt thời gian khi đủ tài nguyên, cùng thread/máy và môi trường tải; luân phiên thứ tự engine, ghi RAM process-tree và OCR call count. Không dùng throughput mock để thay inference thật. Giữ nhánh thất bại và log timeout.

Sau bằng chứng độc lập đạt ngưỡng và được phê duyệt mới thiết kế tích hợp có feature flag/rollback, bỏ scoped monkeypatch offline để hỗ trợ đồng thời an toàn, rồi UAT upload → OCR → review/edit → validation → lưu/mở lại trên DB/upload test biệt lập. Không dùng database chính; không tự ký nghiệm thu hoặc đổi engine mặc định.
