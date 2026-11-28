# Task 2 — Tiếp tục Hybrid V8 Final ngày 22/11/2026

**Đã triển khai thay đổi mã nguồn, chưa kiểm chứng bằng chạy thực tế.** Kế thừa G1–G13; không tạo G14 hoặc làm lại benchmark. Task 1 và Task 3 đã hoàn thành, không chỉnh sửa. **NFR01 chưa nghiệm thu độc lập.**

## Lỗi xác định từ source và thay đổi

| Khoảng thiếu | Nguyên nhân từ mã nguồn | Thay đổi triển khai |
|---|---|---|
| Nhãn người bán/MST tách dòng | Chỉ vào nhánh label khi có dấu hai chấm; MST chỉ nhận cùng dòng. Nhãn/value không giữ riêng evidence | Nhận nhãn đầy đủ không có dấu hai chấm, nhãn có dấu hai chấm ASCII/fullwidth; lấy một dòng gần, cùng cột, trước header, không lấy nhãn kế tiếp hoặc metadata. Seller/buyer/tax role được giữ. Giá trị và nhãn có evidence riêng; MST chỉ bỏ khoảng trắng in sẵn, không sửa chữ thành số |
| Bằng chứng ô bill gán sai | Quantity/unit/price/amount dựa vào vị trí token cố định; OCR có thể gộp token hoặc có VND sau amount | Dùng character span của biểu thức in sẵn để tìm đúng box nguồn. Token gộp dùng chung box gốc, không bịa polygon riêng. Unit có thể nhiều từ. Không dùng token VND làm amount |
| Bổ sung ô từ hàng khác cùng số tiền | Baseline có thể được ghép chỉ bằng amount; cùng tiền không chứng minh cùng sản phẩm, có thể dùng một hàng baseline nhiều lần | Ghép description + amount và các ô số đã quan sát không mâu thuẫn; một-một; hàng lặp cần tọa độ phân biệt rõ, không rõ thì bỏ qua và cảnh báo. Không dùng amount null làm khóa. Không suy quantity/price từ tổng |
| Nhãn trang sau ghi đè trang trước | Chọn field ngay trong vòng từng trang; ứng viên/conflict bị tách giữa các trang | Thu thập ứng viên toàn tài liệu rồi chọn một lần; read ID có page để không lẫn các read cùng tên, lưu literal/selected/conflict. Selection vẫn chưa phải xác minh đúng |
| Unit đã thay nhưng evidence vẫn của giá trị trước | Nhánh đồng thuận unit reread chỉ đổi row.unit | Cập nhật evidence từ lượt đọc đã chọn cùng lúc với giá trị unit, vẫn yêu cầu các read đồng thuận theo logic cũ |

Thay đổi chỉ ở lớp Final. Không thay engine Tesseract, thuật toán current/V6/V7/V8 gốc, XML parser, mapper/API contract, schema, validation/ITEM-SUM, Approval, Lookup, RBAC hoặc giao diện. Không hardcode tên doanh nghiệp, model/sản phẩm hoặc số tiền từ chứng từ lịch sử.

## Tệp

- Mới: `backend/tools/ocr_benchmark/source_links_v8_final.py` — liên kết span/token, nhãn/value và matching baseline một-một; không gọi OCR/DB/network.
- Sửa: `backend/tools/ocr_benchmark/refine_v8.py` — sử dụng liên kết nguồn trong field/receipt/row recovery, giữ warning khi không thể ghép chắc chắn.
- Sửa: `backend/tools/ocr_benchmark/hybrid_v8_final.py` — gom ứng viên nhiều trang; cập nhật evidence unit theo value.
- Mới: `backend/tests/test_ocr_final_source_links.py` — các ca phát triển độc lập cho label tách dòng, chữ/số không suy đoán, token gộp/currency, amount trùng/0/null, ô mâu thuẫn, hàng lặp và source conflict. **Được viết nhưng không chạy**.
- Tài liệu: báo cáo này; cập nhật ghi chú trong `CODEX_HANDOFF.md` và `docs/OCR_PHASE13_CHECKPOINT.md`. Giữ nguyên báo cáo kết quả G13.

## Kiểm tra đã làm và chưa làm

| Nội dung | Trạng thái |
|---|---|
| Đọc source và đối chiếu logic | Đã thực hiện; đây là phân tích tĩnh, không chứng minh accuracy |
| Cú pháp Python | AST parse các file mới/sửa, không import/chạy ứng dụng |
| Tests mới | **NOT RUN** theo yêu cầu; không có số PASS/FAIL mới |
| Suite cũ, Web build, benchmark | **Không chạy lại** |
| OCR trên hóa đơn/HTTP/Browser/PostgreSQL | **NOT TESTED trong lượt này**; không upload/reprocess/đổi dữ liệu |
| 441 Backend/37 Web/build PASS ở G13 | Giữ nguyên là **kết quả lịch sử của source trước lượt này**, không chuyển thành PASS cho bản vừa sửa |
| NFR01/accuracy độc lập | **CHƯA NGHIỆM THU**, chưa có bằng chứng mới |

Không yêu cầu người dùng kiểm thử thủ công. Không chạy dịch vụ hoặc bật bản thay đổi mặc định; không tự đoán các lỗi accuracy trước đây đã hết chỉ dựa trên những thay đổi này.

## Runtime, rollback và bảo toàn

- Source default `current`, cấu hình `.env`/cổng/CORS không thay đổi. Không đọc/kết nối database, không chỉnh invoice cũ, không chạm ground truth/dataset.
- Nhánh `feature/thien`, HEAD/stash và thay đổi cũ giữ nguyên. Không stage/commit/push/pull/merge/reset hoặc switch.
- V8 gốc giữ nguyên. Hai file Final trước sửa được sao lưu tại `<LOCAL_PATH>` để đối chiếu/rollback có kiểm soát; không tự copy ngược đè thay đổi khác.
- `ocr_task2_final/OFFLINE_GATE.json` và hồ sơ PASS G13 **giữ nguyên**. Hai hash Final đã đổi nên launcher G13 sẽ chặn restart `hybrid_v8_final` bằng gate cũ. Không sửa hash/PASS hoặc bỏ guard để giả đã xác minh. Không tự thay process đang chạy, không khẳng định Website đã nạp code mới.
- Nếu dịch vụ trước đó còn chạy, nó có thể vẫn giữ module cũ trong bộ nhớ; lượt này không kiểm lại listener/runtime. Tình trạng dịch vụ 20/11 trong bàn giao là lịch sử.

Hồ sơ không chứa mật khẩu/token: `<LOCAL_PATH>` và `IMPLEMENTATION_REVIEW.json` lưu hash source/trạng thái Git/phạm vi kiểm tra tĩnh. Không làm lại các kết quả cũ.

## Còn thiếu

Các bố cục khác, cải thiện chữ có dấu thực tế, tổng hợp bảng không có header, chất lượng fallback current, hiệu năng/confidence và nghiệm thu độc lập vẫn chưa được chứng minh giải quyết. Nhãn nhiều cột phức tạp hoặc tên bên bán trải nhiều dòng hơn giới hạn hiện tại có thể chưa lấy đủ; parser không đoán phần bị thiếu. Các ca hồi quy mới chưa chạy nên rủi ro hồi quy được công khai. Tiếp tục Task 2 bằng thay đổi chức năng có căn cứ, không tự mở chuỗi kiểm thử dài và không coi thay đổi hôm nay là nghiệm thu OCR.
