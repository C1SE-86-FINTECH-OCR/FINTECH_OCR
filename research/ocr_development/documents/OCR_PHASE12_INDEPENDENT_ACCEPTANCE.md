# Giai đoạn 12 — Nghiệm thu độc lập Hybrid OCR V8

Ngày 20/11/2026 (Asia/Ho_Chi_Minh), `FINTECH_OCR_GitHub`, nhánh `feature/thien`.

**Kết luận trường hợp D: BLOCKED do chưa có bộ hóa đơn thật độc lập và ground truth A/B đủ điều kiện. Chưa nghiệm thu Hybrid V8/Task 2.** Đã thực hiện phần kiểm kê, khóa nguồn, preflight/backup, full regression và Browser đăng nhập+GET có thể chạy; không tạo V9 hoặc chuyển G13.

## 1. Căn cứ và trạng thái thực tế

Đã đối chiếu toàn bộ các báo cáo G11 thiết kế/benchmark/checkpoint; G10 UAT/checkpoint; G9 V7; tiêu chí và hồ sơ chuẩn bị G7; trạng thái G3.5; source/evaluator/runtime/permission hiện có và hồ sơ dữ liệu liên quan. Các kết quả trong báo cáo cũ được giữ là lịch sử, không gọi là phép đo độc lập G12.

- `git status`, `diff --check`, `diff --stat`, branch, stash và HEAD chỉ đọc. `feature/thien` giữ nguyên, 3 stash backup còn nguyên. Diff hiện có từ các giai đoạn trước được giữ; không add/commit/push/pull/merge/reset/chuyển nhánh. Không fetch, không suy về commit remote mới.
- Khóa SHA-256 **141 file source/test/env/manifest/nhãn cũ** trước kiểm thử, so lại sau: **141/141 không đổi**. current, V6 frozen, V7 baseline, V8, API, Website, models/schema và ground truth cũ không bị sửa. G11 baseline 21 file vẫn khớp khi bắt đầu.
- So với checkout develop hiện có, full regression mới vẫn PASS ở Profile/Report/Schedule/workspace search/approval/lookup/RBAC/correction/validation/runtime. Điều này không thay thế UAT đầy đủ mọi thao tác hoặc xác nhận remote chưa tải.

Bằng chứng: [GIT_READONLY.json](../../ocr_phase12_acceptance/GIT_READONLY.json), [source lock](../../ocr_phase12_acceptance/SOURCE_AND_LABEL_LOCK.json), [source cuối](../../ocr_phase12_acceptance/SOURCE_FINAL_CHECK.json), [ENGINE_FREEZE.json](../../ocr_phase12_acceptance/ENGINE_FREEZE.json). Chỉ khóa source; chưa freeze nhãn/dataset nghiệm thu vì chưa đủ điều kiện.

## 2. Kiểm kê và tính độc lập

Quét workspace và thư mục nguồn CAPSTONE đã có, bỏ môi trường node_modules/venv/Git, preview/portable-package trùng và thư mục output G12; không đọc database/archive DB. Tìm **476 đường dẫn ảnh/PDF/XML**, **332 hash byte khác nhau**, **84 nhóm trùng byte**. Các số này gồm screenshot, fixture, cache, asset phần mềm và bản sao upload; **không phải 332 hóa đơn thật độc lập**.

| Nhóm đường dẫn | Số file vật lý |
| --- | --- |
| archived_prior_upload_not_independent | 11 |
| regression_fixture | 1 |
| evidence_or_regression | 163 |
| prior_uploaded_document_not_independent | 97 |
| prior_development_or_evidence | 26 |
| synthetic_regression | 11 |
| software_asset_not_document | 6 |
| development_or_old_candidate_review_required | 20 |
| old_source_download_or_review_cache | 20 |
| phase7_candidate_or_reference_unapproved | 97 |
| reserved_phase7_draft_no_benchmark_permission | 24 |

Các dataset phải phân biệt:

