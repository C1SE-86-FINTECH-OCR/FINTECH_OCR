# Task 2 — Hoàn thiện mã nguồn Hybrid V8 Final, 22/11/2026

**Trạng thái: đã triển khai các phần bổ sung dưới đây; KHÔNG chạy hoặc xác minh thực thi.** Kế thừa G1–G13 và lượt source-link trước đó, không tạo G14. Task 1/Task 3 giữ nguyên. **NFR01 chưa được nghiệm thu độc lập.**

## Phạm vi đã triển khai trực tiếp

1. **Thông tin chứng từ có nhãn:** nhận số hóa đơn/số phiếu, ký hiệu, ngày, subtotal, VAT, payable và currency từ nhãn rõ. Hỗ trợ nhãn/value cùng dòng có hoặc không có dấu hai chấm và value ở dòng gần phía dưới. Giữ số 0 đầu; không đổi O thành 0, không suy số phiếu thành hóa đơn VAT. Trường khó đọc giữ baseline/null và cảnh báo.
2. **Seller/buyer/MST:** giữ liên kết role và label/value/evidence; nhận role ghi trong ngoặc như MST (người mua), không lấy role khi các nhãn mâu thuẫn. Ghép tên đơn vị xuống dòng có giới hạn khoảng cách/cột, dừng ở nhãn/metadata/số tiền/bảng. Điểm dùng để xét ứng viên lấy cả token của giá trị, không chỉ label. Crop seller chỉ bỏ tiền tố nhãn seller thực sự nhận diện, không cắt tên doanh nghiệp có dấu hai chấm một cách mù quáng.
3. **Chọn giá trị khi mâu thuẫn:** gom ứng viên đa trang, ưu tiên tầng nguồn PDF text/nhãn và số read hỗ trợ. Các giá trị khác nhau có mức hỗ trợ ngang nhau không bị chọn chỉ vì hơn một chút confidence; giữ giá trị trước đó và cảnh báo. Không ưu tiên thêm dấu một cách tự động để đổi danh tính. Literal/alternative/selected/source vẫn được lưu.
4. **Bảng tiếp trang:** chuyển tọa độ cột đã quan sát sang trang liền kề khi khổ/aspect phù hợp; dừng nếu số chứng từ xung đột hoặc trang trước có tổng cuối. Không coi carry-forward/page total là tổng cuối. Không truyền cột qua trang không có hàng hoặc không có cấu trúc bảng đủ. Không gộp các dòng có cùng tên/giá ở các trang khác nhau thành một sản phẩm.
5. **Bill không bảng rõ, chỉ có tên và thành tiền:** bổ sung đường đọc amount-only khi parser trước không có hàng; yêu cầu classification phù hợp, token tiền định dạng rõ ở box tách bên phải, tên có evidence và không thuộc metadata/summary. Hỗ trợ một dòng rõ; quantity/unit/unit_price giữ null. Không copy tổng thanh toán thành một sản phẩm.
6. **Liên kết ô và baseline:** tiếp tục span/token và matching một-một đã có; giữ amount-only nếu có bằng chứng hình học. Loại đường sửa mô tả bằng fuzzy/equal price giữa các model khác trong lớp Final; chỉ giữ mô tả baseline qua liên kết danh tính và ô số phù hợp. Nếu tái parse ít hàng hơn thì giữ bảng V8 kèm cảnh báo, không âm thầm làm mất hàng.
7. **Dấu và đơn vị:** đọc lại ô có nguồn rõ theo budget hiện có; chỉ thay mô tả/đơn vị khi hai cấu hình đọc cục bộ đồng thuận, cùng danh tính và đủ điểm heuristic. Giữ cả variant, không coi nhiều dấu hơn là đúng hơn. Evidence đổi cùng value. Không có từ điển tên nhà cung cấp/sản phẩm hoặc sửa riêng vi/vị theo mẫu.
8. **Ngữ nghĩa tài chính:** lưu discount, surcharge, cash tendered và change thành các observation riêng trong evidence; tách khỏi subtotal/VAT/payable. Không tạo cột mới, không phân bổ discount hoặc suy VAT/price/quantity từ phép tính. Giá trị không rõ hoặc nhiều số vẫn là evidence cần xem xét.
9. **Phục hồi bước bổ sung:** lỗi trong Final trên một trang giữ hàng V8 của trang đó, ghi lỗi/stage rõ và tiếp tục trang khác; lỗi Final toàn tài liệu trả lại snapshot V8. Lỗi engine baseline V8 vẫn đi qua fallback runtime hiện có. Điều này tránh mất dữ liệu V8 chỉ vì crop/refinement lỗi; không biến chất lượng current khi fallback thành PASS.
10. **Cảnh báo và provenance cuối:** selected field evidence, candidates, OCR readbacks, trạng thái từng trang và financial observations được giữ trong layout/extraction JSON hiện có. Bổ sung cảnh báo trường/ô thiếu, biến thể/xung đột, amount thiếu evidence, arithmetic scope, truncation và lỗi vận hành tầng trước. Không hiển thị cảnh báo arithmetic cũ như lỗi hiện tại sau khi dữ liệu đã đổi; chúng còn nguyên trong v8_baseline. Không tự đặt Approval/Lookup/Validation.

Các chức năng nói trên là **mã nguồn đã triển khai**, không phải tuyên bố độ chính xác thực tế hoặc trạng thái Website đã chạy bản mới.

## Lỗi từ source đã xử lý

