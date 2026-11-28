## Checkpoint Giai đoạn 8 — Web UAT thực tế đã chạy, 19/11/2026

Đã dùng Chromium điều khiển Website thật + Uvicorn + PostgreSQL `fintech_ocr_rbac_test` sau backup mới. Đăng nhập Employee HTTP 200; ba ảnh bill thật development (ngoài 24 ảnh G7) upload HTTP 201 tạo #25/#26/#28. DB ExtractionRun xác nhận Hybrid V6 thực sự chạy, có raw/boxes/score/routing/enhanced page. API → DB → UI fields/items khớp, ảnh gốc/checksum PASS và F5 giữ dữ liệu. Sửa seller/ngày/mô tả #25, unit #28 lưu/F5/correction history PASS, validation vòng 2 và Approval/Lookup giữ độc lập. Không dùng kết quả sửa tay để báo OCR đúng.

Tiến trình test lỗi riêng 8011 tiêm RuntimeError tại bridge trong bộ nhớ, không sửa module frozen; upload thật qua UI tạo #27 bằng OCR cũ, ghi fallback true và cảnh báo UI. Cơ chế fallback PASS nhưng OCR cũ trả unknown/fields/items rỗng; không coi accuracy PASS. Đã dừng riêng 8011, giữ 8000/5173 đang phục vụ Hybrid. Không mock response OCR/API, không dùng fixture thay các ảnh thật.

**Chất lượng OCR còn FAIL:** #25 sai chuỗi số/tháng/dấu; #26 mô tả lẫn khuyến mãi; #28 chỉ 5/6 hàng, sai/thiếu lượng/đơn vị và một ô giá/amount. Total #26=95800 và #28=116000 đúng theo ảnh nhưng chưa đủ chứng minh toàn bộ đúng. MST/VAT dương trên VAT thật, PDF thật và Browser Accountant/Admin **NOT TESTED**. ITEM-SUM #26 false do subtotal thiếu dù sum=total; không nới validation hoặc tự điền số. Giữ thuật toán frozen và ground truth nguyên vẹn.

DB test hiện **28 invoices/28 files/11 items/28 extraction_runs/37 corrections/300 validation_results/69 notifications/137 audit_logs/18 schedules**. Hash **568 bản ghi business trước UAT không đổi**; chỉ thêm/sửa invoice mới #25–28, không kết nối DB chính. Đã cập nhật [báo cáo UAT và lỗi](OCR_PHASE8_WEB_UAT.md), [đề xuất G9 chưa triển khai](OCR_PHASE9_PROPOSED_PLAN.md), [bằng chứng](../../ocr_phase8_integration/web_uat/DB_POSTCHECK.json). Không đổi code sản phẩm hoặc chạy lại 325/25/build; các PASS tự động thuộc lượt tích hợp trước. Phase7 tạm dừng, không benchmark/duyệt GT/commit/push/pull/merge/chuyển nhánh; chưa nghiệm thu OCR.

---

## Checkpoint Giai đoạn 8 — đã chạy môi trường test, 19/11/2026

Docker từ chối do tài khoản sandbox khác người dùng Windows. Ngữ cảnh Windows truy cập được Engine/container healthy mà không sửa ACL/config Docker. Đã tạo backup `fintech_ocr_rbac_test_before_phase8_20261119_190605.dump`, 83.910 byte, pg_restore list exit 0 và SHA Windows khớp. Đã kiểm tra DB test hiện có và toàn bộ cột ORM, không tạo/migrate/seed/restore DB. Upload test mới tại `FINTECH_OCR_GitHub/backend/uploads_rbac_test` có đủ 24 file cũ khớp checksum, chỉ sao chép từ nguồn, không ghi đè hoặc UPDATE DB.

Backend **127.0.0.1:8000**, PID 16864; Web **127.0.0.1:5173/upload**, PID 3040. In-process attestation + SQL chỉ đọc + PID listener xác nhận APP_ENV testing, DB **fintech_ocr_rbac_test**, upload test, Hybrid V6 và fallback true. Vite thực sự phục vụ repo FINTECH_OCR_GitHub và API URL đúng test. Health 200/testing và browser fetch/CORS/login-page startup PASS; không chỉ căn cứ .env/health. Không đăng nhập/upload/edit trong lượt này, Browser UAT/accuracy vẫn NOT TESTED. Counts trước/sau giữ 24 invoices/18 schedules/65 notifications. DB chính không được mở kết nối.

[Báo cáo runtime và rollback](OCR_PHASE8_RUNTIME.md), [bằng chứng process/config](../../ocr_phase8_integration/RUNNING_SERVICES.json), [browser chỉ đọc](../../ocr_phase8_integration/LIVE_BROWSER_STARTUP.json). Script chuyển mode có preflight và guard đúng test process; chưa chạy chuyển về current vì người dùng đang cần Hybrid bật. Không sửa code sản phẩm, .env hoặc CORS; không chạy lại 325/25 tests/build đã PASS. Phase7 tiếp tục tạm dừng, không benchmark/duyệt GT/nghiệm thu; không commit/push/pull/merge. Phần dưới là lịch sử lượt tích hợp code.

---

## Checkpoint Giai đoạn 8 — tích hợp Hybrid V6 thử nghiệm, 19/11/2026

Người dùng yêu cầu tạm dừng Phase7 và triển khai adapter Hybrid V6 vào Website. **Không coi Phase7 đã nghiệm thu:** 24 draft/0 approved/0 scored, 51 câu hỏi + 5 cảnh báo chờ người xác minh, chưa A/B/freeze/benchmark, vẫn thiếu VAT/PDF/nhiều trang. Ground truth và thuật toán frozen không đổi.

