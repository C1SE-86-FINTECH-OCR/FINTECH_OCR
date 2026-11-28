# Giai đoạn 6 — Vấn đề còn mở và thứ tự tiếp tục

Chốt ngày 18/11/2026 từ bằng chứng đã lưu. Không tạo lỗi mới từ suy đoán, không chạy lại bài đã PASS trong lượt này. **Chưa đủ điều kiện tích hợp hoặc nghiệm thu.**

| ID | Ưu tiên | Vấn đề / bằng chứng | Trạng thái | Công việc tiếp theo và điều kiện xác nhận |
| --- | --- | --- | --- | --- |
| P6-01 | Cao | Supplier mới 3/10 exact; còn sai dấu, tên bị cắt hoặc chọn metadata. | OPEN — chất lượng chưa đạt | Phân biệt nhận chữ sai với chọn nhầm vùng; kiểm tra lại nhãn–MST–vị trí. Dùng development riêng, không hardcode cửa hàng. Bảo toàn các scalar/dòng đang đúng. |
| P6-02 | Cao | MST 0/2; các chữ số OCR mâu thuẫn nên giữ null/review. | OPEN — chưa cải thiện | Cải thiện nhận dạng vùng MST bằng evidence ảnh. Không thay digit theo kỳ vọng hoặc tự tạo MST cho bill không có. Cần thêm mẫu MST thật được A/B duyệt. |
| P6-03 | Cao | Total 6/8; ảnh vé thiếu kết quả, bill MINISTOP vẫn 21000 so nháp 27000. Payable đã sửa có cảnh báo readback mâu thuẫn. | OPEN — còn sai/thiếu | Giữ raw và cảnh báo, tách tổng khỏi tiền mặt/tạm tính/giảm giá. Không điền tổng từ phép cộng hoặc từ đáp án. Kiểm chứng trên nguồn và nhãn mới. |
| P6-04 | Cao | Chỉ 5/16 dòng, 1/7 bảng exact; còn mất hàng, sai tên/SL/đơn giá. Có 9 FP và 11 FN theo exact row; FP không đồng nghĩa toàn bộ là sản phẩm giả. | OPEN — chất lượng chưa đạt | Tiếp tục xử lý ownership dòng/cột, mô tả xuống dòng và OCR ký tự; không ép ITEM-SUM hoặc tạo hàng khớp tổng. Kiểm tra riêng unit/page/VAT khi có nhãn. |
| P6-05 | Cao | 10 ảnh đã dùng phát triển; nhãn draft và chưa có A/B. | BLOCKED — chờ dữ liệu/hồ sơ | Tiếp nhận bộ mới đa nguồn/đa bố cục, quyền sử dụng rõ; người A/B khác nhau xác minh trước inference. Kiểm tra 35 hash đã biết, ảnh gần trùng và nhóm mẫu. Không gọi lại 10 ảnh cũ là độc lập. |
| P6-06 | Vừa | CER/WER chưa đo; mẫu PDF text/scan nhiều trang, nhiều VAT và phối cảnh mạnh chưa có bằng chứng thực trong bộ 10 JPEG. | NOT TESTED | Bổ sung transcription người duyệt và dữ liệu thật. Kiểm tra schema page evidence/adapters; thiếu evidence phải PARTIAL/NOT TESTED. |
| P6-07 | Vừa | Giảm 38,4% latency chỉ từ một lượt bốn nhánh; 0/10 ảnh chạy fast-path hoàn toàn. | PARTIAL — giới hạn phép đo | Sau khi có bộ mới đã khóa, đo lặp cold/warm và p95, luân phiên thứ tự engine, ghi CPU/RAM/tải. Không cần chạy lại vòng đã có bằng chứng trong lượt chốt này. |
| P6-08 | Trước tích hợp | Profiling/capture dùng hook scoped và lock offline; chưa thiết kế cho API đồng thời. | NOT READY FOR INTEGRATION | Sau phê duyệt, chuyển sang adapter/callback rõ ràng, kiểm tra exception/đồng thời/bộ nhớ, feature flag và rollback. Không gắn prototype trực tiếp vào API đang chạy. |
| P6-09 | Sau bằng chứng độc lập | Browser/API/PostgreSQL UAT với Hybrid chưa chạy. | NOT TESTED | Chỉ sau phê duyệt tích hợp và xác minh DB/upload test + backup; kiểm tra upload → OCR → review/edit → validation → lưu/mở lại. Không dùng DB chính, không tự ký sign-off. |

Nguồn: [báo cáo Giai đoạn 6](OCR_PHASE6_HYBRID_RESULTS.md), [đối chiếu từng ảnh](../../ocr_phase6_development/measured_20261118_172554/ERROR_ANALYSIS.md), [kế hoạch nghiệm thu độc lập](OCR_PHASE6_INDEPENDENT_ACCEPTANCE_PLAN.md).

Thứ tự đề xuất: P6-01–04 phát triển trên dữ liệu development; chuẩn bị P6-05–06 song song. Chỉ đo tập độc lập sau khi chốt mã/nhãn, không điều chỉnh parser trên held-out. Nếu dùng kết quả held-out để phát triển, phải ghi nhận ảnh hưởng và chuẩn bị tập nghiệm thu mới. P6-08–09 cần phê duyệt tích hợp riêng; giữ pipeline hiện tại trong lúc chờ.
