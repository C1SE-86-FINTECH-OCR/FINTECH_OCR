# Giai đoạn 10 — Web UAT Hybrid V7 sau merge develop

Ngày **20/11/2026, Asia/Ho_Chi_Minh**. Repository `FINTECH_OCR_GitHub`, nhánh `feature/thien`.

**Tích hợp và vận hành test: PASS trong các phạm vi có bằng chứng bên dưới. Chất lượng OCR: FAIL/chưa đủ điều kiện nghiệm thu Task 2.** Không đổi pipeline mặc định, không sửa thuật toán V6/V7, không chạy benchmark Phase7 hoặc sửa ground truth.

## 1. Mã nguồn sau merge

Đã đọc checkpoint/báo cáo G9, đề xuất G9, UAT/runtime/integration G8, tiêu chí Phase7, trạng thái Phase3.5 và hồ sơ G10 cũ. Đã rà soát core/main/models/extraction/runtime, modules benchmark V6/V7, InvoiceDetail, Profile, Report, Schedule và migrations liên quan.

- `git status`, `diff --check`, `diff --stat`, `branch --show-current`, `stash list`, `rev-list --left-right --count HEAD...origin/develop` chỉ đọc. Branch `feature/thien`; ahead/behind **0/0** theo remote ref đang có, không fetch. Ba stash backup còn nguyên. Không có conflict marker hoặc lỗi whitespace. Các thay đổi Task 2 chưa commit vẫn được giữ.
- Modules V7, bridge/API, cảnh báo Web và test đã có. Source mặc định `ocr_pipeline='current'`; V6/V7 chỉ được bật trong testing. Core sau merge dùng `.env` theo đường dẫn Backend tuyệt đối.
- So source lock lịch sử: **13/14 file khớp byte**. `test_ocr_hybrid_v6.py` đổi LF → CRLF khi khôi phục; hash sau chuẩn hóa xuống dòng khớp bản frozen. Không chỉnh lại test này. Không có khác biệt nội dung thuật toán V6. V7 và cấu hình hiện tại được hash trước/sau UAT, không thay đổi trong lượt.
- **Không sửa source sản phẩm trong G10.** Khác biệt/giới hạn phát hiện được ghi nhận, không refactor code của thành viên khác.

Bằng chứng: [GIT_READONLY.json](../../ocr_phase10_integration/postmerge_20261120/GIT_READONLY.json), [FROZEN_AUDIT.json](../../ocr_phase10_integration/postmerge_20261120/uat/FROZEN_AUDIT.json).

## 2. Preflight, schema và backup

Checkpoint cũ 28 invoices/18 schedules/backup 188.891 byte là lịch sử. Sau merge, baseline thực tế là **31 invoices, 31 files, 17 items, 31 extraction_runs, 37 corrections, 324 validation_results, 73 notifications, 141 audit_logs, 18 schedules**. Toàn bộ **31 file** có checksum khớp DB.

Docker `fintech_ocr_postgres` Healthy, PostgreSQL 5432 hoạt động. Sandbox thường không truy cập được Docker pipe; thao tác được thực hiện bằng quyền truy cập Windows phù hợp, không đổi ACL/quyền bảo mật hoặc Docker config.

Đã đọc migration Profile, Report history, Schedule compatibility/notes và đối chiếu **tất cả cột mapped trong models** với schema PostgreSQL test. **Không thiếu cột; không chạy migration nào.** Profile migration người dùng đã thực hiện không bị chạy lại. Startup testing không create_all.

Backup mới trước các request ghi:

`<LOCAL_PATH>`

- **382.624 byte**, custom pg_dump, magic `PGDMP`.
- `pg_restore --list` trong container: **exit code 0**, tên DB/archive và dữ liệu invoices đúng.
- SHA-256: `8cc1f00ced9941dd5f19b54523a8683fa6a5aaa0672b781eb9b39338a5d11e4c`.
- server/client encoding UTF8. Không restore, seed, reset hoặc kết nối `fintech_ocr`.

