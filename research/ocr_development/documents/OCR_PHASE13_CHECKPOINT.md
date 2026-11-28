# Checkpoint Giai đoạn 13 — Chốt kỹ thuật Task 2

## Quyết định Free-only, giữ hóa đơn thật tại máy · 23/11/2026

Người dùng từ chối Paid Tier/Billing/phí API. Đã thay điều kiện Paid bắt buộc bằng xác nhận Free/Billing tắt cùng quyền truyền dữ liệu. Thêm `ocr_free_tier.py`, whitelist SHA-256 của từng file không nhạy cảm được phê duyệt và phạm vi ContextVar từ bytes upload thực; ngoài danh sách giữ OCR tại máy. Paid confirmation=true bị chặn, không tự thử/chuyển model/key/project trả phí. Mỗi file đủ điều kiện tối đa một request; lỗi/quota giữ OCR. Thông báo Website dùng khu vực cũ, không đổi API/schema/bố cục hoặc merger. [Cấu hình và manifest mới nhất](OCR_TASK2_FINAL_REPORT.md).

SDK đã cài ở lượt trước, không cài thêm. Không đọc khóa/.env, không gọi API/test/OCR/benchmark/DB; không sửa Task 1/3, sáu module frozen, backup/stash hoặc ghi Git. Không tự bật cờ hay tạo phê duyệt. Model có Free theo tài liệu không chứng minh quyền/quota project; chưa kiểm chứng vận hành. G13, TBD-02 và NFR01 giữ nguyên. Các điều kiện Paid bên dưới chỉ còn là lịch sử, không được dùng để bật Billing.

## Bảo vệ luồng Gemini cho hóa đơn thật · 23/11/2026

Đã thêm kiểm tra Paid Tier/reference và phê duyệt xử lý dữ liệu thật, mặc định chưa xác nhận, tại `core.py`/`ocr_llm.py`; không thay hợp nhất hoặc fallback. Xác minh billing và quyền xử lý là công việc của người có thẩm quyền, không được suy ra từ API key hay boolean. Model hiện đã cấu hình `gemini-3.8-flash`; enable/transfer vẫn false, approval reference trống; SDK được khai báo nhưng chưa có trong `.venv`. Không sửa `.env`/cài SDK/gọi API hoặc xử lý chứng từ. Chi tiết biến cấu hình và giới hạn lưu giữ tại [báo cáo Task 2](OCR_TASK2_FINAL_REPORT.md). Chưa đủ điều kiện kích hoạt dữ liệu thật; không có PASS thực thi. Giữ nguyên Task 1/3, G13, TBD-02, Hybrid Final và Database; không test/OCR/benchmark/commit/push hoặc sửa stash/backup.

## Hợp nhất OCR và Gemini theo nguồn độc lập · 23/11/2026

Đã bổ sung so sánh chuẩn hóa, lưu riêng OCR/proposal/quyết định từng trường và ghép ô thiếu chỉ khi dòng/trang khớp duy nhất. Nhãn, vị trí dòng/cột và span do Backend đối chiếu; không tin tọa độ/bằng chứng model tự khai. Mâu thuẫn, nhiều mức VAT, tên chữ ký và số trong model sản phẩm không được dùng để tự thay dữ liệu OCR. Kiểm tra số học chỉ cảnh báo, không sửa tiền. PDF thiếu bằng chứng trang không nhận bảng AI tự gán trang. Website hiện thông báo Gemini/fallback và cảnh báo dễ đọc trong khu vực cũ.

Sửa bốn tệp chức năng: `ocr_llm.py`, `ocr_runtime.py`, `ocrRuntimeInfo.js`, `InvoiceDetailPage.jsx`; cập nhật ba tài liệu bàn giao hiện có. Giữ cấu hình model, API/schema, XML, sáu module Final, Gate và confidence. Không chạy test/OCR/benchmark/API/build, không cài SDK, không đọc hóa đơn/Database hay sửa `.env`. Không thao tác ghi Git/backup/stash.