| Lỗi | Cách xử lý mã nguồn |
|---|---|
| Final chỉ có seller/receipt, bỏ qua nhiều nhãn document hoặc footer | Bộ nhãn document riêng; vùng party và vùng financial được xét riêng, giữ value/source |
| Seller/name tách dòng hoặc MST role trong ngoặc bị bỏ sót | Theo cột/khoảng cách và role rõ; không suy từ thứ tự toàn trang khi có nhãn role trực tiếp |
| Confidence/diacritics quyết định giá trị mâu thuẫn quá dễ | Giữ baseline khi bằng chứng ngang nhau, literal variants và heuristic score không phải xác minh |
| Crop cắt mọi dấu hai chấm trong tên | Chỉ loại prefix khi nhận diện được label seller |
| Final bỏ đường parser grid khi không có header hoặc loại cả dòng thiếu SL/price | Thử parser hiện có rồi đường amount-only có source tách rõ; không điền thiếu bằng số 0 |
| Header tiếp trang không có state riêng | State cột/trang/khổ/số chứng từ; đóng khi có tổng cuối, không đóng ở carry forward |
| Tái dùng mô tả model từ hàng khác cùng tiền | Liên kết một-một theo danh tính/ô số; bỏ fuzzy description protection trong Final |
| Lỗi crop/refinement làm rơi về current toàn tài liệu | Bảo toàn snapshot V8 theo trang/tài liệu, lưu error type rõ |
| Cảnh báo và unit evidence không theo output cuối | Tổng hợp cảnh báo hiện tại và provenance, giữ baseline cũ riêng; value và evidence đổi cùng nhau |

## File thay đổi

### Source mới

- `backend/tools/ocr_benchmark/document_fields_v8_final.py`: nhãn/normalization/evidence cho fields và adjustment observations.
- `backend/tools/ocr_benchmark/table_state_v8_final.py`: continuation và amount-only source rows.
- `backend/tools/ocr_benchmark/review_v8_final.py`: review metadata/provenance, không thay nghiệp vụ.

### Source sửa tiếp, không ghi đè thay đổi trước đó

- `backend/tools/ocr_benchmark/source_links_v8_final.py`: role trong ngoặc, continuation tên theo source.
- `backend/tools/ocr_benchmark/refine_v8.py`: sử dụng helper mới cho fields/table/selection/source links.
- `backend/tools/ocr_benchmark/hybrid_v8_final.py`: tách bước theo trang, phục hồi V8, bounded readbacks, evidence cuối.

### Tài liệu

- Báo cáo này, `CODEX_HANDOFF.md`, `docs/OCR_PHASE13_CHECKPOINT.md`.
- Giữ nguyên `OCR_TASK2_FINAL_REPORT.md`, báo cáo tiếp tục đầu tiên và mọi kết quả G1–G13 để không thay bằng chứng lịch sử.

## Không thực hiện theo yêu cầu người dùng

- Không chạy test/pytest/regression/benchmark, OCR thực tế, Browser UAT/HTTP, build hoặc kiểm thử thủ công.
- Không import/chạy pipeline hoặc ứng dụng; không chạy bộ kiểm tra cú pháp trong lượt này. Chỉ đọc và chỉnh mã/tài liệu, lưu hash bảo toàn file.
- Không thêm/chạy/chỉnh file tests trong lượt này. Các tests của lượt trước vẫn chưa chạy.
- Không kết nối database, không upload/reprocess/chỉnh invoice/ground truth, không migration/seed/restore/reset.
- Không đổi source engine current/V6/V7/V8 gốc, mapper/API/schema, workflow/RBAC, Task 1/3 hoặc Web/Mobile.
- Không thay `.env`, CORS, cổng, mode mặc định; không khởi động/dừng dịch vụ, không đổi gate hoặc tạo kết quả PASS.
- Không stage/commit/push/pull/merge/reset/chuyển nhánh/xóa stash.

## Trạng thái Task 2, Gate và nghiệm thu

| Hạng mục | Trạng thái trung thực |
|---|---|
| Triển khai bổ sung trong lượt này | Đã viết/cập nhật mã, chưa xác minh thực thi |
| Kết quả 441 Backend/37 Web/build PASS | Lịch sử G13 trước các thay đổi ngày22/11, không áp dụng để gán PASS cho mã mới |
| Gate G13 `ocr_task2_final/OFFLINE_GATE.json` | Giữ nguyên; hash Final hiện khác nên launcher cũ tiếp tục chặn, không bypass |
| Website đang dùng mã mới | Không xác nhận, không restart/kiểm tra runtime trong lượt này |
| Chất lượng OCR trên hóa đơn mới/NFR01 | Chưa nghiệm thu độc lập; không có số accuracy hoặc PASS mới |
| Task 1/3, dữ liệu/cấu hình/nhánh/stash/công việc khác | Giữ nguyên |

## Giới hạn còn lại

Không thể khẳng định nhận đúng mọi tên/dấu/ô số hoặc mọi layout từ việc chỉnh source. OCR ký tự sai nhưng điểm cao, ảnh quá mờ/che, bảng phức tạp, biến thể thuế/discount và phân loại chưa gặp vẫn có thể sai hoặc thiếu. Giá trị phải giữ null/baseline và evidence khi không chắc chắn; không ép số học khớp hoặc giả dữ liệu. Confidence và SLA chưa hiệu chuẩn; NFR01 và hồ sơ độc lập vẫn chưa nghiệm thu. Current fallback vẫn có giới hạn đã ghi ở G13; lớp Final chỉ tránh gọi lại current khi lỗi nằm ở bước bổ sung.

Không đề xuất thêm vòng test/benchmark hoặc yêu cầu người dùng kiểm thử thủ công. Đây là điểm bàn giao **triển khai mã nguồn Task 2**, không phải nghiệm thu đã xác minh.

Bản source trước lượt này và hồ sơ bảo toàn nằm ngoài repo: `<LOCAL_PATH>`. Gate G13 và snapshot cũ giữ nguyên.