Đã tích hợp `app/ocr_runtime.py` qua threadpool vào upload hiện có, giữ **OCR_PIPELINE=current mặc định**. `hybrid_v6` chỉ bật với APP_ENV testing; fallback tự động có cờ và metadata rõ ràng, XML giữ parser cũ. Ánh xạ cột/InvoiceItem không đổi schema; raw text/boxes/confidence/candidates/page evidence lưu trong ExtractionRun JSON. Web hiển thị chế độ thử/fallback và đơn vị có thể review/edit; confidence chưa đo không hiển thị 0% giả. Không tác động quy tắc Approval/Lookup/RBAC; không reprocess hóa đơn cũ.

**Backend 325 PASS / 0 FAIL / 0 SKIP**, 5 warnings, 83,85 s; **Web 25 PASS / 0 FAIL**, build PASS (bundle warning). Có PNG OCR Tesseract/Hybrid thật + API upload/persist/readback trên SQLite memory và PDF text synthetic; tests mapping PNG/JPG/JPEG/PDF và quyền/correction/fallback/XML. Không dùng các ca synthetic làm benchmark chất lượng hoặc Browser UAT. Docker Engine không cho quyền từ phiên Codex: PostgreSQL runtime/backup **BLOCKED**, Website/hóa đơn thực mới **NOT TESTED**; cấu hình checkout vẫn DB chính/current nhưng không kết nối hay khởi động nó.

Xem [báo cáo/lệnh bật thử/rollback Phase8](OCR_PHASE8_INTEGRATION.md), [JUnit](../../ocr_phase8_integration/backend-tests.xml). Chưa bật pipeline trên service đang chạy, chưa đổi default hoặc nghiệm thu. Không sửa .env/CORS/ports/schema/dữ liệu, không chạy benchmark Phase7 hoặc commit/push/pull/merge. Các phần sau là lịch sử trước khi được phép tích hợp thử nghiệm.

---

## Checkpoint Giai đoạn 7 mới nhất — 51 câu hỏi và phiếu A/B rút gọn, 19/11/2026

Đã đọc lại hồ sơ AI/checkpoint/51 câu hỏi và mở riêng từng ảnh gốc của đủ 24 chứng từ. [PHASE7_ISSUE_RESOLUTION.md](../../ocr_phase7_acceptance/PHASE7_ISSUE_RESOLUTION.md) có kết quả đối chiếu, mức quan sát, vị trí bằng chứng và đề xuất từng câu theo nhóm seller/MST/số/ngày/VAT/hàng/tổng/che; không lấy OCR làm đáp án. Có đề xuất cho **51 câu gốc + 5 cảnh báo mới = 56 mục**, tất cả vẫn cần con người: 22 đọc được, 13 cần thống nhất quy tắc nhãn, 13 nghi vấn/một phần, 8 không quan sát đủ. 51 câu gốc giữ nguyên, **0 câu được con người chốt**, không sửa nhãn hoặc tự duyệt.

Đã tạo [phiếu A/B rút gọn không đáp án](../../ocr_phase7_acceptance/PHASE7_AB_SHORT_REVIEW.html) và [hướng dẫn](../../ocr_phase7_acceptance/PHASE7_AB_SHORT_GUIDE.md), không ghi đè phiếu cũ. 24 ảnh/56 câu trung tính, không nhúng đáp án AI/GT vào HTML/script; mọi tên/vai trò/câu trả lời/cam kết để trống. Chromium QA artifact PASS: ảnh/điều hướng/neutral mapping/guard xuất trống, không lỗi JS hoặc mạng ngoài, desktop/mobile không tràn ngang; [bằng chứng](../../ocr_phase7_acceptance/issue_resolution_20261119/SHORT_REVIEW_HTML_QA.json). Người dùng tự xuất draft/ghi nhận với scope riêng, không tự đưa vào schema A/B cũ hoặc GT. Xuất/tải JSON với người thật NOT TESTED; phiếu rút gọn chưa có resume nên lưu file và giữ tab mở khi chưa hoàn tất.

Giữ **24 draft/0 approved/0 scored**, 0 hồ sơ A/B thực; cần chốt bất đồng Hà Như/Hà Nhữ, GD/GĐ, I/1, tên hàng/giá, vắng so với bị che và các chính sách subtotal/VAT/modifier. Cần bổ sung **4 VAT Việt–Anh, ít nhất 3 PDF, 2 nhiều trang** thật có quyền dùng, xác minh độc lập và thống nhất tiêu chí trước freeze/benchmark. Không sửa Hybrid V6/default/Website/API/database hoặc chạy lại tests/benchmark Phase6; accuracy/CER/WER/latency và V6 Browser/API/DB UAT bộ mới vẫn NOT TESTED. **Chưa đủ điều kiện tích hợp hoặc nghiệm thu.** Không commit/push/pull/merge. Xem [checkpoint Phase7](../../ocr_phase7_acceptance/PHASE7_STATUS.md); lịch sử phía dưới giữ nguyên.

---

## Checkpoint Giai đoạn 7 mới nhất — audit JSON AI, 19/11/2026