- **Development**: HD-01–07, 10 ảnh G3.5, nguồn đã dùng G4–G11, ảnh từng upload/chẩn đoán. Các ứng viên cũ chưa rõ provenance không tự nâng thành independent.
- **Regression**: fixture/XML, source đã dùng kiểm thử và các bản upload lặp. Không tính nhiều request cùng SHA thành nhiều tài liệu độc lập.
- **Synthetic**: ảnh/PDF VAT/bill/multipage đã tạo từ trước và bộ Paddle thử nghiệm cũ. Không tạo thêm để lấp coverage thật trong G12.
- **Independent candidate G7**: 24 JPEG, **24 draft, 0 approved, 0 hồ sơ A/B**. Giữ reserved; không OCR, freeze hoặc benchmark lại. Không coi AI review/SHA đúng là con người xác minh.
- **G12 mới đủ điều kiện**: **0**. `intake/documents` rỗng, CSV chỉ có header, ground truth mới có documents rỗng. Không tạo ID/nhãn/ảnh giả.

Đã làm dHash256 trên **147 ảnh khác byte**, 4 hướng và full/center90%, có 3 cặp cần đối chiếu; đã mở trực tiếp cả sáu ảnh: (1) cùng graphic synthetic không phải hóa đơn, JPG/PNG; (2) cùng bill gốc và ảnh chỉnh phối cảnh cũ; (3) hai hóa đơn synthetic khác số/người bán nhưng gần bố cục, là false positive dHash. Không tự gộp các hóa đơn chỉ vì bố cục giống. SHA và dHash âm không chứng minh tuyệt đối độc lập theo hóa đơn/nhà cung cấp; PDF crop/chụp lại và supplier/layout cần con người rà soát. Một PNG không decode được là file test lỗi có sẵn **ID40** từ G10, checksum vẫn khớp; giữ nguyên, không xóa/sửa.

Bằng chứng: [DOCUMENT_INVENTORY.json](../../ocr_phase12_acceptance/DOCUMENT_INVENTORY.json), [DATASET_READINESS.json](../../ocr_phase12_acceptance/DATASET_READINESS.json), [NEAR_DUPLICATE_AUDIT.json](../../ocr_phase12_acceptance/NEAR_DUPLICATE_AUDIT.json), [catalog cũ](../../ocr_phase12_acceptance/known_documents.json).

## 3. Ground truth và tiêu chí

Không lấy output OCR hoặc Invoice đã correction làm nhãn. Đã tạo intake riêng, schema hướng dẫn present/absent/illegible/not_applicable/unreviewed cho 13 field hóa đơn và các ô dòng hàng, unit/page/VAT/discount. Dữ liệu không đọc được bị loại khỏi expected/scoring; không dùng null như câu trả lời cho phần bị che. Không xem items rỗng là bảng đã đọc đủ.

**Chưa có nhãn mới được người A/B duyệt; không ai được tự điền approved.** Tên/ngày/MST/số/tiền/dòng hàng của chứng từ mới chỉ được ghi sau khi có bản gốc và người xác minh thật. CER/WER chưa có transcription đã duyệt nên NOT TESTED.

SRS NFR01 có mục tiêu >=85% theo trường trên 100–500 hóa đơn. G7 ghi pilot20–30 và đề xuất coverage, chưa phải mọi ngưỡng đã được PO phê duyệt. G12 đề xuất pilot30–50, không tự thay cỡ mẫu NFR01. Cách tổng hợp field accuracy, row/financial thresholds và SLA latency còn cần quyết định thật trước prediction. Đã gửi câu hỏi người dùng, giữ [CRITERIA_PENDING_PO.json](../../ocr_phase12_acceptance/CRITERIA_PENDING_PO.json) chưa phê duyệt, không hạ ngưỡng.

Đã chạy [check_readiness.py](../../ocr_phase12_acceptance/check_readiness.py) thực tế: **BLOCKED, exit2 đúng dự kiến**, 0 manifest rows/0 ground-truth records, 141 hash giữ nguyên, không inference/freeze/auto-approval. [READINESS.json](../../ocr_phase12_acceptance/READINESS.json).

