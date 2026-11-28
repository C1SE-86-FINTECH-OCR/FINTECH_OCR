# Giai đoạn 6 — Hybrid OCR: chất lượng và hiệu năng

Ngày 18/11/2026, nhánh `feature/thien`. **Đã triển khai prototype độc lập, đo 40 lượt OCR thật và chạy tests; chưa đủ chất lượng để tích hợp/nghiệm thu.**

Giữ Tesseract; Current, V4, V5, table-v3 và PaddleOCR có sẵn được bảo toàn. Không sửa app/extraction.py, API/Website/default, Mobile, .env, CORS, cổng, schema hoặc database. Không cài/tải mô hình, không gửi chứng từ ra ngoài, không commit/push.

## 1. Phạm vi dữ liệu và đo kiểm

- Cùng 10 JPEG thật đã dùng phát triển Giai đoạn 4/5. Ground truth gốc, manifest gốc, bộ nhãn chấm draft và ảnh giữ nguyên hash. Không gọi đây là held-out.
- Chỉ chấm nhãn đọc rõ đã có: 7 bảng/16 dòng với description/quantity/unit_price/amount. Bảng ANAN và hai dịch vụ vé chưa đủ nhãn, không lấy rỗng làm PASS. Giữ key chưa xác minh ngoài mẫu chấm; tách null-null khỏi exact trường có in.
- Chạy Current/V4/V5/Hybrid mới, tuần tự, cùng source snapshot/CPU ceiling 1/Python hashseed 0 và công cụ profiling. Không thay prediction cũ vào lần chạy mới. Nhãn chỉ được dùng sau khi prediction đã lưu.
- Một lượt/engine, 10 ảnh. Latency là wall time cục bộ, RAM sampled process-tree gồm Tesseract con; CPU-only, VRAM N/A. Không có nhiều lần lặp/đảo thứ tự nên chưa suy ra mức cải thiện cố định trên máy khác hoặc tải Website.

## 2. Vì sao V5 chậm

V5 gọi toàn bộ V4 trước, sau đó luôn chạy tìm giấy/biến đổi ảnh, OCR toàn trang, ba lượt header, hai footer, ba table, đọc lại tên và một số ô số. Nhiều lượt này chạy cả khi trường đã rõ; chỉ thay regex parser không giải quyết chi phí nhận dạng lặp. Giai đoạn 5 đo V4 5,16 s và V5 13,43 s; phép đo mới có số cụ thể bên dưới, không gán toàn bộ chênh lệch giữa các lần đo cho code.

| Công đoạn TB/ảnh | Current | V4 | V5 | Hybrid |
| --- | --- | --- | --- | --- |
| Tổng wall time (s) | 9.4087 | 3.9714 | 13.2903 | 8.1919 |
| Số lần gọi Tesseract (kể cả OSD) | 7.9000 | 4.0000 | 22.1000 | 10.1000 |
| Thời gian gọi OCR (s) | 8.8013 | 3.5330 | 11.0193 | 6.5414 |
| Trong đó image_to_data (s) | 4.4940 | 3.0319 | 9.3157 | 5.6449 |
| Trong đó image_to_string (s) | 3.5340 | 0.0000 | 1.0244 | 0.2096 |
| Trong đó OSD (s) | 0.7732 | 0.5011 | 0.6792 | 0.6869 |

V5 tìm/biến đổi giấy tốn 1.019 s/ảnh; V4 fallback bên trong V5 5.029 s. Hybrid baseline V4 5.250 s và phần bổ sung 2.930 s. Không cộng lại các span inclusive chứa nhau. Bảng đầy đủ có inclusive/exclusive/call count theo từng tên vùng trong REPORT.md/PROFILING.json.

Thời gian V4 chạy riêng và V4 nested khác nhau dù kết quả/cùng source khớp; CPU scheduling/nhiệt/tải và overhead thực thi có thể ảnh hưởng. Không kết luận bản V4 bên trong đã đổi thuật toán. Audit xác minh thời gian exclusive không vượt elapsed và đếm đúng số call; profiling không lưu ảnh/text/nhãn.

## 3. Thiết kế Hybrid đã triển khai

