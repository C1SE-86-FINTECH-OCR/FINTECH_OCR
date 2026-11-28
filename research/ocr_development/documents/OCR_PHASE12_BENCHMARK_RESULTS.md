# Giai đoạn 12 — Benchmark và hiệu năng

Ngày 20/11/2026. **Không có benchmark độc lập mới đủ điều kiện.** 0 chứng từ/0 nhãn A-B được đưa vào chấm; không có prediction nghiệm thu mới. Mọi accuracy/latency mới là N/A, không phải0% hay100%. Không chạy lại bộ frozen24 G7 hoặc dùng ảnh synthetic/development làm independent.

## Kết quả G12 trên dữ liệu độc lập

| Pipeline | Nguồn độc lập đủ điều kiện | Field / dòng / tài chính | Latency / timeout / fallback | Trạng thái |
| --- | --- | --- | --- | --- |
| current | 0 | N/A — chưa đo | N/A — chưa đo | BLOCKED |
| Hybrid V6 frozen | 0 | N/A — chưa đo | N/A — chưa đo | BLOCKED |
| Hybrid V7 | 0 | N/A — chưa đo | N/A — chưa đo | BLOCKED |
| Hybrid V8 | 0 | N/A — chưa đo | N/A — chưa đo | BLOCKED |

Chưa có bảng per-invoice vì không có invoice mới đủ điều kiện. Không tạo dòng P12 giả để lấp báo cáo. G11#42–47 là dữ liệu cũ, đã dùng phát triển/UAT; API sau correction không dùng làm output OCR gốc để chấm.

Các chỉ số độc lập chưa đo: exact/normalized field, number/date/supplier/tax/subtotal/VAT/total, line-item, quantity/unit/price/amount/discount, missing/hallucination, full-document accuracy, row detectionP/R/F1, arithmetic/ITEM-SUM, fallback/timeout/success rate. CER/WER thiếu transcription A/B. CPU/RAM/VRAM và cold/warm inference mới NOT TESTED.

## Phương pháp phải chốt trước inference

- Chỉ trường đã được con người xác minh: positive accuracy=số đúng/số field nguồn có giá trị; absent check riêng cho OCR tự tạo giá trị; illegible/cropped/unreviewed không coi là missing hay null đúng.
- Exact thô và normalized tách riêng; NFC/whitespace và alias unit phải áp dụng giống nhau cho mọi engine; quy tắc case/dấu/unit phải đóng trước đo. Không sửa đáp án/normalizer sau nhìn kết quả để nâng điểm. Giữ leading zero và dấu Việt đúng scope.
- Dòng hàng ghép one-to-one, giữ duplicate thật bằng multiset. Precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN). TP full-row exact là chỉ số trích xuất, **khác detection theo polygon/IoU**. Count-only proxy G11 không chứng minh cell ownership; cần nhãn geometry và ngưỡng trước đo cho geometric row detection.
- Chấm quantity/unit/price/amount/VAT/discount riêng; dòng thiếu/thừa và số tiền sai không được loại mẫu để tăng điểm. Luôn báo mẫu số nguồn/ô được chấm, unknown loại trừ và unsupported fields. Công cụ cũ có field currency, unit/page/VAT; metricdiscount chuyên biệt/matching mới phải chốt trước khi gọi bao phủ đầy đủ.
- ITEM-SUM giữ nguyên business validation; không dùng sum(payable) suy subtotal/VAT hoặc cân dòng. Cảnh báo và OCR evidence không thay thế kết quả đúng.
- Full-document accuracy chỉ trên nhãn approved đủ trường thực sự hiện diện và toàn bảng; correction không thành OCR đúng. Engine failed/timeout vẫn trong denominator xử lý.
- Fallback tự nhiên=số request thật phải fallback/số request thử; fault injection phải báo riêng. Offline direct engine không có fallback bridge thì N/A, không gán0%.
- Cùng bytes/source/phiên bản/threads/maxpages/máy/phương pháp; giữ text/box/score, sai số và failed outputs. Ghi mỗi lượt engine/HTTP riêng; mean=sum/n; median; P95 nearest-rank ceil(.95n); min/max; số lượt cold/warm. RAM/CPU có monitoring thật mới báo.
- NFR01>=85% trên100–500; pilot30–50 chưa thay thế. Ngưỡng dòng/tài chính/latency và cách weighting chờ PO; không tự hạ.

Hồ sơ: [ENGINE_FREEZE.json](../../ocr_phase12_acceptance/ENGINE_FREEZE.json), [CRITERIA_PENDING_PO.json](../../ocr_phase12_acceptance/CRITERIA_PENDING_PO.json), [READINESS.json](../../ocr_phase12_acceptance/READINESS.json).

## Số liệu G11 cũ để tham khảo — không là kết quả G12

Không inference lại. Chỉ đọc output/scoring đã lưu ở G11 và tổng hợp thống kê; 3 bill thật development, 5 synthetic hồi quy, 8 nguồn khác SHA. Các nhãn thật này chưa phải A/B nghiệm thu. Bảng dưới normalized theo scorerG11, không phải phương pháp mới được PO phê duyệt.

