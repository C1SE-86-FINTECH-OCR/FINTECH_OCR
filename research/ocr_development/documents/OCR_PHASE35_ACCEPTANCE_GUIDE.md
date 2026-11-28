# Giai đoạn 3.5 — Hướng dẫn nghiệm thu OCR trên hóa đơn thật

Trạng thái 18/11/2026: **WAITING FOR INDEPENDENT REAL DATA**. Công cụ sẵn sàng tiếp nhận, chưa có kết quả nghiệm thu trên bộ real held-out mới. Tesseract, parser chính thức, API, Website và database giữ nguyên. Parser thử nghiệm vẫn chưa tích hợp.

## 1. Thành phần dùng lại và phần bổ sung

Dùng lại manifest, inference, scoring trường, baseline Tesseract, prototype bảng, raw text/polygon/confidence và phép đo thời gian/RAM trong `backend/tools/ocr_benchmark`. Không chạy lại 36 lượt benchmark cũ và không điều chỉnh parser theo hóa đơn mới.

Thêm CLI độc lập `python -m tools.ocr_benchmark.acceptance` với bốn lệnh:

- `init`: tạo nơi tiếp nhận rỗng; không sinh nhãn từ OCR.
- `prepare`: đọc manifest và số trang gốc, tạo bản nháp **expected rỗng**; giữ nguyên nhãn đã có và lưu bản sao trước khi thêm bản nháp mới.
- `freeze`: kiểm tra nguồn, người duyệt, tính độc lập, SHA-256; xuất nhãn tương thích benchmark và khóa bản chụp dữ liệu trước inference.
- `evaluate`: chấm dự đoán đã chạy trên đúng bộ đã khóa; xuất `acceptance.json` và bảng từng hóa đơn `acceptance.md`. Không gọi OCR, API hoặc database.

## 2. Nơi lưu dữ liệu đã chuẩn bị

```text
<LOCAL_PATH>
  documents\                 # Hiện rỗng. Thêm file gốc, giữ các trang cùng một hóa đơn trong một PDF.
  documents.csv              # Hiện chỉ có tiêu đề cột.
  ground_truth.json          # Hiện documents: [], không có đáp án tự sinh.
  known_documents.json       # 25 SHA-256 khác nhau từ dữ liệu đã biết/phát triển.
  intake_status.json         # 0 hóa đơn được tiếp nhận/chấm; không có accuracy.
```

Danh mục đã biết gồm các manifest pilot, HD-01–HD-07, tổng hợp Giai đoạn 2/3 và fingerprint benchmark trước. Công cụ chặn SHA-256 hoặc nhóm nhà cung cấp/bố cục/gần trùng đã đăng ký. **Chặn hash không phát hiện đầy đủ ảnh crop, resize, scan lại hay bố cục gần trùng.** Người xác minh phải kiểm tra nguồn và khai báo trung thực; các nhóm cũ `legacy-*-unverified` chưa đại diện cho phân loại nhà cung cấp chính xác.

Không dùng các tập development cũ, kể cả 6 chứng từ tổng hợp từng đạt 11/11 dòng, làm bằng chứng nghiệm thu thực tế.

## 3. Thêm hóa đơn thật mới

Chuẩn bị các chứng từ được phép dùng, ưu tiên bộ 30–50 hóa đơn có nhiều nhà cung cấp/họ bố cục. Có thể bắt đầu một pilot nhỏ được duyệt nhãn để kiểm tra quy trình, nhưng không suy rộng thành độ chính xác toàn hệ thống.

| Nhóm cần phủ | Giá trị trong cột categories |
| --- | --- |
| VAT PDF có lớp chữ | vat_pdf_text |
| VAT JPG/PNG | vat_image |
| PDF scan nhiều trang | multipage_scan |
| Bill nhiệt, có thể không MST/bảng | thermal_bill |
| Nhiều dòng hàng | many_items |
| Nhiều mức VAT | multiple_vat |
| Bảng bố cục khác | different_table_layout |
| Việt–Anh | bilingual_vi_en |

Một file có nhiều nhóm, phân cách bằng dấu `;`. Coverage dựa trên nhãn nhóm do người kiểm thử khai báo, không phải kết luận tự động từ OCR.

Chép file gốc vào `documents` bằng tên mới, không ghi đè. Thêm dòng vào `documents.csv` bằng trình soạn thảo UTF-8. Dòng **minh họa cấu trúc**, cần thay tên file/nhóm bằng giá trị thực, không phải hóa đơn mẫu được tiếp nhận:

