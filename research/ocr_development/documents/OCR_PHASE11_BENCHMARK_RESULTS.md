# Giai đoạn 11 — Kết quả benchmark Hybrid V8

Ngày 20/11/2026. **Chỉ phát triển/hồi quy; chưa nghiệm thu độc lập.** Không đổi ground truth, không đo lại tập frozen Giai đoạn 7. Kết quả trước/sau dùng cùng 8 nguồn có SHA-256 khác nhau, không tính các lần upload trùng thành mẫu độc lập.

## Dữ liệu và cách đo

- 3 JPEG thật đã dùng phát triển: retail/RVQA_00000505, supermarket/RVQA_00000022, units/RVQA_00001100. Nhãn tham khảo đọc ảnh từ G10, chưa được con người A/B phê duyệt; không coi là ground truth nghiệm thu.
- 5 synthetic hồi quy từ bộ cũ: PDF text hai trang, PDF scan Việt–Anh, VAT chụp nghiêng JPEG, bill PNG không bảng/MST, PDF ba mức VAT. Nhãn do bộ sinh cung cấp, không là hóa đơn thật độc lập.
- 32 lượt inference (8 × current/V6/V7/V8), Tesseract v5.5.3.20260724, vie+eng, cùng Python/CPU, chạy nối tiếp, OMP_THREAD_LIMIT=1, max_pages=12. Không DB trong benchmark. Giữ kết quả thăm dò riêng; số dưới đây lấy output cuối của V8 sau sửa và baseline cùng điều kiện. Không đo cold/warm lặp nhiều lần, p95/RAM/VRAM chưa có bằng chứng.
- Giữ raw text, polygon, OCR score và transform riêng cho từng view. Source manifest/hash ở [BENCHMARK_INPUTS.json](../../ocr_phase11_development/BENCHMARK_INPUTS.json); kết quả ở [BENCHMARK.json](../../ocr_phase11_development/BENCHMARK.json), [SCORES.json](../../ocr_phase11_development/SCORES.json), script [score.py](../../ocr_phase11_development/score.py).
- Exact = giá trị thô bằng nhau (số so Decimal); normalized = NFC, casefold, gộp khoảng trắng và alias đơn vị áp dụng **giống nhau cho cả bốn engine**. Không bỏ dấu tiếng Việt khỏi tên/mô tả. `GOI` → `Gói` có thể giảm exact nhưng normalized bằng nhau; báo cả hai, không giấu sự khác biệt biểu diễn.
- Accuracy = số đúng / số trường có nhãn dương đủ rõ. Null/vắng không được cộng điểm đúng; hai mô tả ANAN chưa đọc chắc loại khỏi mẫu số và khỏi 2 dòng fully-scorable. Ảnh thật có 9 dòng, chỉ 7 dòng đủ tất cả ô để chấm exact toàn dòng; 40 ô được chấm riêng.
- Missing rate = số actual null / số nhãn dương được chấm. Kiểm tra các trường được nhãn xác định vắng riêng; V8 không có hallucination trong phạm vi absent checks này. Không suy rộng ra mọi trường/ảnh chưa gán nhãn.
- Fallback offline = **N/A**: gọi trực tiếp engine, không chạy bridge/fallback. 32/32 hoàn tất không exception không đồng nghĩa OCR đúng.

## So sánh tổng hợp

### 3 ảnh thật đã dùng phát triển

| Pipeline | Field exact / normalized | Ô dòng hàng exact | Ô normalized | Dòng exact | Dòng normalized | Trường thiếu | Ô thiếu | Giây/tài liệu |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | 0/13 (0.00%) | 0/40 (0.00%) | 0/40 (0.00%) | 0/7 (0.00%) | 0/7 (0.00%) | 10/13 | 40/40 | 12.045 |
| v6 | 10/13 (76.92%) | 22/40 (55.00%) | 22/40 (55.00%) | 0/7 (0.00%) | 0/7 (0.00%) | 0/13 | 10/40 | 6.927 |
| v7 | 11/13 (84.62%) | 31/40 (77.50%) | 31/40 (77.50%) | 2/7 (28.57%) | 2/7 (28.57%) | 0/13 | 2/40 | 9.985 |
| v8 | 11/13 (84.62%) | 31/40 (77.50%) | 35/40 (87.50%) | 0/7 (0.00%) | 4/7 (57.14%) | 0/13 | 0/40 | 13.507 |