Đã đọc đủ 24 review trong `PHASE7_AI_REVIEW_24.json`, lưu [báo cáo AI riêng](../../ocr_phase7_acceptance/ai_review_received_20261119/PHASE7_AI_REVIEW_24_AUDIT.md) và [audit JSON](../../ocr_phase7_acceptance/ai_review_received_20261119/PHASE7_AI_REVIEW_24_AUDIT.json), kèm bản nhận nguyên byte; không nhập thành hồ sơ con người. SHA nguồn JSON `c96e5e0cf9a27af3113e66c08520402bb960755cf90367e942a3aa1bd16debb3`. Kiểm tra **PASS kỹ thuật**: 24 ID duy nhất, 24 hash ảnh khớp, HTML/snapshot/Markdown đúng phiên bản, 24 ai_notes nguyên văn khớp HTML nguồn, 24 total khớp nháp và 45 hàng chính cùng số hàng; 132 ô số so được khớp nháp. Không dùng sự khớp với nháp để suy ra OCR accuracy hoặc ground truth đã đúng.

AI đã xem lại 24 ảnh qua sáu tờ đối chiếu; **PARTIAL nội dung**, không phải phiên âm lại toàn bộ ký tự hoặc xác minh A/B. Giữ các nghi vấn P7-024 Hà Như/Hà Nhữ, P7-006 khoảng trắng/ký tự tên hàng, P7-005 đơn giá; ghi thêm MST seller P7-021/022 và MST buyer P7-020 cần phân biệt vùng không quan sát được với null-vắng. Có 7 khác biệt chuỗi mô tả tại 6 chứng từ, gồm case và ghi chú chưa chắc, không tự coi là lỗi đã xác nhận hoặc sửa nhãn. 51 câu hỏi hiện có giữ nguyên; topping/VAT/I-1/giá bị che còn chờ người kiểm thử.

**24 draft / 0 approved / 0 scored; 0 hồ sơ A/B thực.** 49 file được bảo vệ không đổi, 14 file frozen source khớp SOURCE_LOCK; HTML gốc và bản có AI hỗ trợ giữ nguyên. Còn thiếu 4 VAT thật Việt–Anh, ít nhất 3 PDF và 2 chứng từ nhiều trang, cùng quyền sử dụng/độc lập và xác minh A/B trung thực. Nếu người kiểm thử đã xem AI, hồ sơ phải khai đúng hỗ trợ AI; không giả đọc độc lập không gợi ý. Không OCR/freeze/benchmark hoặc chạy lại 310 tests; không đổi Hybrid V6/default/Website/API/database. Accuracy/CER/WER/latency tập mới và V6 Website/API/DB UAT NOT TESTED. **Chưa đủ điều kiện tích hợp hoặc nghiệm thu.** Không commit/push/pull/merge. Xem [checkpoint Phase7](../../ocr_phase7_acceptance/PHASE7_STATUS.md); các phần sau là lịch sử.

---

## Cập nhật Giai đoạn 7 — AI review, 19/11/2026

Quy trình A/B đã chuẩn bị: [hướng dẫn nhanh](../../ocr_phase7_acceptance/AB_QUICK_START.md), [phiếu trống đọc độc lập](../../ocr_phase7_acceptance/AB_INDEPENDENT_REVIEW_24.html), mẫu hồ sơ/đối chiếu và [tiếp nhận VAT/PDF từ thành viên](../../ocr_phase7_acceptance/MEMBER_INVOICE_INTAKE.md). Cả A/B kiểm tra 24 ảnh, ghi riêng trước khi xem nháp AI/trao đổi. Có thư mục tiếp nhận và mẫu quyền nhưng 0 file mới; chưa thêm manifest hoặc prepare. Kiểm tra phiếu/guard/24 ảnh desktop/mobile PASS kỹ thuật; 0 hồ sơ A/B thực, xuất/tiếp tục với người dùng NOT TESTED. 24 draft/0 approved, source và dữ liệu không đổi; chưa benchmark.

Hồ sơ mới: [ZIP AI review ngày 19/11](../../OCR_PHASE7_VERIFICATION_24_20261119_AI_REVIEW.zip), 7.412.450 byte, 24 ảnh/46 mục kê hash, CRC/SHA PASS; ZIP cũ giữ nguyên. Kiểm tra schema/UTF-8/source lock và HTML desktop/mobile PASS kỹ thuật, không phải đo accuracy hoặc UAT Website. Xem `reviews_20261119/REVIEW_AUDIT.json` và `PACKAGING_RESULT_20261119.json` trong bộ Phase7.

Đã nhận kết quả ChatGPT qua người dùng và mở lại 18 ảnh gốc liên quan 14 nhóm đề xuất. Tự kiểm tra ZIP 18/11: 42/42 file kê manifest, 24/24 ảnh SHA-256 và CRC PASS. Lưu [AI review riêng](../../ocr_phase7_acceptance/CHATGPT_REVIEW_PHASE7.md), snapshot/changelog; không giả A/B.

Nháp đã sửa tên ASCII P7-004, GD-TC, ứng viên I102/I662 và số dài, nguyên văn Hóa đơn 1, buyer Hà Nhữ. Giữ số 0 đầu 01017257, VAT nhiều nhóm/SL thập phân/topping riêng, không suy đơn giá bị che. P7-020/023/024 bỏ seller_name và seller_tax_code khỏi expected do không quan sát được header; không chấm null vắng. Tổng tiền của cả 24 nhãn và toàn bộ ảnh/manifest giữ nguyên. Vẫn **24 draft / 0 approved / 0 scored**, 18 bảng/29 dòng nháp đủ + 16 dòng đề xuất, 51 câu hỏi chờ người xác minh.

