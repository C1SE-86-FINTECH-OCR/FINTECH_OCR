# Checkpoint Giai đoạn 12 — Nghiệm thu độc lập V8

Ngày 20/11/2026. **Trường hợp D: BLOCKED nghiệm thu vì thiếu dữ liệu thật độc lập, nhãn A/B và tiêu chí đủ. Task 2 chưa ACCEPTED; chưa chuyển G13.** Các kiểm tra không phụ thuộc dữ liệu thiếu đã thực hiện; dừng tại checkpoint này.

## Đã thực hiện

- Đọc hồ sơ G11/G10/G9/G7/G3.5, mã và bằng chứng liên quan. Git chỉ đọc; nhánh `feature/thien`, ba stash giữ nguyên. Không add, commit, push, pull, merge, reset hoặc chuyển nhánh.
- Khóa 141 file source, test, ground truth, manifest và `.env` trước/sau: không đổi. Current, V6, V7, V8 nguyên thuật toán; không V9, không đổi API, Website, Mobile, schema hoặc validation.
- Kiểm kê 476 đường dẫn ảnh/PDF/XML, 332 hash byte và 84 nhóm trùng byte. Bao gồm screenshot, fixture, asset và cache, **không phải 332 hóa đơn thật**. dHash kiểm 147 ảnh nguồn, báo ba cặp; đã mở trực tiếp sáu ảnh để phân biệt cùng nguồn và giống bố cục. Giữ PNG lỗi cũ ID40 có checksum đúng. Độc lập theo PDF crop/nhà cung cấp/mẫu vẫn cần con người.
- G7 giữ 24 draft, 0 approved, 0 hồ sơ A/B; G3.5 có 10 draft đã dùng phát triển. Không benchmark lại G7, không sửa nhãn. Intake G12 mới có 0 nguồn/0 nhãn đủ điều kiện.
- Readiness gate chạy thật: BLOCKED, exit2 đúng dự kiến; không inference, freeze hoặc phê duyệt giả.
- Backend **412 PASS, 0 FAIL, 0 SKIP, 71.32s**; Web **36 PASS**; build **PASS, 9.05s**. Giữ cảnh báo chunk>500kB và 27 warning thư viện. Tests dùng SQLite/thư mục tạm mới, không xóa DB test cũ.
- Docker/PostgreSQL Healthy, schema test đủ cột/UTF8, 47 file khớp SHA. Tạo backup test mới, pg_restore --list exit0.
- Khởi động Backend/Vite trên cổng 8000/5173 đang trống, không dừng process khác. Runtime kiểm DB test trong cùng process, không chỉ dựa /health.
- Browser Chromium local thật: **36/36 kiểm tra login+GET PASS**, 0 lỗi JavaScript. Ba vai trò; quyền đọc/deny đúng; UI #44 có sáu dòng và banner V8; file auth checksum/F5 đúng; #42 còn hai correction. Kỳ vọng QA ban đầu Accountant được xem Audit Logs bị sai; sửa theo SRS Admin-only thành403, không sửa sản phẩm.
- Không upload, edit, submit, approve/reject, lookup hoặc tạo user trong Browser G12; chặn mọi API mutation trừ login. Không có invoice G12 mới, #1–47 nguyên trạng.

## Bảo toàn dữ liệu

DB test vẫn 20 bảng/1069 hàng, không thêm/xóa. **1058 hàng ngoài users giữ nguyên hash**, 47 file giữ checksum. Bảng users có11 hàng: chỉ ba tài khoản đã đăng nhập thay `last_login_at` và `updated_at` theo onupdate; tám user khác nguyên trạng. Mọi cột users ngoài hai timestamp được so strict với backup.

Không gọi đây là “toàn bộ DB không đổi”. Hậu kiểm chỉ dùng pg_restore xuất SQL trong bộ nhớ để so backup, **không restore vào DB**, không lộ mật khẩu/hash/JWT và không cập nhật dữ liệu để giấu tác động login.

Backup: `<LOCAL_PATH>`

- **1,203,995 bytes**, list exit0.
- SHA-256 `336f5bbf17ae17178b081fad22658997bcb65e269f3e92bcd9e62c26965810f1`.

