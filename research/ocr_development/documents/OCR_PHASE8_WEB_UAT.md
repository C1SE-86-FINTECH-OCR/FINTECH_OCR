# Giai đoạn 8 — Web UAT trên PostgreSQL test và bill thật

Ngày 19/11/2026. **Luồng tích hợp hoạt động; chất lượng OCR còn FAIL, chưa nghiệm thu.** Không yêu cầu xác minh 24 chứng từ, không benchmark Giai đoạn 7 hoặc sửa ground truth/Hybrid frozen.

## Môi trường và dữ liệu dùng thử

Web thật `htt<LOCAL_PATH>`, Backend thật 8000/PID 16864, đúng repo `FINTECH_OCR_GitHub`. Đối chiếu listener PID với attestation in-process Settings/engine/source: `APP_ENV=testing`, DB `fintech_ocr_rbac_test`, upload `backend/uploads_rbac_test`, Hybrid V6 và fallback bật. Health testing không được dùng thay bằng chứng DB.

Đã tạo **backup mới trước request ghi** bằng pg_dump/pg_restore list và đối chiếu hash file Windows; đường dẫn/dung lượng/SHA tại [BACKUP.json](../../ocr_phase8_integration/web_uat/BACKUP.json). Baseline business rows lưu hash chỉ đọc tại [DB_BASELINE.json](../../ocr_phase8_integration/web_uat/DB_BASELINE.json). Không mở kết nối database chính. Không schema/migration/seed/restore.

Đăng nhập bằng tài khoản Employee test có sẵn qua form Web, HTTP 200; không đặt lại mật khẩu hoặc tạo tài khoản. Không lưu mật khẩu/JWT vào báo cáo, network trace hoặc kết quả kiểm thử. Playwright điều khiển Chromium local vào Website thật, chọn file bằng input thật, nhấn nút upload và xem detail. Không mock response OCR/API. Font ngoài được chặn trong context QA, không sửa cấu hình Website.

Ba ảnh thật ReceiptVQA được phép nghiên cứu đã có trong **tập development cũ**, không thuộc 24 ảnh Phase7:

| Ảnh nguồn | Mục đích | Invoice mới |
|---|---|---:|
| `ocr_phase35_acceptance/documents/RVQA_00000505.jpg` | Bill bán lẻ Năm Oánh, một mặt hàng | 25 |
| `ocr_phase35_acceptance/documents/RVQA_00000022.jpg` | Bill siêu thị, hai mặt hàng và dòng khuyến mãi | 26 |
| `ocr_phase35_acceptance/documents/RVQA_00001100.jpg` | Minimart ANAN, sáu mặt hàng/cột đơn vị | 28 |

Đã đọc trực tiếp ảnh gốc để đối chiếu, không dùng predicted/ground-truth JSON làm đáp án. Đây chỉ là kiểm tra tích hợp và đối chiếu AI trực quan, **không phải bộ nghiệm thu mới/độc lập hoặc xác nhận con người A/B**. Không báo tỷ lệ accuracy tổng quát từ ba ảnh đã dùng development. File gốc và nhãn giữ nguyên.

## Kết quả luồng Web/API/DB