### 5 chứng từ synthetic hồi quy

| Pipeline | Field exact / normalized | Ô dòng hàng exact | Ô normalized | Dòng exact | Dòng normalized | Trường thiếu | Ô thiếu | Giây/tài liệu |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | 39/42 (92.86%) | 23/45 (51.11%) | 23/45 (51.11%) | 3/11 (27.27%) | 3/11 (27.27%) | 1/42 | 22/45 | 2.276 |
| v6 | 39/42 (92.86%) | 36/45 (80.00%) | 36/45 (80.00%) | 4/11 (36.36%) | 4/11 (36.36%) | 3/42 | 4/45 | 1.518 |
| v7 | 39/42 (92.86%) | 32/45 (71.11%) | 32/45 (71.11%) | 0/11 (0.00%) | 0/11 (0.00%) | 3/42 | 4/45 | 1.773 |
| v8 | 41/42 (97.62%) | 44/45 (97.78%) | 44/45 (97.78%) | 10/11 (90.91%) | 10/11 (90.91%) | 1/42 | 0/45 | 2.157 |

V8 có cải thiện định lượng so V7 trên tập này: ô normalized ảnh thật 31/40 → 35/40, dòng normalized 2/7 → 4/7; synthetic ô 32/45 → 44/45, dòng 0/11 → 10/11, field 39/42 → 41/42. Field ảnh thật giữ 11/13. Exact raw dòng ảnh thật 2/7 → 0/7 do canonical hóa đơn vị; không được gọi mọi chỉ số đều tăng. Đây không là bằng chứng tổng quát hóa trên hóa đơn mới.

Hiệu năng ảnh thật V8 13.507 giây so V7 9.985 giây, tăng khoảng 35%; V6 6.927 giây. Nhánh OCR paper-view thêm chi phí, chưa chứng minh cải thiện tốc độ. Không đánh đổi độ chính xác bằng tắt cảnh báo.

## Từng tài liệu và từng pipeline