| Bộ G11 | Pipeline | Field normalized | Ô normalized | Dòng normalized | Mean s |
| --- | --- | --- | --- | --- | --- |
| real_development | current | 0/13 | 0/40 | 0/7 | 12.045 |
| real_development | v6 | 10/13 | 22/40 | 0/7 | 6.927 |
| real_development | v7 | 11/13 | 31/40 | 2/7 | 9.985 |
| real_development | v8 | 11/13 | 35/40 | 4/7 | 13.507 |
| synthetic_regression | current | 39/42 | 23/45 | 3/11 | 2.276 |
| synthetic_regression | v6 | 39/42 | 36/45 | 4/11 | 1.518 |
| synthetic_regression | v7 | 39/42 | 32/45 | 0/11 | 1.773 |
| synthetic_regression | v8 | 41/42 | 44/45 | 10/11 | 2.157 |

Chi tiết raw exact, normalization, lỗi per-document/per-cell và số mẫu trong [báo cáo G11](OCR_PHASE11_BENCHMARK_RESULTS.md). Không giấu raw unit representation regression: dòng exact ảnh thật V7=2/7, V8=0/7 do đơn vị canonical; normalized tương ứng2/7 và4/7. Không tính đây là mọi chỉ số đều tăng.

## Hiệu năng G11 tính lại từ thời gian đã có

| Nguồn G11 | Pipeline | n | Mean s | Median s | P95 s | Min s | Max s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| real_development | current | 3 | 12.045 | 11.505 | 15.610 | 9.021 | 15.610 |
| real_development | v6 | 3 | 6.927 | 7.189 | 7.189 | 6.403 | 7.189 |
| real_development | v7 | 3 | 9.985 | 8.786 | 13.150 | 8.020 | 13.150 |
| real_development | v8 | 3 | 13.507 | 12.225 | 18.211 | 10.084 | 18.211 |
| synthetic_regression | current | 5 | 2.276 | 2.880 | 4.705 | 0.020 | 4.705 |
| synthetic_regression | v6 | 5 | 1.518 | 2.133 | 2.759 | 0.048 | 2.759 |
| synthetic_regression | v7 | 5 | 1.773 | 2.318 | 3.447 | 0.069 | 3.447 |
| synthetic_regression | v8 | 5 | 2.157 | 2.392 | 4.507 | 0.075 | 4.507 |

3/5 nguồn mỗi nhóm chỉ một lượt mỗi pipeline; P95 tiny-n bằngmax, không ổn định và không là SLA. Ảnh thật development V8 mean13.507s vsV7 9.985s, tăng khoảng35.3%; không có bằng chứng speedup. Cold/warm chưa tách trong dữ liệu cũ, không tối ưu hoặc chạy OCR thêm trong G12. [HISTORICAL_G11_PERFORMANCE.json](../../ocr_phase12_acceptance/HISTORICAL_G11_PERFORMANCE.json).

Máy kiểm tra hiện tại: Intel Core i5-12450HX, 8 cores/12 threads; RAM16,873,545,728bytes (~15.7GiB); có Intel UHD/RTX2050 nhưng Tesseract chạyCPU, không đo VRAM. Python3.14.7, Tesseract v5.5.3.20260724; vie/eng; phiên bản thư viện/exe hash được lưu trong freeze. `numpy`, `opencv-python`, `psutil` không cài trong venvBackend; không tự cài thêm. Dữ liệu phần cứng hiện tại không thay phép đo tải/RAM thực khi inference.

## Lỗi còn tồn tại (bằng chứng G11, chưa chạy độc lập G12)

- Retail seller/mô tả sai dấu, invoice suffix45644 khác55644; không sửa V8 theo nhãn trong lượt này.
- Supermarket descriptions còn `500m]`/dấu sai; tiền đúng trong phạm vi nhãn development.
- ANAN q/p/amount đã được đọc bằng OCR thật ở G11, tổng116000;2unit GOT/Got chưa rõ. Subtotalnull khiến ITEM-SUM vẫnfalse, không bỏ rule.
- Headerless synthetic POS thiếu seller/sai dấu tên món; không dùng nó chứng minh bill thật chưa gặp.
- PDF text/scan/multipage cải thiện trên synthetic; coverage VAT/PDF thật mới, chiết khấu phức tạp, nhăn/bóng/mixed-PDF còn thiếu.

## Lựa chọn pipeline và kết luận

**D — Không đủ dữ liệu độc lập.** Chưa chọn phiên bản chính thức, giữ current mặc định và V8 test. Tương thích hệ thống: regression412 Backend/36 Web/buildPASS và login+GETBrowser36 checks có bằng chứng mới; không biến chúng thành accuracy. Cần dataset thật mới A/B, tiêu chí chốt, freeze nhãn và harness bốn phiên bản/evaluator đã kiểm trước prediction. Không tự chạy benchmark G7, phát triểnV9 hoặc chuyểnG13.
