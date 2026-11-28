# Giai đoạn 8 — Tích hợp Hybrid V6 có cấu hình thử nghiệm

> **Kết quả mới nhất:** [Web UAT thực tế](OCR_PHASE8_WEB_UAT.md) đã kiểm chứng login/upload/lưu/readback/edit và fallback trên PostgreSQL test; chất lượng OCR vẫn FAIL ở nhiều trường/hàng. [Giai đoạn 9 mới là đề xuất](OCR_PHASE9_PROPOSED_PLAN.md), chưa triển khai. Các trạng thái chưa chạy Web bên dưới giữ lịch sử lúc vừa hoàn tất code.

> **Cập nhật vận hành sau lượt code, 19/11/2026:** đã truy cập Docker từ ngữ cảnh Windows, tạo/xác minh backup mới, preflight PostgreSQL test và khởi động Backend 8000/Web 5173 với Hybrid bật. Xem [báo cáo runtime hiện tại](OCR_PHASE8_RUNTIME.md). Các mục BLOCKED/NOT TESTED phía dưới mô tả thời điểm hoàn tất code trước khi chạy môi trường; Browser UAT upload/accuracy vẫn chưa được thực hiện.

Ngày 19/11/2026. Nhánh `feature/thien`. **Tại thời điểm hoàn tất code: đã tích hợp và kiểm thử tự động, chưa bật dịch vụ. Runtime hiện tại xem cập nhật phía trên; chưa nghiệm thu OCR.**

## Phạm vi và kiến trúc

Theo yêu cầu mới, Giai đoạn 7 tạm dừng: 24 draft, 0 approved, 51 câu hỏi cũ + 5 cảnh báo mới, chưa có hồ sơ con người A/B, chưa freeze/benchmark. Còn thiếu 4 VAT Việt–Anh thật, ít nhất 3 PDF và 2 chứng từ nhiều trang có quyền dùng/độc lập. Không sửa nhãn hoặc chạy benchmark Giai đoạn 7. Các kết quả development Phase6/310 tests trước đây là lịch sử, không phải nghiệm thu độc lập.

Luồng mới: Web upload hiện có → kiểm tra file/RBAC hiện có → `app/ocr_runtime.py` trong threadpool → current hoặc Hybrid V6 → ánh xạ trường/dòng hàng sang ORM hiện có → lưu `ExtractionRun`/`InvoiceItem` → validation hiện có → API detail → giao diện review/edit. Không đổi endpoint upload, không thêm schema/migration, không đổi CORS, .env hoặc cổng đang chạy.

- `OCR_PIPELINE=current` là mặc định. Không import Hybrid khi dùng mặc định. Parser XML cũ được dùng ngay cả khi bật Hybrid; XML không cần OCR ảnh.
- `OCR_PIPELINE=hybrid_v6` chỉ hợp lệ với `APP_ENV=testing`, tránh bật thử nghiệm trong cấu hình production/development thông thường. Không có nút cho client tự chọn engine hay vượt cấu hình Backend.
- Tái sử dụng nguyên `tools/ocr_benchmark/hybrid_v6.py` cùng V4/V5/table modules, **không sửa thuật toán frozen**. Chỉ import hàm extraction, không chạy CLI benchmark, đọc nhãn hoặc gọi dịch vụ AI ngoài. Tesseract vẫn là OCR engine; không cài mô hình/thư viện mới, giữ PaddleOCR.
- `OCR_HYBRID_FALLBACK=true` mặc định: lỗi Hybrid hoặc dữ liệu không tương thích cột hiện có được phát hiện trước khi tạo dòng ORM, quay về pipeline current. API/UI ghi rõ fallback, không giả đây là kết quả V6. Nếu tắt fallback, giữ hành vi extraction failed/validation error hiện có và vẫn giữ file nguồn.
- `OCR_HYBRID_MAX_PAGES=12` mặc định, cho phép 1–12. Hybrid báo `truncated` khi vượt giới hạn; UI cảnh báo chưa bao phủ cả file, không âm thầm gọi đủ trang. Không thay quy tắc validation/approval/lookup.
- Các lệnh Hybrid dùng RLock/raster hook scoped sẵn có của V6, tuần tự trong một process; không bật instrumentation `measured()` offline trên API. Threadpool tránh chặn event loop trong lúc OCR. Chưa đo tải đồng thời/latency Website.

