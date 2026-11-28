# Checkpoint Giai đoạn 9 — 19/11/2026

Đã triển khai Hybrid V7 riêng, opt-in/testing, kế thừa V6 và thêm phân cột/hàng, scope điều chỉnh, đọc lại nhãn/cell và cảnh báo. V6/14 file frozen và ground truth Phase7 giữ nguyên. `current` vẫn default; không restart service/đổi engine Website, không truy cập hoặc ghi PostgreSQL.

Thực OCR offline trên đúng ba ảnh development của #25/#26/#28; #27 cùng ảnh #25 là test fallback trước đó. V7 sửa ngày #25, bỏ khuyến mãi khỏi mô tả #26, khôi phục 6/6 vùng hàng #28. Vẫn sai số HĐ/dấu #25, một amount/số lượng/đơn vị #28; tổng hàng #28 là 146000 so total 116000, cần review. Không sửa bản ghi invoice cũ, không ép ITEM-SUM hoặc điền subtotal.

Báo cáo: [OCR_PHASE9_HYBRID_V7.md](OCR_PHASE9_HYBRID_V7.md). Bằng chứng: [ocr_phase9_development](../../ocr_phase9_development). Kết quả: **Backend 350 PASS/0 FAIL/0 SKIP, Web 26 PASS/0 FAIL, build PASS**. Có API + Tesseract thật + SQLite fixture readback; không lấy test PASS làm bằng chứng accuracy hoặc Browser UAT. Chi tiết ghi tại `TEST_RESULTS.json` và JUnit.

Website/PostgreSQL V7 NOT TESTED, OCR chưa nghiệm thu; Phase7 tiếp tục tạm dừng, không tự xác minh A/B. Bước sau: xử lý lỗi ký tự/ô còn lại trên development, kiểm thử V7 opt-in với backup/runtime test đã xác minh; cần dữ liệu mới và nhãn độc lập trước nghiệm thu. Không commit/push/pull/merge/chuyển nhánh.