Nhãn/HTML hiện tại có hash mới, ZIP cũ giữ để truy vết. [Nguồn bổ sung rà soát ngày 19/11](../../ocr_phase7_acceptance/source_records/VAT_SOURCE_SEARCH_20261119.md) chưa có file Việt–Anh đủ điều kiện; còn thiếu **4 VAT thật, ít nhất 3 PDF, 2 chứng từ nhiều trang**. Không OCR/freeze/benchmark hoặc sửa Hybrid V6/Website/API/DB; không commit/push. Chưa nghiệm thu hoặc đủ điều kiện tích hợp. Phần sau là lịch sử.

---

## Cập nhật Giai đoạn 7 — chuẩn bị dữ liệu độc lập, 18/11/2026

Người dùng đã xác nhận **nguồn bổ sung chỉ thuộc phạm vi Việt–Anh**, không nhập bộ tiếng Bồ Đào Nha. Giữ nguyên 24 chứng từ và ZIP hiện tại; tiếp tục ghi thiếu 4 VAT thật, ít nhất 3 PDF và 2 chứng từ nhiều trang. Chưa A/B, chưa benchmark. Đây là cập nhật phạm vi, không phải yêu cầu chạy lại tìm kiếm/kiểm thử.

Lượt bổ sung/đóng gói: đã kiểm tra nguồn VAT/PDF và giấy phép, nhưng **chưa bổ sung file đạt phạm vi Việt–Anh**; các nguồn phù hợp định dạng phần lớn synthetic hoặc chưa đủ bằng chứng quyền/file gốc. Nguồn thật CC BY 4.0 xác minh qua Zenodo chỉ phân phối ảnh tiếng Bồ Đào Nha, chưa nhập vào bộ Việt–Anh. Giữ **24 JPEG/24 draft**, 0 PDF/0 nhiều trang/0 VAT điện tử; còn thiếu **4 VAT thật, ít nhất 3 PDF và 2 nhiều trang**. Manifest/nhãn/ảnh cũ bảo toàn byte, không tạo hàng giả hoặc tự duyệt A/B. Đã chuẩn bị ZIP ngoài repo để đối chiếu: `OCR_PHASE7_VERIFICATION_24_20261118.zip`, chi tiết [nguồn bổ sung đã kiểm tra](../../ocr_phase7_acceptance/source_records/vat_supplement_20261118/SOURCE_SEARCH_REVIEW.md), [checkpoint/đóng gói](../../ocr_phase7_acceptance/PHASE7_STATUS.md). Chưa benchmark hoặc sửa runtime/Website/DB.

Giữ frozen Hybrid V6, Tesseract default và kết quả Phase6; không chạy lại OCR/benchmark/tests. Đã tiếp nhận **24 JPEG thật** ReceiptVQA qua HTTP Range, không tải whole ZIP: body **20.841.904 byte**, dưới 30 MB kể cả dự phòng 1 MB. SHA/CRC nguyên vẹn, so **35 tài liệu/37 trang cũ**, 888 cặp ngoài + 276 nội bộ: không trùng byte, không ứng viên gần trùng ở ngưỡng đã ghi. Độc lập nguồn/mẫu vẫn **PARTIAL**, có bill không tên và nhóm lặp, chờ A/B; không chứng nhận chỉ từ hash.

Đọc trực tiếp 24 ảnh để lập manifest/nháp: **24 draft / 0 approved / 0 scored**, 18 bảng/29 dòng nháp đủ, 6 bảng/16 dòng đề xuất giữ ngoài nhãn chấm, **51 câu hỏi**. Có [phiếu A/B trực quan](../../ocr_phase7_acceptance/HUMAN_VERIFICATION_24.html), [hướng dẫn](../../ocr_phase7_acceptance/HUMAN_VERIFICATION_GUIDE.md), [nhãn nháp](../../ocr_phase7_acceptance/ground_truth.json). Chromium chỉ kiểm tra phiếu HTML, không phải UAT Website. Không giả người xác minh, không lấy OCR/QA làm đáp án.

**Dừng trước freeze/benchmark.** Bộ mới có 24 bill một trang, **0 VAT điện tử / 0 PDF / 0 tài liệu nhiều trang**; hai bill có MST/VAT không thay VAT e-invoice. Cần bổ sung các nhóm thiếu và A/B thật. [Tiêu chí đối chiếu SRS](OCR_PHASE7_ACCEPTANCE_CRITERIA.md) ghi NFR01 >=85% trên 100–500; 24 là pilot, chưa đủ để nghiệm thu toàn diện. Accuracy/CER/WER/latency bộ mới NOT TESTED; không thay parser/API/Website/DB, không commit/push. Xem [báo cáo Phase7](OCR_PHASE7_INDEPENDENT_PREPARATION.md) và [checkpoint chi tiết](../../ocr_phase7_acceptance/PHASE7_STATUS.md). Phần dưới giữ lịch sử Giai đoạn 6.

---

## Cập nhật Giai đoạn 6 — 18/11/2026

Đã triển khai Hybrid offline V4-first tái sử dụng raster/alternatives, chỉ bổ sung vùng theo thiếu/mâu thuẫn/word score thấp. Giữ Tesseract, Current/V4/V5, Website/API/default/DB/ground truth. Benchmark mới 40/40 lượt trên cùng 10 JPEG development: Current/V4/V5/Hybrid TB **9,41 / 3,97 / 13,29 / 8,19 s**; call Tesseract **7,9 / 4,0 / 22,1 / 10,1**. Hybrid giảm 38,4% thời gian so V5 trong lượt này. Supplier **0/10 → 1/10 → 2/10 → 3/10**; total **0/8 → 5/8 → 6/8 → 6/8**; MST tất cả **0/2**; dòng **0/16 → 1/16 → 3/16 → 5/16**, bảng **0/7 → 0/7 → 1/7 → 1/7**. Hybrid line P/R/F1 **35,7% / 31,2% / 33,3%**. Không mất field/dòng V4/V5 đang exact trong nhãn chấm. Backend **310 PASS/0 FAIL**, 5 warnings; hash/replay/recount/profiling audit PASS.