1. Chạy V4 đúng một lần, giữ các alternative OCR/polygon và chụp bản sao đúng raster V4 đã tiền xử lý. Không OCR lại toàn trang và không chạy paper_view thường trực.
2. Tái phân tích các tọa độ đã có. Quyết định header/table/footer dựa thiếu trường có nhãn in, supplier là metadata/cắt cụt, điểm word thấp, các alternative mâu thuẫn, SL/giá có cột nhưng chưa đọc được, số học sai hoặc tổng có điều chỉnh. Bill không MST không bị buộc điền MST.
3. Header chủ yếu một pass vie, chỉ thêm pass khi vẫn thiếu/yếu; nhận MST riêng người bán/người mua theo nhãn, chỉ giữ ID được hỗ trợ, không đổi ký tự thành số đoán. Supplier vùng tập trung được xét theo word evidence thay vì đa số các lượt toàn trang tương quan.
4. Bảng phân tích numeric row theo tiêu đề/cột trước, rồi ghép mô tả phía trên/xuống dòng theo khoảng cách. Tên dài có model được giữ ở vùng mô tả; model đơn lẻ không đủ SL/giá/định dạng tiền không tạo anchor sản phẩm. Loại text nằm bên phải cột amount trên cùng baseline và summary gần footer không có ô hàng độc lập.
5. Footer lấy mốc summary sớm nhất trong các pass V4 có sẵn, không cắt mất payable nằm trên commission. Chứng từ có giảm giá/phụ phí hoặc total không có evidence vùng chính được kiểm tra lại dù confidence cao.
6. Payable khác baseline cần nhãn thanh toán trực tiếp và hỗ trợ OCR ô ảnh. Cho phép loại đúng một dấu phân cách thừa sau số đã có các nhóm nghìn hoàn chỉnh; giữ raw, không thay digit/sửa nhóm sai. Regional PSM6 cộng isolated-cell segmentation là hai quan sát thực; nếu các readback khác mâu thuẫn vẫn giữ PAYABLE_READBACK_CONFLICT/needs review. Không dùng subtotal ± discount để điền tổng.
7. Chỉ đọc lại ô thiếu/mâu thuẫn/word score thấp; cache theo cell polygon trong một tài liệu. Không dùng cache kết quả giữa hóa đơn, không đọc labels/fixture trong parser. Có nhánh V4 fast-path khi routing sạch; luôn experimental/unverified, không tự verify.
8. Phép quantity×price và tổng dòng so subtotal chỉ phát cảnh báo khi đủ dữ liệu. Không suy quantity/unit_price, không ép ITEM-SUM và không thay Approval/Lookup/Validation của hệ thống.

Trên 10 ảnh còn nhiều lỗi, header được route 10/10, footer 9/10, bảng 8/10. **0/10 đi fast-path toàn bộ**; nhánh không OCR bổ sung mới có bằng chứng unit test. Không dùng nhánh synthetic để báo latency thật thấp hơn.

## 4. Kết quả trước/sau

| Chỉ số | Current | V4 | V5 | Hybrid |
| --- | --- | --- | --- | --- |
| Phân loại | 1/9 | 8/9 | 8/9 | 8/9 |
| Số hóa đơn | 0/6 | 3/6 | 4/6 | 4/6 |
| Ngày | 0/9 | 7/9 | 7/9 | 7/9 |
| Supplier | 0/10 | 1/10 | 2/10 | 3/10 |
| MST người bán | 0/2 | 0/2 | 0/2 | 0/2 |
| Tiền hàng được in | 0/3 | 3/3 | 3/3 | 3/3 |
| Tổng thanh toán | 0/8 | 5/8 | 6/8 | 6/8 |
| Dòng exact 4 ô | 0/16 | 1/16 | 3/16 | 5/16 |
| Bảng exact | 0/7 | 0/7 | 1/7 | 1/7 |
| Line Precision / Recall / F1 | N/A/0.0%/0.0% | 5.6%/6.2%/5.9% | 21.4%/18.8%/20.0% | 35.7%/31.2%/33.3% |
| RAM peak MiB | 261.93 | 210.51 | 237.21 | 223.09 |

Hybrid giảm wall time 38.4% và số call OCR 54.3% so V5 trong lượt đo này. Dự đoán 14 dòng ở 7 bảng được chấm, TP=5, FP=9, FN=11. FP là không khớp đủ bốn ô, không đồng nghĩa mọi FP là hàng bịa. Bảng chi tiết có field Precision/Recall/F1, cell metrics và từng ảnh; không chỉ báo trung bình.

