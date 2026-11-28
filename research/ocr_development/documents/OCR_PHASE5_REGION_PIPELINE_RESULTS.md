# Giai đoạn 5 — OCR V5 nhận diện vùng thử nghiệm

Ngày 18/11/2026. Repository `FINTECH_OCR_GitHub`, nhánh `feature/thien`. **Đã triển khai và đo thật; chưa đạt chất lượng để tích hợp mặc định hoặc nghiệm thu.**

Giữ nguyên Tesseract làm engine, PaddleOCR/table-v3 và V4 để đối chứng/rollback. V5 chỉ là lựa chọn offline `tesseract-region-v5`; không import vào app/API, không thay Website, .env, CORS, schema, kết nối hoặc dữ liệu database. Không cài mô hình, gọi dịch vụ AI bên ngoài hoặc commit/push.

## Phạm vi bằng chứng

- Mở lại trực tiếp 10 ảnh JPEG gốc, đối chiếu raw OCR, polygon, nhóm dòng và output V4. Các hình là dữ liệu thật đã dùng phát triển; không phải 10 hóa đơn độc lập để nghiệm thu.
- Ground truth gốc và bộ nhãn draft đọc rõ giữ nguyên hash. Chỉ chấm trường có nhãn; tách giá trị vắng khỏi accuracy trên trường có in. Có 7 bảng/16 dòng đủ nhãn nháp để chấm exact 4 ô. Bảng ANAN, hai dòng dịch vụ vé và các trường mờ chưa chốt không chấm.
- Chạy mới cả ba nhánh tuần tự, cùng 10 SHA-256, nhãn, máy, 1 CPU thread ceiling, Python hashseed 0 và source snapshot. Không tái dùng prediction cũ làm kết quả chạy mới. Chấm nháp sau khi lưu prediction; không đưa nhãn vào parser.
- Nhãn vẫn draft, chưa có A/B thật, không freeze hoặc bỏ qua gate nghiệm thu. Không có transcription đã xác minh nên CER/WER NOT TESTED. Không khẳng định OCR tổng quát hay đạt benchmark độc lập.

## Nguyên nhân và cải tiến

1. Text phẳng/cluster y đơn thuần làm lẫn header, thông tin liên hệ, số model và footer vào bảng. V5 dùng nhóm block/paragraph/line thực từ TSV Tesseract, nhận tiêu đề/cột, tách khoảng header–table–footer và giữ tọa độ nguồn.
2. Nền ảnh xám/nâu, phối cảnh giấy, cỡ glyph khác nhau và nhiễu làm OCR sai dấu/số. Dùng component giấy có giới hạn và phép QUAD chỉ khi bao phủ an toàn; chuyển bbox/original khi không đủ bằng chứng. EXIF/PIL, autocontrast và đọc theo vùng vie+eng/vie; không tự dựng lại chữ. Một phiên bản crop ban đầu cắt mép đã bị loại, giữ lịch sử lỗi.
3. Tỷ lệ resize dự kiến khác resize thực có thể làm crop đọc lại sai vị trí. Đã map theo kích thước ảnh thực, giữ transform/bbox/polygon. Header chứa đầy đủ vùng MST trước bảng; footer không được ghi đè supplier.
4. Supplier không còn lấy cả cột địa chỉ/điện thoại cạnh logo, loại nhãn hóa đơn/cột và metadata; dùng vị trí, typography, ngữ cảnh pháp nhân và các lượt đọc. Tuy nhiên nhiều dấu/case/logo vẫn sai; consensus các lượt OCR tương quan không bảo đảm đúng.
5. MST chỉ nhận theo nhãn MST/tax, tách ngữ cảnh người mua. Có đọc lại vùng số thực, giữ leading zero. Bill không có MST giữ null. Không đổi ký tự OCR lỗi thành MST đoán; hai MST trong tập này vẫn chưa khớp.
6. Số hóa đơn có thể nằm cạnh ngày ở cột phải; đọc theo nhãn, không lấy số giao dịch hay ngày. Tổng cuối đọc theo nhãn footer, tách tiền khách đưa/thối/NOW/commission; không suy VAT hoặc tổng bằng cộng dòng.
7. Bảng dựa tiêu đề/cột và dòng OCR, loại metadata, dòng tổng/giảm giá/ghi chú quà; giữ null khác 0. Ô số chưa parse được vẫn giữ evidence để OCR lại. Chỉ nhận thay đổi có ít nhất hai lượt đọc số thực đồng ý, không điền từ amount/price. Chặn thêm dấu âm không có trong cell OCR gốc; giữ nguyên số cũ và cảnh báo. Giữ hàng V4 đủ ô, nhất quán và có đối chiếu bằng chứng khi hàng vùng thiếu/không nhất quán.
8. Loại ứng viên số model dính mô tả khi không có SL/đơn giá, ngay sau là dòng giá/thành tiền riêng và không có bằng chứng đó là hàng độc lập. Giữ raw và lý do loại để review. Không loại chỉ bằng ngưỡng giá tiền hay tên thương hiệu.
9. PDF có text giữ đường cũ; PDF scan xử lý từng trang, trang sau không ghi đè trường đã có ở trang đầu. XML đi nguyên V4. Nhánh scan nhiều trang/XML được kiểm tra bằng fixture/unit, chưa có PDF thực mới trong 10 ảnh này.
10. Giữ tất cả dữ liệu đọc được, candidates/xung đột, OCR score, crop transform và warnings. `requires_review=True`, `EXPERIMENTAL_UNVERIFIED`; word confidence không phải field accuracy hay verified tax.