Preflight lần đầu sau merge dừng ở guard do CRLF của test frozen; không bỏ qua thay đổi code. Đã chứng minh nội dung LF giống hệt, lưu audit riêng và chạy preflight mới trong thư mục con, giữ nguyên backup/baseline của lần dừng. [BACKUP.json](../../ocr_phase10_integration/postmerge_20261120/uat/BACKUP.json), [SCHEMA_CHECK.json](../../ocr_phase10_integration/postmerge_20261120/uat/SCHEMA_CHECK.json).

## 3. Regression sau merge

| Kiểm thử | Kết quả mới | Phạm vi/giới hạn |
|---|---|---|
| Backend chạy từ thư mục backend | **376 PASS, 1 FAIL**, 74,90 s | `test_api.py` chọn SQLite tương đối `test_fintech.db` cũ thiếu `users.phone`. Không phải PostgreSQL test bị thiếu schema. |
| Toàn bộ Backend trong thư mục tạm mới | **377 PASS, 0 FAIL, 0 SKIP**, 70,23 s | Cùng test/assertions, SQLite/fixture độc lập. Không sửa/reset/migrate file SQLite cũ để làm PASS. |
| Toàn bộ Frontend `npm.cmd test` | **35 PASS, 0 FAIL** | Bao gồm search/date ranges mới từ develop và các test Task 2. |
| `npm.cmd run build` | **PASS**, 9,53 s | Còn cảnh báo chunk >500 kB. |

Bộ Backend bao gồm V6/V7/extraction/XML/runtime/RBAC, Profile, report/export, Schedule/migration compatibility, invoice search, validation/approval/lookup. Có 27 warning deprecation thư viện; không sửa test để giảm tiêu chí. Vấn đề test dùng SQLite tương đối cũ vẫn cần cải thiện isolation trong một thay đổi test harness riêng; không sửa chức năng sản phẩm để né lỗi.

[backend-isolated.xml](../../ocr_phase10_integration/postmerge_20261120/backend-isolated.xml), [log lần đầu](../../ocr_phase10_integration/postmerge_20261120/backend-tests.log), [log cô lập](../../ocr_phase10_integration/postmerge_20261120/backend-isolated.log), [Web tests](../../ocr_phase10_integration/postmerge_20261120/web-tests.log), [build](../../ocr_phase10_integration/postmerge_20261120/build.log).

## 4. Runtime Website thực tế

- Website: **htt<LOCAL_PATH>
- Backend: **htt<LOCAL_PATH>
- `APP_ENV=testing`, `OCR_PIPELINE=hybrid_v7`, `OCR_HYBRID_FALLBACK=true`.
- `current_database()` chạy chỉ đọc **trong cùng process ứng dụng** xác nhận `fintech_ocr_rbac_test`; Settings và engine dùng cùng object. Upload path tuyệt đối `FINTECH_OCR_GitHub/backend/uploads_rbac_test`.
- Đối chiếu PID attestation với listener, hash module app/runtime/V7, health và JavaScript `api.js` do Vite phục vụ: frontend trỏ `htt<LOCAL_PATH>`. Không chỉ dùng `/health` làm bằng chứng DB/engine. Không sửa `.env`, CORS hoặc cổng.
- Port 8000/5173 trống trước khi khởi động. Không dừng process không rõ nguồn. Khi restart test đã kiểm PID/source/DB và **0 kết nối API Established** sau khi các browser test đóng.

[RUNNING_SERVICES.json](../../ocr_phase10_integration/postmerge_20261120/uat/RUNNING_SERVICES.json), [RUNTIME_8000.json](../../ocr_phase10_integration/postmerge_20261120/uat/RUNTIME_8000.json).

## 5. Browser UAT và PostgreSQL