```csv
document_id,file,split,origin,supplier_group,layout_family,duplicate_group,language,categories
REAL-001,documents/ten-file-thuc-te.pdf,test,real,NCC-moi-001,BOCUC-moi-001,NHOM-moi-001,vi,vat_pdf_text;many_items
```

Giữ số trang của cùng hóa đơn trong cùng file. Đặt cùng nhóm cho các tài liệu cùng nhà cung cấp/họ bố cục/gần trùng; không đổi nhóm chỉ để vượt kiểm tra độc lập. Manifest kiểm tra đường dẫn nằm trong dataset root, file có tồn tại, định dạng và giới hạn 20 MB.

Sau khi đã có dòng/file thực tế, chạy PowerShell:

```powershell
Set-Location '<LOCAL_PATH>
$dataRoot = '<LOCAL_PATH>
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark.acceptance prepare --dataset-root $dataRoot
if ($LASTEXITCODE -ne 0) { throw 'Chưa chuẩn bị được dữ liệu; đọc lỗi trước khi tiếp tục.' }
```

Không chạy `prepare` khi manifest còn rỗng. Lệnh không OCR, không truy cập dự đoán hoặc database.

## 4. Hai người xác minh ground truth

Mở **file gốc** để gán nhãn trước khi xem prediction. Người A nhập, người B đối chiếu lại và điều hòa khác biệt bằng chứng từ. Không sao chép đầu ra OCR làm đáp án. Không đưa tên placeholder vào trường người duyệt.

`ground_truth.json` có `schema_version: 1`, mảng `documents`. Mỗi bản ghi do prepare tạo giữ `document_id`, `sha256`, `review_status: draft`, hai người duyệt còn trống, thông tin nguồn chưa xác nhận, `page_count`, các trang có `transcription: null`, và `expected: {}`.

Chỉ đưa vào `expected` những trường đã xác minh:

| Nội dung | Key | Kiểu |
| --- | --- | --- |
| Loại | document_type | einvoice / bill / unknown |
| Nhà cung cấp | seller_name | Chuỗi hoặc null khi chắc chắn không xuất hiện |
| MST người bán | seller_tax_code | Chuỗi, giữ số 0 đầu; bill không MST được null |
| Số/ký hiệu hóa đơn | invoice_number / invoice_symbol | Chuỗi, giữ số 0 đầu |
| Ngày lập | invoice_date | YYYY-MM-DD hoặc null đã xác minh |
| Người mua/MST người mua | buyer_name / buyer_tax_code | Chuỗi hoặc null đã xác minh, nếu chấm |
| Trước thuế/VAT/tổng phải trả | subtotal / vat_amount / total_amount | Số không phân cách hàng nghìn, hoặc null đã xác minh |
| Thuế suất chung | vat_rate | Số hoặc null; không tự gộp hóa đơn nhiều mức thuế |
| Các dòng hàng | items | Chỉ thêm khi đã kiểm tra đủ cả bảng |

Mỗi dòng `items` phải có `description`, `unit`, `quantity`, `unit_price`, `amount`, `page` (trang tính từ 1). Mô tả/đơn vị là chuỗi; số lượng/giá/thành tiền là số; trường thực sự không in ghi null. Có thể thêm `vat_rate`, `vat_amount` cấp dòng khi đã đối chiếu. Không điền giá tính ngược để bù chỗ trống; phân biệt VAT 0 với thiếu dữ liệu. Giữ hai dòng giống nhau nếu chứng từ thực sự có hai dòng.

**Null nghĩa là đã xác nhận trường không có, không phải chưa đọc được.** Trường không chắc/chưa đọc được bỏ key và ghi vào `source_issues`. Nếu bảng chưa đầy đủ, bỏ `items` và dùng `partial`; không ghi `items: []` để thay bảng chưa đọc được. Mảng rỗng chỉ dùng khi đã xác nhận không có dòng hàng.

Trong `pages`, chép nguyên văn từng trang, theo thứ tự đọc từ trên xuống và trái qua phải, gồm header, bảng, tổng kết, footer. Không sửa chính tả gốc, không ép thứ tự để giống đầu ra OCR. Khi không chép được trọn trang, giữ transcription null và ghi lý do. Xuống dòng/khoảng trắng được chuẩn hóa khi chấm; dấu tiếng Việt, chữ hoa/thường, dấu câu vẫn giữ. Ghi chú vùng không đọc được riêng, không thay bằng chữ đoán.