**Chất lượng chưa đạt, chưa tích hợp/nghiệm thu.** Nhãn vẫn 10 draft, không có A/B/freeze; supplier/MST/missing rows/total còn sai. CER/WER, bộ mới/PDF thực nhiều trang/VAT đa mức và V6 Browser/API/PostgreSQL UAT NOT TESTED. Đã chuẩn bị [kế hoạch nghiệm thu mới](OCR_PHASE6_INDEPENDENT_ACCEPTANCE_PLAN.md), catalog 35 hash phát triển. Xem [báo cáo Giai đoạn 6](OCR_PHASE6_HYBRID_RESULTS.md); các mục sau là lịch sử.

Chốt lượt tiếp tục: đã kiểm tra JUnit/snapshot/kết quả lưu, hoàn tất [lịch sử Giai đoạn 6](../../ocr_phase6_development/RUN_HISTORY.md) và [danh sách việc còn mở](OCR_PHASE6_OPEN_ISSUES.md); không chạy lại OCR/benchmark/tests, không sửa source pipeline. Trạng thái chất lượng và nghiệm thu giữ nguyên.

---

## Cập nhật Giai đoạn 5 — 18/11/2026

Đã triển khai V5 offline `tesseract-region-v5`, giữ Tesseract/V4/current và API/Website/DB không đổi. Chạy mới 30/30 lượt trên cùng 10 JPEG development, không sửa ground truth hoặc nhãn draft. So Current → V4 → V5: loại 1/9 → 8/9 → 8/9; số 0/6 → 3/6 → 4/6; ngày 0/9 → 7/9 → 7/9; supplier 0/10 → 1/10 → 2/10; MST 0/2 → 0/2 → 0/2; tổng 0/8 → 5/8 → 6/8; dòng 0/16 → 1/16 → 3/16; bảng 0/7 → 0/7 → 1/7. Không mất trường/dòng V4 đang khớp trong nhãn chấm. Backend **284 PASS / 0 FAIL**, 5 warnings; hash/replay/đếm độc lập PASS.

**Chất lượng chưa đạt, chưa tích hợp hoặc nghiệm thu.** Supplier/MST/bảng còn lỗi; nhãn 10 draft, chưa A/B/freeze; CER/WER và V5 Browser/API/PostgreSQL UAT NOT TESTED. Chỉ 7 bảng/16 dòng đủ nhãn nháp để chấm; không tính ANAN/hai vé là PASS. Cần bộ nghiệm thu độc lập mới. Xem [báo cáo V5](OCR_PHASE5_REGION_PIPELINE_RESULTS.md). Các mục sau là lịch sử.

---

## Cập nhật Giai đoạn 4 — 18/11/2026

Đã dùng 10 ảnh làm **development** theo yêu cầu người dùng, xây pipeline ngữ cảnh V4 opt-in, không thay API/Website/DB. Audit benchmark/scorer và replay bằng chứng PASS. Backend 256/256 PASS. So current → V4: loại 1/9 → 8/9, ngày 0/9 → 7/9, tổng 0/8 → 5/8, supplier 0/10 → 1/10, MST 0/2 → 0/2, dòng 0/16 → 1/16, bảng 0/7 → 0/7. Không có hồi quy trên trường current đang đúng trong tập nhãn được chấm cuối, kể cả absent.

**Chưa đạt chất lượng và chưa tích hợp/nghiệm thu**. Nhãn vẫn draft; CER/WER và Website/API/PostgreSQL UAT NOT TESTED. Cần bộ nghiệm thu độc lập mới được A/B xác minh. Xem [báo cáo Phase 4](OCR_PHASE4_CONTEXT_PIPELINE_RESULTS.md); các phần sau là lịch sử.

---

## Cập nhật mới nhất: benchmark sơ bộ 10 chứng từ (18/11/2026)

Người dùng xác nhận chưa có người B độc lập và cho phép chạy sơ bộ phục vụ phát triển. Ground truth giữ 10 draft; 10/10 ảnh khớp hash, không giả A/B, không freeze nghiệm thu. Chạy current/v3 thật trên cùng 10 JPEG: 20/20 lượt hoàn tất, nhưng phân loại 1/9 mỗi nhánh, tổng tiền 0/8, dòng đúng 0/16, bảng đúng 0/7. V3 tạo 1 dòng sai từ số hóa đơn; không chứng minh cải thiện. TB current 13.6665 s, V3 15.177 s; RAM đỉnh 261.89/286.36 MiB.

Nhãn sơ bộ chỉ gồm trường/bảng đọc rõ trong nháp, chưa được hai người duyệt. Không chấm các trường chưa chắc; chưa có transcription nên CER/WER NOT TESTED. Guard tests 12/12 PASS; gate chính thức vẫn BLOCKED (35 điều kiện). Không thay parser/API/Website/DB. Chưa đủ điều kiện tích hợp/nghiệm thu.

