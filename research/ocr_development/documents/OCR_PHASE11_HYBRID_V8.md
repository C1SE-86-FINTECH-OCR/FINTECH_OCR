# Giai đoạn 11 — Hybrid V8 thử nghiệm

Ngày 20/11/2026, repository `FINTECH_OCR_GitHub`, nhánh `feature/thien` giữ nguyên. **Hoàn tất triển khai và kiểm thử trong phạm vi G11; độ chính xác OCR toàn diện chưa đạt nghiệm thu.** Không bắt đầu G12.

## Căn cứ và nguyên nhân

Đã đọc G10 Web UAT/checkpoint, G9 V7/checkpoint, G8, tiêu chí G7, trạng thái G3.5 và mã extraction/runtime/core/main, V6/V7, tests trước khi sửa. Bảng nguyên nhân được lưu **trước** thay đổi thuật toán tại [CAUSE_ANALYSIS.md](../../ocr_phase11_development/CAUSE_ANALYSIS.md), dựa trên ảnh/PDF gốc và raw/evidence/output G10. API/DB/UI không làm mất items; lỗi chủ yếu ở OCR và parser.

| Lớp | Bằng chứng V7 | Sửa V8 / giới hạn |
| --- | --- | --- |
| Ảnh/engine | Dấu tiếng Việt mờ và OCR số mâu thuẫn giữa crop/PSM | View từ bytes gốc, EXIF/paper/deskew helper sẵn có, tương phản nhẹ, giữ evidence từng view; không đoán ký tự |
| Ô số | Row2 ANAN crop đọc1/blank; amount40000 hoặc10000 | Giữ ứng viên OCR, khóa literal nếu successful isolated reads đồng thuận, chỉ chọn bộ q×p≈amount duy nhất có quan sát; không lấy total làm đáp án |
| Cột giá | Giá đăng ký và giá bán khác nhau | Theo label/cột/row anchor, giữ giá bán quan sát; chặn registered-price metadata |
| Bảng/ghép dòng | PDF inline continuation gắn nhầm hàng kế tiếp; STT lọt tên | Tách inline/stacked-description, geometry cột STT, loại numeric/unit cell khỏi mô tả, giữ model |
| PDF trường | Supplier label có text nhưng scoreNone bị gate OCR bỏ | Xác định provenance pdf-text; dùng nhãn rõ và vị trí, không giả score |
| Field/date/number | Nhầm ký tự số, signed/printed dates và signature metadata | Nhãn+ngữ cảnh tương đối seller/buyer/MST/số/ngày; giữ leading zero, không thay O/0/S/5 mù quáng |
| Unit | GOI/CAI xen GOT/Got | Alias từ literal có bằng chứng; GOT không được đoán thành Gói |
| Runtime | G10 mapping API==DB==UI | Bridge opt-in V8, cột hiện có và metadata; không sửa dữ liệu UAT cũ |
| Validation | Sum146000 khác total116000, subtotalnull | Giữ ITEM-SUM và validation/approval/lookup độc lập; cải thiện numeric evidence, không cân tiền |

## Thiết kế và bảo vệ dữ liệu

Tesseract vẫn là engine thực (vie+eng). V8 gọi baseline V7 bất biến, tái dùng raster/read evidence đã có; phân tích table/field ở module riêng, chỉ thêm OCR biến thể khi thiếu/không chắc/mâu thuẫn. Không đọc fixture/ground truth trong runtime. Không tải model/dùng API bên ngoài.

Các row/cell giữ text, polygon, confidence nguồn, ứng viên q/p/a và lý do chọn trong JSON evidence sẵn có. Khuyến mãi/registered-price/footer không là sản phẩm. Discount được giữ trong evidence khi đọc được; không thêm schema hay tính ngược dữ liệu. Nếu thấy discount, không áp phép sửa q×p=a cho row đó. Coverage thực tế cho nhiều loại discount còn thiếu, không tuyên bố đã giải mọi hóa đơn.

PDF text, PDF scan và carry header nhiều trang được xử lý riêng; page/transform không trộn hệ tọa độ. Headerless bill chỉ nhận dãy dòng có amount được in rõ và hình học phù hợp; quantity/price/unit thiếu giữ null. Multi-rate VAT giữ từng dòng trong evidence, không tạo VAT chung.

Mọi kết quả V8 luôn `requires_review=true`, confidence field null/chưa hiệu chuẩn; word score không là accuracy. Baseline V7 được giữ riêng trong evidence; current findings tính lại từ V8, tránh cảnh báo tổng cũ146000 gây hiểu nhầm.