| Kiểm tra | Actual Result | Trạng thái |
|---|---|---|
| Đăng nhập tài khoản test qua Web | HTTP 200, vào giao diện Employee | PASS |
| Chọn file → queue → upload | Ba ảnh thật xuất hiện trong queue; mỗi upload HTTP 201 | PASS |
| Hybrid V6 thực sự chạy | #25/#26/#28: method `hybrid-v6`, used_pipeline `hybrid_v6`, fallback false, source `hybrid-v6`, enhanced_pages=1 từng ca | PASS |
| Bằng chứng nhận diện | PostgreSQL ExtractionRun có raw_text, page/boxes/score, routing, candidates/findings và output hàng | PASS |
| Original document | Web tải file có xác thực, ảnh gốc hiển thị; 4 file UAT có checksum khớp bản lưu | PASS |
| Invoice Detail so API | Từng field/form value và từng ô dòng hàng khớp API, gồm null/đơn vị/số; F5 giữ dữ liệu | PASS mapping, không phải accuracy |
| Sửa tay #25 | Seller/ngày/mô tả hàng theo ảnh; PUT 200, F5 còn; 3 correction old/new/user/time | PASS |
| Sửa đơn vị #28 | Dòng 3 `GOT` → `GOI` theo cột nguồn; PUT 200/F5 còn, 1 correction | PASS |
| Validation sau sửa | #25/#28 có vòng 2, findings còn đúng theo quy tắc hiện hành | PASS thực thi; không ép valid |
| Approval/Lookup khi sửa | #25/#28 vẫn draft/not_applicable; không tự approved/verified | PASS |
| Fallback khi Hybrid lỗi | Tiêm lỗi ở bridge trong process riêng 8011; UI upload tạo #27 bằng OCR cũ, có cảnh báo/fallback true | PASS cơ chế, accuracy OCR cũ FAIL |
| Bảo toàn dữ liệu cũ | Hash 568 bản ghi business có trước UAT không đổi; chỉ thêm/chỉnh các ID mới, lịch vẫn 18 | PASS |
| Browser Accountant/Admin | Không chạy lại trong lượt Employee này | NOT TESTED |
| MST/VAT số dương từ VAT thật; PDF thật | Các mẫu đã chạy không có các giá trị này để kiểm chứng | NOT TESTED |
| OCR chính xác đầy đủ trên chứng từ mới | Có lỗi trường và hàng được mô tả bên dưới | FAIL / chưa đạt |

HTTP upload elapsed: #25 **10,156 s**, #26 **11,479 s**, #28 **11,479 s**, fallback #27 **14,412 s**. Đây là thời gian chờ HTTP trọn luồng gồm OCR/validation/DB/network, không phải profiling engine hoặc benchmark Phase7.

### Phân biệt dữ liệu OCR với dữ liệu sửa tay

`BROWSER_UAT.json`/`UNIT_BROWSER.json` lưu `upload_response` gốc trước sửa. #25 sửa ngày `2020-03-12` → `2020-08-12`, seller `CUA HANG NAM OÁNH` → `CỬA HÀNG NĂM OÁNH`, mô tả `Phở bò Dé Nhat 65g` → `Phở bò Đệ Nhất 65g`. #28 chỉ sửa unit dòng 3; không dựng thêm dòng mất hay thay số tiền để tăng điểm.

ExtractionRun và bằng chứng OCR gốc không bị ghi đè khi sửa Invoice/InvoiceItem. Correction history ghi đủ old/new/actor/time. Không dùng dữ liệu đã sửa tay để tuyên bố OCR nhận đúng. `input[type=date]` được kiểm bằng giá trị ISO DOM/API; browser QA mặc định en-US có thể hiển thị kiểu tháng/ngày trên screenshot, không suy ngày lưu từ kiểu trình bày native.

## Đối chiếu chất lượng OCR trước chỉnh sửa