## Dữ liệu và giao diện

Các trường loại, số/ký hiệu/ngày hóa đơn, seller/buyer/MST, subtotal, VAT và total đi vào các cột `invoices` sẵn có. Đơn vị, lượng, đơn giá, thành tiền đi vào `invoice_items`; null và 0 phân biệt, không suy từ tổng hoặc tự tạo hàng. Chỉ ánh xạ cột được hỗ trợ, kiểm tra số hữu hạn/phạm vi/độ dài trước khi persist. Không thay, xóa hay xử lý lại hóa đơn cũ.

`extraction_runs.method=hybrid-v6`; `raw_text` lưu văn bản OCR, `extracted_json.items` là các dòng đã ánh xạ. `_ocr.evidence` giữ output gốc, page boxes/polygon, OCR word score, dòng/cột/đơn vị/trang/VAT khi engine hỗ trợ, candidates, findings và fallback V4. Metadata này không được dùng để tự verified/approved. Điểm từ engine chưa hiệu chuẩn; confidence_score của Hybrid giữ null, UI hiển thị “Chưa đo độ đầy đủ” thay vì 0% chính xác.

Detail response bổ sung tùy chọn `ocr` gồm requested/used pipeline, fallback/reason, requires_review, findings, truncated; không trả cả bằng chứng lớn qua danh sách. File/schema cũ không có `_ocr` vẫn đọc được. Không thay các field cũ hoặc endpoint. Quyền truy cập detail vẫn qua `invoice_allowed`.

Web giữ giao diện review hiện có, bổ sung nhãn thử nghiệm/fallback/XML và cột đơn vị có thể chỉnh sửa theo quyền Employee draft/rejected. Unit dùng payload/correction history hiện có; người khác không được chỉnh sửa. Approval/Tax Lookup độc lập. Thuế cấp dòng/trang không có cột riêng vẫn giữ trong evidence, không tạo schema hoặc gộp giả nhiều rate thành một giá trị. Những khả năng nhận diện chưa đủ bằng chứng vẫn cần người dùng đối chiếu.

## Kết quả đã chạy

| Hạng mục | Kết quả thực tế | Giới hạn bằng chứng |
|---|---|---|
| Toàn bộ Backend tests | **325 PASS / 0 FAIL / 0 SKIP**, 5 warnings, 83,85 s | SQLite memory/tmp fixtures; không dùng PostgreSQL/SQLite Website |
| Adapter/runtime/API mới | 15 ca trong tổng 325 | Flag/default/guard, PNG/JPG/JPEG/PDF mapping, null/unit/evidence, XML, fallback on/off, readback/edit/history/RBAC |
| Tesseract thật + Hybrid | PASS thực thi với ảnh PNG synthetic mới | Có raw text/box/score, không phải benchmark accuracy hóa đơn thật |
| Upload → Hybrid thật → DB → GET/file | PASS API TestClient với PNG synthetic | DB in-memory và uploads tạm; không phải HTTP/Uvicorn/Browser UAT |
| PDF text nhúng | PASS extraction Hybrid thật trên PDF synthetic | Không chứng minh chất lượng PDF scan hoặc nhiều trang thật |
| Web tests | **25 PASS / 0 FAIL** | Kiểm thử helper/state; không phải browser nghiệp vụ |
| `npm.cmd run build` | **PASS**, Vite 6.4.5 | Cảnh báo bundle >500 kB; không sửa cấu hình ngoài phạm vi |
| Source lock V6 và GT Phase7 | PASS giữ nguyên | 14 source hashes frozen, 24 ảnh/nhãn không đổi |
| PostgreSQL/Docker runtime | **BLOCKED** | Docker Engine từ chối quyền phiên Codex; không thử lặp lại, không kết nối DB chính |
| Website UAT và hóa đơn thực mới | **NOT TESTED** | Cần Backend test/backup/runtime riêng được xác minh trước upload |