Phần mã hợp nhất/tích hợp đã triển khai, **chưa xác minh hoạt động hoặc accuracy**. Gemini chưa được bật; SDK/quyền truyền dữ liệu và tham chiếu phê duyệt còn chờ. Tài liệu Google ghi alias `gemini-3.5-flash` được phía dịch vụ định tuyến sang model kế nhiệm; ứng dụng không tự đổi cấu hình. Gate G13, Final và NFR01 chưa nghiệm thu; TBD-02 chưa duyệt nên score=null/needs_review. [Chi tiết triển khai và giới hạn](OCR_TASK2_FINAL_REPORT.md).

## FR10 — Adapter Gemini và đăng ký Backend · 23/11/2026

Người dùng chọn Gemini API; đã thêm adapter trong `ocr_llm.py`, cấu hình opt-in trong `core.py`, đăng ký không gọi mạng ở lifespan `main.py` và dependency `google-genai==1.55.0`. Giữ nguyên điểm nối `ocr_runtime.py`: OCR → adapter được cho phép → JSON/evidence/mapper → confidence → lưu/validation/API/Web. Không sửa thuật toán Final/V8 hoặc XML.

Gemini mặc định tắt; đủ `GEMINI_ENABLED`, `GEMINI_ALLOW_EXTERNAL_TRANSFER`, key, model và tham chiếu phê duyệt mới đăng ký. Không có model mặc định, không tự dùng GOOGLE_API_KEY/Vertex AI, không gửi ảnh/PDF gốc. Thiếu SDK/cấu hình, lỗi mạng, phản hồi không hoàn chỉnh hoặc không khớp chứng cứ giữ OCR. Giữ timeout, giới hạn dữ liệu/đầu ra, không retry tự động trong SDK; lớp chung tối đa hai lần. Cấu hình chi tiết tại [báo cáo Task 2](OCR_TASK2_FINAL_REPORT.md).

**CODE COMPLETE – PENDING CONFIGURATION/ACCEPTANCE cho phần adapter và điểm nối đã phê duyệt.** Chưa cài thư viện, chưa gọi Gemini hoặc xác minh runtime. Không chạy test/benchmark/OCR/API/build, không truy cập Database, không sửa .env, Task 1/Task 3/Website hoặc thao tác ghi Git. TBD-02 vẫn chưa duyệt: score=null, cần xem xét. Gate G13 và pipeline mặc định current giữ nguyên; **không có Final PASS/NFR01 PASS mới**. Các ghi nhận thiếu adapter ở dưới là lịch sử trước lượt này.

## Triển khai bổ sung theo FR08 FR10 FR12 · 22/11/2026

Đã bổ sung OpenCV vào tiền xử lý current và lớp gọi Final, giữ fallback Pillow. Đã viết giao diện provider LLM có schema/evidence span, giới hạn và giữ OCR khi lỗi; chưa chọn provider hoặc gửi chứng từ đi. Đã nối confidence policy vào extraction, validation_round, API và hiển thị Web. Khi chưa có TBD-02, giữ score=null và needs_review; không tạo điểm từ completeness. XML và các trạng thái Approval/Lookup được giữ theo luồng cũ.

Ba module mới và sáu tệp chức năng sửa được liệt kê trong [báo cáo Task 2](OCR_TASK2_FINAL_REPORT.md). Chỉ hoàn tất lớp tích hợp theo các lựa chọn đã được cho phép. Provider/adapter LLM, công thức/ngưỡng confidence và khả năng có sẵn OpenCV còn chưa được xác minh/kích hoạt. Không chạy test, benchmark, OCR, API hoặc Database, không cài thư viện. Gate giữ nguyên và chưa bao phủ bản mới; Final/NFR01 chưa nghiệm thu.

## Đính chính theo SRS gốc · 22/11/2026

Đã đọc FR08–FR13 và PB03–PB08 từ ba tài liệu DOCX gốc. OCR/parser Hybrid đã tích hợp và có thể chốt phạm vi đó, nhưng không được gọi là hoàn thành toàn bộ SRS. FR10 còn thiếu LLM thực trong luồng extraction; FR12 còn thiếu confidence của Hybrid và điều kiện confidence thấp → needs_review theo UC06/TBD-02. FR08 dùng Pillow thay OpenCV nêu trong tài liệu. FR09, luật FR11, lưu FR13, review/edit đã có mã nguồn.

