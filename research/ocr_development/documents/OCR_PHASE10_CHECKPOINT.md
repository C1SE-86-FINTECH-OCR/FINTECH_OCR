# Checkpoint Giai đoạn 10 — 20/11/2026

**Web UAT Hybrid V7 trên PostgreSQL test đã thực hiện; OCR vẫn FAIL/chưa nghiệm thu Task 2.** Đã đọc/rà soát sau merge develop, branch feature/thien, HEAD...origin/develop 0/0 theo ref hiện có; ba stash giữ nguyên, diff --check PASS. Không sửa source sản phẩm hoặc thuật toán.

- Schema PostgreSQL test đủ cột models/Profile/Report/Schedule, **không migration**. Backup mới 382.624 byte, `pg_restore --list` và SHA PASS; baseline **31 invoices/18 schedules**, 31 file checksum đúng.
- Regression mới: Backend **377/377 PASS** trong SQLite/thư mục tạm mới; lần đầu **376 PASS/1 FAIL** vì SQLite test cũ thiếu users.phone được giữ trong hồ sơ. Web **35/35 PASS**, build PASS. Không sửa assertion hoặc DB cũ để làm xanh test.
- Browser thật: login ba role; 5 upload #32–36 HTTP201, V7 thực sự chạy/raw/boxes/JSON lưu PG; field/item UI khớp API và F5. #32 sửa seller/mô tả có hai correction, rồi Admin reject; #33 Employee submit/Accountant approve. RBAC và độc lập Lookup/Validation PASS trong các bước đã chạy.
- Ba bill development có 1/2/6 hàng; hai PDF synthetic có 3/1 hàng. V7 còn sai số/dấu #32, số/unit/amount #34; sum **146000** so total **116000**. PDF chữ ghép sai phần mô tả; PDF scan bị STT lẫn tên. Không sửa số hoặc nới ITEM-SUM.
- Chẩn đoán sơ bộ, không phải GT A/B: trên 3 bill thật development, field **11/13**, ô hàng **31/40**, exact row **2/7** (2 hàng partial loại khỏi exact). PDF synthetic field **19/20**, ô **16/20**, exact **0/4**, có hồi quy so V6. Không chứng minh tổng quát/NFR01.
- Fault engine/timeout/output không hợp lệ tạo #37–39, fallback current thật và banner PASS cơ chế, chất lượng current không đạt. Tệp hỏng #40–41 lưu failed, bad magic400 không tạo invoice. Restart V7 giữ dữ liệu; current/V6 startup/health ở cổng phụ PASS, đã dọn process phụ.
- Sau UAT **41 invoices/41 files/30 items/41 runs/39 corrections/384 validations/89 notifications/157 audits/18 schedules**. **703 bản ghi nghiệp vụ cũ không đổi**, không đụng #1–31/DB chính. Phase7/GT giữ nguyên; 13 file frozen khớp byte, một test chỉ đổi LF→CRLF từ lần restore, nội dung không đổi.

Website đang chạy: **htt<LOCAL_PATH>`.env` không đổi. Attestation PID/source/database ở [RUNNING_SERVICES.json](../../ocr_phase10_integration/postmerge_20261120/uat/RUNNING_SERVICES.json).

[Báo cáo đầy đủ và lệnh rollback](OCR_PHASE10_WEB_UAT.md). Bằng chứng mới ở `ocr_phase10_integration/postmerge_20261120/`; không dùng hồ sơ cũ 28 hóa đơn/188.891 byte làm baseline hiện tại.

Còn thiếu: VAT/PDF thật và dữ liệu độc lập, tra cứu thuế có bằng chứng (**BLOCKED**), UAT CRUD toàn diện các tính năng develop (**NOT TESTED** ngoài phần đã chạy), xử lý hồi quy/bất định OCR và nghiệm thu con người. G10 dừng tại đây; không tự triển khai G11/V8 hoặc đánh dấu ACCEPTED.
