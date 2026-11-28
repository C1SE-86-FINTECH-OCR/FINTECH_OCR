# Giai đoạn 3.1–3.4 — Checkpoint parser bảng thử nghiệm

Ngày chốt: 18/11/2026. Repository: `FINTECH_OCR_GitHub`, nhánh `feature/thien`.

> Checkpoint tiếp theo: [Giai đoạn 3.5 — công cụ nghiệm thu thực tế và trạng thái chờ dữ liệu](OCR_PHASE35_ACCEPTANCE_STATUS.md). Các số liệu bên dưới là kết quả Giai đoạn 3.1–3.4, không được đổi thành kết quả real held-out.

**Kết luận: prototype offline có cải thiện trên dữ liệu tổng hợp, chưa đủ điều kiện tích hợp vào API/Website.** Không thay đổi engine mặc định Tesseract, không loại bỏ PaddleOCR, không thay đổi database hay giao diện. Không chạy seed, migration, restore, upload hoặc xử lý lại hóa đơn đang lưu. Không commit/push.

## 1. Kiểm tra trạng thái và bảo toàn công việc cũ

Git đầu lượt có bốn file tracked đã sửa từ các lượt trước: `backend/app/extraction.py`, `backend/tests/test_extraction.py`, `backend/tests/test_phase2_api.py`, `web/src/InvoiceDetailPage.jsx`; tổng diff tracked là 1.630 dòng thêm, 68 dòng bỏ. Các file chưa tracked gồm nhóm công cụ benchmark/evaluator, test tương ứng, fixture XML, tài liệu OCR và CSS Invoice Detail. Không reset, ghi đè hay bỏ các thay đổi này.

Đã tiếp tục module có sẵn `backend/tools/ocr_benchmark/table_v3.py`, adapter `tesseract-table-v3` trong CLI và scoring VAT cấp dòng. Những thành phần này đã được tạo ở lượt gián đoạn trước, không viết lại từ đầu. Bộ tổng hợp mới cùng manifest, nhãn, SHA-256 và `run_comparison.ps1` cũng đã có sẵn. Lượt này không tạo lại chứng từ.

SHA-256 của `backend/app/extraction.py` trước/sau lượt này giữ nguyên:

`c878ec80cb32e1d2f8dada0329e70c6bf4eed708246dcef0ef1b108c094c3218`

Tìm trong `backend/app` không có import `table_v3` hoặc lựa chọn `tesseract-table-v3`. Các file pipeline chính thức, API, frontend, Mobile và cấu hình kết nối không được chỉnh trong lượt này.

## 2. Hai dòng phát triển chưa khớp: đối chiếu chứng từ gốc

Đã xem ảnh gốc `angled-vat.jpg` và render PDF gốc `bilingual-borderless-scan.pdf` bằng PyMuPDF để đối chiếu nhãn tổng hợp. Không dùng dự đoán làm nhãn. Bản render đối chiếu nằm tại `ocr_phase3_benchmark/diagnostics/bilingual-original.png`.

| Chứng từ | Nhãn từ chứng từ | Kết quả prototype | Phân loại lỗi |
| --- | --- | --- | --- |
| NEW-VAT, dòng 2 | `Bộ đầu nối 40 mm`, SL 3, đơn giá 18.000, thành tiền 54.000 | `Bộ đầu nói 40 mm`; ba ô số đúng | OCR sai dấu trong mô tả; không phải thiếu hàng hay gán nhầm cột tiền. |
| NEW-BILINGUAL, dòng 1 | `Dịch vụ đo áp suất`, SL 1, đơn giá/thành tiền 582.000 | `Dịch vụ do áp suất`, SL 4, đơn giá/thành tiền 582.000 | OCR sai mô tả và chữ số; cấu trúc hàng/cột đã được phát hiện. `4 × 582.000 ≠ 582.000`, có cảnh báo. |

Đọc lại vùng số của NEW-BILINGUAL bằng crop phóng to và Tesseract PSM 7 cho ứng viên SL `1`, đơn giá/thành tiền `582.000`. Bằng chứng ứng viên được lưu trong `findings[].reread`; giá trị xuất ban đầu vẫn giữ `4`, không tự thay bằng phép chia tổng tiền. Mô tả vẫn sai nên dòng không được tính exact. Cần chính sách lựa chọn ứng viên đã được kiểm chứng trước khi cho tự sửa giá trị.