Guard SHA-256 xác nhận **21/21** file baseline/current/V6/V7/env/ground truth không đổi, và **24/24** file guard lúc UAT không đổi sau kiểm thử. [FINAL_IMMUTABLE_CHECK.json](../../ocr_phase11_development/FINAL_IMMUTABLE_CHECK.json). Giữ toàn bộ thay đổi từ trước, không git add/commit/push/pull/merge/reset, không xóa stash. Không đổi thuật toán XML, schema, validator, approval, lookup, RBAC hay giao diện/CSS khác. Mặc định cấu hình vẫn `current`; V8 chỉ cho testing.

## Tệp thay đổi trong G11

| Tệp trong repository | Thay đổi G11 |
| --- | --- |
| backend/tools/ocr_benchmark/hybrid_v8.py | Mới: điều phối V8, giữ baseline/evidence, đọc lại có điều kiện, ghép page và cảnh báo |
| backend/tools/ocr_benchmark/table_v8.py | Mới: bảng/cột/ordinal, wrapped description, observed candidates, đơn vị, arithmetic |
| backend/tools/ocr_benchmark/fields_v8.py | Mới: nhãn/ngữ cảnh seller/buyer/tax/number/date/currency |
| backend/tools/ocr_benchmark/preprocess_v8.py | Mới: paper view, tương phản nhẹ, nguồn/transform, vòng đời tài nguyên |
| backend/app/core.py | Thêm option hybrid_v8 testing-only; default current |
| backend/app/ocr_runtime.py | Dispatch V8, map cột currency sẵn có, kiểm tra giá trị và fallback |
| backend/app/main.py | Bao gồm V8 trong xử lý lỗi extraction hiện có |
| backend/tests/test_ocr_hybrid_v8.py | 25 test case parser/preprocess/field/evidence |
| backend/tests/test_phase11_runtime_api.py | 10 test config/runtime/API/fallback/correction/RBAC/Tesseract synthetic |
| web/src/ocrRuntimeInfo.js | Hiển thị tên/cảnh báo V8 theo metadata thật |
| web/tests/ocrRuntimeInfo.test.js | Test banner V8 |
| docs/OCR_PHASE11_HYBRID_V8.md | Báo cáo thiết kế/UAT |
| docs/OCR_PHASE11_BENCHMARK_RESULTS.md | Kết quả đo và lỗi |
| docs/OCR_PHASE11_CHECKPOINT.md | Checkpoint/phạm vi tiếp tục |

Các file extraction.py/test_extraction.py/test_phase2_api.py/InvoiceDetailPage và nhiều file untracked khác đã tồn tại từ các lượt trước; `git status` không phải danh sách thay đổi riêng G11. Không ghi đè chúng. Công cụ điều phối/benchmark/UAT và evidence riêng nằm ngoài repo tại `<LOCAL_PATH>`.

## Kiểm thử tự động

| Hạng mục | Kết quả | Bằng chứng |
| --- | --- | --- |
| Test mới V8/parser/runtime/API | 35 PASS, 0 FAIL | v8-focused.xml |
| Toàn bộ Backend | 412 PASS, 0 FAIL, 0 SKIP; 69.32s; 27 warnings thư viện | backend-tests.xml / backend-tests.log |
| Toàn bộ Web | 36 PASS, 0 FAIL | web-tests.log |
| Vite production build | PASS, 9.24s; warning chunk>500kB sẵn có | build.log |
| Benchmark inference | 32/32 hoàn tất; không đồng nghĩa dữ liệu đúng | BENCHMARK.json / SCORES.json |

Bằng chứng tại [thư mục G11](../../ocr_phase11_development/). Baseline G10 sau develop377 Backend/35 Web; G11 thêm35 Backend/1 Web. Không xóa test hoặc hạ assertion cũ. Lần đầu chạy từ repo gặp 1 lỗi SQLite test cũ thiếu users.phone; không sửa schema hay xóa DB đó. Lần full được báo ở đây chạy từ thư mục tạm mới ngoài repo với PYTHONPATH Backend, nên test tự tạo SQLite cô lập; không truy cập PostgreSQL trong full regression. Không dùng file test cũ để kết luận regression sản phẩm.

Đã tương thích với checkout sau develop hiện có qua full tests/build; không pull/merge lại. Không thể khẳng định tương thích với commit remote chưa tải.

## Benchmark

Xem [kết quả chi tiết](OCR_PHASE11_BENCHMARK_RESULTS.md). Trên 3 ảnh development, field giữ11/13, ô normalized31/40 →35/40, dòng normalized2/7 →4/7. Synthetic5: field39/42 →41/42, ô32/45 →44/45, dòng0/11 →10/11. Không phải dữ liệu nghiệm thu mới. Exact raw và normalized được tách rõ. V8 chậm hơn V7 trên ảnh thật, chưa tối ưu tốc độ.

## Website UAT giới hạn — thực sự chạy

