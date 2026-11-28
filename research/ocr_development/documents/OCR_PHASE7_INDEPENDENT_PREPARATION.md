# Giai đoạn 7 — Chuẩn bị bộ nghiệm thu độc lập Hybrid V6

Ngày 18/11/2026. Tiếp tục từ [Giai đoạn 6](OCR_PHASE6_HYBRID_RESULTS.md); không chạy lại những phép đo đã hoàn tất. Giữ Tesseract default và toàn bộ source Hybrid V6. **Dừng tại xác minh ground truth, chưa freeze/benchmark/nghiệm thu.**

## Phạm vi đã thực hiện

Người dùng chưa có thêm VAT/PDF nhiều trang và cho phép tìm nguồn nghiên cứu, tải từng ảnh ReceiptVQA qua HTTP Range. Đã chuẩn bị ngoài repo tại `<LOCAL_PATH>`:

- **24 JPEG thật**, chọn từ 87 ứng viên chưa thuộc danh sách ảnh cũ. Mỗi file có source ZIP member, SHA-256, CRC, kích thước và nguồn/quyền. Chỉ tải byte range, không tải ZIP lớn. Body nhận 20.841.904 byte; cộng dự phòng 1 MB vẫn dưới 30.000.000 byte.
- Kiểm tra 35 tài liệu/37 trang cũ, **888 cặp mới–cũ** và **276 cặp nội bộ**. Không trùng SHA; không ứng viên gần trùng ở ngưỡng dHash/pHash <=6 đồng thời (full/crop/bốn hướng). Đây là bằng chứng kiểm tra ảnh, không phải chứng nhận hoàn toàn khác nhà cung cấp/mẫu.
- Loại ảnh báo cáo thu ngân và ảnh thuộc Điện Máy 30-4 đã dùng. Nhóm nguồn mới gom thận trọng thành 15 nhóm: có 4 bill sách cùng mẫu, 2 CoopFood, 2 The Coffee House, 5 POS chung chưa chứng minh được danh tính nguồn. Không đếm 24 nhà cung cấp riêng. Bill vô danh và nguồn/mẫu lặp còn chờ A/B.
- Chạy prepare chỉ tạo metadata, sau đó đọc trực tiếp từng ảnh gốc để điền **nháp**, không lấy prediction/QA làm đáp án: 24 draft, 0 approved; 18 bảng/29 dòng có nháp đầy đủ, 6 bảng/16 dòng đề xuất chưa đủ nhãn, 51 câu hỏi. Các ô che/mờ/không chắc không được dùng null làm nhãn “vắng”.
- Đã tạo manifest thực, ground truth, bảng đọc nhãn, phiếu HTML A/B có ảnh gốc tương đối, hướng dẫn và biểu mẫu xuất hồ sơ riêng. Không tự ghi tên, chữ ký hoặc phê duyệt thay A/B. Chromium kiểm tra phiếu HTML (desktop/mobile, 24 ảnh/card, mặc định pending, chặn xuất hồ sơ trống); **không phải UAT Website FINTECH OCR**.
- Đối chiếu SRS/User Story và [đề xuất tiêu chí](OCR_PHASE7_ACCEPTANCE_CRITERIA.md). NFR01 đặt >=85% theo trường trên 100–500 hóa đơn; bộ 24 là pilot, không tự nhận đủ mẫu. Ghi rõ khác biệt yêu cầu MST cho bill và công thức VAT/giảm giá, không tự đổi validator.