JUnit: [backend-tests.xml](../../ocr_phase8_integration/backend-tests.xml), lần targeted trước đó 14/14 tại [targeted-tests.xml](../../ocr_phase8_integration/targeted-tests.xml). Bộ sau cùng có thêm ca thực OCR/API; không cộng các tập con vào tổng. Lần đầu ba ca API fixture dùng byte giả thay file PNG hợp lệ đã bị kiểm tra file từ chối; sửa fixture sang PNG thật, không nới kiểm tra upload. Web lần đầu vướng cờ Node đã bỏ và PowerShell chặn npm.ps1; chạy lại bằng `node --test` và `npm.cmd`, không đổi execution policy.

Đọc cấu hình checkout (không chứng minh process đang chạy): PostgreSQL driver psycopg, DB `fintech_ocr`, APP_ENV development, upload `backend/uploads`, pipeline current. Không mở kết nối DB đó; tất cả tests override DATABASE_URL sang SQLite memory, APP_ENV testing và upload tạm. Không dừng hay khởi động lại service đang hoạt động.

## Bật thử nghiệm trên PostgreSQL test bằng PowerShell Windows

Chạy tại repo **FINTECH_OCR_GitHub**, không chạy ở starter. Không dùng cấu hình chính để upload thử. Hoàn tất backup DB test và xác minh danh mục trước mọi upload. Các lệnh dưới đây dành cho người vận hành trên Windows; **Codex chưa thực thi backup/khởi động hoặc upload PostgreSQL** trong lượt này.

Backup DB test mới (tên container phải đúng container đã kiểm tra; dừng nếu Docker không truy cập được):

```powershell
$containerName = 'fintech_ocr_postgres'
$dumpName = 'fintech_ocr_rbac_test_before_phase8_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.dump'
$backupDir = '<LOCAL_PATH>
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
docker exec $containerName pg_dump -U fintech -d fintech_ocr_rbac_test -Fc -f "/tmp/$dumpName"
if ($LASTEXITCODE -ne 0) { throw 'Backup DB test thất bại; không upload.' }
docker exec $containerName pg_restore --list "/tmp/$dumpName"
if ($LASTEXITCODE -ne 0) { throw 'Không đọc được danh mục backup; không upload.' }
docker cp "${containerName}:/tmp/$dumpName" (Join-Path $backupDir $dumpName)
if ($LASTEXITCODE -ne 0) { throw 'Chưa sao chép được backup về Windows.' }
Get-Item -LiteralPath (Join-Path $backupDir $dumpName) | Select-Object Name,Length
```

Terminal Backend **mới**: dùng tài khoản/kết nối đã có trong cấu hình để đổi duy nhất tên DB thành test trong biến môi trường của terminal, không in URL/mật khẩu hoặc ghi `.env`. Đoạn đọc Settings chỉ tạo Engine lazy, không mở DB chính. Dừng khi backend không dùng PostgreSQL hoặc thiếu quyền DB test; không tạo DB/seed/migration để vượt kiểm tra.