## Runtime lúc bàn giao

- Backend8000 PID **11976**; Vite5173 PID **13756**, theo snapshot đã kiểm.
- `APP_ENV=testing`, database `fintech_ocr_rbac_test`.
- Upload: `<LOCAL_PATH>`.
- `OCR_PIPELINE=hybrid_v8`, `OCR_HYBRID_FALLBACK=true`; source/default và `.env` vẫn giữ current.
- Website htt<LOCAL_PATH>
- Đây là môi trường test, không là OCR nghiệm thu PASS. Metadata cũ trên hóa đơn không chứng minh có inference mới trong G12.
- Helper G12 `ocr_phase12_acceptance/restart_test.ps1 -Pipeline current` hoặc `hybrid_v6`, `hybrid_v7`, `hybrid_v8` kiểm guard/PID/idle/backup trước khi dừng process test. Chỉ kiểm cú pháp helper, chưa chạy switch mọi mode trong G12; V8 startup đã chạy thật. Không dùng helper G11 với PID cũ.

## Còn thiếu

| Hạng mục | Trạng thái |
|---|---|
| Accuracy độc lập bốn pipeline và tính chính xác tài chính | BLOCKED: 0 chứng từ/nhãn mới đủ điều kiện |
| UAT upload, correction, workflow, restart và fallback trên nguồn mới | BLOCKED; kết quả G10–11 chỉ là lịch sử |
| CRUD user/role trên Browser G12 | NOT TESTED; không sửa tài khoản cũ để thử |
| Tax Lookup thật | BLOCKED; không tạo verified giả |
| Latency/RAM/CPU/timeout/fallback độc lập mới | NOT TESTED; G11 chỉ được tổng hợp lại từ dữ liệu cũ |
| CER/WER, geometric row detection, discount đa dạng | NOT TESTED; thiếu nhãn và quy tắc đã chốt |
| NFR01, UAT sign-off, Task 2 ACCEPTED, G13 | BLOCKED |

Cần người dùng/PO cung cấp hóa đơn thật mới được phép dùng và hồ sơ A/B trước prediction, đủ nhóm VAT, bill không MST/VAT, nhà hàng, siêu thị, nhiều mặt hàng, PDF text/scan/multipage, ảnh khó và discount. Khoảng thiếu G7: ít nhất4 VAT thật,3 PDF,2 chứng từ nhiều trang; các nhóm có thể chồng lấp. Không lấy synthetic thay thế.

Pilot G12 đề xuất30–50 không thay NFR01 >=85% trên100–500 hóa đơn. Cần chốt weighting, ngưỡng dòng hàng/tài chính/latency trước inference. Không dùng tập nghiệm thu để chỉnh thuật toán sau đo.

Thư mục nhận file gốc:
`<LOCAL_PATH>`

[Hướng dẫn thêm file, manifest, ground truth và A/B](../../ocr_phase12_acceptance/INTAKE_AND_VERIFICATION_GUIDE.md). CSV hiện chỉ có header và ground truth rỗng; có schema phân biệt present/absent/illegible/N/A, không có nhãn giả.

## Tài liệu và bằng chứng

- [Báo cáo nghiệm thu hiện tại](OCR_PHASE12_INDEPENDENT_ACCEPTANCE.md).
- [Benchmark/phương pháp và thống kê lịch sử G11](OCR_PHASE12_BENCHMARK_RESULTS.md).
- [Evidence G12](../../ocr_phase12_acceptance/): source/engine lock, inventory/dedup/readiness/criteria, JUnit/test/build logs, intake/guide và helpers.
- [Browser mới](../../ocr_phase12_acceptance/uat/BROWSER_READONLY.json), [hậu kiểm DB](../../ocr_phase12_acceptance/uat/DB_FINAL_CHECK.json), [runtime](../../ocr_phase12_acceptance/uat/LIVE_SERVICES.json).

Trong repository chỉ thêm ba file Markdown G12; giữ toàn bộ source và thay đổi cũ. Dừng, chưa triển khai G13. Chờ người dùng quyết định sau khi đủ dữ liệu và tiêu chí.