Computer Use native pipe không khả dụng; dùng Chromium local thật bằng Playwright đã có. Web/React thật, HTTP/Uvicorn thật, PostgreSQL thật, Tesseract thật; **không mock response OCR/API**. Fault injection được tách riêng và công bố bên dưới. Không lưu mật khẩu/JWT, storage state hoặc network trace chứa Authorization. Ảnh chụp và JSON nghiệp vụ lưu cục bộ; các font ngoài bị chặn trong browser QA, không đổi source giao diện.

| Nguồn | Loại dữ liệu | Invoice mới | HTTP / thời gian trọn request | Hàng |
|---|---|---:|---|---:|
| RVQA_00000505.jpg, ảnh #25 cũ | Bill thật, development đã biết | **32** | 201 / **11,066 s** | 1 |
| RVQA_00000022.jpg, ảnh #26 cũ | Bill siêu thị thật, development | **33** | 201 / **12,662 s** | 2 |
| RVQA_00001100.jpg, ảnh #28 cũ | Bill ANAN thật, development | **34** | 201 / **17,836 s** | 6 |
| continuation.pdf | **Synthetic**, PDF text 2 trang | **35** | 201 / **0,500 s** | 3 |
| bilingual.pdf | **Synthetic**, PDF scan Việt–Anh 1 trang | **36** | 201 / **3,336 s** | 1 |

Ba ảnh thật là cùng các mẫu G8/G9, không phải held-out mới. Hai PDF đã được render/đọc trực tiếp để đối chiếu, không gọi là hóa đơn VAT thật. Không lấy các ảnh/PDF hoặc labels có sẵn làm output OCR. V6 chạy thật bên trong bước baseline của V7, output trước nâng cấp được lưu trong `evidence.v6_fallback`; so sánh cùng bytes/cùng run, không upload thêm một loạt V6 hoặc sửa kết quả cũ.

| Luồng/tiêu chí | Actual result | Trạng thái |
|---|---|---|
| Đăng nhập Employee/Accountant/Admin | Form Web thật, API 200, role đúng | PASS |
| Chọn file → queue → upload | Năm request 201, invoice mới, queue hiển thị đúng file | PASS thực thi |
| V7 thực sự chạy | #32–36 method `hybrid-v7`, used_pipeline `hybrid_v7`, fallback false, raw/boxes/evidence trong DB | PASS |
| Original document | Ảnh/PDF hiển thị, tải có auth, checksum khớp | PASS |
| API → UI và F5 | Mọi field/input và năm ô từng item khớp API, null không thành 0 | PASS mapping |
| Sửa tay #32 | Chỉ sửa seller và mô tả theo ảnh; PUT 200; hai correction old/new/actor/time, validation chạy vòng 2 | PASS |
| Độc lập trạng thái khi sửa | #32 vẫn draft/not_applicable lúc save; extraction gốc không bị ghi đè | PASS |
| Employee submit #33 → Accountant approve | Web/API 200; #33 approved, Lookup vẫn not_applicable, Validation không tự valid | PASS workflow test |
| Employee submit #32 → Admin reject | Web/API 200, lý do rõ; Employee F5 thấy rejected và lý do | PASS workflow test |
| RBAC | Employee approve/lookup 403, sửa approved 400; Accountant edit 403 đúng quyền; invoice/file người khác 404 | PASS |
| API smoke và chức năng mới develop | 33 kiểm tra login/GET/RBAC; Profile/Schedule/Report/Ranking/Notifications/directory/audit/search | PASS đúng phạm vi đã chạy |
| UI smoke bổ sung | 10 case hiện hành PASS: Admin profile/users/audit/search, tải XLSX, Employee Schedule/Ranking/Notifications/Chat/rejection | PASS render/thao tác nêu trên |
| Restart Backend | Năm invoice giữ fields/items, correction và trạng thái; file/raw không mất | PASS |
| Tra cứu thuế thật hợp lệ | Không có VAT thật/đối chiếu chính thức; PDF synthetic không được gán verified | **BLOCKED** |
| CRUD Profile/Avatar/Schedule/User toàn diện trên browser | Chỉ read/render regression và unit/API tests, không thao tác toàn bộ form thật | **NOT TESTED** trong phạm vi Browser UAT này |
| Hóa đơn thật độc lập/VAT thật mới | Không có mẫu/nhãn phù hợp; không dùng bộ 24 Phase7 thay thế | **NOT TESTED** |