## Kết quả thực đo trên nhãn draft

| Chỉ số | Current | V4 | V5 |
| --- | --- | --- | --- |
| Phân loại | 1/9 | 8/9 | 8/9 |
| Số hóa đơn | 0/6 | 3/6 | 4/6 |
| Ngày | 0/9 | 7/9 | 7/9 |
| Nhà cung cấp | 0/10 | 1/10 | 2/10 |
| MST người bán | 0/2 | 0/2 | 0/2 |
| Tiền hàng được in | 0/3 | 3/3 | 3/3 |
| Tổng thanh toán | 0/8 | 5/8 | 6/8 |
| Dòng exact 4 ô | 0/16 | 1/16 | 3/16 |
| Bảng exact | 0/7 | 0/7 | 1/7 |
| TB giây/chứng từ | 12.6706 | 5.1594 | 13.4311 |
| RAM đỉnh MiB | 261.51 | 210.46 | 239.11 |

V5 dự đoán 14 dòng trong 7 bảng được chấm, TP=3, FP=11, FN=13; precision=0.2143, recall=0.1875, F1=0.2000. FP là dòng không khớp đủ bốn ô, không đồng nghĩa mọi FP là sản phẩm bịa. Xem từng ô và từng ảnh trong bảng đầy đủ.

Không mất trường V4 đang khớp trong bộ nhãn chấm (kể cả absent): 0 hồi quy. Dòng V4 đúng bị mất: 0. Đây là bảo toàn trên tập này, không chứng minh không hồi quy mọi tài liệu.

Hạn chế phải giữ rõ: bộ chặn model mới có unit test PASS nhưng **0 ứng viên bị loại trong lần chạy 10 ảnh cuối**; hai anchor giả `12` ở ảnh siêu thị vẫn còn. Không coi test tổng hợp này là bằng chứng đã xử lý được lỗi trên ảnh thật. Guard dấu âm có tác dụng thực tế: giữ amount 20600 khi hai lượt đọc ô nhiễu trả -20600, kèm cảnh báo thay vì ghi số âm mới. Precision ô unit_price theo scorer giảm từ 28,6% xuống 25,0%, recall vẫn 15,4%; không khẳng định mọi ô số đều cải thiện.

Các trường chưa có mẫu đủ nhãn như buyer MST, VAT amount, invoice symbol/currency không báo accuracy. Buyer name và VAT rate còn sai; số đúng subtotal ít mẫu không phải chứng minh mọi loại VAT. RAM là sampled Windows process-tree working set, gồm Tesseract con; VRAM N/A trên CPU. V5 gồm chi phí V4 fallback cộng nhiều lượt đọc vùng, chậm hơn V4. Một lượt đo/nhánh, không phải load test Website.

## Đối chiếu từng chứng từ và lỗi còn lại