| Trường | #25 — Năm Oánh | #26 — VinCommerce | #28 — ANAN |
|---|---|---|---|
| Loại | bill, phù hợp ảnh | bill, phù hợp ảnh | bill, phù hợp ảnh |
| Người bán | Sai/mất dấu: `CUA HANG NAM OÁNH` | Đọc thương hiệu `VinCommerce`; chưa giữ tên chi nhánh in cùng header | `MINIMART ANAN` đọc đúng |
| Số hóa đơn | `SON45644`; ảnh nhìn `SON55644` — sai chuỗi số, chữ O/0 có thể cần người đọc chốt | `00064574`, giữ số 0 đầu đúng | null; ảnh có Số GD, không tự coi giao dịch là số HĐ |
| Ngày | `2020-03-12` thay vì ảnh `12-08-2020` — FAIL | `2020-08-15` đúng | `2020-08-13` đúng |
| Tiền hàng/subtotal | 53000 từ nhãn Cộng tiền hàng; chưa chứng minh trước VAT | null | null |
| VAT/MST | null, không tự điền | null; ảnh chỉ nói giá đã gồm GTGT, không in rate/tiền VAT/MST | null, không tự điền |
| Tổng thanh toán | null; ảnh chỉ thấy Cộng tiền hàng 53000, không tự suy thêm một total | 95800 đúng theo nhãn tổng phải thanh toán | 116000 đúng |
| Số dòng | 1/1 | 2/2 | **5/6**, mất một dòng |
| Mô tả | Sai dấu/nhận dạng tên | Sai chữ `hổi`, `500m]`; khoản `~31.000` lẫn vào mô tả hàng 2 | Sai nhiều ký tự, mô tả một hàng thành `mac Gi An:` |
| Lượng/giá/thành tiền | 10 / 5300 / 53000 đúng | Hai hàng 2 / 37900 / 75800 và 2 / 10000 / 20000 đúng | Hai lượng null; một giá/amount thành 40000 thay 10000; thiếu hàng cuối |
| Đơn vị | null, nguồn không có cột đơn vị | null, không tự suy từ tên | Có `GOT` sai so với GOI, có HOP; nhiều đơn vị còn thiếu |

MST/VAT và đơn vị không in phải giữ null, không suy 0 hay thuế từ tổng. Vì chưa có VAT thật phù hợp ngoài tập Phase7, không lấy việc null hiển thị đúng làm bằng chứng trích xuất MST/VAT dương PASS. Không suy mô tả hoặc số liệu bị thiếu. Các chuỗi đối chiếu ở đây là AI đọc ảnh cho UAT, không sửa hoặc phê duyệt ground truth.

### Nơi lỗi phát sinh

Đối chiếu raw OCR, output gốc trong `extracted_json`, `invoice_items`, detail API và input Web: dữ liệu chưa chỉnh sửa được lưu/hiển thị nguyên theo output, không mất ở API/ORM/UI. Raw #25 đã đọc sai chuỗi số và `12-03-2020`; các lượt OCR vùng được chọn tiếp tục tạo ứng viên sai. #26 raw grouping đưa `~31.000` cùng dòng mô tả; parser ghép thành tên hàng. #28 lỗi ký tự/ô số và ghép hàng/cột; chưa xác nhận hết từng lỗi thuộc OCR hay parser, cần phân tích evidence/crop ở phiên phát triển sau.

**Không phát hiện lỗi tích hợp sản phẩm cần thay source trong lượt này.** Hai lỗi selector của script UAT (nút submit mặc định và nhãn supplier trùng substring) đã sửa trong script ngoài repo, tiếp tục đúng invoice ID đã tạo thay vì upload lại. Không sửa thuật toán frozen theo các ảnh này.

### Validation không bị bỏ qua

- #25: ITEM-SUM PASS, TOTAL vẫn FAIL do total null, cả trước và sau sửa. Không tự điền total từ subtotal.
- #26: hai dòng cộng **95800** bằng total, nhưng subtotal null nên quy tắc ITEM-SUM hiện có trả false. Thông báo hiện tại không phân biệt thiếu cơ sở so với lệch số học; đây là việc cần thống nhất nghiệp vụ, **không tự nới quy tắc trong UAT**.
- #28: trước/sau sửa unit, tổng 5 amount OCR là **121000**, khác total **116000** và thiếu một hàng; subtotal cũng null. Cần review thực, không tạo hàng/giá giả để khớp phép tính.

## Fallback — kiểm tra lỗi có kiểm soát