Trước khi khóa:

- Điền `annotated_by`, `verified_by` khác nhau và `verified_at` thực tế.
- Ba xác nhận `permitted_use`, `never_used_for_development`, `annotated_without_predictions` chỉ đặt true nếu thực sự đúng.
- `approved` đòi hỏi các trường nghiệp vụ bắt buộc đã được kiểm tra và bảng đủ; `partial` chỉ chấm các key đã xác minh; `draft`/`excluded` không được chấm.
- Transcription còn thiếu khiến phép đo ký tự chưa đủ; ngay cả khi expected đủ, công cụ không chuyển tài liệu thành PASS đầy đủ.

## 5. Khóa dữ liệu trước chạy và chạy hai nhánh

Các lệnh dưới chỉ chạy sau khi có nhãn thật đã được duyệt. Mỗi thư mục đầu ra phải mới. Không chạy trên `fintech-ocr-starter`, không dùng database hoặc API Website.

```powershell
Set-Location '<LOCAL_PATH>
$dataRoot = '<LOCAL_PATH>
$runTag = Get-Date -Format 'yyyyMMdd_HHmmss'
$frozen = Join-Path $dataRoot "frozen_$runTag"
$before = Join-Path $dataRoot "baseline_$runTag"
$after = Join-Path $dataRoot "prototype_$runTag"

& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark.acceptance freeze --dataset-root $dataRoot --known-documents "$dataRoot\known_documents.json" --output $frozen
if ($LASTEXITCODE -ne 0) { throw 'Không đủ điều kiện khóa nhãn. Không chạy nghiệm thu.' }

$common = @('--manifest', "$frozen\documents.csv", '--dataset-root', $dataRoot,
            '--split', 'test', '--labels', "$frozen\labels.json", '--cpu-threads', '4')
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark run --engine tesseract-current @common --output $before
if ($LASTEXITCODE -ne 0) { throw 'Baseline lỗi; kiểm tra report.' }
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark run --engine tesseract-table-v3 @common --output $after
if ($LASTEXITCODE -ne 0) { throw 'Prototype lỗi; kiểm tra report.' }

& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark compare "$before\report.json" "$after\report.json" --output "$dataRoot\comparison_$runTag.json"
if ($LASTEXITCODE -ne 0) { throw 'Hai kết quả không đủ điều kiện so sánh.' }

& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark.acceptance evaluate --frozen $frozen --run $before --output "$dataRoot\acceptance_baseline_$runTag"
if ($LASTEXITCODE -ne 0) { throw 'Chưa chấm được baseline.' }
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark.acceptance evaluate --frozen $frozen --run $after --output "$dataRoot\acceptance_prototype_$runTag"
if ($LASTEXITCODE -ne 0) { throw 'Chưa chấm được prototype.' }
```

Benchmark giữ lại dự đoán trước khi mở labels; freeze giữ manifest, nhãn mở rộng, nhãn benchmark, danh mục dữ liệu cũ và hash. Evaluator từ chối nhãn/file thay đổi, dự đoán thiếu/trùng, nhầm dataset hoặc dự đoán không tái tạo được điểm của report gốc. Không có thao tác chọn lại parser hoặc cấu hình dựa trên đáp án.

## 6. Đọc kết quả và giới hạn phép đo

