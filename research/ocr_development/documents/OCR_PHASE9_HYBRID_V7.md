# Giai đoạn 9 — Hybrid V7 thử nghiệm

Ngày 19/11/2026. Repo `FINTECH_OCR_GitHub`, nhánh `feature/thien`. **Đã triển khai phiên bản thử nghiệm; chất lượng OCR chưa đạt nghiệm thu.** Không đổi pipeline mặc định, không khởi động lại Website/Backend đang chạy, không ghi PostgreSQL. Phase7 tiếp tục tạm dừng; không benchmark hoặc chỉnh nhãn bộ 24 chứng từ.

## Căn cứ và nguyên nhân

Đã đọc [Web UAT Giai đoạn 8](OCR_PHASE8_WEB_UAT.md), [đề xuất Giai đoạn 9](OCR_PHASE9_PROPOSED_PLAN.md), bridge/runtime, parser V4/V5/V6, model/API và các test liên quan. Đọc trực tiếp ba ảnh thật development và đối chiếu `ocr_phase8_integration/web_uat/DB_POSTCHECK.json`, gồm output ExtractionRun **trước sửa tay**, không lấy Invoice đã được chỉnh làm đáp án OCR.

| Invoice tham chiếu | Nguyên nhân xác định | Xử lý V7 / giới hạn |
|---|---|---|
| #25 | Raw OCR nhận sai ký tự số và tháng. V5/V6 giữ ngày baseline khi đã có dữ liệu nên lượt vùng không thay được ngày sai. Mất dấu/tên là lỗi nhận dạng, không phải mất dữ liệu API. | Đọc lại dòng có nhãn, lưu ứng viên xung đột; sửa được ngày. Số HĐ và dấu tên vẫn sai. Không thay O/0, 3/8 hoặc tên bằng từ điển cửa hàng. |
| #26 | Dòng khuyến mãi ở cột phải bị grouping cùng mô tả sản phẩm kế tiếp. Parser gán văn bản gần anchor, thiếu ranh giới điều chỉnh. | Loại số âm/khuyến mãi khỏi anchor hàng bán và khỏi mô tả, giữ bằng chứng loại. Hai hàng và giá trị số được bảo toàn. Một số chữ/dấu vẫn sai. |
| #27 | Lượt trước chủ động gây RuntimeError ở bridge để kiểm fallback. OCR cũ chạy thật nhưng parser cũ không trích đủ trên ảnh này. Đây là cùng ảnh của #25. | Giữ cơ chế fallback, thêm kiểm thử V7 lỗi bật/tắt fallback. Không coi #27 là ảnh thứ tư độc lập; không sửa bản ghi hay tái upload. |
| #28 | Parser loại cả dòng có nhãn Giá bán; ghép mô tả theo khoảng cách làm tên sai/mất hàng. OCR nhầm 1/4, I/J, GOT/GOI/CAT/CAI. Giá đăng ký khác giá bán cần tách vai trò. | Khôi phục đủ sáu vùng hàng, gắn mô tả trước ô bán và bỏ dòng giá đăng ký. Còn một amount sai, một quantity null và đơn vị/dấu sai. Đọc lại ô vẫn có thể cùng nhận sai; phải review. |

API/ORM/UI ở Phase8 đã giữ nguyên output; không sửa dữ liệu cũ để làm kết quả đẹp hơn. Không sửa ITEM-SUM: subtotal null vẫn có thể làm quy tắc này không đạt dù sum bằng total.

## Mã nguồn thực tế