Process 8011 dùng cùng source ứng dụng và DB/upload test đã preflight/backup, chỉ monkeypatch **trong bộ nhớ process phụ** tại `app.ocr_runtime._run_hybrid` để raise RuntimeError. Không thay file Hybrid V6, không phá Tesseract, không đổi service 8000. Browser test chuyển tiếp request API tới **server HTTP thật** 8011 trong context riêng; không mock nội dung response hoặc dữ liệu OCR.

Một upload kiểm tra riêng của ảnh Năm Oánh tạo **#27**, HTTP 201. Fault marker ghi một lần gọi; ExtractionRun `method=image-ocr`, status completed, `_ocr.used_pipeline=current`, fallback true. Raw OCR cũ có văn bản thực; parser cũ trả unknown, fields/items rỗng và needs_review, UI cảnh báo fallback đúng. **PASS cơ chế khôi phục, FAIL trích xuất đầy đủ của OCR cũ trên ảnh này**; không giả fallback cho kết quả tốt.

Đã dừng riêng process tiêm lỗi sau khi kiểm PID/command/DB/cổng. Backend 8000 và Web 5173 tiếp tục hoạt động với Hybrid bật. Xem `FALLBACK_CLEANUP.json`. #27 được giữ để đối chiếu, không xóa, và không nhầm với ba lượt Hybrid bình thường.

## Trạng thái dữ liệu và bằng chứng

DB test sau lượt: **28 invoices, 28 files, 11 invoice_items, 28 extraction_runs, 37 corrections, 300 validation_results, 69 notifications, 137 audit_logs, 18 schedules**. Tạo bốn invoice mới #25–28, trong đó #27 là test fallback; chỉ sửa #25/#28. Hash 568 bản ghi nghiệp vụ baseline không đổi. User test có last_login cập nhật theo đăng nhập hợp lệ, không đổi mật khẩu/vai trò/tài khoản. Database chính không được kết nối.

Bằng chứng tại [web_uat/](../../ocr_phase8_integration/web_uat):

- `BROWSER_UAT.json`, `UNIT_BROWSER.json`, `FALLBACK_BROWSER.json`: HTTP/UI/form/readback và output OCR trước sửa.
- `DB_BASELINE.json`, `DB_POSTCHECK.json`: hash baseline, ORM rows, raw/evidence, validation rounds, correction và audit.
- Screenshot `retail_no_tax_detail.png`, `supermarket_detail.png`, `units_receipt_detail.png`, `retail_after_manual_edit.png`, `units_after_unit_correction.png`, `fallback_receipt_detail.png` (đã xem lại các ảnh đại diện sau chỉnh sửa).
- `fallback_server/FAULT_INJECTION.json`, `FALLBACK_CLEANUP.json`: fault và cleanup riêng.

Không lưu auth body/JWT hoặc Playwright network trace. Hồ sơ raw chứa nội dung chứng từ, chỉ dùng nội bộ. Không tái chạy 325 Backend/25 Web/build vì code sản phẩm không đổi; các PASS đó vẫn là kết quả lượt tích hợp trước. Lượt này thêm bằng chứng Browser/Uvicorn/PostgreSQL thật, không thay bằng fixture.

## Kết luận và bước sau

Tích hợp upload → Hybrid → lưu PostgreSQL → detail → sửa/lưu/F5 đã có bằng chứng hoạt động trên ba bill thật. Fallback cũng có bằng chứng lỗi có kiểm soát. **OCR vẫn sai và thiếu trường/hàng; chưa đủ điều kiện nghiệm thu hoặc đổi default.** Current vẫn mặc định cấu hình repo; chỉ tiến trình test đang bật Hybrid.

Xem [đề xuất Giai đoạn 9](OCR_PHASE9_PROPOSED_PLAN.md). Không tự triển khai G9, không mở lại benchmark G7, không xác nhận A/B hoặc đổi GT. Chưa Browser UAT Accountant/Admin, VAT thật/MST-VAT dương, PDF thật nhiều trang, kiểm tra tải đồng thời hoặc lỗi production tự nhiên. Không commit/push/pull/merge/chuyển nhánh.