| Mẫu | Pipeline | Field normalized | Ô normalized | Dòng đầy đủ normalized | Số dòng nhận/nhãn | Tổng dòng nhận | Tổng phải trả nhận | Giây |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| retail | current | 0/4 (0.00%) | 0/4 (0.00%) | 0/1 (0.00%) | 0/1 | 0 | None | 9.021 |
| retail | v6 | 1/4 (25.00%) | 3/4 (75.00%) | 0/1 (0.00%) | 1/1 | 53000 | None | 6.403 |
| retail | v7 | 2/4 (50.00%) | 3/4 (75.00%) | 0/1 (0.00%) | 1/1 | 53000 | None | 8.020 |
| retail | v8 | 2/4 (50.00%) | 3/4 (75.00%) | 0/1 (0.00%) | 1/1 | 53000 | None | 10.084 |
| supermarket | current | 0/5 (0.00%) | 0/8 (0.00%) | 0/2 (0.00%) | 0/2 | 0 | None | 15.610 |
| supermarket | v6 | 5/5 (100.00%) | 6/8 (75.00%) | 0/2 (0.00%) | 2/2 | 95800 | 95800.0 | 7.189 |
| supermarket | v7 | 5/5 (100.00%) | 6/8 (75.00%) | 0/2 (0.00%) | 2/2 | 95800 | 95800.0 | 8.786 |
| supermarket | v8 | 5/5 (100.00%) | 6/8 (75.00%) | 0/2 (0.00%) | 2/2 | 95800 | 95800.0 | 12.225 |
| units | current | 0/4 (0.00%) | 0/28 (0.00%) | 0/4 (0.00%) | 0/6 | 0 | None | 11.505 |
| units | v6 | 4/4 (100.00%) | 13/28 (46.43%) | 0/4 (0.00%) | 5/6 | 121000 | 116000 | 7.189 |
| units | v7 | 4/4 (100.00%) | 22/28 (78.57%) | 2/4 (50.00%) | 6/6 | 146000 | 116000 | 13.150 |
| units | v8 | 4/4 (100.00%) | 26/28 (92.86%) | 4/4 (100.00%) | 6/6 | 116000 | 116000 | 18.211 |
| pdf_text | current | 9/9 (100.00%) | 10/15 (66.67%) | 2/3 (66.67%) | 2/3 | 362000.0 | 479600.0 | 0.048 |
| pdf_text | v6 | 8/9 (88.89%) | 12/15 (80.00%) | 0/3 (0.00%) | 3/3 | 436000 | 479600 | 0.050 |
| pdf_text | v7 | 8/9 (88.89%) | 12/15 (80.00%) | 0/3 (0.00%) | 3/3 | 436000 | 479600 | 0.069 |
| pdf_text | v8 | 9/9 (100.00%) | 15/15 (100.00%) | 3/3 (100.00%) | 3/3 | 436000 | 479600 | 0.116 |
| pdf_scan | current | 10/11 (90.91%) | 5/5 (100.00%) | 1/1 (100.00%) | 1/1 | 210000.0 | 231000.0 | 3.728 |
| pdf_scan | v6 | 11/11 (100.00%) | 5/5 (100.00%) | 1/1 (100.00%) | 1/1 | 210000 | 231000 | 2.133 |
| pdf_scan | v7 | 11/11 (100.00%) | 4/5 (80.00%) | 0/1 (0.00%) | 1/1 | 210000 | 231000 | 2.318 |
| pdf_scan | v8 | 11/11 (100.00%) | 5/5 (100.00%) | 1/1 (100.00%) | 1/1 | 210000 | 231000 | 2.392 |
| F3-VAT | current | 8/9 (88.89%) | 0/8 (0.00%) | 0/2 (0.00%) | 0/2 | 0 | 232200.0 | 4.705 |
| F3-VAT | v6 | 9/9 (100.00%) | 6/8 (75.00%) | 0/2 (0.00%) | 2/2 | 215000 | 232200 | 2.600 |
| F3-VAT | v7 | 9/9 (100.00%) | 6/8 (75.00%) | 0/2 (0.00%) | 2/2 | 215000 | 232200 | 3.447 |
| F3-VAT | v8 | 9/9 (100.00%) | 8/8 (100.00%) | 2/2 (100.00%) | 2/2 | 215000 | 232200 | 4.507 |
| F3-POS | current | 4/5 (80.00%) | 0/4 (0.00%) | 0/2 (0.00%) | 0/2 | 0 | 46000.0 | 2.880 |
| F3-POS | v6 | 4/5 (80.00%) | 0/4 (0.00%) | 0/2 (0.00%) | 0/2 | 0 | 46000 | 2.759 |
| F3-POS | v7 | 4/5 (80.00%) | 0/4 (0.00%) | 0/2 (0.00%) | 0/2 | 0 | 46000 | 2.956 |
| F3-POS | v8 | 4/5 (80.00%) | 3/4 (75.00%) | 1/2 (50.00%) | 2/2 | 46000 | 46000 | 3.694 |
| F3-VAT-GROUP | current | 8/8 (100.00%) | 8/13 (61.54%) | 0/3 (0.00%) | 2/3 | 408000.0 | 475040.0 | 0.020 |
| F3-VAT-GROUP | v6 | 7/8 (87.50%) | 13/13 (100.00%) | 3/3 (100.00%) | 3/3 | 438000 | 475040 | 0.048 |
| F3-VAT-GROUP | v7 | 7/8 (87.50%) | 10/13 (76.92%) | 0/3 (0.00%) | 3/3 | 438000 | 475040 | 0.076 |
| F3-VAT-GROUP | v8 | 8/8 (100.00%) | 13/13 (100.00%) | 3/3 (100.00%) | 3/3 | 438000 | 475040 | 0.075 |

## Từng trường và ô dòng hàng (normalized)

### Ảnh thật phát triển: từng trường