Playwright Chromium local headless, React/Vite thật5173, FastAPI/Uvicorn thật8000, Tesseract thật, PostgreSQL test thật; không API mock hoặc render fixture để giả Website PASS. 3 JPEG thật đã biết +2 PDF synthetic, không là 5 hóa đơn thật mới. Ảnh được kiểm tra trực quan lại ở units/pdf_text; các field/item UI còn được so từng ô với response thật trước/sau F5. Không thay UAT sign-off của con người.

Trước ghi: Docker container Healthy, PostgreSQL17; runtime wrapper truy vấn `current_database()` READ ONLY ngay trong process và kiểm tra `APP_ENV=testing`, DB test, upload tuyệt đối; kiểm tra schema hiện có không DDL, backup và checksum. Không dựa riêng /health hay .env. Backup mới:

- `<LOCAL_PATH>`
- 662,945 bytes; SHA-256 `731507a1997960cc50c586bc8444afe35fd4b609d0086c2a069ddb9b158ea1a5`; pg_restore --list exit0. File ban đầu có tên phase10 do helper tái dùng, đã sao chép byte-identical sang tên phase11 mới bằng create-exclusive; giữ provenance/ảnh gốc, không dùng backup G10 cũ.

Bằng chứng: [BACKUP.json](../../ocr_phase11_development/uat/BACKUP.json), [backup-list.txt](../../ocr_phase11_development/uat/backup-list.txt), [runtime sau restart](../../ocr_phase11_development/uat/RUNTIME_8000.json), [DB trước](../../ocr_phase11_development/uat/DB_BASELINE.json).

| Mẫu / invoice mới | HTTP upload | Dòng | UI/API/F5/restart | Độ chính xác / giới hạn |
| --- | --- | --- | --- | --- |
| retail #42 | 201 /12.937s | 1 | PASS mapping/persistence | FAIL seller accents/suffix trước correction; correction2 trường được lưu riêng, không tính OCR đúng |
| supermarket #43 | 201 /14.951s | 2 | PASS | Tiền đúng; mô tả còn lỗi dấu/500m]; ITEM-SUM false vì subtotalnull |
| ANAN #44 | 201 /19.173s | 6 | PASS | q/p/amount đúng; tổng116000; units2 ô sai/chưa chắc; ITEM-SUM false vì subtotalnull |
| PDF text #45 (synthetic) | 201 /0.411s | 3, 2 trang | PASS | Field/item theo nhãn đủ; ITEM-SUM true; thiếu buyer tax vẫn cần review |
| PDF scan #46 (synthetic) | 201 /2.802s | 1 | PASS | Field/item theo nhãn; ITEM-SUM true |
| Fallback #47 | 201 /12.248s | 0 | PASS cơ chế + banner sau restart | Controlled engine exception tại process8011; OCR current thật chạy, dữ liệu retail vẫn kém; không là accuracy PASS |