NEW-VAT không phát ra cảnh báo OCR thấp: confidence cao vẫn có thể sai dấu. Không coi confidence là xác suất trường đúng hoặc thay thế review/ground truth.

## 3. Phần tiếp tục hoàn thiện trong lượt này

Module đã có: dựng vùng tiêu đề theo tọa độ; cột mô tả/lượng/giá/thành tiền/thuế; neo hàng bằng ô thành tiền; nối mô tả xuống dòng; tiếp bảng qua trang khi chưa gặp tổng kết; đọc bill theo phân loại; giữ riêng VAT cấp dòng trong JSON thử nghiệm; giữ polygon, điểm OCR, trang và nguồn PDF-text/OCR. Bảng tiếp trang giữ các dòng giống nhau ở hai vị trí thật, không gộp nhầm thành một dòng.

Lượt này bổ sung cảnh báo `LOW_OCR_CONFIDENCE` cho token trong ô dưới 0,85, với trường và điểm nhỏ nhất. Ngưỡng chỉ là heuristic review chưa hiệu chuẩn. Giữ cảnh báo của candidate ngay cả khi fallback giữ bảng baseline; tránh mất bằng chứng nghi ngờ. Không suy diễn trường thiếu, không thay số OCR bằng kết quả tính toán.

Kiểm thử mới xác nhận: token số lượng mơ hồ giữ null và chữ gốc; bảng đã đóng không được truyền cột sang trang không liên quan; VAT mâu thuẫn được cảnh báo mà không sửa giá trị. Các test sẵn có tiếp tục kiểm tra mô tả xuống dòng, tiếp trang, dòng lặp thật, bill thiếu lượng/giá, nhiều VAT, số tiền Việt Nam, số 0 và tính bất biến của trường ngoài bảng.

## 4. Thiết kế phép đo và giới hạn dữ liệu

Đã chạy sáu nhánh tuần tự: baseline hiện tại và prototype cho mỗi bộ bên dưới, tổng 36 lần xử lý trên 18 tài liệu. CPU tối đa bốn luồng; Tesseract `vie+eng`, phiên bản 5.5.3.20260724; Python backend 3.14.7. Không cài thư viện, model hoặc tải dataset mới. SHA-256 của bộ tổng hợp mới được kiểm tra trước khi chạy. Dự đoán được ghi trước khi công cụ mở nhãn.

- **phase2-diagnostics:** 5 chứng từ tổng hợp cũ, 7 dòng; đã dùng phát triển. Manifest cũ ghi split=`test` nhưng bộ này được báo cáo là development, không phải held-out mới.
- **historical-development:** HD-01–HD-07 đã dùng chẩn đoán trước đây. Chỉ HD-01 có nhãn toàn bộ được duyệt; HD-02 excluded; HD-03–HD-07 chỉ chấm các key đã xác minh. Không chấm items chưa được duyệt.
- **fresh-synthetic:** 6 chứng từ tổng hợp, 11 dòng, nhãn lấy từ dữ liệu tạo chứng từ và khóa trước chạy. Không dùng kết quả bộ này để chỉnh parser trong lượt này. Nhãn `approved` biểu thị nhãn fixture xác định từ nguồn tạo, **không phải UAT sign-off hoặc nhãn hóa đơn thật được người kiểm tra độc lập duyệt**. Đây là kiểm tra tổng hợp bổ sung, chưa thay thế bộ real held-out.

Exact dòng đòi hỏi đúng cả mô tả, số lượng, đơn giá và thành tiền; giữ dấu tiếng Việt. Dòng sai một ô được tính một FP và một FN. Ghép theo multiset để bảo toàn số lần lặp. Điểm toàn bảng tính cả mẫu âm có bảng rỗng; báo riêng để không nhầm với tỷ lệ đúng trên hóa đơn có hàng. Null đã xác minh được chấm; key chưa xác minh bị bỏ khỏi mẫu số.

## 5. Kết quả trước/sau

