# Giai đoạn 8 — Website thử nghiệm đã khởi động

> **Cập nhật sau khởi động:** đã chạy [Web UAT với ba bill thật](OCR_PHASE8_WEB_UAT.md), tạo #25/#26/#28 bằng Hybrid và #27 kiểm tra fallback. Luồng lưu/hiển thị/sửa hoạt động, OCR còn lỗi; DB test hiện 28 invoices/18 schedules/69 notifications. Các dòng NOT TESTED đăng nhập/upload và counts 24/18/65 bên dưới là lịch sử tại thời điểm khởi động. Chưa nghiệm thu chất lượng.

Ngày 19/11/2026. **Môi trường test đã chạy; chưa nghiệm thu OCR hoặc hoàn thành Browser UAT.**

## Địa chỉ và cấu hình runtime đã xác minh

- Website: **htt<LOCAL_PATH>
- Backend: htt<LOCAL_PATH>`/health` HTTP 200, `mode=testing`.
- Repository thực sự phục vụ: `<LOCAL_PATH>`, nhánh feature/thien. Không phải starter.
- Backend listener PID **16864**, Web listener PID **3040** tại thời điểm kiểm tra; PID có thể đổi khi người dùng khởi động lại.
- `APP_ENV=testing`, DB **fintech_ocr_rbac_test**, `OCR_PIPELINE=hybrid_v6`, `OCR_HYBRID_FALLBACK=true`, max pages 12.
- Upload: **<LOCAL_PATH>
- Vite thực sự phục vụ `api.js` có API URL `htt<LOCAL_PATH>`, App import InvoiceDetailPage hiện tại và module OCR UI có Hybrid/failure handling. Không chỉ kiểm HTTP 200 hoặc build.

`phase8_runtime.py` chạy trong cùng PID Uvicorn: đổi duy nhất tên DB sang test trước khi import app/core, kiểm tra backup SHA, Settings, `engine.url`, `current_database()` trong transaction chỉ đọc, schema hiện có và đúng upload path. Engine của app được đối chiếu cùng instance với core. PID ghi bằng chứng khớp tiến trình chiếm 8000. Do đó kết luận isolation không dựa chỉ vào `/health` hoặc `.env`.

## Docker và PostgreSQL

Docker Desktop có process hoạt động. CLI trong sandbox chạy bằng `CodexSandboxOffline`, bị chặn đọc `<LOCAL_PATH>` và named pipe Docker. Truy cập từ ngữ cảnh người dùng Windows bên ngoài sandbox, kèm Docker CLI config riêng tại `ocr_phase8_integration/docker_client`, đã thành công. **Không sửa ACL, nhóm docker-users, Docker Desktop, container hoặc Docker config người dùng.** Không cần người dùng cấp lại quyền trong lượt này.

Engine 29.4.0 / Docker Desktop 4.69.0. Container `fintech_ocr_postgres` healthy, publish 5432. PostgreSQL **17.11**. Chỉ kết nối DB test; không mở DB `fintech_ocr` để kiểm thử. Schema hiện có khớp toàn bộ các cột ORM cần dùng; không DDL/migration/seed/restore hoặc tạo lại database.

DB test hiện có **24 invoices, 18 schedules, 65 notifications**. Các số lượng sau khởi động và kiểm tra chỉ đọc vẫn giữ nguyên. Có tài khoản active cho cả Employee/Accountant/Admin, không tạo/sửa mật khẩu hoặc tài khoản. Các danh tính/tài khoản disabled không thay đổi.

## Backup và tệp upload

Backup mới: `<LOCAL_PATH>`.

- Dung lượng **83.910 byte**.
- `pg_dump -Fc` hoàn tất; `pg_restore --list` trong container thành công, exit 0, 192 dòng danh mục.
- SHA-256 Windows: `f158e46c38ccdd44441c5e1b166722f8f092b1408e0d1b08da8c0b42c2e5f783`.
- Launcher đối chiếu lại kích thước/hash backup trước khi mở test app; không restore backup.

Thư mục upload test tại repo chưa có trước lượt. Đã tạo đúng đường dẫn riêng và sao chép **24/24 file** được DB test tham chiếu từ các thư mục upload sẵn có. Mỗi file chỉ được copy khi SHA-256 khớp checksum DB; không ghi đè, không sửa file nguồn, không tạo nội dung giả và không UPDATE DB. [UPLOAD_DIRECTORY_CHECK.json](../../ocr_phase8_integration/UPLOAD_DIRECTORY_CHECK.json) lưu đối chiếu nội bộ. Không công khai file chứng từ hoặc log chứa dữ liệu cá nhân.

## Kết quả kiểm tra thực tế

| Kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| Docker/container/PG test | PASS | Ngữ cảnh Windows, không sửa quyền hệ thống |
| Backup mới và khả năng đọc | PASS | Dump DB test, TOC + SHA Windows |
| Runtime isolation | PASS | In-process Settings/engine/SQL/schema/backup/upload + PID listener |
| File upload cũ của DB test | PASS | 24/24 checksum, chỉ copy vào upload test |
| Backend health | PASS | HTTP 200 / testing |
| Web → Backend, CORS | PASS | Browser thật fetch health từ origin 127.0.0.1:5173 |
| Vite phục vụ đúng source/API URL | PASS | Nội dung JS thực tế, không dựa build đơn thuần |
| Form đăng nhập Web hiển thị | PASS | Chromium local, không lỗi JS; ảnh `live-login.png` |
| Đăng nhập, upload mới, OCR, sửa/lưu | NOT TESTED trong lượt này | Không thực hiện request ghi |
| Browser UAT nghiệp vụ/accuracy | NOT TESTED | Không thay bằng kết quả smoke hoặc tests cũ |
| Chuyển pipeline bằng script | NOT TESTED thực thi | Chỉ kiểm cú pháp/guard; đang giữ Hybrid bật |

Kiểm tra browser dùng profile mới, chỉ mở giao diện và GET health. Chặn tải font bên ngoài trong phiên QA; không sửa source/config font. Backend 325 PASS, Frontend 25 PASS và build PASS là bằng chứng của lượt code trước, không chạy lại vì lượt này không đổi code sản phẩm.

## Sử dụng và chuyển lại pipeline cũ

Mở Website trên Windows, đăng nhập **tài khoản test có sẵn**, chọn chứng từ mới được phép dùng. Mở detail để đối chiếu nhãn Hybrid/fallback, số/ngày/người bán/MST/tổng/VAT, dòng hàng/đơn vị/lượng/giá. Giữ dữ liệu cũ để so sánh, không xử lý lại invoice cũ nhằm biến thành kết quả PASS. Backup test đã có ở mốc trước upload; tạo backup mới trước các lượt ghi tiếp theo theo quy trình nhóm. Không coi login hay HTTP 201 là OCR accuracy.

Hai dịch vụ đã chạy nền với cửa sổ ẩn; không cần chạy thêm Vite/Uvicorn lên cùng cổng. Log ở `ocr_phase8_integration/backend-runtime.*.log` và `web-runtime.*.log`. Không chia sẻ toàn bộ log nếu chứa dữ liệu chứng từ hoặc thông tin xác thực.

**Chỉ khi không còn upload/request test đang xử lý**, chuyển lại OCR cũ trong PowerShell Windows bằng tài khoản đang chạy dịch vụ:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<LOCAL_PATH>" -Pipeline current
```

Script preflight test trước, kiểm PID/command launcher/cổng/DB, chỉ dừng đúng Backend test của lượt này rồi khởi động lại bằng `--pipeline current`. Nếu guard không đạt, không dừng process. Script không dừng Web hay service khác; không chỉnh .env/database. ExecutionPolicy chỉ áp dụng cho process PowerShell này, không thay policy máy. Kiểm tra `/health` và `BACKEND_RUNTIME.json` mới sau khi chạy; health testing một mình không cho biết engine.

Muốn bật lại Hybrid, cùng lệnh với `-Pipeline hybrid_v6`. Dữ liệu hóa đơn cũ vẫn giữ nguyên engine/kết quả tại lúc tạo, không tự OCR lại. Việc chuyển chỉ ảnh hưởng upload tiếp theo. Đây là hướng dẫn, **chưa chạy thao tác chuyển mode** trong lượt này.

## Bằng chứng và việc còn lại

[BACKEND_RUNTIME.json](../../ocr_phase8_integration/BACKEND_RUNTIME.json), [RUNNING_SERVICES.json](../../ocr_phase8_integration/RUNNING_SERVICES.json), [RUNTIME_BACKUP.json](../../ocr_phase8_integration/RUNTIME_BACKUP.json), [LIVE_BROWSER_STARTUP.json](../../ocr_phase8_integration/LIVE_BROWSER_STARTUP.json) và checkpoint ngoài repo `ocr_phase8_integration/STATUS.md`.

Tiếp theo là người dùng đăng nhập và upload chứng từ mới qua Website, kiểm tra extraction/validation/edit/readback/fallback trên DB test. Chưa có phép đo accuracy hóa đơn thực hoặc nghiệm thu. Giai đoạn 7 vẫn tạm dừng: A/B, bổ sung chứng từ, freeze/benchmark chưa hoàn thành, GT giữ 24 draft/0 approved. Không benchmark, không sửa ground truth, không commit/push/pull/merge.