Chi tiết hiện tại: [checkpoint sơ bộ](../../ocr_phase35_acceptance/PRELIMINARY_STATUS.md), [bảng từng trường/chứng từ](../../ocr_phase35_acceptance/preliminary_development_20261118_121925/REPORT_PROVISIONAL.md), [phân tích lỗi](../../ocr_phase35_acceptance/preliminary_development_20261118_121925/ERROR_ANALYSIS.md), [quy tắc nhãn](../../ocr_phase35_acceptance/ANNOTATION_RULES.md). Các mục phía dưới là lịch sử trước đợt tiếp nhận 10 chứng từ; không dùng số lượng 0 lúc khởi tạo làm trạng thái mới nhất.

Tập này đã được xem để chẩn đoán phát triển. Sau cải tiến dựa vào kết quả, cần tập độc lập mới có A/B xác minh trước nghiệm thu. Giữ Tesseract làm mặc định; chưa tích hợp V3.

---

# Giai đoạn 3.5 — Báo cáo trạng thái và checkpoint nghiệm thu OCR

Ngày: 18/11/2026. Repository `FINTECH_OCR_GitHub`, nhánh `feature/thien`.

> Rà soát hai người kiểm thử, 18/11/2026: đã mở lại từng ảnh gốc trong cả 10 chứng từ, đối chiếu trường và 22 dòng hàng + 2 dịch vụ đề xuất. Bốn mục chưa chắc (MST vé xe, total bill Năm Oánh, loại/total vé phim) đã giữ riêng ở candidate, không dùng null/giá trị nháp chưa chốt làm nhãn chấm. Có [phiếu đối chiếu ảnh và dữ liệu cạnh nhau](../../ocr_phase35_acceptance/HUMAN_VERIFICATION_10.html), [quy trình xác minh A/B](../../ocr_phase35_acceptance/HUMAN_VERIFICATION_GUIDE.md), mẫu hồ sơ riêng theo hash và script benchmark mặc định chỉ kiểm tra. 12/12 test cơ chế chặn PASS; lần chạy kiểm tra thực tế dừng đúng BLOCKED vì 10 nhãn còn draft và chưa có hồ sơ hai người. **0 approved, 0 scored; chưa freeze/OCR/benchmark, chưa tích hợp.** Xem [bằng chứng rà soát](../../ocr_phase35_acceptance/REREVIEW_VALIDATION.json). 12 test này không phải đo độ chính xác OCR; không chạy lại Backend 230 tests vì không sửa source Backend.

> Cập nhật nháp 10 chứng từ: đã kiểm kê **10 JPEG**, so 45 cặp nội bộ và 25 tài liệu/27 trang tham chiếu; không có trùng byte hay ứng viên hình gần trùng ở ngưỡng sử dụng. Manifest hiện có 10 bản ghi/6 nhóm bố cục thận trọng. Đã prepare và đọc trực tiếp cả 10 ảnh để lập nháp: **22 dòng hàng + 2 dòng dịch vụ vé đề xuất**, 10 draft, 0 approved, 0 scored. Sáu dòng ANAN và hai dòng vé vẫn nằm ở draft_items, chưa đưa vào nhãn bảng để chấm. Xem [bảng xác minh đầy đủ](../../ocr_phase35_acceptance/GROUND_TRUTH_REVIEW.md) và [kiểm tra cấu trúc nháp](../../ocr_phase35_acceptance/DRAFT_VALIDATION_10.json). Chưa freeze, OCR hoặc benchmark. Các trạng thái số lượng ít hơn bên dưới là lịch sử trước lần cập nhật này.

> Cập nhật sau khi người dùng chép file: đã kiểm kê **1 JPEG**, thêm REAL-001 vào manifest, chạy prepare và điền **nháp đọc trực tiếp ảnh gốc**. Hiện **1 draft, 0 approved, 0 scored**; chờ người dùng xác minh, chưa freeze/benchmark. Xem [bảng nhãn nháp và điểm cần xác nhận](../../ocr_phase35_acceptance/GROUND_TRUTH_REVIEW.md). Các phần ghi bộ rỗng bên dưới mô tả thời điểm công cụ được chuẩn bị trước khi tiếp nhận file.

**WAITING FOR INDEPENDENT REAL DATA — chưa đủ điều kiện tích hợp.** Lượt này hoàn thiện công cụ, không có phép đo accuracy thực tế mới, không tích hợp parser vào API/Website. Chưa đạt nghiệm thu Task 2 hoặc toàn hệ thống OCR.

## 1. Kiểm tra trạng thái trước khi tiếp tục

- Đã đọc lại benchmark, prototype và báo cáo Giai đoạn 3.1–3.4; giữ toàn bộ thay đổi Git chưa commit. Không viết lại hệ thống benchmark hoặc parser.
- Đã rà soát manifest/nhãn hiện có. Các bộ pilot, HD-01–HD-07 và các tập tổng hợp đều đã dùng phát triển/chẩn đoán. Chưa tìm thấy bộ real held-out mới có nhãn được hai người xác minh.
- Đã tạo danh mục dữ liệu cũ với 25 SHA-256 khác nhau để chặn dùng lại. SHA-256 không thay thế kiểm tra ảnh gần trùng hoặc nguồn nhà cung cấp/bố cục.
- `<LOCAL_PATH>` có 9 ảnh; 7 ảnh nằm trong danh mục phát triển. Hai file chưa đăng ký là `c55e6d89-616f-4b1e-af3c-05be03f19b0c.png` và `e1b0dc02-4b1b-40b1-899a-2a8e055adb7e.png`. Chưa có xác nhận độc lập, quyền sử dụng và ground truth nên không tự đưa vào nghiệm thu, không chạy OCR hoặc gán nhãn cho chúng.
- Không chạy lại 36 lượt benchmark cũ. Các kết quả 5/7, 11/11 và 0/4 là bằng chứng trước đó, không phải kết quả nghiệm thu mới.

