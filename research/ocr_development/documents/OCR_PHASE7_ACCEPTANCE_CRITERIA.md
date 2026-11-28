# Giai đoạn 7 — Phạm vi và tiêu chí nghiệm thu OCR cần xác nhận

Ngày 18/11/2026. Đây là đề xuất đối chiếu tài liệu và hồ sơ chuẩn bị, **không phải kết quả nghiệm thu hoặc ngưỡng mới đã được PO phê duyệt**.

## Căn cứ

Đọc SRS `C1SE_86_SRS_FINTECH_OCR_v1_0.docx` và User Story `C1SE_86_User_Story_FINTECH_OCR_v1.0.docx` trong `fintech-ocr-starter/docs/reference`, chỉ đọc, không sửa tài liệu. Bản trích văn bản và hash được lưu tại [source_records](../../ocr_phase7_acceptance/source_records/). Số đoạn dưới đây là chỉ mục trong bản trích, không phải số trang Word.

| Yêu cầu | Căn cứ | Cách đo/điều kiện dự kiến |
|---|---|---|
| Độ chính xác trích xuất theo trường tối thiểu 85% trên 100–500 hóa đơn | SRS NFR01, đoạn 556–559; mục tiêu 284–285 | Báo numerator/denominator từng trường, exact match, precision/recall/F1; quy tắc tổng hợp và tập trường phải thống nhất trước đo. Bộ 24 hiện tại chỉ là pilot, chưa đủ cỡ mẫu NFR01. Không gọi 24/24 xử lý được là 100% chính xác. |
| Đọc dữ liệu hóa đơn, giữ text/vị trí, xuất dữ liệu có cấu trúc | UC04, đoạn 1182–1265; PB04 | So seller/buyer/MST/số/ký hiệu/ngày/subtotal/VAT/total và từng ô dòng hàng với nhãn người xác minh; giữ raw OCR, box, confidence khi có. Lỗi engine khác lỗi parser/table/source. |
| Phân loại einvoice/bill/unknown | FR26, đoạn 548–550 | Đánh giá từng nhóm, confusion matrix; không xếp bill thành einvoice chỉ vì có MST/VAT hoặc file PDF/XML. Bộ hiện tại mới có bill. |
| Kiểm tra số học, MST, ngày, dữ liệu mâu thuẫn và độ tin cậy | UC06, đoạn 1337–1425; BR04–06/09; PB06 | Không bịa hoặc sửa số OCR để khớp tổng; báo trường sai/không chắc và nhu cầu review. Quy tắc VAT/giảm giá phải đối chiếu nguồn; confidence không chứng minh kết quả đúng. Validation độc lập Approval/Lookup. |
| Cho người dùng đối chiếu và chỉnh sửa | BR10, đoạn 2573; PB08 | Sau benchmark offline, còn cần UAT upload → extraction → validation → review/edit → lưu/mở lại trên môi trường test riêng. Giai đoạn 7 chưa kiểm thử API/Website/DB. |
| PDF/JPG/PNG/XML, tiếng Việt và Anh | BR03, đoạn 2552; BR14, đoạn 2585; PB03/PB05 | Báo riêng định dạng/ngôn ngữ; Phase7 hiện chỉ JPEG, 0 PDF/multipage/XML. P7-019 Việt–Trung là challenge ngoài phạm vi Việt–Anh, không thay thế kiểm thử song ngữ Việt–Anh. |
| Dữ liệu có quyền sử dụng, không lộ thông tin | BR12, đoạn 2579 và yêu cầu người dùng mới nhất | ReceiptVQA dùng nghiên cứu nội bộ theo điều kiện nguồn gốc, không gửi hóa đơn tới dịch vụ OCR bên ngoài; giữ attribution/hash. Không dùng ảnh tổng hợp làm bằng chứng hóa đơn thật. |

## Điểm cần thống nhất, không tự đổi nghiệp vụ