Hướng dẫn thêm dữ liệu/khai báo CSV/prepare/đọc gốc/A-B/freeze được lưu tại [INTAKE_AND_VERIFICATION_GUIDE.md](../../ocr_phase12_acceptance/INTAKE_AND_VERIFICATION_GUIDE.md). CLI benchmark legacy chỉ đăng ký engine đến V6; runner G11 chạy source development cố định, không dùng nhầm làm benchmark độc lập V7/V8. Khi có dữ liệu phải nối runner bốn phiên bản với snapshot mới và chốt evaluator/discount/matching trước đo, không đổi thuật toán OCR.

## 4. Preflight và backup PostgreSQL test

Đầu lượt 8000/5173 không có listener; Docker PostgreSQL Healthy, 5432 đang lắng nghe. Không tự dừng process nào. Kết nối URL được đổi sang test **trước khi tạo engine/import app**, `current_database()` chạy READ ONLY xác nhận đúng `fintech_ocr_rbac_test`. Không kết nối database chính.

- Baseline47 invoices/47files/43items/47runs/41corrections/432validation/95notifications/164audit/18schedules. Snapshot mở rộng toàn bộ **20 bảng, 1069 bản ghi**.
- Toàn bộ cột mapped hiện có, không migration/DDL/create_all/seed/restore/reset. server/client encoding UTF8.
- 47/47 file gốc trong `backend/uploads_rbac_test` có SHA-256 khớp DB.

Backup mới: `<LOCAL_PATH>` — **1,203,995 bytes**, SHA-256 `336f5bbf17ae17178b081fad22658997bcb65e269f3e92bcd9e62c26965810f1`, custom PGDMP, `pg_restore --list` trong Docker exit0.

[BACKUP.json](../../ocr_phase12_acceptance/uat/BACKUP.json), [backup-list.txt](../../ocr_phase12_acceptance/uat/backup-list.txt), [SCHEMA_CHECK.json](../../ocr_phase12_acceptance/uat/SCHEMA_CHECK.json), [DB_BASELINE.json](../../ocr_phase12_acceptance/uat/DB_BASELINE.json), [ALL_TABLES_BASELINE.json](../../ocr_phase12_acceptance/uat/ALL_TABLES_BASELINE.json). Backup được tạo trước các lần login thật.

## 5. Regression mới và Browser thực tế

| Kiểm tra | Kết quả G12 mới | Bằng chứng |
| --- | --- | --- |
| Full Backend | 412 PASS /0FAIL/0SKIP, 71.32s; 27 warning thư viện | backend-tests.xml / backend-tests.log |
| Full Frontend | 36 PASS /0FAIL | web-tests.log |
| Production build | PASS, 9.05s; chunk>500kB warning giữ nguyên | build.log |
| Browser login+GET | 36/36 checks PASS sau sửa kỳ vọng QA; 0 JS error | uat/BROWSER_READONLY.json |
| Đọc 47 file/checksum, metadata/nguồn runtime | PASS môi trường test | uat/LIVE_SERVICES.json / DB_FINAL_CHECK.json |

Backend chạy trong working directory tạm G12 mới với SQLite/fixture cô lập, PYTHONPATH Backend; không xóa/migrate SQLite test cũ. Một số test có OCR synthetic thật như thiết kế sẵn; không dùng chúng làm benchmark hóa đơn độc lập. Không thay assertion/test/source sản phẩm để làm PASS. Các suite bao gồm runtime/V6/V7/V8/fallback/RBAC/correction/validation/Profile/Report/Schedule/search/approval/lookup.

Playwright Chromium local headless chạy React/Vite thật, API/Uvicorn và PostgreSQL test thật. Chỉ cho POST login, còn mọi POST/PUT/PATCH/DELETE khác bị chặn tại harness; không upload/edit/submit/approve/reject/lookup/create-user trong Browser G12. Nhãn “read-only” của artifact nghĩa là login + GET, **không có nghĩa toàn DB không ghi**: endpoint login cập nhật hai timestamp như mục bảo toàn dưới đây.

