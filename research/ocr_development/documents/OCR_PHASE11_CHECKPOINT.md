# Checkpoint Giai đoạn 11 — Hybrid V8

Ngày 20/11/2026. **G11 triển khai/kiểm thử đã chốt; OCR CHƯA NGHIỆM THU. DỪNG, chờ chỉ đạo G12.**

Repository `<LOCAL_PATH>`, nhánh `feature/thien`. Giữ dirty changes cũ; không commit/push/pull/merge/reset/add/chuyển nhánh, không xóa stash. Không sửa main DB, ground truth, current extraction, V6 frozen hoặc V7 baseline.

## Kết quả đã có bằng chứng

- 4 module V8 riêng, bridge opt-in testing, mapping cột sẵn có, banner metadata thực; current vẫn mặc định.
- Backend **412 PASS /0FAIL/0SKIP**, Web **36 PASS**, build **PASS**; 35 Backend +1 Web mới. Bài full dùng working directory tạm mới, không sửa DB/schema test cũ. 27 warning thư viện và chunk>500kB giữ nguyên.
- Benchmark32 lượt/8 nguồn khác SHA: 3 JPEG thật **development**, 5 synthetic hồi quy; không benchmark G7, không đổi nhãn.
- V7→V8 real: field11/13 giữ, ô normalized31/40→35/40, dòng normalized2/7→4/7; raw exact đơn vị bị khác do canonical hóa, báo riêng. Synthetic: field39/42→41/42, ô32/45→44/45, dòng0/11→10/11. Real V8 mean13.507s vsV7 9.985s: chưa cải thiện tốc độ.
- Browser Chromium local thật→Uvicorn→Tesseract→PostgreSQL test→UI: #42–46 HTTP201, mapping/F5/restart PASS; #42 correction2 bản ghi giữ extraction gốc; #47 fallback engine→current thực và banner PASS cơ chế. Các tài khoản/quyền read/deny kiểm tra15/15 PASS. Không gọi đây là nghiệm thu accuracy.
- ANAN#44 có6 dòng, q/p/amount đúng theo nguồn, tổng116000; GOT/Got chưa giải. Subtotalnull giữ nguyên, ITEM-SUM vẫnfalse; không ép số tiền hoặc nới quy tắc.
- 840 bản ghi snapshot9bảng trướcUAT không đổi,41 file cũ checksum giữ; không ghi đè #1–41. Test cuối47 invoices/43items/47runs/41corrections/432validation/95notifications/164audits/18schedules/47files.
- 21baselinehash +24guardhash không đổi. Không sửa Website layout, các trang khác hoặc Mobile; chỉ banner runtime V8.

## Môi trường bàn giao

- Vite5173 PID13224; Backend8000 PID26280, healthok/testing.
- `APP_ENV=testing`, database `fintech_ocr_rbac_test`, upload tuyệt đối `<LOCAL_PATH>`.
- Runtime `OCR_PIPELINE=hybrid_v8`, `OCR_HYBRID_FALLBACK=true`; source/.env defaultcurrent không thay đổi.
- htt<LOCAL_PATH>
- Backup mới `<LOCAL_PATH>`, 662945bytes, pg_restorelist0, SHA256 `731507a1997960cc50c586bc8444afe35fd4b609d0086c2a069ddb9b158ea1a5`; metadata runtime kiểm chứng ngay trong process, không chỉ health.
- Auxiliary fault8011 đã dừng, Vite giữ. Runtime proof `ocr_phase11_development/uat/FINAL_LIVE_SERVICES.json`.

Để đổi pipeline **chỉ trong test**, PowerShell:

```powershell
& '<LOCAL_PATH>
# Các giá trị được phép: current, hybrid_v6, hybrid_v7, hybrid_v8.
# Chỉ chạy sau khi đóng các tab đang gọi API; helper dừng nếu còn request/PID lệch.
```

Helper chỉ đổi env của child test process, không viết .env. Giữ backup, proof và wrapper cùng thư mục; nếu source/backup bị đổi guard sẽ chặn để kiểm tra lại. Không dùng lệnh Uvicorn thiếu DATABASE_URL/UPLOAD_DIR vì có thể vào DB khác. Helper được kiểm tra cú pháp; nhánh runtime V8/restart và fallbackcurrent đã chạy thực, không tự nhận đã chạy thử mọi giá trị helper.

## Còn thiếu

- FAIL: ký tự Việt seller/description, suffix số hóa đơn retail,2unit ANAN; headerless POS seller cònnull.
- BLOCKED: dataset thật mới được A/B xác minh, đủ loại/cỡ mẫu, PO/UAT sign-off. G7 giữ tạm dừng, không có nhãn approved mới.
- NOT TESTED: true polygon/semantic rowP/R/F1, CER/WER; PDF mixed/VAT thật/multipage thật/discount đa dạng/ảnh nhăn bóng nặng chưa có tập thật đủ nhãn. Không có benchmark RAM/VRAM/cold-warm lặp.
- G11 không lặp submit/approve/reject đầy đủ đãPASSG10; regression tự độngPASS và trạng tháiđộc lập vẫn giữ. Tax Lookup thật tiếp tụcBLOCKED theo hồ sơ cũ.
- Đề xuất G12 phải chốt tiêu chí/cỡ mẫu và frozen version trước đo độc lập; không biến bộ này thành held-out, không tự bật mặc địnhV8 hoặc tuyên bố ACCEPTED.

## Tài liệu và bằng chứng

- [Thiết kế/UAT/tệp thay đổi](OCR_PHASE11_HYBRID_V8.md).
- [Benchmark per-document/per-field/per-row, raw và normalized](OCR_PHASE11_BENCHMARK_RESULTS.md).
- [Bằng chứng ngoài repo](../../ocr_phase11_development/): CAUSE_ANALYSIS, IMMUTABLE_BASELINES, OFFLINE_GATE, BENCHMARK_INPUTS, BENCHMARK, SCORES, test/build logs và uat snapshots/screenshots.
- [Hậu kiểm read-only cuối](../../ocr_phase11_development/uat/DB_AFTER_RESTART.json), [Browser sau restart](../../ocr_phase11_development/uat/RESTART_BROWSER.json).

Không sử dụng mật khẩu/JWT trong báo cáo. Không yêu cầu xác minh lại24chứng từ G7 trong lượt này. Không thay dữ liệu nghiệm thu hoặc tự ký A/B. Kết thúc tại G11.