| Trường | current | V6 | V7 | V8 |
| --- | --- | --- | --- | --- |
| document_type | 0/3 (0.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| invoice_date | 0/3 (0.00%) | 2/3 (66.67%) | 3/3 (100.00%) | 3/3 (100.00%) |
| invoice_number | 0/2 (0.00%) | 1/2 (50.00%) | 1/2 (50.00%) | 1/2 (50.00%) |
| seller_name | 0/3 (0.00%) | 2/3 (66.67%) | 2/3 (66.67%) | 2/3 (66.67%) |
| total_amount | 0/2 (0.00%) | 2/2 (100.00%) | 2/2 (100.00%) | 2/2 (100.00%) |

| Ô dòng hàng | current | V6 | V7 | V8 |
| --- | --- | --- | --- | --- |
| amount | 0/9 (0.00%) | 7/9 (77.78%) | 8/9 (88.89%) | 9/9 (100.00%) |
| description | 0/7 (0.00%) | 1/7 (14.29%) | 4/7 (57.14%) | 4/7 (57.14%) |
| quantity | 0/9 (0.00%) | 6/9 (66.67%) | 8/9 (88.89%) | 9/9 (100.00%) |
| unit | 0/6 (0.00%) | 1/6 (16.67%) | 2/6 (33.33%) | 4/6 (66.67%) |
| unit_price | 0/9 (0.00%) | 7/9 (77.78%) | 9/9 (100.00%) | 9/9 (100.00%) |

### Synthetic hồi quy: từng trường

| Trường | current | V6 | V7 | V8 |
| --- | --- | --- | --- | --- |
| buyer_name | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) |
| buyer_tax_code | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) |
| document_type | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) |
| invoice_date | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) |
| invoice_number | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) |
| seller_name | 3/5 (60.00%) | 2/5 (40.00%) | 2/5 (40.00%) | 4/5 (80.00%) |
| seller_tax_code | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) |
| subtotal | 3/4 (75.00%) | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) |
| total_amount | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) |
| vat_amount | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) |
| vat_rate | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |

| Ô dòng hàng | current | V6 | V7 | V8 |
| --- | --- | --- | --- | --- |
| amount | 5/11 (45.45%) | 9/11 (81.82%) | 9/11 (81.82%) | 11/11 (100.00%) |
| description | 5/11 (45.45%) | 4/11 (36.36%) | 0/11 (0.00%) | 10/11 (90.91%) |
| quantity | 5/8 (62.50%) | 8/8 (100.00%) | 8/8 (100.00%) | 8/8 (100.00%) |
| unit | 3/4 (75.00%) | 4/4 (100.00%) | 4/4 (100.00%) | 4/4 (100.00%) |
| unit_price | 5/8 (62.50%) | 8/8 (100.00%) | 8/8 (100.00%) | 8/8 (100.00%) |
| vat_rate | 0/3 (0.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |

Ảnh thật không đủ nhãn MST/VAT/buyer để đo các trường này: **NOT TESTED trên hóa đơn thật**. Không dùng 4/4 synthetic tax/VAT làm độ chính xác thật. Multi-rate VAT được giữ ở evidence dòng hàng; không tự tạo một VAT rate chung.

## Row detection — giới hạn phương pháp

**Bảng này chỉ là proxy theo số lượng dòng, không phải precision/recall/F1 ghép dòng theo polygon hoặc ngữ nghĩa.** TP=min(số nhận,số nhãn), FP=max(nhận−nhãn,0), FN=max(nhãn−nhận,0). P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN). Đúng số lượng vẫn có thể sai tên/ô; phải đọc cùng accuracy dòng/cell phía trên. Row spatial/semantic F1: NOT TESTED vì chưa có nhãn polygon ghép dòng độc lập.

| Nhóm | Engine | TP/FP/FN theo số lượng | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- |
| real_development | current | 0/0/9 | 0.000 | 0.000 | 0.000 |
| real_development | v6 | 8/0/1 | 1.000 | 0.889 | 0.941 |
| real_development | v7 | 9/0/0 | 1.000 | 1.000 | 1.000 |
| real_development | v8 | 9/0/0 | 1.000 | 1.000 | 1.000 |
| synthetic_regression | current | 5/0/6 | 1.000 | 0.455 | 0.625 |
| synthetic_regression | v6 | 9/0/2 | 1.000 | 0.818 | 0.900 |
| synthetic_regression | v7 | 9/0/2 | 1.000 | 0.818 | 0.900 |
| synthetic_regression | v8 | 11/0/0 | 1.000 | 1.000 | 1.000 |

## Lỗi V8 còn lại so nhãn tham khảo