```powershell
Set-Location '<LOCAL_PATH>
$env:APP_ENV = 'testing'
$env:OCR_PIPELINE = 'current'
$phase8Url = & .\.venv\Scripts\python.exe -c "from app.core import settings; from sqlalchemy.engine import make_url; u=make_url(settings.database_url); assert u.get_backend_name()=='postgresql', 'Expected PostgreSQL config'; print(u.set(database='fintech_ocr_rbac_test').render_as_string(hide_password=False))"
if ($LASTEXITCODE -ne 0) { throw 'Không lấy được cấu hình PostgreSQL; dừng.' }
$env:DATABASE_URL = $phase8Url.Trim()
Remove-Variable phase8Url
$env:UPLOAD_DIR = Join-Path (Get-Location) 'uploads_rbac_test'
$env:OCR_PIPELINE = 'hybrid_v6'
$env:OCR_HYBRID_FALLBACK = 'true'
$env:OCR_HYBRID_MAX_PAGES = '12'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
@'
from pathlib import Path
from sqlalchemy import text
from app.core import engine, settings
assert settings.app_env == 'testing'
assert engine.url.get_backend_name() == 'postgresql'
assert engine.url.database == 'fintech_ocr_rbac_test'
assert Path(settings.upload_dir).resolve() == (Path.cwd() / 'uploads_rbac_test').resolve()
assert settings.ocr_pipeline == 'hybrid_v6'
with engine.connect() as connection:
    assert connection.scalar(text('select current_database()')) == 'fintech_ocr_rbac_test'
print('PREFLIGHT PASS: testing / fintech_ocr_rbac_test / uploads_rbac_test / hybrid_v6')
'@ | & .\.venv\Scripts\python.exe -X utf8 -
if ($LASTEXITCODE -ne 0) { throw 'Runtime preflight không đạt; không khởi động/upload.' }
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { throw 'Cổng 8000 đang có tiến trình; không tự tắt. Chọn cổng test trống và cập nhật VITE_API_URL của terminal Web tương ứng.' }
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Uvicorn này phải được khởi động ngay trong **cùng terminal/env/interpreter đã preflight**, không tái dùng một process cũ chỉ vì `/health` ok. Không dùng `--reload`/nhiều worker khi kiểm tra ban đầu. `/health` không đủ chứng minh DB runtime. Chỉ tiến hành upload khi backup và preflight đều đạt, xác nhận process mới/command/cổng và Web gọi đúng địa chỉ đó. Nếu chọn cổng Backend khác, thay cả lệnh uvicorn và VITE_API_URL dưới đây; không sửa CORS để che lỗi.

Terminal Web mới:

```powershell
Set-Location '<LOCAL_PATH>
if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { throw '5173 đã được sử dụng; kiểm tra đúng Vite đang chạy, không tự tắt process.' }
$env:VITE_API_URL = 'htt<LOCAL_PATH>
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Mở `htt<LOCAL_PATH>`, đăng nhập Employee test có sẵn. Upload **file mới** được phép dùng (không upload lại/xử lý lại ID 1/2/3 hoặc #12 để sửa lịch sử). Mở detail: kiểm tra nhãn Hybrid/fallback, raw/extracted data, đơn vị/null, sửa/lưu/F5 và correction history. Kiểm tra approval/lookup không tự verified. Người dùng/PO phải đối chiếu hóa đơn thật, không lấy unit tests làm bằng chứng accuracy. Accountant/Admin chỉ thực hiện chức năng theo RBAC hiện có; upload vẫn Employee.

## Tắt và rollback

Trong terminal Backend test, Ctrl+C **đúng tiến trình do mình vừa mở**, đặt `$env:OCR_PIPELINE='current'` rồi chạy lại cùng lệnh Uvicorn với cùng DB/upload test. XML/current không cần module Hybrid. Không đổi dữ liệu hoặc reprocess bản ghi cũ: các invoice đã tạo bằng V6 vẫn giữ kết quả/bằng chứng để review. Muốn thử fallback lỗi có thể dùng test tự động; không cố tình phá engine hoặc file thực. Không tự stop service chính, chuyển nhánh, commit/push/pull/merge.

## File thay đổi và phần chưa hoàn thành

Code: `backend/app/core.py`, `backend/app/main.py`, mới `backend/app/ocr_runtime.py`; mới `backend/tests/test_ocr_runtime.py`, `backend/tests/test_phase8_runtime_api.py`; `web/src/InvoiceDetailPage.jsx`, `.css`, mới `web/src/ocrRuntimeInfo.js` và `web/tests/ocrRuntimeInfo.test.js`. Tài liệu: báo cáo này, `docs/OCR_PHASE35_ACCEPTANCE_STATUS.md`, checkpoint ngoài repo Phase7/Phase8. Các thay đổi extraction/tests/benchmark và frontend có sẵn trước lượt được giữ nguyên, không reset/ghi đè bằng Git.

Cần tiếp tục: backup và runtime PostgreSQL test trên Windows; upload/browser UAT thật với file mới; kiểm tra readback/refresh/restart và bằng chứng OCR trong PostgreSQL; tải đồng thời/timeouts/hiệu năng; bộ dữ liệu độc lập và A/B/tiêu chí chất lượng khi mở lại Phase7. Chưa đo độ chính xác hoặc tuyên bố V6 tốt hơn trên hóa đơn mới; chưa đủ điều kiện đổi default hoặc nghiệm thu.