| Chứng từ | Kết quả/giới hạn sau V5 |
| --- | --- |
| REAL-001, vé xe trong screenshot nhỏ | OCR chỉ nhận các mảnh tên pháp nhân; số vé/tổng/loại còn sai hoặc thiếu. Nguồn ít pixel và nhiều khoảng trắng; không điền fare/VAT từ kỳ vọng. Bảng dịch vụ chưa chấm. |
| RVQA-00000022, bill bán lẻ | Supplier và số H: lấy được từ vùng header, tổng giữ đúng. SL/giá/tiền có kết quả nhưng tên sản phẩm/dấu còn lệch, chưa bảng exact. |
| RVQA-00000505, bill một dòng so le | Đã có hàng thay vì rỗng; tên/dấu và số lượng còn thiếu. Raw có lượng trên dòng riêng nhưng parser/header chưa luôn ghép được. Ngày và seller chưa exact. Không suy tổng khi nguồn chưa chốt. |
| RVQA-00000509, nhiều mã hàng/dòng numeric riêng | Giữ hàng V4 đúng; mô tả tràn cột và số model vẫn có thể làm anchor giả; bộ chặn mới chỉ xử lý trường hợp đủ dấu hiệu hình học, không giải quyết hết các dòng có nhiễu/ĐVT. MST và dấu tên siêu thị vẫn sai. Một số SL/giá/amount chưa ghép đúng; không ép tổng. |
| RVQA-00000513, bill một dòng | Dòng Nước ép dưa hấu khớp đủ 4 ô; tổng/số/ngày đúng. Supplier vẫn sai dấu, chưa hóa đơn đầy đủ exact. |
| RVQA-00001100, minimart nhiều mã hàng | Các trường scalar được chấm giữ đúng, bảng nhận thiếu/ghép sai. Bảng nhãn chưa duyệt đầy đủ nên không lấy items rỗng hoặc số lượng nhận được để báo PASS. |
| RVQA-00002901, bill nhiệt | Header vie có ứng viên tên có dấu nhưng consensus chọn phiên bản thiếu dấu; MST OCR lẫn ký tự, total còn nhận 71000 thay cho nháp 27000. Mất một sản phẩm và mô tả lẫn cột; đây là lỗi còn mở. |
| RVQA-00002905, phiếu bán/giao hàng có dấu mộc | Giữ tổng 400000; seller, số/ngày, buyer và tên/SL hàng còn sai. Dấu mộc và typography tác động OCR, selection chưa ổn; không tự ghi đè trường nguồn. |
| RVQA-00002910, vé phim | Parser không sinh sản phẩm giả từ ticket chưa phân loại. Tên pháp nhân/rate còn sai/thiếu; loại/total/dịch vụ chưa đủ nhãn chấm, không báo đúng. |
| RVQA-00005500, bill đồ uống/giảm giá/quà | Tổng cuối được đọc đúng từ footer thay cho 460000 của V4; không lấy NOW/cộng lại discount. Có một dòng đủ 4 ô; tên dòng khác/cỡ chữ/lượng và dòng quà còn thiếu, supplier đang lấy địa chỉ cũ. |

Các nhận định dựa đối chiếu ảnh/raw và output; mismatch có thể do nhận dạng ký tự hoặc selection/ghép cột. Đã xác minh scorer bằng đếm riêng và replay bằng chứng, không quy mọi lỗi cho OCR. Chưa có transcription người duyệt nên không đo tỷ lệ lỗi ký tự.

## Kiểm thử và kiểm tra tính toàn vẹn

- Toàn bộ Backend: **284 PASS, 0 FAIL, 0 ERROR, 0 SKIP**; 5 deprecation warnings. 28 test V5 là tập con, không cộng thêm. DATABASE_URL SQLite memory và upload tạm; không ghi PostgreSQL.
- Các test V5: giấy/crop an toàn, scale tọa độ, supplier/contact/footer, MST buyer/seller/leading zero, bill không MST, null/0, model vs hàng, footer total vs cash, reread không đồng thuận/không tự thêm dấu âm, không suy qty, giữ hàng V4, XML và PDF nhiều trang/text fallback. Test hình/mocking không thay bằng chứng OCR thực tế.
- Ba nhánh hoàn tất 30/30 lượt OCR thực; evidence replay và đếm lại độc lập khớp điểm. V4 standalone so với V4 nested trong V5 khớp các trường được chuẩn hóa và bốn ô dòng; không coi khác kiểu số JSON là khác nhận dạng.
- Hash nguồn app/extraction.py, pipeline_v4.py, table_v3.py, scorer và ground truth/nhãn giữ nguyên từ đầu Giai đoạn 5. Source freeze của lượt benchmark cuối không đổi trong lúc chạy.
- Có lưu các vòng V5 chưa đạt: crop ban đầu, sửa pixel mapping và sửa sign/model. Không chỉnh nhãn hoặc xóa lịch sử để tăng điểm.