Một lượt QA Schedule chờ nhầm tiêu đề `Lịch công tác`; source Employee dùng `Lịch công tác của tôi`. Đã sửa selector **chỉ trong script QA**, giữ lỗi lịch sử và retest PASS; không sửa sản phẩm hoặc xóa assertion.

XLSX tải qua giao diện khớp **toàn bộ bytes** artifact Report #12 trong PostgreSQL test (metadata row_count=37 tại thời điểm export), các report cũ không đổi. Đây là kiểm tra tải/lưu artifact, không thay một cuộc đối soát kế toán toàn diện. [EXPORT_ARTIFACT_CHECK.json](../../ocr_phase10_integration/postmerge_20261120/uat/EXPORT_ARTIFACT_CHECK.json).

## 6. Đối chiếu OCR từng chứng từ, trước sửa tay

| Invoice | Fields và tài chính thực tế | Sai/thiếu và dòng hàng |
|---:|---|---|
| 32 | bill; số `SON45644`; ngày **2020-08-12**; seller `CUA HANG NAM OÁNH`; subtotal 53000; total/VAT/MST/buyer null | Số ảnh có đuôi **55644**; O/0 ở prefix cần người đọc chốt, nhưng sai đuôi là rõ. Seller/mô tả mất dấu. 1 hàng `Phở bò Dé Nhat 65g`, SL 10, giá 5300, amount 53000. Unit không in giữ null. Không suy total từ Cộng tiền hàng. |
| 33 | bill; số **00064574**, ngày **2020-08-15**, seller VinCommerce theo logo; total **95800** | Hai hàng số đúng: 2×37900=75800 và 2×10000=20000. Mô tả còn lỗi dấu/chữ/`500m]`; khoản -31000 không còn lẫn vào mô tả. VAT/MST/subtotal không in rõ giữ null. Không tự trừ lại KM khi tổng in khác phạm vi. |
| 34 | bill, MINIMART ANAN, ngày **2020-08-13**, total **116000**; invoice number null vì chỉ có Số GD | 6/6 vùng hàng nhưng row 2 quantity=null, amount **40000** thay **10000**; unit GOT/null/CAT còn sai. Tổng amount **146000**. Không tự chia tổng hoặc dựng giá trị. ITEM-SUM vẫn không đạt, không nới validation. |
| 35 | einvoice; **RC-36125**, 2026-09-07, MST **3803901266**, subtotal **436000**, rate **10**, VAT **43600**, total **479600** | Seller **null** dù PDF text in Supplier: Ridge Control Works; lỗi parser/ngữ cảnh, không phải API mất field. Đủ 3 hàng, số/đơn vị pc đúng. V7 kéo `for nitrogen circuit` từ hàng 1 sang mô tả hàng 2; STT lẫn tên. |
| 36 | einvoice; **0007941**, 2026-10-21; Công ty Vật tư Hạ Lam / MST **2007645239**; Trung tâm Minh Hà / MST **4201432168**; subtotal **210000**, rate **10**, VAT **21000**, total **231000** | 1 hàng Cái / 2 / 105000 / 210000 đúng. Tên bị thêm STT `1 Hiệu chuẩn thiết bị D46`; V6 không có STT này. Chưa đúng toàn dòng strict. |

Invoice symbol không xuất hiện trong các mẫu; không tự điền. Currency API là VND ở cả năm trường hợp theo hệ thống, không coi default currency là OCR đọc được ký hiệu tiền không in. Trường thực sự không có trên nguồn được ghi absent/N/A, không coi là thiếu OCR. Supplier logo của #33 chỉ chứng minh tên thương hiệu, không tự suy pháp nhân/MST.