- BR07 (đoạn 2564) yêu cầu MST người bán/người mua nói chung; yêu cầu cập nhật của người dùng cho phép **bill bán lẻ không MST** và không tự xem sai chỉ vì thiếu MST. Hồ sơ nhãn ưu tiên yêu cầu cập nhật: null nếu thực sự vắng, không bịa MST. Đây là điểm cần PO ghi nhận cho tiêu chí từng loại; không sửa validator hoặc schema trong lượt này.
- BR05 mô tả công thức tổng tiền đơn giản; chứng từ thật có giá gồm VAT, giảm giá, nhiều VAT và công nợ. Không áp một công thức để suy nhãn thiếu hoặc cộng VAT hai lần. Cần thống nhất cách đối chiếu từng trường in trên nguồn trước khi đo; giữ dữ liệu gốc.
- Phụ lục SRS có nhắc bộ giả lập 100–500, trong khi nhiệm vụ mới yêu cầu chứng từ thật độc lập. Bộ tổng hợp chỉ dùng regression; nghiệm thu khả năng tổng quát phải có chứng từ thật và báo riêng cỡ mẫu/chất lượng.
- SRS không đưa ngưỡng cụ thể cho exact toàn bảng, strict unit/page/VAT, false positive, CER/WER hay thời gian xử lý p95. Không tự nhận các ngưỡng đó là yêu cầu SRS hoặc đặt sau khi thấy điểm.

## Đề xuất gate để PO chốt trước inference

1. A/B thực, hai định danh khác nhau, nhãn/ảnh/hash/quyền và lịch sử độc lập được xác minh trước prediction. Không tự điền approved hoặc bật provenance từ nháp chatbot. Trường chưa rõ không đưa vào mẫu số; báo rõ trường loại trừ và số tài liệu được chấm.
2. Khóa Hybrid V6 và baseline cùng môi trường/thread trước đo; kiểm tra trùng byte, ảnh gần trùng, nhà cung cấp và mẫu. Không sửa pipeline theo tập này. Nếu dùng để phát triển, đánh dấu đã ảnh hưởng và tạo bộ nghiệm thu khác.
3. Mục tiêu field accuracy >=85% theo NFR01, với cỡ mẫu/định nghĩa trường thống nhất. Báo exact tiền tổng, MST, tên, ngày, số riêng; báo cả absent/present để không tăng điểm bằng trường null. Không tuyên bố đạt NFR chỉ từ pilot bill.
4. Đề xuất thêm để xem xét tích hợp: không mất trường/dòng baseline đang đúng; không bịa giá trị; mọi sai tổng/MST phải được báo. Exact từng ô và từng dòng, precision/recall/F1, bảng exact, số dòng giả/bỏ sót, unit/page/VAT khi schema hỗ trợ. Ngưỡng số cụ thể cho dòng hàng và review-rate **chờ PO chốt**, chưa tự nghiệm thu.
5. CER/WER chỉ khi có transcription A/B từng trang; hiện chưa có. Đo cold/warm, mean/median/p95, RAM/OCR call count trên cùng máy, báo thất bại/timeout. Có thể so Hybrid với Current/V4/V5, không hy sinh độ chính xác để đạt thời gian. Chưa có SLA latency đã duyệt.
6. Báo riêng ảnh rõ, ảnh khó/cắt/che và ngoài ngôn ngữ hỗ trợ. Coverage đủ loại trước khi gọi nghiệm thu toàn diện; còn thiếu VAT điện tử/PDF/multipage phải ghi BLOCKED/NOT TESTED.
7. Chỉ sau kết quả độc lập đạt tiêu chí và phê duyệt mới đề xuất tích hợp có rollback, kiểm tra concurrency của prototype offline và UAT Web trên DB/upload test. Không tự đổi default hoặc ký thay PO.

## Trạng thái hiện tại

**PREPARATION PARTIAL / WAITING A/B. 24 draft, 0 approved, 0 scored. Chưa đủ điều kiện freeze/benchmark/nghiệm thu/tích hợp.** 310 backend tests PASS là bằng chứng lịch sử Giai đoạn 6, không phải độ chính xác bộ mới. Chưa chạy lại test hoặc OCR ở lượt chuẩn bị dữ liệu này.