## Trạng thái và quyết định tích hợp

| Hạng mục | Trạng thái |
| --- | --- |
| Module V5 offline và Backend regression | PASS về kiểm thử mã nguồn |
| Benchmark ba nhánh, hash, metric audit/replay | PASS về thực thi/kiểm tra bằng chứng |
| Chất lượng trích xuất đầy đủ trên dữ liệu phát triển | FAIL mục tiêu chất lượng; đã cải thiện một phần |
| OCR PDF/scan nhiều trang thực, VAT nhiều mức, ảnh mới độc lập | NOT TESTED trong vòng ảnh thật này |
| CER/WER có transcription đã duyệt | NOT TESTED |
| Tập nghiệm thu được hai người xác minh/freeze | BLOCKED, nhãn draft và thiếu hồ sơ A/B |
| API/Website/PostgreSQL với V5 | NOT TESTED, chưa tích hợp theo yêu cầu |

**Chưa đủ điều kiện tích hợp mặc định.** Giữ current/V4 để rollback. Ưu tiên tiếp theo: phân tích quan hệ các ô và dòng mô tả–numeric thay vì chỉ neo amount; xử lý header OCR thiếu cột/SL; cân bằng lựa chọn supplier theo từng vùng/chất lượng thay vì số phiếu OCR tương quan; tái nhận dạng chữ/số khó với bằng chứng. Chỉ thử mô hình layout/recognition khác sau đánh giá tài nguyên và phê duyệt tải/cài. Không tiếp tục thêm ngoại lệ theo cửa hàng.

Chuẩn bị bộ nghiệm thu mới có đa nguồn/bố cục, VAT JPG/PNG/PDF text/scan nhiều trang, người A/B xác minh nhãn và transcription. Freeze trước inference, đo từng trường/bảng và lượng cần review trên cả lỗi; sau đó mới xem xét feature flag tích hợp và UAT upload–review–validation–lưu–mở lại trên DB biệt lập. Không dùng lại 10 ảnh đã phát triển làm bằng chứng tổng quát hóa.

## File thay đổi trong Giai đoạn 5

- `backend/tools/ocr_benchmark/pipeline_v5.py` — module mới độc lập.
- `backend/tools/ocr_benchmark/__main__.py` — thêm engine opt-in, không đổi mặc định.
- `backend/tests/test_ocr_context_v5.py` — 28 test mới; không ghi đè test_ocr_v5.py có sẵn.
- `docs/OCR_PHASE5_REGION_PIPELINE_RESULTS.md` và cập nhật đầu `docs/OCR_PHASE35_ACCEPTANCE_STATUS.md`.
- Ngoài repo: `ocr_phase5_development/` chứa `report_phase5.py`, `describe_phase5.py`, `verify_phase5.py`, `finalize_phase5.py`, source snapshot, probe, prediction/raw, metric, JUnit và checkpoint. Các thay đổi app/extraction.py, Web, test cũ từ trước lượt này được giữ, không sửa thêm trong Giai đoạn 5.

## Bằng chứng

- [Bảng field/line/per-document và latency](../../ocr_phase5_development/measured_20261118_160742/REPORT.md)
- [Ảnh gốc, giá trị kỳ vọng/actual và raw/crop evidence](../../ocr_phase5_development/measured_20261118_160742/ERROR_ANALYSIS.md)
- [Audit hash, replay và đếm lại](../../ocr_phase5_development/measured_20261118_160742/FINAL_VERIFICATION.json)
- [Kết quả JSON ba nhánh](../../ocr_phase5_development/measured_20261118_160742/COMPARISON.json)
- [JUnit Backend](../../ocr_phase5_development/backend-tests-final.xml)
- [Lịch sử V5](../../ocr_phase5_development/RUN_HISTORY.md)
- [Checkpoint ngoài repository](../../ocr_phase5_development/PHASE5_STATUS.md)

Chạy lại offline bằng Python Backend hiện có, từ backend/: `python -m tools.ocr_benchmark run --engine tesseract-region-v5 --manifest <documents.development.csv> --dataset-root <ocr_phase35_acceptance> --split development --cpu-threads 1 --output <THU_MUC_MOI>`; không truyền ground truth cho inference. Để chấm nháp đúng cùng mask, dùng `report_phase5.py <run>` sau khi có ba prediction như plan.json; không gọi đây là lệnh nghiệm thu.