**Lỗi hồi quy PDF V7:** V6 đã ghép phần `for nitrogen circuit` vào hàng 1; V7 chuyển sang hàng 2. PDF scan V6 không có STT trong tên nhưng V7 thêm. Đây là lỗi thuật toán bảng, không sửa tùy tiện trong UAT hoặc che bằng UI. Chưa triển khai V8/G11.

## 7. Số liệu chẩn đoán — không phải nghiệm thu độc lập

Đối chiếu **output OCR gốc trong ExtractionRun**, không dùng Invoice đã correction, với bản đọc ảnh/PDF AI riêng `uat_visual_reference.json`. Không sửa bất kỳ `ground_truth.json` nào hoặc tự xác minh A/B. Số liệu này là **provisional development diagnostics**, không chứng minh NFR01 hoặc độ chính xác trên hóa đơn mới.

- Field accuracy = số field hiện diện khớp / số field hiện diện được đối chiếu. NFC + casefold + gom khoảng trắng; giữ dấu/chữ số/model. Retail number FAIL dựa trên đuôi sai rõ, không chốt O/0 thay người kiểm thử.
- Cell accuracy = ô khớp / ô có giá trị nguồn rõ. Hai mô tả viết tắt của ANAN còn nghi vấn không chấm; unit absent không được tự suy. Đối chiếu theo thứ tự hàng in, báo riêng thiếu/thừa hàng.
- Exact row = toàn bộ ô được xác minh của hàng khớp; **hai hàng partial không tính vào mẫu số exact row**. Row count đúng không đồng nghĩa exact row đúng.
- Trường absent được kiểm riêng về không bịa giá trị, không cộng vào field accuracy. Subtotal #32 có giá trị tiền hàng nhưng chưa chứng minh trước VAT, không chấm scope này là đúng; không cộng null để nâng điểm.

| Nhóm | Chỉ số | V6 baseline thật | V7 |
|---|---|---:|---:|
| 3 bill thật development | Field accuracy | 10/13 = 76,92% | **11/13 = 84,62%** |
| 3 bill thật development | Ô dòng hàng | 22/40 = 55,00% | **31/40 = 77,50%** |
| 3 bill thật development | Exact row đủ nhãn | 0/7 | **2/7**; 2 hàng partial không chấm exact |
| 3 bill thật development | Đúng số hàng từng chứng từ | 2/3 | **3/3**; tổng 9 hàng, không có nghĩa 9/9 exact |
| 3 bill thật development | Loại / ngày / seller / số HĐ / payable | 3/3; 2/3; 2/3; 1/2; 2/2 | **3/3; 3/3; 2/3; 1/2; 2/2** |
| 2 PDF synthetic | Field accuracy | 19/20 = 95,00% | **19/20 = 95,00%** |
| 2 PDF synthetic | Ô dòng hàng | 17/20 = 85,00% | **16/20 = 80,00% — hồi quy** |
| 2 PDF synthetic | Exact row | 1/4 | **0/4 — hồi quy** |
| 2 PDF synthetic | Đúng số hàng / loại / payable | 2/2; 2/2; 2/2 | **2/2; 2/2; 2/2** |

V7 thiếu **1/33 field hiện diện** được đối chiếu (seller PDF text), **2/40 ô** trên bill thật (unit hàng 1 và quantity hàng 2 ANAN); PDF 0/20 ô bị null nhưng có mô tả sai. Buyer/MST/VAT dương có bằng chứng synthetic, **chưa có bằng chứng VAT thật mới**. Chi tiết từng field/từng ô, absent và row arithmetic nằm ở [OCR_DIAGNOSTICS.json](../../ocr_phase10_integration/postmerge_20261120/uat/OCR_DIAGNOSTICS.json).