- `backend/tools/ocr_benchmark/hybrid_v7.py`: gọi V6 frozen, tái sử dụng raster và OCR đã có trong cùng lock; nâng cấp riêng, không monkeypatch thuật toán V6 để đổi kết quả. Đọc lại có điều kiện vùng bảng, nhãn số/ngày, tên người bán và ô số còn nghi vấn. Giữ V6 output đầy đủ để đối chiếu.
- `backend/tools/ocr_benchmark/table_v7.py`: phân cột bằng tiêu đề/tọa độ; gom ô gần cùng baseline, giữ mô tả nhiều dòng giữa hai hàng bán; loại barcode, metadata, giảm giá và giá niêm yết khỏi sản phẩm. Dòng có nhãn Giá bán vẫn được lấy ô số nhưng không dùng nhãn làm tên. Mang hình học cột sang trang tiếp theo khi thiếu header, không mang nội dung hàng cũ.
- `backend/tools/ocr_benchmark/fields_v7.py`: ngữ cảnh người bán/người mua với nhãn MST; tách quan sát subtotal, VAT, discount, payable, cash và change. Giữ nhiều mức VAT trong evidence; không suy tổng/VAT/đơn giá hoặc gom thuế bằng phép tính. Đây là bổ sung quan sát, chưa giải quyết mọi bố cục/ứng viên baseline sai.
- `backend/tools/run_hybrid_v7.py`: CLI đọc file bất kỳ offline, xuất JSON mới chứa raw/box/score/findings. Không đọc dataset/ground truth/DB, không ghi đè output cũ, không tải mô hình.
- `backend/app/core.py`, `backend/app/ocr_runtime.py`, `backend/app/main.py`: thêm lựa chọn `hybrid_v7` **chỉ trong testing**; dispatch, mapping/null/evidence, method `hybrid-v7`, lỗi và fallback. `current` vẫn mặc định; V6 giữ nhánh cũ. XML vẫn dùng parser hiện có.
- `web/src/ocrRuntimeInfo.js`: cảnh báo phân biệt V6/V7/fallback/thất bại/XML; không thiết kế lại giao diện hoặc đổi endpoint.
- Test mới: `backend/tests/test_ocr_hybrid_v7.py`, `backend/tests/test_phase9_runtime_api.py`; cập nhật `web/tests/ocrRuntimeInfo.test.js`.

Tiền xử lý gốc của V6 tiếp tục xử lý EXIF/orientation/deskew/contrast/noise; V7 thêm tăng kích thước crop có giới hạn và sharpening nhẹ, trả tọa độ về raster gốc đã xử lý. **Chưa có thuật toán làm phẳng nếp gấp hoặc bảo đảm phục hồi ảnh mờ nặng.** Không cài OCR engine/mô hình mới; Tesseract vẫn mặc định, công cụ PaddleOCR còn nguyên.

Confidence không được coi là độ chính xác: `confidence_score=null`, `requires_review=true`, có `uncertain_fields`, xung đột field/cell, reread, thiếu ô, chênh lệch phạm vi tiền. Cảnh báo so sum với payable không thay thế validation và không tự suy subtotal. Giữ nguyên approval, lookup, RBAC và correction history.

## Kiểm thử cuối lượt

| Hạng mục | Kết quả thực tế | Phạm vi bằng chứng |
|---|---|---|
| Toàn bộ Backend pytest | **350 PASS / 0 FAIL / 0 SKIP**, 139,14 giây | SQLite in-memory/tmp uploads; 5 cảnh báo deprecation của thư viện hiện có |
| Frontend Node tests | **26 PASS / 0 FAIL** | Có phân biệt banner V7/V6/current/fallback/XML và kiểm thử các chức năng trước |
| `npm.cmd run build` | **PASS**, 31,68 giây | Vite 6.4.5; còn cảnh báo bundle >500 kB, không đổi cấu hình để che cảnh báo |
| API V7 với output có kiểm soát | PASS | Lưu null/unit/evidence, đọc lại, correction history và chặn truy cập invoice người khác trong fixture DB |
| API V7 + Tesseract thật | PASS thực thi | Render ảnh synthetic mới → upload TestClient → OCR V7 thật → SQLite riêng → API/detail/file readback; không mock engine, không chứng minh accuracy trên hóa đơn thật |
| V7 XML/fallback/testing-only/PDF text | PASS tự động | XML không đổi; lỗi engine không bị giấu; không bật V7 trong production; PDF text không OCR lại không cần thiết |
| Ba ảnh thật development → V7 → mapping API | PASS thực thi | 1/2/6 hàng qua bridge, không có amount âm; chất lượng từng trường vẫn có FAIL như bảng dưới |
| 14 file frozen + ground truth Phase7 | PASS checksum | Giữ nguyên SHA-256; không chạy benchmark G7 |
| Browser/Uvicorn/PostgreSQL V7 | **NOT TESTED** | Không đổi runtime hay upload invoice mới; không lấy TestClient làm Browser UAT |
| OCR tổng quát đạt nghiệm thu | **Chưa đạt** | Còn sai dữ liệu; thiếu tập độc lập và coverage thực tế |