| Bộ | Dòng exact baseline → prototype | F1 dòng | Toàn danh sách | Mean giây/tài liệu | p95 giây | RAM đỉnh MiB |
| --- | --- | --- | --- | --- | --- | --- |
| Tổng hợp development cũ | 2/7 → 5/7 | 0,364 → 0,714 | 1/5 → 3/5, gồm 1 mẫu âm | 2,275 → 2,930 | 3,492 → 4,345 | 167,95 → 175,96 |
| Ảnh lịch sử, chỉ bảng HD-01 có nhãn đủ | 0/4 → 0/4 | 0 → 0 | 0/1 → 0/1 | 10,950 → 14,317 | 13,267 → 18,427 | 153,76 → 179,69 |
| Tổng hợp mới đã khóa | 5/11 → 11/11 | 0,625 → 1,000 | 2/6 → 6/6, gồm 1 mẫu âm | 2,437 → 3,293 | 4,260 → 5,267 | 164,36 → 164,26 |

Mức **5/7 của prototype được giữ nguyên**, không tăng thêm so với checkpoint trước. Thành công mới là chạy hoàn tất phép so sánh trên bộ tổng hợp bổ sung, cùng kiểm tra hồi quy và bằng chứng review. Thời gian/RAM là một lượt đo mỗi nhánh, chưa đo tải đồng thời Website; RAM lấy mẫu working set cả cây tiến trình, có thể bỏ lỡ đỉnh ngắn. Không sử dụng VRAM.

### Từng chứng từ tổng hợp

| ID / loại | Baseline dòng đúng/kỳ vọng | Prototype dòng đúng/kỳ vọng | Ghi nhận |
| --- | --- | --- | --- |
| NEW-VAT / JPG nghiêng | 1/2 | 1/2 | Còn lỗi dấu mô tả. |
| NEW-BILL / PNG bill không MST | 0/2 | 2/2 | Lượng/giá thiếu giữ null. |
| NEW-TWO-PAGE / PDF có chữ | 1/2 | 2/2 | Thu đủ trang 2. |
| NEW-BILINGUAL / PDF scan song ngữ | 0/1 | 0/1 | Sai chữ/số, lưu OCR đọc lại và cảnh báo số học. |
| NEW-UNKNOWN / tài liệu âm | 0/0 | 0/0 | Không tạo hàng giả. |
| F3-VAT / JPG nghiêng, tương phản giảm | 0/2 | 2/2 | Có cảnh báo OCR thấp; tên người bán ngoài bảng còn sai dấu. |
| F3-POS / PNG bill không bảng/MST | 0/2 | 2/2 | Parser trường người bán vẫn lấy nhầm tiêu đề; ITEM-SUM hiện hành không PASS khi thiếu subtotal. |
| F3-CONT / PDF nhiều trang | 2/3 | 3/3 | Mô tả xuống dòng, trang tiếp không header, giữ dòng lặp thật. |
| F3-SCAN / PDF scan song ngữ | 1/1 | 1/1 | Subtotal baseline thiếu, ITEM-SUM hiện hành vẫn FAIL. |
| F3-VAT-GROUP / PDF nhiều mức VAT | 2/3 | 3/3 | VAT cấp dòng 3/3; không ghi vào schema API hiện tại. |
| F3-NEG / chứng từ âm | 0/0 | 0/0 | Giữ unknown, không sinh sản phẩm. |

### Trường ngoài bảng: không hồi quy, cũng chưa sửa các lỗi cũ

So sánh dict `fields` trước/sau khớp trên **18/18 tài liệu**. Bảng dưới là exact theo nhãn; số sau bằng số trước.

| Trường | Development tổng hợp cũ | Tổng hợp mới | HD-03–HD-07: chỉ key đã xác minh |
| --- | --- | --- | --- |
| Loại | 5/5 | 6/6 | Chưa có nhãn được chấm |
| Nhà cung cấp | 3/5 | 3/5 | 0/1 |
| MST người bán | 5/5 | 5/5 | 0/1 |
| Số hóa đơn | 5/5 | 5/5 | Chưa có nhãn được chấm |
| Ngày lập | 5/5 | 5/5 | Chưa có nhãn được chấm |
| Tiền trước thuế | 5/5 | 3/4 | 0/1 |
| Tiền VAT | 5/5 | 4/4 | 0/1 |
| Tổng thanh toán | 5/5 | 6/6 | 2/5 |