Nguồn: [BROWSER_UAT.json](../../ocr_phase11_development/uat/BROWSER_UAT.json), [BROWSER_FAULT_engine.json](../../ocr_phase11_development/uat/BROWSER_FAULT_engine.json), [RESTART_BROWSER.json](../../ocr_phase11_development/uat/RESTART_BROWSER.json). Screenshot: [#44](../../ocr_phase11_development/uat/units_detail.png), [#45](../../ocr_phase11_development/uat/pdf_text_detail.png), [#42 correction](../../ocr_phase11_development/uat/retail_corrected.png), [fallback sau restart](../../ocr_phase11_development/uat/fallback_engine_47.png). Còn screenshot từng mẫu và log trong cùng thư mục; không lưu JWT/mật khẩu vào báo cáo.

- Đăng nhập thật Employee/Accountant/Admin PASS; 15 checks PASS trong BROWSER_UAT, không lỗi JavaScript.
- Employee approve/lookup403, Accountant edit403, Employee hóa đơn người khác404; Accountant/Admin đọc tài nguyên theo quyền200. Đây có kiểm tra API từ browser, không gọi mọi thao tác đó là click UAT đầy đủ.
- Manual correction chỉ #42 seller+description (2 bản ghi correction), giữ extraction gốc làm đối chứng, validation chạy lại, F5/restart giữ dữ liệu. Không sửa số tiền để ép tổng.
- Không submit/approve/reject lại workflow đã PASS G10. G11 kiểm tra trạng thái vẫn draft, lookup not_checked/not_applicable, không tự verified. Workflow đầy đủ V8 theo từng sự kiện mới: NOT TESTED trong lượt này; hồi quy tự động PASS.
- Fallback controlled engine exception trên8011 chỉ thay seam `_run_hybrid_v8` trong process; OCR current vẫn chạy thực. Timeout/invalid/NaN/strict mode được test tự động, chưa lặp Browser cho từng lỗi vì G10 đã có; không báo Browser V8 PASS cho các loại chưa chạy.
- Sau Browser kết thúc, xác minh idle/PID/DB rồi restart Backend test8000; đọc lại #42–46 và banner history#47 PASS. Đã dừng fault server8011, giữ Vite.

Hậu kiểm READ ONLY: **840 bản ghi trước UAT thuộc 9 bảng snapshot không đổi**, 41 file cũ giữ checksum, toàn bộ checksum được kiểm tra lúc restart. #1–41 không bị sửa/ghi đè. [DB_AFTER_RESTART.json](../../ocr_phase11_development/uat/DB_AFTER_RESTART.json). Số lượng cuối:

| Bảng | Số bản ghi |
| --- | --- |
| invoices | 47 |
| invoice_files | 47 |
| invoice_items | 43 |
| extraction_runs | 47 |
| invoice_corrections | 41 |
| validation_results | 432 |
| notifications | 95 |
| audit_logs | 164 |
| schedules | 18 |

Chỉ thêm #42–47 vào test và uploads test; không kết nối DB chính, không seed/migration/reset/restore. Dữ liệu trùng file UAT được giữ để đối chiếu, UI cảnh báo duplicate là đúng; không tính thành mẫu mới.

## Runtime bàn giao và rollback

- Website: htt<LOCAL_PATH>
- Runtime sau restart PID **26280**, `APP_ENV=testing`, `fintech_ocr_rbac_test`, upload `backend/uploads_rbac_test`, `OCR_PIPELINE=hybrid_v8`, fallbacktrue; Vite PID13224 giữ nguyên. `/health`: ok/testing. JS Vite phục vụ có bannerV8 và api target8000 đã kiểm tra, không chỉ HTTP200/build.
- Source default `current` và .env không đổi. Runtime V8 là bật thử nghiệm theo lệnh, không đổi mặc định sản phẩm. Guard yêu cầu app_env testing.
- Dùng helper ngoài repo `ocr_phase11_development/restart_test.ps1 -Pipeline current` để quay về current, hoặc hybrid_v6/hybrid_v7/hybrid_v8; helper kiểm tra đúng PID/runtime/DB/upload và không còn kết nối trước khi dừng. Nếu guard từ chối thì dừng thao tác, không kill Node/Python khác. Không khởi động Uvicorn trần thiếu env vì có thể dùng DB khác.
- Cấu hình test hiện tại đã được chứng minh bởi [FINAL_LIVE_SERVICES.json](../../ocr_phase11_development/uat/FINAL_LIVE_SERVICES.json). Runtime có thể dừng sau phiên/máy ngủ; không bảo đảm luôn tồn tại.

## Phân loại kết quả và việc còn thiếu

| Hạng mục | Trạng thái | Căn cứ / còn thiếu |
| --- | --- | --- |
| V8 độc lập + API mapping + defaultcurrent + XML unchanged | PASS giới hạn | 35 tests mới; hashes baseline; full regression |
| Upload/PG/UI/F5/restart/correction/fallback/RBAC | PASS giới hạn | Chỉ 5 mẫu +1 controlled fallback kể trên |
| OCR chính xác toàn bộ | FAIL | Retail seller/number; descriptions; GOT/Got; POS seller |
| Sửa tài chính ANAN | PASS q/p/amount; FAIL đơn vị2 ô | 6 dòng quan sát đúng tổng116000, không suy subtotal; ITEM-SUM vẫn cảnh báo |
| PDF text/multipage/scan đã chấm | PASS synthetic | Không suy thành chất lượng trên PDF thật mới |
| Đạt NFR01/nghiệm thu độc lập | BLOCKED | Thiếu bộ thật mới A/B đã duyệt/cỡ mẫu đủ; G7 vẫn tạm dừng |
| True row polygon F1; CER/WER | NOT TESTED | Thiếu nhãn polygon/transcription con người |
| VAT thật/PDF mixed/ảnh khó/discount phức tạp | NOT TESTED đầy đủ | Coverage hiện tại không đủ |
| Tax Lookup dịch vụ thật | BLOCKED lịch sử | Không thuộc G11, không giả verified |
| UAT sign-off / ACCEPTED | Chưa có | Người dùng/PO quyết định |

Điều kiện đề xuất trước G12: chốt bộ thật mới và nhãn A/B, tiêu chí/cỡ mẫu SRS trước inference; xử lý lỗi ký tự/number/unit bằng development khác; đo row matching thật, latency/cost/rate-review; kiểm tra discount/mixed-PDF thật và workflow V8 cần thiết. Không dùng lại bộ phát triển để gọi độc lập, không hạ mục tiêu sau thấy điểm. **Dừng G11, chưa triển khai G12.**