JUnit/log: [backend-tests.xml](../../ocr_phase9_development/backend-tests.xml), [backend-tests.log](../../ocr_phase9_development/backend-tests.log), [TEST_RESULTS.json](../../ocr_phase9_development/TEST_RESULTS.json). Các regression mới dùng giá trị phát triển độc lập cho multiline/model/barcode, Giá bán/Giá đăng ký, số âm/khuyến mãi, số 0/null/số lượng thập phân, cash/change, MST người bán/người mua, nhiều mức thuế trong evidence, cột trang tiếp theo và giữ literal đã hỗ trợ. Không đưa đáp án ba ảnh thật vào thuật toán.

## Đối chiếu trên ảnh thật development

Không dùng bộ Phase7; không sửa ground truth. Ba ảnh cũ đã được xem và dùng phát triển, **không phải held-out**. Bảng là đối chiếu AI trực quan phục vụ hồi quy; không phải nhãn chuẩn được người xác minh độc lập hoặc accuracy tổng quát.

| Tiêu chí | V6 | V7 | Kết luận |
|---|---|---|---|
| #25 ngày | 2020-03-12 | 2020-08-12 | PASS hồi quy trên ảnh này |
| #25 số HĐ | SON45644 | SON45644 | FAIL, còn sai chữ số so ảnh |
| #25 seller/dấu | CUA HANG NAM OÁNH | Vẫn thiếu dấu | FAIL, chưa phục hồi đầy đủ |
| #25 số hàng / lượng / giá / amount | 1 / 10 / 5300 / 53000 | Giữ nguyên | PASS bảo toàn số; mô tả chưa đúng toàn bộ dấu |
| #25 total | null | null | Không tự sao chép từ Cộng tiền hàng; TOTAL validation không được ép PASS |
| #26 hàng | 2; khuyến mãi lẫn mô tả | 2; bỏ khoản âm khỏi mô tả | PASS cấu trúc, còn lỗi ký tự |
| #26 lượng / giá / amount | 2×37900=75800; 2×10000=20000 | Giữ nguyên | PASS bảo toàn các ô số |
| #26 total | 95800 | 95800 | PASS trên ảnh; subtotal vẫn null |
| #28 số hàng | 5/6 | 6/6 | PASS độ phủ vùng hàng, không phải đúng toàn bộ ô |
| #28 tên hai hàng cuối | Tên hàng 5 sai, mất hàng 6 | Khôi phục mô tả hai hàng | PARTIAL, còn sai dấu/chữ |
| #28 lượng/giá/amount | Hai lượng null; hàng 2 giá/amount 40000 | Hàng 1 quantity=1; hàng 2 price=10000 nhưng quantity=null, amount vẫn 40000 | FAIL đầy đủ/chính xác |
| #28 tổng amount hàng | 121000 | 146000 | FAIL so ảnh: phục hồi thêm hàng nhưng amount sai chưa khắc phục; không tự sửa để khớp tổng |
| #28 total | 116000 | 116000 | PASS bảo toàn field tổng, không xác nhận các hàng đúng |
| Đơn vị #28 | GOT/null/HOP… | Có thêm literal GOI/HOP/CAT nhưng còn GOT, null và CAT sai | PARTIAL / chưa đạt |

V7 tốn thêm thời gian do đọc ô tranh chấp; chưa chứng minh cải thiện hiệu năng. Số đo từng lượt và thời gian các vùng có trong JSON, không gọi đây là benchmark nghiệm thu. Các lượt có tải CPU từ pytest, không dùng để kết luận tốc độ engine nhanh/chậm theo tỷ lệ.

