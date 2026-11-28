# Giai đoạn 4 — OCR ngữ cảnh thử nghiệm

Ngày 18/11/2026. Đã triển khai opt-in `tesseract-context-v4` trong công cụ offline; **chưa đổi pipeline API/Website mặc định**. Giữ Tesseract, PaddleOCR và table-v3, không schema/migration/seed hoặc dữ liệu thật.

 **Đã sửa mã và chạy benchmark thật; chất lượng còn thiếu, chưa tích hợp Website hoặc nghiệm thu.**

Audit benchmark cũ PASS: raw -> field parser tái tạo output đã lưu; đếm độc lập điểm trường/dòng khớp evaluator. Đã giữ snapshots và toàn bộ kết quả từng vòng, không sửa nhãn theo dự đoán.

Code mới: `backend/tools/ocr_benchmark/pipeline_v4.py`; thêm lựa chọn `tesseract-context-v4` trong CLI; 26 tests mới ở `backend/tests/test_ocr_context_v4.py`. Giữ app/extraction.py, table-v3, PaddleOCR và API/Website cũ. Không đổi DB, schema, .env hoặc dịch vụ.

Công nghệ thực tế: Tesseract vie+eng, tiền xử lý PIL và parser bố cục/ngữ cảnh. Chưa có mô hình neural document understanding/fine-tuning mới, không dùng API AI bên ngoài. Không hardcode nhà cung cấp/file/đáp án.

| Chỉ số trên nhãn draft đọc rõ | Current | V4 |
| --- | --- | --- |
| Phân loại | 1/9 | 8/9 |
| Số hóa đơn | 0/6 | 3/6 |
| Ngày | 0/9 | 7/9 |
| Người bán | 0/10 | 1/10 |
| MST người bán | 0/2 | 0/2 |
| Tiền hàng được in | 0/3 | 3/3 |
| Tổng thanh toán | 0/8 | 5/8 |
| Dòng khớp đủ 4 ô | 0/16 | 1/16 |
| Bảng khớp toàn bộ | 0/7 | 0/7 |
| Thời gian TB/chứng từ (giây) | 9.5943 | 4.3892 |
| RAM đỉnh (MiB) | 261.75 | 210.25 |

V4 dự đoán 18 dòng trong 7 bảng được chấm, chỉ một dòng khớp cả mô tả/SL/đơn giá/thành tiền. Không coi số dòng gần đúng là trích xuất đúng. MST/VAT và supplier còn yếu; một số tổng vẫn sai. Các trường có giá trị vắng/nhãn chưa đủ rõ không được cho điểm giả. CER/WER NOT TESTED, không có transcription đầy đủ được duyệt. 10 ảnh là development, không phải nghiệm thu độc lập.

Backend: **256 PASS / 0 FAIL**, 5 warnings deprecation, với SQLite memory và tmp uploads. Evidence replay cuối PASS; **0 hồi quy** trên các trường current đang khớp nhãn trong tập này, bao gồm trường vắng. Không chứng minh không hồi quy trên dữ liệu khác. Các lỗi lập trình trung gian và lần benchmark chưa đạt được giữ trong RUN_HISTORY.md; không chọn kết quả tốt nhất để che lỗi.

**Kết luận:** Mã thử nghiệm tiến bộ về phân loại/ngày/tổng, nhưng chưa đạt trích xuất bảng hoặc nhà cung cấp/MST. Giữ current mặc định. Browser/API/PostgreSQL UAT NOT TESTED; không commit/push.


Bằng chứng đầy đủ: [checkpoint Phase 4](../../ocr_phase4_development/PHASE4_STATUS.md), [bảng từng trường/tài liệu](../../ocr_phase4_development/measured_20261118_144249/REPORT.md), [lỗi thực tế](../../ocr_phase4_development/measured_20261118_144249/ERROR_ANALYSIS.md), [xác minh benchmark](../../ocr_phase4_development/measured_20261118_144249/FINAL_VERIFICATION.json), [JUnit 256 PASS](../../ocr_phase4_development/backend-tests-final-success.xml).