Nguồn gốc ReceiptVQA nêu CC BY-NC-SA 4.0 cho nghiên cứu; metadata mirror gắn MIT khác nguồn gốc. Hồ sơ sử dụng theo nguồn tác giả, giữ attribution, không suy quyền thương mại từ mirror: [tác giả LiGT_VQA](http<LOCAL_PATH>

## Trạng thái và coverage

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| HTTP Range, CRC/SHA, nguyên vẹn 24 file | PASS kỹ thuật | [transfer](../../ocr_phase7_acceptance/transfer.json), [acquisition](../../ocr_phase7_acceptance/source_records/acquisition.json) |
| Trùng byte / tìm ảnh gần trùng | PASS trong phạm vi phép so | [audit](../../ocr_phase7_acceptance/DUPLICATE_AND_INTEGRITY_AUDIT.json); không thay xác minh nguồn/mẫu |
| Độc lập nhà cung cấp/bố cục | PARTIAL | Bill không tên, nhóm lặp; chờ A/B; không đổi group để vượt gate |
| Manifest, nháp, phiếu A/B | ĐÃ CHUẨN BỊ | [phiếu HTML](../../ocr_phase7_acceptance/HUMAN_VERIFICATION_24.html), [bảng nháp](../../ocr_phase7_acceptance/GROUND_TRUTH_REVIEW.md) |
| Hóa đơn VAT điện tử | MISSING / BLOCKED | 0; hai bill có MST/VAT không thay thế VAT e-invoice |
| PDF có chữ / PDF scan nhiều trang | MISSING / BLOCKED | 0/0; không chuyển ảnh thành PDF giả coverage |
| A/B và nhãn đủ điều kiện | BLOCKED / CHỜ XÁC MINH | 24 draft, 0 approved, không có hồ sơ người kiểm thử được tạo thay |
| Accuracy, CER/WER, latency bộ mới | NOT TESTED | Chưa inference/benchmark; transcription chưa được duyệt |
| Source lock và nguyên vẹn nhãn phát triển | Kiểm tra trong audit cuối | [validation](../../ocr_phase7_acceptance/PREPARATION_VALIDATION.json) |
| Browser/API/PostgreSQL UAT Hybrid V6 | NOT TESTED | Không thay pipeline Website/API/default/DB |

Coverage nháp hiện có: 24 bill/POS một trang; 22 không in MST người bán, 2 in MST/VAT; 1 có nhiều VAT; 5 có >=3 dòng; 1 gắn nhóm Việt–Anh và 1 Việt–Trung ngoài phạm vi core SRS. Ảnh có cắt/nhăn/che được đánh dấu chất lượng, không gộp vào “ảnh rõ đầy đủ” khi nghiệm thu. Chi tiết [checkpoint ngoài repo](../../ocr_phase7_acceptance/PHASE7_STATUS.md).

## Việc cần làm tiếp theo — chưa thực hiện

1. A/B thực đọc độc lập [phiếu và hướng dẫn](../../ocr_phase7_acceptance/HUMAN_VERIFICATION_GUIDE.md), giải quyết 51 câu hỏi, ghi danh tính/thời điểm/hash và quyền/độc lập thật. Nháp không phải ground truth đã duyệt. Chưa rõ thì giữ partial/draft, không ép đủ nhãn.
2. Bổ sung VAT/PDF/multipage thật có quyền; đề xuất ít nhất 4 VAT, trong đó 3 PDF gồm 2 scan nhiều trang và 1 PDF có chữ (có thể chồng lấp), thêm/đổi bill cùng nhóm để pilot còn 20–30. Đây là đề xuất cơ cấu, chờ xác nhận; chưa đủ cỡ mẫu NFR01.
3. Chốt tiêu chí trước inference, so source lock và provenance, freeze khi đủ điều kiện. Dùng [quy trình có sẵn](OCR_PHASE6_INDEPENDENT_ACCEPTANCE_PLAN.md) với dataset Phase7; không init/prepare ghi đè nhãn. Báo riêng absent/present, từng field/dòng/table, lỗi OCR/parser/table/source, mean/p95/RAM và review-rate. CER/WER chỉ khi có transcription được người xác minh.
4. Sau bằng chứng đạt tiêu chí mới đề xuất tích hợp có rollback và UAT test DB/upload biệt lập; không tự đổi default hoặc tuyên bố nghiệm thu.

## Thay đổi trong lượt này

Chỉ thêm artifact tiếp nhận/xác minh ngoài repo, hai báo cáo Phase7 này và cập nhật checkpoint `OCR_PHASE35_ACCEPTANCE_STATUS.md`. Không sửa pipeline/runtime/Frontend/Mobile/DB hoặc dữ liệu cũ. Source lock được kiểm tra lại. Giữ các thay đổi chưa commit đã có; không commit/push/merge. Backend **310 PASS** là kết quả lịch sử Phase6, **không chạy lại và không dùng làm bằng chứng chất lượng bộ mới**.

**Kết luận: đã chuẩn bị bộ bill pilot để người kiểm thử đối chiếu; nghiệm thu độc lập và tích hợp vẫn chưa đủ điều kiện.**