## 2. Công cụ đã hoàn thiện

Thêm `backend/tools/ocr_benchmark/acceptance.py`, độc lập với API/database/OCR inference. Dùng lại CLI benchmark và scorer hiện có, không thay đổi parser.

| Khả năng | Trạng thái | Bằng chứng/phạm vi |
| --- | --- | --- |
| Tiếp nhận JPG/JPEG/PNG/PDF và nhiều trang | PASS kiểm thử công cụ | Draft chỉ ghi metadata/hash/số trang, không tự điền expected. |
| Ground truth được xác minh độc lập | PASS kiểm tra điều kiện | Hai người duyệt khác nhau, nguồn real/test, xác nhận chưa dùng phát triển/chưa xem prediction, hash đúng. Vẫn cần con người khai báo trung thực. |
| Khóa nhãn trước OCR | PASS kiểm thử công cụ | Snapshot manifest, nhãn mở rộng, nhãn benchmark và catalog cũ; chặn sai snapshot/dataset/prediction. |
| Loại, người bán, MST, số/ngày hóa đơn, subtotal/VAT/tổng | PASS kiểm thử scorer | Exact, Precision/Recall/F1; tách approved/partial; không chấm key chưa xác minh. |
| Tên hàng, đơn vị, lượng, giá, thành tiền và trang | PASS kiểm thử scorer | Điểm bốn ô cũ và sáu ô mở rộng; giữ dòng trùng thật, phân biệt 0/null/missing metadata. |
| Nhiều VAT | PASS kiểm thử scorer | Thuế suất/tiền VAT cấp dòng khi có nhãn; không sửa dữ liệu OCR để khớp phép tính. |
| OCR ký tự | PASS kiểm thử thuật toán | CER/WER Levenshtein; giữ dấu/case, chuẩn hóa whitespace/NFC; kiểm tra đối chứng thuật toán. Chưa có transcription thật mới để đo. |
| Phân biệt OCR raster với PDF có lớp chữ | PASS kiểm thử công cụ | Page source và điểm tách riêng; raw text toàn chứng từ chấm riêng khi có. |
| Ghép hàng và nhận diện bảng | PARTIAL phạm vi đo | Exact toàn dòng, đếm hàng/trang và hiện diện bảng; chưa có polygon IoU/nhãn cấu trúc ô độc lập. Không gọi đúng số hàng là ghép đúng. |
| Phân tích nguyên nhân lỗi | PASS kiểm tra hồ sơ | Review riêng gắn hash prediction, người duyệt và evidence; không tự phán nguyên nhân từ output sai. |
| Giữ dữ liệu nhận diện khi chưa chắc | PASS kiểm thử báo cáo | Giữ recognized fields/items, validation, warnings và đường dẫn/hash raw prediction. Không điền đáp án vào kết quả. |
| Engine inference lỗi hẳn | Giới hạn sẵn có | Benchmark cũ có thể chỉ giữ tên exception và kết quả rỗng; công cụ chấm FAIL, không khôi phục dữ liệu không được engine lưu. Không sửa inference trong lượt này. |

## 3. Trạng thái bộ nghiệm thu thực tế

Thư mục [ocr_phase35_acceptance](../../ocr_phase35_acceptance/README.md) đã tạo với `documents/` rỗng, CSV chỉ có header, `ground_truth.json` có mảng documents rỗng, catalog cũ và intake_status.json. **0 hóa đơn được tiếp nhận, 0 hóa đơn được chấm.** Không có accuracy, CER, field F1 hoặc line-item F1 thực tế mới; các giá trị này chưa đo, không phải 0% hay 100%.

| Nhóm chứng từ cần kiểm tra | Trạng thái nghiệm thu mới | Lý do |
| --- | --- | --- |
| VAT PDF có chữ | NOT TESTED | Chưa có file và nhãn mới đủ điều kiện |
| VAT JPG/PNG | NOT TESTED | Chưa có file và nhãn mới đủ điều kiện |
| PDF scan nhiều trang | NOT TESTED | Chưa có file và nhãn mới đủ điều kiện |
| Bill nhiệt | NOT TESTED | HD-01 đã dùng phát triển, không phải held-out mới |
| Nhiều dòng hàng | NOT TESTED | Chưa có bảng ground truth thực tế mới được duyệt đầy đủ |
| Nhiều mức VAT | NOT TESTED | Chưa có nhãn dòng/nhóm thuế thực tế mới được duyệt |
| Bảng nhiều bố cục | NOT TESTED | Chưa có nhóm bố cục độc lập được xác minh |
| Việt–Anh | NOT TESTED | Chưa có transcription và nhãn thực tế mới |

**Bảng từng hóa đơn:** chưa có hàng đủ điều kiện. Công cụ sẽ sinh `acceptance.md`/`acceptance.json` theo ID sau khi có bộ thật đã khóa và inference tương ứng; không tạo ID giả hoặc tái dùng điểm synthetic để lấp bảng. Các test của công cụ dùng payload/fixture synthetic chỉ chứng minh thuật toán đánh giá và cơ chế bảo vệ, không chứng minh chất lượng OCR thực tế.

## 4. Kết quả kiểm thử mã nguồn