Chưa có mô hình/provider LLM được chọn và cho phép, cũng chưa chốt công thức/ngưỡng confidence. Không tự điền điểm hoặc tạo nhánh LLM giả để đánh dấu hoàn thành. Lượt này chỉ cập nhật ba tài liệu bàn giao; không sửa mã chức năng hay dữ liệu và không chạy test/OCR/benchmark. [Ma trận và giới hạn chốt Task 2](OCR_TASK2_FINAL_REPORT.md). Gate G13 giữ nguyên; Final/NFR01 chưa nghiệm thu.

## Trạng thái kích hoạt dự án chính · 22/11/2026

Chưa bật Final mặc định. Mặc định mã nguồn là `current`; cấu hình tệp Backend là `development` và không đặt `OCR_PIPELINE`. Hybrid chỉ được validator cho phép trong testing. Chưa xác minh cấu hình process đang chạy.

Đối chiếu tĩnh Gate G13 cho thấy 5/8 tệp khóa khác SHA-256 lịch sử. Chưa có bằng chứng kỹ thuật/Gate hợp lệ cho bản mã hiện tại và chưa có quyết định sử dụng Final ngoài testing. Giữ cấu hình an toàn theo yêu cầu. Các module/API/UI đã nối trong mã nguồn; dự phòng Final giữ V8 cùng lần xử lý, dự phòng ngoài cùng vẫn là current khi được bật. NFR01 chưa nghiệm thu độc lập; không có Final PASS mới. [Điều kiện và danh sách tệp lệch](OCR_TASK2_FINAL_REPORT.md#dieu-kien-kich-hoat).

Ngày 20/11/2026 (Asia/Ho_Chi_Minh). Nhánh `feature/thien`.

**Đã chốt triển khai kỹ thuật trong phạm vi đã kiểm thử, còn giới hạn OCR. Chưa nghiệm thu độc lập/NFR01. Dừng G13, không triển khai G14.** Checkpoint này thay thế trạng thái vận hành G12; giữ nguyên tài liệu và bằng chứng cũ.

## Kết quả có bằng chứng

- Backend **441 PASS, 0 FAIL, 0 SKIP**; Web **37 PASS**; build **PASS**. Tám nguồn development/regression cũ không mất giá trị từng đúng.
- V8 hoàn thiện là module mới `hybrid_v8_final`; V8 gốc/current/V6/V7 giữ nguyên. Mặc định source vẫn `current`; mode mới chỉ được bật trong testing. Không đổi schema, validation, RBAC hay giao diện nghiệp vụ.
- Sáu nguồn #48–53 đều là **DEMO giả lập**, được đọc trực tiếp và chạy OCR thực. Supplier từ 2/6 lên 6/6; ngày và tổng 6/6; VAT 3/3; phát hiện 28/28 dòng, quantity/unit/price/amount 28/28. Mô tả đúng 27/28, đủ cả năm ô 27/28; còn “vi” thay “vị”. Không suy rộng thành accuracy độc lập.
- Chromium/Vite/Uvicorn/PostgreSQL test thật: upload mới **#54–59**, HTTP 201, API ↔ UI/F5/restart giữ dữ liệu. Không sửa #48–53 hoặc #1–47.
- Sửa một dấu qua UI trên #59, lưu correction; không tính sửa tay vào điểm OCR. Employee submit #57 → Accountant approve; submit #58 → Admin reject. Quyền trái phép bị từ chối; Validation/Approval/Lookup giữ độc lập.
- Fault có kiểm soát ở process phụ tạo #60: fallback thật về current và banner đúng; **cơ chế PASS nhưng chất lượng current FAIL (5 dòng thay 3)**. Process fault đã dừng. Không dùng #60 vào điểm V8.
- Sau test: 60 invoices, 97 items, 60 runs, 42 corrections, 18 schedules. **1154 hàng ngoài users có trước UAT giữ nguyên hash**; ba user đăng nhập chỉ đổi hai timestamp auth, các cột còn lại giữ nguyên. Tất cả 60 file khớp checksum. Không kết nối DB chính.

## Runtime bàn giao

- Web: htt<LOCAL_PATH>
- APP_ENV=testing; DB `fintech_ocr_rbac_test`; upload `FINTECH_OCR_GitHub/backend/uploads_rbac_test` (đường dẫn tuyệt đối được kiểm trong process).
- OCR_PIPELINE=hybrid_v8_final; OCR_HYBRID_FALLBACK=true. PID/backend và snapshot dịch vụ trong `ocr_task2_final/handoff`.
- Backup sau UAT: `Database_Backup/fintech_ocr_rbac_test_after_task2_final_20261120_191738.dump`, 2.647.063 bytes; pg_restore --list exit 0; SHA trong BACKUP.json.
- Restart/rollback có guard: `ocr_task2_final/restart_test.ps1 -Pipeline hybrid_v8_final` hoặc `-Pipeline hybrid_v8` / `current`. Không dùng helper G12 với PID cũ; không chạy thêm dịch vụ trùng cổng.

## Còn thiếu và giới hạn

- NFR01, hóa đơn thật mới, nhãn A/B độc lập, UAT sign-off: **BLOCKED/chưa đủ bằng chứng**. Bộ 24 G7 giữ draft, không benchmark lại hoặc sửa ground truth.
- Một lỗi dấu trong mô tả, fallback current có thể sai; confidence chưa hiệu chuẩn; OCR không bảo đảm mọi bố cục/ảnh nhăn/che nặng.
- CER/WER, geometric row F1, latency/SLA và coverage nhiều VAT/discount trên dữ liệu thật độc lập: chưa đủ kiểm chứng.
- Khoảng thiếu dữ liệu G7/G12 vẫn được giữ: tối thiểu 4 VAT thật, 3 PDF, 2 chứng từ nhiều trang, có thể chồng lấp. Không dùng sáu DEMO thay thế.
- Không commit/push/pull/merge/reset/chuyển nhánh; ba stash giữ nguyên. Không thay Website mặc định/production, Mobile, .env, CORS, cổng hoặc dữ liệu chính.

[Báo cáo đầy đủ, nguyên nhân, tệp thay đổi, kiểm thử và lệnh chạy](OCR_TASK2_FINAL_REPORT.md).
[Bằng chứng](../../ocr_task2_final/STATUS.json) · [Gate kỹ thuật](../../ocr_task2_final/OFFLINE_GATE.json) · [Browser](../../ocr_task2_final/uat/BROWSER_UAT.json) · [Hậu kiểm dữ liệu](../../ocr_task2_final/uat/DB_FINAL_CHECK.json).

## Tiếp tục Task 2 ngày 22/11/2026 — mã mới chưa xác minh runtime

Theo yêu cầu mới nhất, Task 1/3 đã hoàn thành; chỉ tiếp tục Task 2 trên nền G1–G13. Đã bổ sung source-link nhãn tách dòng, evidence token/span cho bill, matching baseline một-một có điều kiện và gom ứng viên toàn trang. V8 gốc/current, workflow/API/schema/Web/dataset và dữ liệu giữ nguyên.

Không chạy test/benchmark/build/OCR/API/DB, không yêu cầu người dùng test thủ công. Chỉ đọc và phân tích cú pháp AST; tests mới được viết nhưng **chưa chạy**. 441/37/build PASS ở trên là **lịch sử trước sửa**, không là PASS của source mới. **NFR01 chưa nghiệm thu độc lập**.

Hai hash Final đã đổi; giữ gate G13 nguyên trạng nên startup Final bằng helper cũ sẽ bị chặn. Không giả cập nhật PASS/hash, không tự restart dịch vụ hoặc đổi mặc định. Không tự gọi đây là G14.

[Báo cáo tiếp tục và danh sách tệp](OCR_TASK2_CONTINUATION_20261122.md). Bản trước sửa và audit tại `ocr_task2_continuation_20261122` ngoài repo.

## Tiếp tục hoàn thiện mã nguồn — lượt tiếp theo 22/11/2026

Đã triển khai nhãn document/tài chính, tên nhiều dòng, role MST trong ngoặc, lựa chọn field không quyết định bằng confidence khi mâu thuẫn ngang nhau; bảng tiếp trang có điều kiện và amount-only có source; evidence/financial observations và cảnh báo hiện tại; giữ V8 theo trang/tài liệu khi bước Final lỗi. Tesseract/current/V6/V7/V8 gốc, XML/API/schema/Validation/Approval/Lookup/RBAC và Task 1/3 giữ nguyên.

**Không chạy test/benchmark/OCR/API/build/kiểm thử thủ công hoặc pipeline; không thêm/chỉnh/chạy tests trong lượt này.** Chưa xác minh runtime hoặc accuracy của mã mới. Không kết nối DB hoặc sửa dữ liệu/config, không restart dịch vụ. Gate G13 giữ nguyên, tiếp tục chặn mã Final khác hash; không cập nhật PASS/bypass. NFR01 chưa nghiệm thu độc lập. Nhánh feature/thien, HEAD/stash và công việc khác được bảo toàn.

[Báo cáo triển khai](OCR_TASK2_IMPLEMENTATION_20261122.md). Bản trước sửa/audit: `ocr_task2_implementation_20261122` ngoài repository. Không mở G14 hoặc đề xuất vòng test mới.

<a id="tich-hop-backend-final"></a>

## Bàn giao tích hợp Backend Hybrid V8 Final · 22/11/2026

**Trạng thái Task 2.** Đã hoàn tất các sửa đổi tích hợp xác định khi đọc mã nguồn. Luồng upload đơn/lô gọi `extract_document`; cấu hình testing chọn `hybrid_v8_final` cho ảnh/PDF. XML đi qua parser XML hiện có. API ghi các trường được hỗ trợ vào `Invoice`, các dòng theo thứ tự vào `InvoiceItem`, văn bản OCR và bằng chứng vào `ExtractionRun`. Chi tiết hóa đơn dùng `inv_ser(..., details=True)` để trả dữ liệu và cảnh báo. Chỉ kiểm tra đường đi này trên mã nguồn.

| Tệp sửa trong lượt | Phần triển khai |
| --- | --- |
| `backend/app/main.py` | Tiếp nhận đuôi `.jpeg` qua nhánh kiểm tra chữ ký và xử lý JPG hiện có, giữ tên tệp gốc. |
| `backend/app/ocr_runtime.py` | Kiểm tra ánh xạ trường/dòng và khả năng lưu JSON trước khi giao kết quả cho upload. Nếu riêng bước Final thất bại, dùng snapshot V8 hợp lệ, ghi `used_pipeline=hybrid_v8` cùng lý do. Cờ `fallback` tiếp tục biểu thị việc quay về `current`. |
| `backend/tools/ocr_benchmark/hybrid_v8_final.py` | Điều phối sáu module, kiểm tra thứ tự trang và liên kết ảnh trang trước bước đọc lại vùng cắt. Giữ bảng V8 khi có dòng chưa xác định được trang, tránh đếm hai lần. Nếu mọi trang đều phải giữ V8, trả lại cả trường và dòng V8. |
| `backend/tools/ocr_benchmark/refine_v8.py` | Gắn MST không nêu rõ vai trò với nhãn bên mua/bán ở cùng cột khi đủ căn cứ. Loại bản đọc lặp trước khi chọn trường. Khi có nhiều thuế suất đủ bằng chứng nhưng khác nhau, giữ các giá trị quan sát và để trống thuế suất chung. |
| `backend/tools/ocr_benchmark/document_fields_v8_final.py` | Gom ứng viên số phiếu/số hóa đơn theo loại chứng từ trước khi chọn kết quả. Xử lý ngày viết bằng chữ và tiền có khoảng trắng không ngắt giữa các nhóm nghìn. Lưu quan sát số tiền và tỷ lệ của khoản điều chỉnh kèm nguồn. |
| `backend/tools/ocr_benchmark/source_links_v8_final.py` | Kiểm tra vai trò mâu thuẫn trong nhãn, vị trí dòng và liên kết một-một trước khi sử dụng dữ liệu V8 của dòng cũ. |
| `backend/tools/ocr_benchmark/table_state_v8_final.py` | Đối chiếu dòng theo trang, dải tọa độ và mô tả. Khi nhiều dòng cạnh tranh cho cùng vị trí, giữ dữ liệu của lượt đọc làm mốc và ghi cảnh báo. |
| `backend/tools/ocr_benchmark/review_v8_final.py` | Dùng cùng quy tắc ánh xạ số chứng từ cho lựa chọn, bằng chứng nguồn và cảnh báo. |

Khoản giảm giá, phụ phí, tiền khách đưa và tiền trả lại là **quan sát** theo trang. Bản tóm tắt ở `ocr.findings` liên kết tới `_ocr.evidence.final_financial_observations` trong lần trích xuất. Backend không cộng những quan sát này vào tổng phải trả. Các trường đã có trên hóa đơn vẫn đi theo hợp đồng API hiện hành.

**Giới hạn bàn giao.** Chưa xác minh runtime, kết quả lưu thực tế hoặc độ chính xác trên chứng từ mới cho bản sửa này. Các dấu tiếng Việt, vai trò của MST thiếu nhãn, dòng sát nhau và bảng tiếp trang thiếu bằng chứng vẫn có thể cần đối chiếu. Gate G13 giữ nguyên danh sách hash của bản lịch sử nên bản mã đã sửa chưa được gate cho phép khởi động qua launcher G13. Số 441 Backend, 37 Web và build PASS thuộc bản lịch sử. **Không có Final PASS mới. NFR01 chưa nghiệm thu độc lập.**

Lượt này chỉ sửa tám tệp Python trên, `CODEX_HANDOFF.md` và checkpoint này. Không chạy test, benchmark, OCR, API hoặc dịch vụ. Không truy cập Database, đổi cấu hình, sửa Website, Task 1, Task 3 hay thao tác ghi Git.

## Chốt phần lập trình Task 2 · 22/11/2026

Đã đối chiếu luồng upload, sáu module Final, ánh xạ và lưu kết quả, API chi tiết, chỉnh sửa và lịch sử với phạm vi G13. Qua đọc mã nguồn, không phát hiện chức năng bắt buộc còn thiếu. **Có thể kết thúc lập trình và bàn giao working tree hiện tại trên `feature/thien`.** Lượt chốt chỉ cập nhật tài liệu. Gate G13 giữ nguyên, bản Final hiện tại chưa được xác minh thực thi, NFR01 chưa nghiệm thu độc lập. [Danh mục tệp, chức năng và trạng thái Git khi chốt](OCR_TASK2_FINAL_REPORT.md#chot-ma-nguon).

## Rà soát bổ sung sau commit 26bc332 · 22/11/2026

Đính chính kết luận chốt trước về phần hiển thị. Đã nối `ocr.findings` vào Invoice Detail, hiển thị thông báo khi Final giữ kết quả V8 và sửa tiền phân nhóm nghìn bằng dấu cách thường trong `document_fields_v8_final.py`. Những sửa này đang ở working tree và chưa commit. Các module Final, luồng Backend, lưu bằng chứng và review/edit đã được đối chiếu qua mã nguồn. Không phát hiện thêm chức năng bắt buộc còn thiếu trong phạm vi này.

Sửa ba tệp chức năng và ba tài liệu bàn giao. Không thực thi test/benchmark/OCR/API/Database/build/Browser, không đồng bộ GitHub. Gate G13 giữ nguyên; các PASS lịch sử không áp dụng cho bản bổ sung hiện tại. NFR01 chưa nghiệm thu độc lập. Có thể kết thúc lập trình trong phạm vi đã giao, giữ trạng thái nghiệm thu chưa xác minh.