Ba vai trò đăng nhập đúng; GET Profile/Dashboard/Schedule/Notifications/Invoice44,45/users/audit/report summary trả200/403 theo role; UI#44 có6 dòng, banner HybridV8; file auth checksum đúng; correction history #42 vẫn2 bản ghi; F5 giữ6 dòng. Đây là đọc lại UAT cũ, không là kết quả OCR mới hoặc upload độc lập PASS. Screenshot: [Employee](../../ocr_phase12_acceptance/uat/employee_invoice44.png), [Accountant](../../ocr_phase12_acceptance/uat/accountant_invoice44.png), [Admin](../../ocr_phase12_acceptance/uat/admin_invoice44.png).

Lượt Browser đầu có1 kỳ vọng sai trong **script QA mới**: Accountant audit200, thực tế403. Đã đối chiếu source `require_roles('admin')`, SRS Admin audit viewer/PB22; sửa expectation thành403, giữ [kết quả ban đầu](../../ocr_phase12_acceptance/uat/BROWSER_READONLY_INITIAL.json) và retest36/36 PASS. Không sửa phân quyền hoặc test sản phẩm.

Workflow V8 trên hóa đơn độc lập mới: **BLOCKED**. Không tái dùng workflow G10 hoặc mock để tuyên bố G12 Browser UAT hoàn tất. Account creation/role changes/full correction-submit-approve-reject/lookup mới vẫn NOT TESTED trên Browser G12; unit/API fixture regression PASS riêng. Tax Lookup thật tiếp tục BLOCKED, không tạo verified.

## 6. Bảo toàn dữ liệu và tác động đăng nhập

[Hậu kiểm READ ONLY](../../ocr_phase12_acceptance/uat/DB_FINAL_CHECK.json) xác nhận:

- 20 bảng vẫn1069 hàng, không thêm/xóa bản ghi; invoices vẫn47, items43; **không tạo invoice G12** và không sửa #1–47.
- **1058 bản ghi ở 19 bảng ngoài users giữ nguyên hash**, gồm invoice/file/run/item/validation/correction/approval/lookup/audit/report/schedule/notification/chat/token…
- Bảng users11 hàng: chỉ3 tài khoản đăng nhập Employee/Accountant/Admin đổi **last_login_at và updated_at**; 8 user khác nguyên trạng. `User.updated_at` có onupdate theo source, đây là tác động bình thường của login đã được yêu cầu, không sửa quyền/mật khẩu/profile để chạy test.
- Để xác minh mọi cột còn lại không đổi, đã dùng `pg_restore --data-only --table=users --file=-` **xuất SQL ra bộ nhớ**, đọc users từ backup, so COPY hiện tại trong transaction READ ONLY sau khi loại đúng2 timestamp. Không restore vào database, không ghi SQL dump chứa password hash ra báo cáo, không UPDATE để giấu tác động login.
- 47/47 file vẫn khớp checksum. Correction history và các trạng thái validation/approval/lookup cũ được giữ. ITEM-SUM không nới lỏng; ví dụ#44 vẫn cảnh báo vì subtotalnull, không tự lấy payable làm subtotal.

Không được viết “toàn bộ database không đổi” vì hai timestamp đăng nhập đã đổi. Guard hậu kiểm đầu chỉ dự kiến last_login_at nên dừng ở updated_at; sau đối chiếu model/onupdate, guard cho phép đúng2 cột trên3 user, mọi cột khác vẫn so strict với backup. Không sửa dữ liệu để làm guard PASS.

## 7. Runtime bàn giao

- Backend8000 PID **11976** tại snapshot, app_env testing, database `fintech_ocr_rbac_test`, upload tuyệt đối `FINTECH_OCR_GitHub/backend/uploads_rbac_test`, OCR_PIPELINE hybrid_v8, fallbacktrue. Chứng minh trong cùng process ứng dụng bằng kết nối READ ONLY, đối chiếu listener PID/module hash; không chỉ dựa /health.
- Vite5173 PID **13756**, root `FINTECH_OCR_GitHub/web`; JavaScript thật phục vụ api target127.0.0.1:8000/api/v1. Source/.env không đổi.
- Website htt<LOCAL_PATH>
- Wrapper/check-only/preflight/proof ở `ocr_phase12_acceptance`. Helper `restart_test.ps1 -Pipeline current` (hoặc hybrid_v6/v7/v8) chỉ dùng test, kiểm PID/idle/DB/backup/upload/source trước dừng. Không chạy switch trong G12; chỉ kiểm cú pháp. Không dùng helper G11 có PID cũ cho runtime mới.
- Không sửa CORS/cổng/.env. Không benchmark G7, không thay ground truth/algorithms và không gửi chứng từ ra ngoài.