Hồi quy trên tập nhãn này: **0 trường V4/V5 đang khớp bị mất (kể cả absent), 0 dòng exact bị mất**. Không chứng minh mọi ô/unit/trang hoặc mọi hóa đơn mới đều không hồi quy. Giữ V4/V5 nguyên source để đối chứng/rollback. Không báo accuracy cho VAT amount, buyer MST hoặc field 0/0; CER/WER NOT TESTED vì chưa có transcription độc lập.

## 5. Lỗi còn lại theo chứng từ

| ID | Kết quả và hạn chế |
| --- | --- |
| REAL-001 | Ảnh vé rất ít pixel; tên pháp nhân/số/tổng/loại vẫn sai hoặc thiếu. Không điền số từ đáp án. Bảng dịch vụ chưa chấm. |
| RVQA-00000022 | Giữ 5/5 scalar có nhãn, nhưng hai tên sản phẩm sai dấu/ghép thêm promo, 0/2 dòng exact. |
| RVQA-00000505 | Đọc được SL 10/đơn giá/thành tiền từ dòng numeric riêng; tên món và ngày/supplier chưa exact. Total không được suy ra khi nhãn chưa chốt. |
| RVQA-00000509 | Hai dòng exact thay vì một; không còn xuất model 12 thành hai dòng sản phẩm. Bảng vẫn chỉ 4/5 dòng, tên siêu thị và MST chưa đúng; đơn giá/SL dòng đầu còn sai/thiếu. |
| RVQA-00000513 | Dòng hàng exact và số/ngày/tổng giữ đúng. Tên quán sai dấu, chưa hóa đơn đầy đủ đúng. |
| RVQA-00001100 | 4/4 scalar được chấm giữ đúng; bảng ANAN chưa đủ nhãn nên không chấm. Parser vẫn có tên/ghép dòng yếu trong raw, chưa tự xác nhận. |
| RVQA-00002901 | Supplier pháp nhân đọc đúng; MST vẫn None vì các chữ số đọc ra mâu thuẫn. Tổng vẫn 21000 khác nháp 27000, một sản phẩm bị thiếu, 0/3 dòng exact. Dòng tạm tính giả đã bị loại, không dùng tạm tính/tiền mặt làm total thay thế. |
| RVQA-00002905 | Giữ total 400000; seller, số/ngày, buyer và tên/SL hàng còn sai. Tesseract lẫn ký tự/ngày và dấu mộc; chưa giải quyết. |
| RVQA-00002910 | Tên pháp nhân/thuế suất còn thiếu/sai; loại/total/dịch vụ chưa đủ nhãn nên không báo PASS. Chưa sinh bảng sản phẩm từ ticket unknown. |
| RVQA-00005500 | Giữ total 160000 của V5 với cảnh báo readback mâu thuẫn; hai dòng exact thay vì một, loại ký tự nhiễu sau amount. Supplier vẫn metadata, tên dòng đầu/format chưa exact. |

Không kết luận mọi mismatch là lỗi nhận dạng: có lỗi OCR ký tự, lỗi chọn supplier/giá trị, lỗi mốc footer và lỗi ownership của mô tả. Đã tái tạo output từ saved evidence và đếm điểm độc lập khớp scorer. Các vấn đề còn lại không được sửa bằng nới validation hoặc đổi nhãn.

## 6. Kiểm thử, nguồn và trạng thái

- Backend **310 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, 5 warnings deprecation; 26 test Giai đoạn 6 là tập con. Dùng SQLite memory/tmp upload, không PostgreSQL.
- 40/40 lượt OCR thật hoàn tất; source/data/nhãn hash, thời gian không cộng lồng, độc lập metric recount và replay Hybrid 10/10 PASS. Baseline V4 được tái sử dụng khớp V4 chạy riêng sau chuẩn hóa kiểu số JSON.
- Module mới: hybrid_v6.py, table_v6.py, profiling.py; CLI chỉ thêm lựa chọn offline và đo thời gian. Test: test_ocr_hybrid_v6.py. Không đổi mã production, V4/V5, table-v3, scorer hoặc cơ chế acceptance.
- Hook đo/capture được giới hạn bằng lock, chỉ cài trong context offline và khôi phục cả khi exception; ảnh cache đóng theo tài liệu. **Chưa phải thiết kế cho API nhiều luồng**. Cần adapter/callback chức năng thay hook global trước khi tích hợp.
- Không chạy paper_view theo mặc định của Hybrid; phép đo này chưa chứng minh chất lượng với phối cảnh mạnh/ảnh nhăn mới. PDF text/scan nhiều trang và mapping raster được unit test, chưa có đo PDF thật mới ở bộ 10 JPEG.