Thời gian HTTP V7 năm lượt: 11,066 / 12,662 / 17,836 / 0,500 / 3,336 s; trung bình **9,080 s** gồm Web/API/OCR/DB, không phải benchmark engine độc lập. Năm nguồn bình thường fallback **0/5**. Ba fault kiểm soát fallback **3/3**; không trộn các ca ép lỗi vào tỷ lệ tự nhiên. Hai tệp hỏng không thể OCR và một bad magic bị từ chối báo riêng.

Không báo CER/WER vì chưa có transcription con người xác minh. Cỡ mẫu 3 bill thật đã dùng development + 2 synthetic **không đủ 100–500 hóa đơn và quy trình độc lập NFR01**. Không thay ngưỡng sau khi thấy điểm.

## 8. Fallback, lỗi đầu vào và rollback

| Ca | Bằng chứng HTTP/Web/DB | Trạng thái |
|---|---|---|
| Engine fault tại `_run_hybrid_v7` process 8011 | Invoice **37**, HTTP 201, `image-ocr`, used current, raw thật, banner fallback | PASS cơ chế; OCR current không trích đủ, **FAIL chất lượng** |
| Timeout báo lỗi có kiểm soát | Invoice **38**, cùng đường fallback current thật | PASS cơ chế; không phải phép đo timeout tự nhiên |
| Output không hợp lệ (NaN) | Invoice **39**, mapping từ chối dữ liệu rồi chạy current thật | PASS cơ chế; không lưu NaN |
| PNG magic đúng nhưng nội dung không đọc được | Invoice **40**, run failed, validation error, file giữ lại, queue failed | PASS xử lý lỗi; **không gọi OCR thành công** |
| PDF magic đúng nhưng tài liệu hỏng | Invoice **41**, run failed/queue failed, file giữ lại | PASS xử lý lỗi; fallback không thể phục hồi tệp hỏng |
| PDF sai magic | HTTP **400**, không tạo invoice/file mới | PASS từ chối đầu vào |
| Khởi động rollback current/V6 | Process test phụ 8012/8013 attested DB test, health 200 | PASS startup/HTTP; không upload thêm ở hai mode này |
| Restart V7 cổng 8000 | DB/file/correction/approval/lookup giữ đúng trên Web | PASS |

Fault chỉ tiêm trong bộ nhớ process phụ tại runtime bridge; không sửa frozen engine/parser hay mock API response. Không giả việc đọc được text là extract đúng. Đã dừng đúng PID mọi process phụ 8011/8012/8013 sau khi hoàn tất; giữ V7 8000 và Vite 5173. [ROLLBACK_SMOKE.json](../../ocr_phase10_integration/postmerge_20261120/uat/ROLLBACK_SMOKE.json), [RESTART_BROWSER.json](../../ocr_phase10_integration/postmerge_20261120/uat/RESTART_BROWSER.json), `BROWSER_FAULT_*.json`, `NEGATIVE_UAT.json`.

## 9. Bảo toàn dữ liệu và giới hạn

Sau UAT: **41 invoices, 41 files, 30 items, 41 extraction_runs, 39 corrections, 384 validation_results, 89 notifications, 157 audit_logs, 18 schedules**. Chỉ thêm #32–41; #32 có hai correction, #32 rejected và #33 approved do các bước UAT được yêu cầu. Không sửa #1–31, đặc biệt #12/#25–28. Hash **703 bản ghi nghiệp vụ trước UAT không đổi**; checksum các file mới khớp. Auth cập nhật last_login theo đăng nhập test; không đổi mật khẩu, role hoặc tài khoản. Report export tạo artifact/history mới đúng API develop. Không truy cập DB chính.

Tra cứu thuế thực tế **BLOCKED** do thiếu chứng từ VAT thật/đối chiếu hợp lệ; synthetic không được marked verified. Kết quả kiểm thử quyền cấm Lookup và không tự thay Lookup khi edit/approve/reject là PASS. Chưa có UAT CRUD toàn diện mọi chức năng mới develop; không lấy GET/render smoke thay sign-off của nhóm.