HD-01 vẫn sai loại, nhà cung cấp, ngày, số hóa đơn, tổng và 0/4 dòng. MST/subtotal/VAT chỉ đúng ở giá trị null đã xác minh, không có nghĩa OCR đọc được những trường này. Vì prototype bảo toàn bộ trích xuất trường hiện tại và chặn lựa chọn bảng mới khi loại là unknown, lỗi phân loại có thể chặn cả nhánh bill. Không sửa bộ phân loại chính thức trong phạm vi này.

Chi tiết Precision/Recall/F1 từng trường, từng ô, từng loại chứng từ, thời gian từng tài liệu, JSON expected/actual và findings xem [tổng hợp phép đo](../../ocr_phase3_benchmark/summary.md) và [đối chiếu nhãn/dự đoán](../../ocr_phase3_benchmark/details.json). Raw text, tọa độ và confidence nằm trong `results/<bộ>/after/predictions.json` ở cùng thư mục. Dữ liệu hóa đơn chỉ lưu cục bộ.

## 6. Kiểm thử đã chạy

| Hạng mục | Kết quả | Giới hạn |
| --- | --- | --- |
| Unit/regression parser + benchmark + evaluator | **30 PASS, 0 FAIL** | Gồm 11 test parser; không phải điểm chính xác hóa đơn thực. |
| Toàn bộ Backend tests | **201 PASS, 0 FAIL**, 5 warnings, 29,32 giây | SQLite/fixtures trong thư mục tạm cô lập; không dùng PostgreSQL hoặc SQLite Website. 30 test trên là tập con, không cộng thành 231. |
| Inference thật trên JPG/PNG/PDF chữ/PDF scan | **PASS thực thi 36/36**, có lỗi độ đúng đã nêu | Thành công thực thi không tương đương trích xuất đúng. |
| Hồi quy trường ngoài bảng | **PASS 18/18 không đổi** | Giữ cả kết quả sai trước đó. |
| Dòng phát triển cũ đúng toàn bộ | **FAIL 2/7 dòng còn sai** | OCR dấu và số lượng; không ép sửa theo đáp án. |
| Dòng bill thực HD-01 | **FAIL 0/4 đúng** | Không tuyên bố tổng quát hóa. |
| Bộ tổng hợp mới: dòng hàng | **PASS 11/11 trong phạm vi fixture** | Chưa có bộ hóa đơn thật mới độc lập. |
| Real held-out mới được hai người xác minh | **NOT TESTED / thiếu dữ liệu** | Không tái sử dụng HD-01–HD-07 làm held-out. |
| PostgreSQL/API/Browser UAT với parser mới | **NOT TESTED** | Chưa được phê duyệt tích hợp, không ghi DB. |

Warnings chỉ gồm Starlette/httpx và SQLite datetime adapter deprecation. Có cảnh báo deprecation import `fitz` ở công cụ cũ khi benchmark; không ảnh hưởng kết quả, không đổi dependency trong lượt này. Web tests/build không chạy vì không có thay đổi frontend hoặc tích hợp runtime.

## 7. File và bằng chứng

**Sửa trong lượt tiếp tục này:**

- `backend/tools/ocr_benchmark/table_v3.py`: cảnh báo confidence thấp; giữ findings khi fallback.
- `backend/tests/test_ocr_table_v3.py`: thêm ba regression test, tổng 11 test.
- `docs/OCR_PHASE3_TABLE_EXTRACTION_RESULTS.md`: báo cáo/checkpoint này.
- `docs/OCR_PHASE3_TABLE_EXTRACTION_PLAN.md`: liên kết trạng thái mới, giữ nội dung kế hoạch cũ.
- Ngoài repo, workspace `ocr_phase3_benchmark/summarize.py`, `summary.md`, `details.json`, `diagnostics/bilingual-original.png` và sáu thư mục kết quả `results/*/{before,after}` cùng `compare.json`.