Thời gian offline quan sát: V6 #25/#26/#28 lần lượt khoảng **9,96 / 12,28 / 12,57 giây**; lượt V7 cuối **17,37 / 21,68 / 31,28 giây**. Xem giá trị chính xác trong COMPARISON; không cùng tải CPU nên đây chỉ là chi phí quan sát, chưa phải phép đo hiệu năng kiểm soát.

Bằng chứng ngoài repo: [COMPARISON.json](../../ocr_phase9_development/COMPARISON.json), `25_v6.json`…`28_v7.json`, [VERIFICATION.json](../../ocr_phase9_development/VERIFICATION.json), [run_development.py](../../ocr_phase9_development/run_development.py). SHA nguồn được ghi trong từng output. Raw OCR, toàn bộ crop boxes/score, các phương án và V6 baseline được giữ trong layout. Output ban đầu có một negative adjustment thành hàng đã phát hiện và sửa; regression riêng không cho tái phát. Không sửa dataset để tăng điểm.

## Cách thử riêng và rollback

Thử **offline, không dùng DB**, trong Windows PowerShell:

```powershell
Set-Location '<LOCAL_PATH>
.\.venv\Scripts\python.exe -X utf8 -m tools.run_hybrid_v7 '<LOCAL_PATH>
```

Đổi đường dẫn thành file thật được phép sử dụng; output phải chưa tồn tại. Không lấy output này làm ground truth.

Để thử qua Website trong phiên sau: chỉ dùng terminal Backend test đã xác minh runtime `DATABASE_URL` trỏ `fintech_ocr_rbac_test`, `UPLOAD_DIR` đúng `backend/uploads_rbac_test`, APP_ENV testing và backup mới đọc được. **Không chạy các lệnh dưới trong terminal chưa được xác minh; không dùng wrapper Phase8 cũ với tham số V7 vì wrapper đó chỉ nhận current/V6.**

```powershell
$env:APP_ENV = 'testing'
$env:OCR_PIPELINE = 'hybrid_v7'
$env:OCR_HYBRID_FALLBACK = 'true'
```

Sau khi chủ động dừng đúng Backend test đang dùng cổng 8000, khởi động cùng DB/upload/environment đã xác minh:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Giữ Web trỏ đúng Backend test; không sửa `.env`, CORS hoặc cổng. Kiểm tra ExtractionRun method `hybrid-v7`, `_ocr.requested_pipeline/used_pipeline`, raw/boxes/evidence; `/health` một mình không chứng minh cấu hình DB hoặc engine. Fallback lỗi dùng `current` và cảnh báo rõ. Để quay lại, dừng đúng tiến trình test rồi đặt `$env:OCR_PIPELINE='hybrid_v6'` (hoặc `'current'`) và khởi động lại cùng environment. Lượt này **chưa thực hiện** việc đổi runtime Website.

## Phần chưa đạt và bước tiếp theo

1. Số HĐ/dấu #25, một amount/quantity và đơn vị #28 còn sai; không công bố OCR chính xác hoàn toàn. Cần cải thiện đọc ký tự/ô với dữ liệu development độc lập, không thêm đáp án nhà cung cấp vào parser.
2. VAT thật, MST người bán/người mua, nhiều mức VAT, tài liệu scan song ngữ/nhiều trang, ảnh nhăn/mờ/thiếu sáng và độ phủ hàng trên bố cục mới chưa có bằng chứng nghiệm thu thực tế V7. Các test synthetic chỉ chứng minh hành vi mã nguồn đã nêu.
3. Browser/Uvicorn/PostgreSQL V7: NOT TESTED. API TestClient/SQLite cô lập và offline Tesseract không được gọi là Website UAT.
4. Cần kiểm thử tải/timeout, dung lượng evidence và so sánh hiệu năng cùng điều kiện không cạnh tranh CPU trước khi đề xuất bật rộng hơn. V7 hiện tăng số lượt OCR và bộ nhớ evidence.
5. Phase7 vẫn 24 draft, 0 approved, chưa A/B/bổ sung VAT/PDF/multipage/freeze/benchmark. Không dùng kết quả development để thay nghiệm thu này.

**Chưa đủ điều kiện đổi pipeline mặc định hoặc nghiệm thu.** Giữ đường quay lại current/V6 và các chức năng nghiệp vụ hiện có.