Chưa nghiệm thu OCR độc lập, ảnh khó mới, VAT thật, PDF thật nhiều trang hoặc unknown hợp lệ mới. Bộ 24 Phase7 vẫn tạm dừng, không gọi người dùng làm A/B trong lượt này, không benchmark lại.

## 10. File thay đổi và cách vận hành

**Trong repo:** chỉ tạo báo cáo này và `docs/OCR_PHASE10_CHECKPOINT.md`. Không sửa Backend/Frontend/algorithm/test sản phẩm. Build tạo output ignored như bình thường.

**Ngoài repo:** cập nhật `ocr_phase10_integration/preflight.py`, `serve_test.py`; thêm `browser_uat.cjs`, `browser_regression.cjs`, `negative_uat.cjs`, `readback_after_restart.cjs`, `postcheck.py`, `evaluate_uat.py`, `uat_visual_reference.json`, `STATUS.md`. Script QA được sửa selector Schedule theo role; không thay app. Hồ sơ mới trong `postmerge_20261120/`, giữ hồ sơ trước merge ở gốc.

Website đang chạy, **không khởi động thêm process trùng cổng**. Khi cần khởi động lại từ terminal Windows sau khi dừng đúng dịch vụ test và bảo đảm không còn upload:

```powershell
Set-Location '<LOCAL_PATH>
$env:PHASE10_EVIDENCE_DIR='<LOCAL_PATH>
.\.venv\Scripts\python.exe -X utf8 '<LOCAL_PATH>
```

Wrapper ép DB test/upload test/testing trước import ứng dụng, xác minh backup/hash/schema; dừng khi guard không đạt. **Không chạy wrapper với hồ sơ gốc trước merge**; dùng biến `PHASE10_EVIDENCE_DIR` như trên. Muốn rollback, dùng `--pipeline hybrid_v6` hoặc `--pipeline current` sau khi dừng đúng process test. Đây là cấu hình runtime, không ghi `.env` hoặc đổi default source.

Web trong terminal khác, chỉ khi 5173 trống:

```powershell
Set-Location '<LOCAL_PATH>
$env:VITE_API_URL='htt<LOCAL_PATH>
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Nếu code/config hoặc DB thay đổi sau checkpoint này, chuẩn bị backup/preflight mới; không bỏ qua hash/schema guard.

## 11. Bằng chứng và điểm dừng

[FINAL_VERIFICATION.json](../../ocr_phase10_integration/postmerge_20261120/FINAL_VERIFICATION.json), [BROWSER_UAT.json](../../ocr_phase10_integration/postmerge_20261120/uat/BROWSER_UAT.json), [BROWSER_REGRESSION.json](../../ocr_phase10_integration/postmerge_20261120/uat/BROWSER_REGRESSION.json), [DB_AFTER_RESTART.json](../../ocr_phase10_integration/postmerge_20261120/uat/DB_AFTER_RESTART.json). Ảnh `retail_detail.png`, `units_detail.png`, `pdf_text_detail.png`, `pdf_scan_detail.png`, `retail_corrected.png`, `accountant_approval.png`, `admin_reject.png`, `admin_search.png`, `fallback_engine_37.png`, `fallback_timeout_38.png`, `fallback_invalid-output_39.png` ở cùng thư mục UAT.

**Chốt G10 tại UAT đã thực hiện; Task 2 chưa đạt nghiệm thu.** Việc tiếp theo được đề xuất, chưa triển khai: sửa tổng quát việc tách STT và ghép multiline/cột trên PDF; cải thiện đọc ô tiền/quantity/unit và số/dấu trên bill; phân biệt rõ thiếu subtotal với sai số học theo quyết định nghiệp vụ; chuẩn bị VAT/PDF thật và tập nhãn độc lập. Không sửa V7 tùy tiện hoặc triển khai V8/G11 trong lượt này. Chờ người dùng quyết định bước tiếp theo. Không git add/commit/push/pull/merge/reset/chuyển nhánh hoặc xóa stash.