**Đã có từ lượt gián đoạn, được kiểm tra và dùng tiếp:** adapter CLI, scoring VAT/review, module prototype ban đầu, tests benchmark/evaluator, script `run_comparison.ps1`, generator `build_fresh_corpus.py`, bộ `frozen` đã khóa. Không tạo lại nhãn từ đầu ra OCR. Tất cả thay đổi vẫn chưa commit trên `feature/thien`.

## 8. Tiếp nhận bộ hóa đơn thật mới và bước tiếp theo

1. Chuẩn bị 30–50 chứng từ thật có quyền sử dụng, với nhà cung cấp/họ bố cục khác tập phát triển. Phủ bill nhiệt, VAT nghiêng, mô tả nhiều dòng, bảng không viền, PDF nhiều trang, scan song ngữ và nhiều VAT. Giữ nguyên ảnh/PDF gốc.
2. Tạo manifest theo [schema benchmark](OCR_BENCHMARK_PHASE2.md): `document_id,file,split,origin,supplier_group,layout_family,duplicate_group,language`; `split=test`, `origin=real`. Tách nhóm nhà cung cấp/bố cục/gần trùng giữa các tập; cùng một hóa đơn nhiều trang phải ở cùng tập. Đóng băng SHA-256 trước chạy.
3. Hai người gán/kiểm tra nhãn độc lập từ ảnh gốc. `expected` chỉ chứa key đã xác minh; absent ghi null, unreadable/unverified bỏ key và ghi chú riêng. Chỉ thêm `items` khi kiểm tra đủ toàn bảng; không dùng `items: []` cho bảng chưa đọc được. Chỉ `approved` sau khi duyệt; còn phần thiếu dùng `partial`.
4. Chạy hai engine trên cùng bộ đã khóa, mỗi đầu ra mới chưa tồn tại. Ví dụ PowerShell từ `FINTECH_OCR_GitHub/backend`:

```powershell
$dataRoot = '<LOCAL_PATH>
$runTag = Get-Date -Format 'yyyyMMdd_HHmmss'
$common = @('--manifest', "$dataRoot\documents.csv", '--dataset-root', $dataRoot,
            '--split', 'test', '--labels', "$dataRoot\labels.json", '--cpu-threads', '4')
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark run --engine tesseract-current @common --output "$dataRoot\baseline_$runTag"
if ($LASTEXITCODE -ne 0) { throw 'Baseline chưa chạy thành công; kiểm tra report trước khi tiếp tục.' }
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark run --engine tesseract-table-v3 @common --output "$dataRoot\prototype_$runTag"
if ($LASTEXITCODE -ne 0) { throw 'Prototype chưa chạy thành công; kiểm tra report.' }
& '.\.venv\Scripts\python.exe' -X utf8 -m tools.ocr_benchmark compare "$dataRoot\baseline_$runTag\report.json" "$dataRoot\prototype_$runTag\report.json" --output "$dataRoot\comparison_$runTag.json"
```

5. Không chỉnh parser theo kết quả held-out. Nếu dùng để chẩn đoán/sửa, chuyển tập đó thành development và chuẩn bị tập nghiệm thu mới.

Các việc còn lại: giảm lỗi OCR dấu và số mà không dùng đáp án để chọn; hiệu chuẩn confidence/review; chứng minh nhánh bill trên dữ liệu thật; xử lý mô tả ngắt giữa hai trang hoặc trước hàng số, cột bị mất tiêu đề, ảnh phối cảnh/nhăn nặng; kiểm tra nhóm VAT có miễn/không chịu thuế và giảm giá/phụ phí. Fallback dựa vào số hàng không bảo đảm bảng chính xác hơn; cần đánh giá ứng viên theo bằng chứng cấu trúc và benchmark độc lập. Hiện tại chưa đề xuất ghi VAT cấp dòng vào database hoặc đổi contract API.

**Điểm dừng:** chưa phê duyệt tích hợp. Chỉ sau khi có benchmark real held-out đạt tiêu chí thống nhất và không hồi quy mới đề nghị thử song song trên UAT cô lập, có rollback. Không đánh dấu toàn hệ thống OCR hoặc Giai đoạn 2 ACCEPTED.