| Hạng mục | Trạng thái |
| --- | --- |
| Prototype/Backend regression, profiling và kiểm tra evidence | PASS về kiểm thử mã/công cụ |
| Cải thiện trên 10 ảnh draft development | PARTIAL, có cải thiện được đo |
| Trích xuất đầy đủ/chính xác mọi trường/bảng | FAIL mục tiêu chất lượng: supplier/MST/tổng/bảng còn lỗi |
| Dữ liệu mới độc lập, xác minh A/B và freeze | BLOCKED chờ dữ liệu/hồ sơ thật |
| CER/WER, ảnh mới đa VAT/PDF nhiều trang, V6 Website/API/PostgreSQL UAT | NOT TESTED |

**Chưa đủ điều kiện tích hợp mặc định hoặc nghiệm thu Task 2.** Ưu tiên tiếp: nhận dạng vùng chữ/số khó và kiểm soát lựa chọn supplier; ghép bảng còn thiếu/sai; mở rộng phép đo trên tập mới đã duyệt. Không tiếp tục chọn cấu hình chỉ để khớp 10 ảnh cũ rồi gọi là tổng quát hóa.

## 7. Kế hoạch nghiệm thu và bằng chứng

- [Kế hoạch bộ độc lập, A/B, freeze và PowerShell](OCR_PHASE6_INDEPENDENT_ACCEPTANCE_PLAN.md). Đã tạo catalog 35 hash, chưa tự init dữ liệu mới/điền nhãn/approved hoặc chạy nghiệm thu.
- [Field/cell/per-document accuracy, Precision/Recall/F1, latency](../../ocr_phase6_development/measured_20261118_172554/REPORT.md)
- [Ảnh nguồn, expected draft/actual, raw, polygon và rejected rows](../../ocr_phase6_development/measured_20261118_172554/ERROR_ANALYSIS.md)
- [Đo từng stage/call, inclusive/exclusive](../../ocr_phase6_development/measured_20261118_172554/PROFILING.json)
- [Audit cuối](../../ocr_phase6_development/measured_20261118_172554/FINAL_VERIFICATION.json)
- [JUnit](../../ocr_phase6_development/backend-tests-final.xml)
- [Lịch sử phát triển](../../ocr_phase6_development/RUN_HISTORY.md)
- [Checkpoint ngoài repository](../../ocr_phase6_development/PHASE6_STATUS.md)

Để chạy offline dùng `python -m tools.ocr_benchmark run --engine tesseract-hybrid-v6` với manifest/dataset-root/split/cpu-threads/output mới như plan; không đổi default Website. Raw inference được lưu trước labels. Không dùng lệnh development để vượt gate nghiệm thu.


## 8. Chốt tiếp tục từ artifact đã lưu

Đã đối chiếu source hiện tại với snapshot benchmark, JUnit 310 PASS và các kết quả JSON đã lưu; không chạy lại benchmark, OCR hoặc pytest trong lượt chốt. Hoàn tất lịch sử các vòng thử nghiệm, danh sách việc còn mở và kiểm tra file UTF-8/liên kết. Đây là hoàn tất hồ sơ Giai đoạn 6, không nâng trạng thái nghiệm thu.

- [Vấn đề còn mở và ưu tiên](OCR_PHASE6_OPEN_ISSUES.md).
- [Rà soát/hash artifact ở lượt tiếp tục](../../ocr_phase6_development/RESUME_REVIEW.json).
- [Danh mục file và checksum cuối](../../ocr_phase6_development/FINAL_ARTIFACTS.json).

Không thay source pipeline hoặc Website/API/default, không thao tác database, ground truth, migration/seed; không commit/push. Chờ dữ liệu độc lập và xác minh A/B theo kế hoạch đã lưu.