- Kiểm thử liên quan công cụ nghiệm thu, parser, benchmark/evaluator: **59 PASS, 0 FAIL**; gồm 29 test mới cho intake, khóa nhãn, chống leakage, CER/WER, unit/page/VAT, dữ liệu partial và tính toàn vẹn bằng chứng.
- Toàn bộ Backend tests: **230 PASS, 0 FAIL**, 5 warnings, 50,43 giây. Xem JUnit cuối lượt tại [tool-tests-final.xml](../../ocr_phase35_acceptance/tool-tests-final.xml). 59 test liên quan là tập con của 230, không cộng thêm. Warnings là deprecation Starlette/httpx và SQLite datetime adapter.
- Các lần kiểm thử Backend dùng SQLite/fixture/thư mục tạm mới, không dùng PostgreSQL hoặc SQLite Website.
- Không chạy Web tests/build vì không đổi frontend/API hoặc tích hợp runtime. Browser UAT, PostgreSQL và thử upload với parser mới vẫn NOT TESTED.

Đã thử CLI init/help thực tế và tạo intake rỗng thành công. Các lệnh freeze/evaluate có kiểm thử tự động với dữ liệu cô lập; chưa chạy freeze/inference nghiệm thu trên hóa đơn thật vì chưa đủ dữ liệu.

## 5. Những lỗi và giới hạn còn tồn tại

Giữ nguyên các kết luận có bằng chứng từ [Giai đoạn 3.1–3.4](OCR_PHASE3_TABLE_EXTRACTION_RESULTS.md):

- Hai dòng development cũ còn sai dấu; bản scan song ngữ còn số lượng sai dù OCR đọc lại có ứng viên khác.
- Bill thực HD-01 vẫn 0/4 dòng đúng; lỗi phân loại có thể chặn nhánh bill.
- Tên người bán và subtotal còn lỗi ở một số mẫu; không được sửa bằng cách lấy đáp án từ chứng từ nghiệm thu.
- Confidence chưa được hiệu chuẩn; điểm cao vẫn có thể sai dấu. Cảnh báo số học không chứng minh chữ/số đọc đúng.
- Nối mô tả qua ranh giới trang, tiêu đề cột mất, bố cục khó và ảnh phối cảnh/nhăn nặng chưa có bằng chứng đủ.
- Baseline không lưu page boxes/đơn vị/trang đầy đủ. Công cụ báo thiếu metadata, không giả lập tọa độ/trang hay nhận điểm đúng cho các phần chưa được hỗ trợ.
- Chưa có benchmark real held-out được xác minh độc lập, chưa thống nhất ngưỡng chấp nhận theo từng chỉ số/nhóm; không tự chọn ngưỡng để tuyên bố đạt.

## 6. File của lượt này và bảo toàn runtime

File mới trong repo:

- `backend/tools/ocr_benchmark/acceptance.py`
- `backend/tests/test_ocr_acceptance.py`
- `docs/OCR_PHASE35_ACCEPTANCE_GUIDE.md`
- `docs/OCR_PHASE35_ACCEPTANCE_STATUS.md`

Tài liệu cũ `docs/OCR_PHASE3_TABLE_EXTRACTION_RESULTS.md` được thêm liên kết checkpoint mới. Workspace ngoài repo có bộ intake rỗng/catalog/trạng thái/README và JUnit kết quả kiểm thử. Không chỉnh các file app/main, extraction, parser prototype, model, Website, Mobile hay .env.

Hash pipeline chính thức vẫn `c878ec80cb32e1d2f8dada0329e70c6bf4eed708246dcef0ef1b108c094c3218`; hash prototype bảng vẫn `3bdaced70ac55603fe2bba9bb1156e1b91e474e3cdd071979f7231d85bafa621`. Tesseract mặc định và công cụ PaddleOCR được giữ nguyên. Không seed/migrate/reset/restore, không sửa dữ liệu, không commit/push.

## 7. Điểm dừng và việc người dùng cần cung cấp

1. File gốc thật mới được phép sử dụng, nhiều nhà cung cấp/họ bố cục, tách khỏi các tập đã dùng phát triển. Nếu hai file chưa đăng ký ở trên được đề nghị sử dụng, trước tiên xác minh chúng chưa từng được xem để phát triển và có quyền dùng; không mặc định chúng là held-out.
2. Người gán nhãn và người xác minh độc lập; đáp án chép từ file gốc, gồm đơn vị tính và vị trí trang, transcription nếu đo CER/WER.
3. Duyệt nhãn trước khi chạy OCR; dùng partial khi chưa kiểm tra đủ bảng/trường. Công cụ không tự chuyển tất cả thành approved.
4. Thực hiện các lệnh trong [hướng dẫn tiếp nhận và đánh giá](OCR_PHASE35_ACCEPTANCE_GUIDE.md). Mỗi output mới, không sửa prediction/GT đã khóa.

Sau đo đầu tiên, phân loại lỗi bằng bằng chứng, chỉ dùng tập development độc lập để cải thiện tổng quát: cấu trúc cột/hàng, nối trang, tiền xử lý, đọc lại ô mơ hồ và hiệu chuẩn confidence. Nếu dữ liệu held-out được dùng để sửa thì phải đổi trạng thái thành development và chuẩn bị bộ nghiệm thu mới.

**Kết luận: công cụ sẵn sàng, nghiệm thu OCR thực tế đang chờ dữ liệu. Chưa đủ điều kiện tích hợp parser vào FINTECH OCR. Dừng tại đây, không mở rộng API/Website.**