## 8. Nghiệm thu, mức hoàn thành và lựa chọn

| Hạng mục | Trạng thái | Giới hạn / còn thiếu |
| --- | --- | --- |
| Bảo toàn source/default/GT/current/V6/V7/V8 | PASS | 141 hash không đổi, branch/stash giữ |
| Preflight/backup/test runtime | PASS | DB test, schema và47checksum; không là OCR accuracy |
| Regression Backend/Web/build | PASS | 412 /36 /build; 448 unit/API/Web tests, không gộp thành chứng từ thật |
| Browser đăng nhập+GET/RBAC đọc | PASS giới hạn | 36 checks trên dữ liệu cũ, không workflow ghi |
| Độ chính xác độc lập/field/line/financial | BLOCKED | 0 nguồn mới+nhãn A/B đủ điều kiện |
| OCR đầy đủ trên mẫu development cũ | FAIL lịch sử G11 | Số hóa đơn, dấu Việt, đơn vị; không sửa trong nghiệm thu |
| Hiệu năng mới, CPU/RAM, timeout/fallback thực | NOT TESTED | Không inference độc lập; thống kê G11 chỉ lịch sử |
| Browser upload/workflow/refresh/restart trên nguồn mới | BLOCKED | Không ghi khi thiếu ground truth độc lập |
| Tra cứu thuế thật | BLOCKED | Không bằng chứng đối chiếu thật, không verified giả |
| NFR01/Task2 ACCEPTED/G13 | BLOCKED | Chưa đủ dữ liệu, ngưỡng và sign-off |

Chọn **D**, chưa đủ dữ liệu độc lập để lựa chọn engine chính thức. Dữ liệu development cho thấy V8 có lợi về một số ô và chậm hơn V7, nhưng không đủ kết luận generalization hoặc chuyển default. Giữ current mặc định, V8 thử nghiệm có rollback, không phát triển V9/khởi động G13.

Cần người dùng cung cấp: bộ thật mới được phép sử dụng, pilot30–50 nếu phù hợp; để kết luận NFR cần cỡ mẫu/quy trình100–500 và quyết định tiêu chí thật. Coverage ưu tiên VAT thật, PDF text, PDF scan, nhiều trang, bill không MST/VAT, nhà hàng/siêu thị, nhiều dòng, ảnh nghiêng/mờ, chiết khấu/khuyến mãi. Khoảng thiếu G7: ít nhất4VAT thật,3PDF,2nhiều trang (có thể chồng lấp), chưa có nguồn bổ sung hợp lệ trong G12. A/B xác minh trước prediction, PO chốt tiêu chí trước so sánh. Không yêu cầu dùng lại24ảnh nháp để thay bộ mới.

## 9. Tệp của G12 và điểm dừng

Trong repository chỉ thêm3 tài liệu:
- `docs/OCR_PHASE12_INDEPENDENT_ACCEPTANCE.md`.
- `docs/OCR_PHASE12_BENCHMARK_RESULTS.md`.
- `docs/OCR_PHASE12_CHECKPOINT.md`.

Ngoài repo có inventory/catalog/dHash audit; source/engine lock; criteria pending/readiness guard; intake CSV/ground truth rỗng/schema/guide; helper preflight/serve/browser/postcheck/restart và backup/evidence/test/build logs. Các helper không chỉnh parser/API và không tạo kết quả nghiệm thu giả. Hướng dẫn chi tiết ở [guide](../../ocr_phase12_acceptance/INTAKE_AND_VERIFICATION_GUIDE.md).

**Dừng G12 tại checkpoint BLOCKED cho phần nghiệm thu độc lập; hoàn tất các kiểm tra không phụ thuộc dữ liệu thiếu. Chờ người dùng quyết định/cung cấp dữ liệu, không tự chuyển G13.**