- **Ký tự OCR:** Levenshtein CER/WER trên transcription được người kiểm thử xác minh. Page OCR và lớp chữ PDF báo riêng, không dùng đọc PDF text để chứng minh OCR ảnh chính xác. CER có thể lớn hơn 1 khi nhiều chữ thừa; không báo `1-CER` thành độ chính xác ảo. Mẫu số bằng 0 trả null.
- **Nhiều lượt OCR:** CER page boxes của prototype phản ánh lượt OCR phục vụ layout. `document_raw_text` chấm riêng lượt raw text dùng cho trường, khi có đủ transcription. Hai lượt có thể đọc khác nhau. Không suy ra nguyên nhân một trường từ CER của lượt khác. Baseline chưa có page boxes nên chấm được raw text toàn tài liệu khi có, còn kiểm tra trang/ô chi tiết là NOT TESTED.
- **Từng trường:** Exact Match, Precision/Recall/F1 từ scorer hiện có; approved và partial tách riêng, key chưa xác minh không tính đúng/sai. Giá trị null đã xác minh có thể exact nhưng không được diễn giải là đọc được trường có nội dung.
- **Dòng hàng:** Giữ điểm bốn ô cũ và thêm exact sáu ô gồm đơn vị/trang; giữ số bản sao của dòng. VAT cấp dòng chấm riêng khi có nhãn. Thiếu metadata đơn vị/trang ở engine được báo rõ, không nhận điểm đúng cho null do thiếu key.
- **Ghép dòng/bảng:** Exact toàn dòng phát hiện ghép sai ô; đếm dòng mỗi trang là chỉ báo cấu trúc, không chứng minh ghép đúng. Table detection đo hiện diện bảng theo trang, chưa có polygon IoU hoặc nhãn cấu trúc ô độc lập. Phân biệt lỗi nhận dạng với lỗi ghép phải xem evidence và review nguyên nhân.
- **Nhiều trang:** Liệt kê trang có evidence, trang thiếu/thừa và truncated, vị trí dòng theo trang. Thiếu metadata trang không tự xem là PASS. Chưa chứng minh nối mô tả bị ngắt giữa hai trang chỉ vì số trang đủ.
- **Thời gian:** Giây từng hóa đơn, mean/p50/p95 trong report benchmark, RAM theo phương pháp hiện có; không thay bằng thời gian giả.

`acceptance.md` là bảng từng hóa đơn; `acceptance.json` chứa expected/actual, điểm, coverage tám nhóm, chi tiết text, trang, cảnh báo, bằng chứng và nguyên nhân được duyệt. Không sửa dự đoán để chấm lại thành đúng. Trạng thái PASS của tài liệu dùng tiêu chí exact nghiêm ngặt trên các phần được hỗ trợ, không ký nghiệm thu sản phẩm. Một ký tự OCR sai vẫn làm tiêu chí exact toàn tài liệu FAIL, dù các trường nghiệp vụ có thể đúng; xem từng chỉ số thay vì chỉ một nhãn.

## 7. Phân loại nguyên nhân sau đo, không thay ground truth

Sau lần chạy đầu, đối chiếu gốc → raw text/boxes → phân vùng bảng → items. Tạo file review riêng gắn với SHA-256 của **predictions.json**, không chỉnh ground truth đã khóa:

```json
{
  "predictions_sha256": "<SHA-256 thực tế của predictions.json>",
  "reviews": [
    {
      "document_id": "<ID thực tế>",
      "category": "undetermined",
      "target": "<trường hoặc dòng/ô bị lỗi>",
      "evidence": "<trang, ảnh gốc, đoạn chữ và hộp OCR đã đối chiếu>",
      "reviewer": "<người xác minh thực tế>"
    }
  ]
}
```

Các category: `ocr_recognition` (chữ/số OCR sai); `parser_assignment` (chữ có nhưng gán/chuẩn hóa/ghép sai); `table_detection` (bỏ sót hoặc nhận nhầm vùng bảng); `source_quality` (bản gốc thiếu/mờ/cắt); `undetermined` (chưa đủ bằng chứng). Không gán một nguyên nhân chắc chắn chỉ từ kết quả tài chính sai.

Lấy hash bằng `Get-FileHash -Algorithm SHA256 -LiteralPath "$after\predictions.json"`. Chạy evaluate với `--reviews '<đường dẫn review thực tế>'` và **thư mục output mới**. Review được gắn vào kết quả, không sửa giá trị OCR/nhãn hoặc thay điểm. Người chẩn đoán lỗi có thể xem prediction sau khi đã khóa nhãn.

## 8. Điều kiện dừng và bước tiếp theo

Hiện không có bộ real held-out đủ nhãn, nên dừng chờ chứng từ và người xác minh; không chấm lại dữ liệu tổng hợp rồi gọi là accuracy thực tế. Các hóa đơn đã xem để sửa thuật toán phải chuyển thành development; nghiệm thu tiếp theo cần tập chưa dùng.

Sau khi đủ dữ liệu, thống nhất mục tiêu chất lượng theo từng trường/dòng và từng nhóm; báo cả lỗi, coverage, nguồn chữ và thời gian. Chỉ đề xuất thử nghiệm tích hợp có rollback khi dữ liệu thực chứng minh cải thiện và bảo toàn trường đang đúng. Không tự tích hợp hoặc ký UAT sign-off.