| Mẫu | Trường | Nhãn tham khảo | V8 actual | Lớp lỗi |
| --- | --- | --- | --- | --- |
| retail | seller_name | CỬA HÀNG NĂM OÁNH | CUA HANG NAM OÁNH | OCR/field |
| retail | invoice_number | SON55644 | SON45644 | OCR/field |
| retail | row1.description | Phở bò Đệ Nhất 65g | Phở bò Dé Nhat 65g | OCR/unit/description |
| supermarket | row1.description | CHIN-SU Nước mắm hương cá hồi chai 500ml | CHIN-SU Nước mắm hƯơng cá hồi chai 500m] | OCR/unit/description |
| supermarket | row2.description | Bánh mỳ Paket Bảo Ngọc 108g | Banh mỳ Paket BẢo NGỌC 108g | OCR/unit/description |
| units | row1.unit | GOI | GOT | OCR/unit/description |
| units | row2.unit | GOI | Got | OCR/unit/description |
| F3-POS | seller_name | Quán Gió Đồng | None | OCR/field |
| F3-POS | row1.description | Xôi vò | XÔI vO | OCR/unit/description |

## Phân tích từng mẫu

- **retail**: ngày 2020-08-12 giữ đúng; số SON45644 chưa khớp SON55644, supplier/mô tả còn mất/sai dấu. Model 65g giữ lại. 1 dòng q10, giá5300, amount53000 đúng. Total không quan sát được giữ null; không dùng subtotal điền total. Chỉnh sửa thủ công sau upload không được dùng để nâng điểm benchmark.
- **supermarket**: 2 dòng tài chính đúng (2×37900=75800; 2×10000=20000), total95800; còn chữ `500m]` và dấu sai. Không gộp thông tin khuyến mãi thành dòng mới. Subtotal null nên ITEM-SUM vẫn báo cần kiểm tra ở API.
- **units/ANAN**: V7 tổng146000 → V8 tổng116000 từ 6 amount quan sát được. Row2 quantity1 có crop PSM7; unit_price10000 có nhiều read độc lập; amount10000 có crop PSM13 trong khi read khác40000. Phép tính chỉ chọn bộ q/p/a có OCR evidence, không tạo amount hoặc lấy total để phân bổ. Hai dòng cuối giữ **giá bán6250**, không giá đăng ký6500. q/p/amount 9/9 trên toàn ảnh thật; 2 đơn vị đầu GOT/Got chưa giải được. Không tự đổi chúng thành Gói. Subtotal không in rõ giữ null, **ITEM-SUM vẫn false** theo validator hiện có dù tổng dòng bằng total. Đây không phải regression do nới validation.
- **pdf_text**: 2 trang/3 dòng giữ thứ tự; `for nitrogen circuit` thuộc mô tả row1, không gắn row2; bỏ STT theo cột thực, giữ NV30/T12. Supplier có explicit label được phục hồi từ text layer, không gán OCR confidence giả. Subtotal436000, VAT43600, total479600; không mất trường V6/V7 đã đúng.
- **pdf_scan**: Việt–Anh/1 trang; description không STT; Cái, q2, giá105000, amount210000; subtotal210000, VAT21000, total231000 đúng nhãn synthetic.
- **F3-VAT**: ảnh nghiêng synthetic 2 sản phẩm, tách quantity khỏi mô tả; tài chính đúng.
- **F3-POS**: 2 dòng chỉ có amount28000/18000; q/unit_price/unit null không bị suy ra. Seller thiếu và tên Xôi vò sai dấu vẫn FAIL.
- **F3-VAT-GROUP**: 3 dòng/3 VAT8%,10%,0% giữ riêng trong evidence; không gán VAT chung để ép tổng.

## Điều kiện chưa đạt

NFR01 theo SRS nêu tối thiểu 85% theo trường trên 100–500 hóa đơn; cách tổng hợp/line threshold còn cần thống nhất trước đo. 3 ảnh development với nhãn AI chưa duyệt không đủ để xác nhận NFR, kể cả 87.5% ô normalized. Tập thật mới đã A/B, VAT thật/PDF thật/multipage thật, kiểm tra discount phức tạp, ảnh nhăn/bóng nặng, PDF mixed text/scan đa bố cục và mọi ngôn ngữ chưa có coverage nghiệm thu: **BLOCKED/NOT TESTED**. CER/WER không báo vì không có transcription đã xác minh. Chưa có sign-off của Product Owner.
