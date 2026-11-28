# FINTECH OCR — Task 2: Tổng kết triển khai kỹ thuật

<a id="cau-hinh-gemini-free"></a>
## Hướng dẫn cấu hình Free-only và phê duyệt manifest · 23/11/2026

Đối chiếu trực tiếp `core.py`, `ocr_free_tier.py`, `configure_gemini_from_settings` và đường upload: **không cần sửa mã chức năng trong lượt này**. Đã bổ sung mẫu cấu hình an toàn ở `backend/.env.example`. Không sao chép toàn bộ mẫu đè lên `.env` hiện tại vì cấu hình Database/upload/môi trường phải được giữ nguyên.

Người dùng xác nhận project hiện chưa bật Billing và không chấp nhận phí API. Xác nhận này được ghi nhận trong bàn giao, không tự biến thành chứng nhận billing/quyền model hay phê duyệt chia sẻ hóa đơn; chưa điền bất kỳ cờ hoặc tham chiếu nào vào cấu hình thật.

### Tất cả biến Gemini mà mã nguồn hiện nhận

| Biến | Giá trị an toàn trong mẫu | Điều kiện khi được phép kích hoạt |
| --- | --- | --- |
| `GEMINI_ENABLED` | false | true chỉ theo quyết định kích hoạt, sau các điều kiện dưới. |
| `GEMINI_ALLOW_EXTERNAL_TRANSFER` | false | true chỉ khi việc truyền dữ liệu sang Google Free được phê duyệt. |
| `GEMINI_API_KEY` | trống | Khóa backend của đúng project; không ghi vào Frontend, manifest, log, báo cáo hoặc Git. Không đọc/xác minh khóa trong lượt này. |
| `GEMINI_MODEL` | gemini-3.8-flash | Model phải thuộc danh sách code cho phép và thực sự có quyền/quota trên project Free. Hai lựa chọn khác trong code: gemini-3.5-flash-lite, gemini-3.1-flash-lite. Không tự chọn model khác hoặc suy ra quyền truy cập từ tên. |
| `GEMINI_FREE_TIER_CONFIRMED` | false | true sau khi xác nhận Free Tier và quyền/quota model của đúng project. |
| `GEMINI_BILLING_DISABLED_CONFIRMED` | false | true sau khi xác nhận project thực sự không liên kết Billing hoạt động. Cờ chỉ ghi nhận xác nhận, không kiểm tra Google. |
| `GEMINI_FREE_TIER_REFERENCE` | trống | Tham chiếu thực tới hồ sơ xác nhận project Free, Billing tắt và khả năng dùng model. Không tự tạo ID/xác nhận giả. |
| `GEMINI_DATA_PROCESSING_APPROVED` | false | true khi có quyền và phê duyệt xử lý/phạm vi chia sẻ dữ liệu không nhạy cảm bằng Free Tier. |
| `GEMINI_APPROVAL_REFERENCE` | trống | Tham chiếu phê duyệt xử lý/truyền dữ liệu thực tế, không thay cho phê duyệt từng file. |
| `GEMINI_FREE_TIER_MANIFEST` | trống | Đường dẫn file JSON phê duyệt từng SHA-256; xem cấu trúc bên dưới. |
| `GEMINI_MAX_OUTPUT_TOKENS` | 8192 | Tùy chọn kỹ thuật, từ 256 đến 32768; không phải công thức/ngưỡng confidence. |
| `GEMINI_PAID_TIER_CONFIRMED` | false | Luôn giữ false theo phương án không phí; true bị chặn. |
| `GEMINI_PAID_TIER_REFERENCE` | trống | Biến lịch sử, không dùng/không bắt buộc trong Free-only. |

Năm cờ cho phép Free ở trên vẫn để false trong mẫu; bảng mô tả điều kiện, không tự cấp quyền. Có đủ cờ/tham chiếu mà manifest không có hash của file thì file đó vẫn chỉ xử lý tại máy. APP_ENV, OCR_PIPELINE, OCR_HYBRID_FALLBACK, OCR_HYBRID_MAX_PAGES, Database và UPLOAD_DIR là cấu hình OCR/môi trường sẵn có, không phải điều kiện để mua dịch vụ và không được đổi chỉ để bật Gemini. Giữ nguyên kiểm soát testing/Gate G13 cho Final.

### Chuẩn bị manifest cho từng chứng từ

1. Chọn file mẫu hoặc dữ liệu không nhạy cảm có quyền sử dụng/chia sẻ. Cần xem xét nội dung thật; không tự coi mọi file mẫu hoặc file đã OCR là an toàn. Hóa đơn thật nhạy cảm giữ tại máy. Nếu cần bản ẩn danh, người có thẩm quyền phải xác minh chính bản đã ẩn danh.
2. Người có thẩm quyền phê duyệt đúng file, phạm vi gửi OCR/layout sang Google Free và việc dữ liệu Free có thể được dùng cải thiện sản phẩm. Giữ hồ sơ thực gồm người duyệt, ngày, phạm vi và nội dung quyết định ở nơi quản lý hồ sơ; manifest chỉ chứa tham chiếu đến hồ sơ đó, không chứa API key hoặc nội dung hóa đơn.
3. Sau khi chốt file, lấy SHA-256 của đúng bytes sẽ upload. Lệnh PowerShell dưới đây chỉ là hướng dẫn, không được thực thi trong lượt này:

```powershell
$approvedFile = '<LOCAL_PATH>
(Get-FileHash -LiteralPath $approvedFile -Algorithm SHA256).Hash.ToLowerInvariant()
```

4. Lưu manifest bên ngoài repository, ví dụ `<LOCAL_PATH>`. Đường dẫn tương đối trong cấu hình tính từ `backend/`, không từ thư mục mở Terminal. File phải có đuôi `.json`, UTF-8 (BOM được chấp nhận), tối đa **256.000 byte**.

Manifest rỗng hợp lệ, chưa phê duyệt bất kỳ file nào:

```json
{"documents": []}
```

Một mục nháp có đúng cấu trúc bên dưới. **Mục nháp này không hợp lệ để kích hoạt**, vì chưa có hash/phê duyệt và hai xác nhận vẫn false. Chỉ người có thẩm quyền mới hoàn tất giá trị thực rồi thêm mục đã duyệt vào danh sách `documents`:

```json
{
  "sha256": "",
  "data_class": "approved_non_sensitive",
  "non_sensitive_confirmed": false,
  "external_transfer_approved": false,
  "approval_reference": ""
}
```

Mỗi mục được phép phải có **đúng năm khóa** trên: `sha256` là 64 ký tự hex của file; `data_class` chỉ nhận `sample` hoặc `approved_non_sensitive`; cả hai xác nhận phải là boolean JSON `true` (không phải chuỗi); `approval_reference` là chuỗi tham chiếu thực không rỗng. Không thêm tên hóa đơn, người duyệt, ngày hoặc chú thích thành field mới trong manifest; các nội dung đó thuộc hồ sơ tham chiếu. Root chỉ có `documents`; không khóa JSON trùng, không hash trùng (kể cả khác chữ hoa/thường), không field thừa. Mục nháp, file sai cấu trúc hoặc thiếu quyền sẽ làm đăng ký Gemini bị từ chối, không tự bỏ qua mục sai.

5. Khi đủ hồ sơ/cấu hình, người quản lý mới quyết định kích hoạt; lượt này không thực hiện thay đổi đó. Manifest được nạp ở startup; thay danh sách cần Backend nạp lại cấu hình bằng quy trình vận hành hiện có, không tự xử lý lại hóa đơn đã lưu. Sửa bytes của file sau duyệt sẽ đổi hash và cần duyệt bản mới; đổi tên file đơn thuần không đổi hash. Gỡ hash khỏi manifest và nạp lại cấu hình sẽ không cho file đó sử dụng Free ở các lượt mới.

### Trạng thái và phần còn thiếu

Đã có SDK theo lượt cài đặt trước và có mã kiểm soát/phê duyệt. Chưa có bằng chứng mới về quyền/quota model trên project hoặc hồ sơ chia sẻ từng file; không suy ra các điều đó từ xác nhận chưa bật Billing. Còn cần các tham chiếu thực, manifest được duyệt và quyết định kích hoạt rõ ràng. Không cài lại SDK hoặc đọc .env/khóa trong lượt này. Client không tự kiểm chứng billing; để không có phí API, project thực sự phải giữ Billing tắt.

File không được duyệt, Gemini chưa cấu hình hoặc hết quota đều giữ OCR/Hybrid local theo mã hiện có, không tự mua dịch vụ/đổi key/project/model. Chỉ bổ sung mẫu và tài liệu; không sửa thuật toán, API, schema, Validation, Website, Gate G13 hoặc TBD-02. Không chạy test/OCR/benchmark/API/DB hoặc thao tác ghi Git. Chưa có PASS thực thi, Final hoặc NFR01 mới.

## Quyết định thay thế: chỉ dùng OCR local và Gemini Free Tier · 23/11/2026

**Không dùng Paid Tier, không bật Billing hoặc chấp nhận phí API.** Điều kiện Paid Tier được ghi ở các mục trước chỉ còn là lịch sử và được thay bằng chế độ Free-only này. Không tự đặt Paid Tier=true hoặc tạo bằng chứng phê duyệt giả. Mặc định và .env hiện có không được sửa.

### Phạm vi triển khai

- Thêm `backend/app/ocr_free_tier.py`: danh sách model text có Free Tier đã đối chiếu, manifest phê duyệt theo file và ContextVar mang SHA-256 tính từ bytes upload thực. Không đọc hóa đơn từ đĩa/DB, không dùng dữ liệu dự đoán để phân loại nhạy cảm.
- `core.py` thêm các cấu hình Free Tier mặc định chưa xác nhận; `ocr_llm.py` bỏ điều kiện bắt buộc Paid, thay bằng xác nhận Free/Billing tắt cùng phê duyệt truyền dữ liệu và xử lý. Paid confirmation=true bị từ chối. Có đủ cờ toàn cục vẫn không có nghĩa được gửi mọi hóa đơn.
- `ocr_runtime.py` gắn phạm vi file thực cho cùng luồng OCR → merger. File không nằm trong manifest giữ OCR/Hybrid tại máy, không dựng nguồn gửi Gemini. Adapter kiểm lại quyền file trước khi tạo client. XML vẫn không gọi LLM; API, schema JSON, Validation, Review/Edit, Approval/Lookup, sáu module Hybrid frozen và fallback không đổi.
- Gemini Free tối đa một request cho mỗi lượt upload đủ điều kiện; SDK không retry. Lỗi/quota/429/timeout/JSON sai đều giữ kết quả OCR, không chuyển model, key, project, provider hoặc trả phí. Không có thao tác bật Billing trong ứng dụng. `ocrRuntimeInfo.js` hiện thông báo local-only hoặc hết hạn mức trong khu vực cảnh báo sẵn có, không thiết kế lại trang.

### Điều kiện cấu hình, không tự áp dụng

| Cấu hình | Yêu cầu |
| --- | --- |
| `GEMINI_ENABLED`, `GEMINI_ALLOW_EXTERNAL_TRANSFER` | Vẫn mặc định false; chỉ bật sau phê duyệt, không bật trong lượt này. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Khóa của project Free thực sự không có Billing, model được project cấp quyền và còn quota; không đọc hoặc xác minh khóa trong lượt này. |
| `GEMINI_FREE_TIER_CONFIRMED`, `GEMINI_BILLING_DISABLED_CONFIRMED` | Mặc định false; người có thẩm quyền xác nhận project, model và Billing thực tế, không suy ra từ khóa. |
| `GEMINI_FREE_TIER_REFERENCE` | Tham chiếu thực tới xác nhận Free Tier/Billing tắt và khả năng truy cập model. |
| `GEMINI_DATA_PROCESSING_APPROVED`, `GEMINI_APPROVAL_REFERENCE` | Quyền xử lý và phê duyệt truyền dữ liệu không nhạy cảm sang Free Tier. Không cấp phép chung cho dữ liệu thật nhạy cảm. |
| `GEMINI_FREE_TIER_MANIFEST` | Đường dẫn JSON chỉ chứa các hash và phê duyệt từng chứng từ. Nên lưu ngoài repository, ví dụ `<LOCAL_PATH>`; chưa tạo file hoặc nhập phê duyệt thay người dùng. Đường dẫn tương đối được tính từ backend/. |
| `GEMINI_PAID_TIER_CONFIRMED` | Giữ false; giá trị true bị chặn. Paid reference cũ không bắt buộc và không kích hoạt dịch vụ trả phí. |

Manifest ban đầu an toàn là `{"documents": []}`: không file nào được phép gửi. Mỗi mục khi thực sự được phê duyệt phải có đúng `sha256` (64 ký tự hex của file đã xét), `data_class` (`sample` hoặc `approved_non_sensitive`), `non_sensitive_confirmed=true`, `external_transfer_approved=true` và `approval_reference` thực tế. Không nhập giá trị mẫu giả để làm phê duyệt. Thiếu trường, sai kiểu, trùng hash hoặc JSON không hợp lệ làm đăng ký Gemini bị từ chối. Manifest được nạp khi Backend khởi động, không làm thay đổi dữ liệu hóa đơn.

Hóa đơn thật nhạy cảm không được đưa vào manifest; tiếp tục OCR/Hybrid tại máy, lưu/chỉnh sửa/validation theo luồng hiện có. Nếu muốn sử dụng bản đã ẩn danh, cần tự có bản được phép sử dụng và phê duyệt đúng SHA của bản đó; hệ thống không tự coi dữ liệu đã được ẩn danh.

Theo [bảng giá Google](http<LOCAL_PATH>`gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` có Free Tier tại thời điểm đối chiếu. Không chọn TTS/image/tool/preview chỉ vì cùng tiền tố; chỉ những tên text này được chấp nhận trong policy hiện tại. GEMINI_MODEL vẫn cấu hình được, không tự đổi .env hoặc thử model để dò quyền. Quota/quyền project có thể khác; chưa xác minh bằng API. Dữ liệu Free Tier có thể được Google sử dụng cải thiện sản phẩm nên chỉ áp dụng cho nguồn được phép, không coi Free là chính sách dữ liệu của Paid.

**Giới hạn:** client không có tùy chọn bảo đảm miễn phí nếu ai đó bật Billing trên project ở ngoài ứng dụng. Muốn không phát sinh phí API, project phải thực sự không liên kết Billing; xác nhận/ref là trách nhiệm vận hành, không phải kiểm chứng tự động. Không có quota vô hạn. SDK đã được cài từ lượt trước; lượt này không đọc .env/khóa, không gọi API, test, OCR, benchmark hoặc Database và không cài thêm thư viện. Mã Free-only đã nối vào luồng, chưa xác minh thực thi/accuracy. Gate G13, confidence TBD-02, Final/NFR01 không được đánh dấu PASS.

## Điều kiện xử lý chứng từ thật · 23/11/2026

Rà soát cho thấy cơ chế opt-in trước đây chưa bắt buộc xác nhận Paid Tier và quyền xử lý dữ liệu thật riêng biệt. Đã thêm ba cấu hình trong `core.py` và yêu cầu tương ứng trong `ocr_llm.py`: `GEMINI_PAID_TIER_CONFIRMED`, `GEMINI_PAID_TIER_REFERENCE`, `GEMINI_DATA_PROCESSING_APPROVED`. Mặc định chưa xác nhận; không bật cờ hoặc tạo bằng chứng thay người dùng. `GEMINI_APPROVAL_REFERENCE` hiện có phải trỏ tới phê duyệt thực, đúng phạm vi hóa đơn và việc truyền nội dung tới Google. Tham chiếu billing phải gắn đúng Cloud Project sở hữu khóa. Tính xác thực và quyền pháp lý do người có thẩm quyền xác minh ngoài hệ thống; giá trị cấu hình không tự chứng minh các sự kiện này.

Kiểm tra ở bước đăng ký và ngay trước khi tạo client/request, kể cả khi adapter được tạo trực tiếp. Gemini luôn phải có ranh giới external và tham chiếu phê duyệt nhất quán. Không sửa phần hợp nhất đã hoàn thiện, API, schema hoặc fallback. Gemini lỗi giữ kết quả OCR/Hybrid đã có, không chạy lại OCR để làm dự phòng. Tiếp tục tối đa hai request cho một lượt trích xuất, chỉ thêm một retry cho một số lỗi máy chủ; 429/timeout/JSON sai không được gọi lại ngay. Đây là giới hạn từng lượt, không chứng nhận hạn mức/budget tổng của Cloud Project.

Theo [điều khoản Gemini API](http<LOCAL_PATH>

Đã kiểm tra riêng các giá trị không bí mật: model là `gemini-3.8-flash`, hai cờ enable/transfer vẫn false, tham chiếu phê duyệt trống. Khóa có mặt nhưng không kiểm chứng hợp lệ. SDK được khai báo `google-genai==1.55.0`, chưa có trong `.venv` đã kiểm tra. [Model 3.8 Flash](http<LOCAL_PATH>

**Mã kiểm soát đã bổ sung; chưa đủ điều kiện vận hành hóa đơn thật.** Còn thiếu SDK sẵn có, xác minh khóa/Paid Tier, bằng chứng/phê duyệt phù hợp và tham chiếu thực; hai cờ chỉ được bật sau đó theo quyết định người có thẩm quyền. Không sửa `.env`, không chạy test/OCR/benchmark/API/DB, không cài thư viện, không commit/push. G13, confidence TBD-02, Hybrid frozen và NFR01 giữ nguyên, không có PASS mới.

## Bổ sung hợp nhất Hybrid/OCR và Gemini · 23/11/2026

Đã chỉnh mã nguồn theo yêu cầu tối ưu, không chạy chương trình, test, OCR, benchmark hoặc Gemini. Không truy cập Database hay chứng từ thật. Không có số liệu accuracy hoặc PASS thực thi mới.

- `backend/app/ocr_llm.py`: lưu riêng đầu vào OCR và đề xuất, nguồn ký tự/trang/region do Backend tạo; chuẩn hóa so sánh Decimal, ngày, tên và MST để tránh báo xung đột chỉ do cách biểu diễn. Giữ số 0 đầu MST/số hóa đơn; không tạo giá trị thiếu.
- Trường mới chỉ được bổ sung sau kiểm span và nhãn ngữ cảnh. Tên là chữ ký, tiêu đề hoặc nhãn người mua/bán bị từ chối. Giá trị OCR khác đề xuất được giữ kèm cảnh báo. Trường đang có nhiều ứng viên/mức VAT chưa phân giải không được LLM tự chọn một giá trị chung.
- Ô dòng hàng chỉ bổ sung khi tên/dòng/trang khớp duy nhất, các ô đã có không mâu thuẫn. Không ghép theo số thứ tự đơn thuần hoặc thay toàn bộ bảng OCR. Nếu OCR chưa có bảng, đề xuất cần vượt kiểm tra nguồn/dòng/cột độc lập trước khi sử dụng. Các ô không được dùng chung OCR region; số trong model sản phẩm không được lấy từ cột mô tả. Dùng lại bộ nhận diện header hiện có; bill không header cần dấu liên kết số lượng/đơn giá in thực. Tên xuống dòng được đối chiếu với hàng số lân cận; trường hợp không đủ căn cứ giữ đề xuất để xem xét.
- `backend/app/ocr_runtime.py`: bổ sung `source_format` vào metadata riêng. Khi PDF không có bằng chứng trang, không tự nhận bảng LLM là các dòng đúng trang. Với ảnh/bill text-only, chỉ dùng ranh giới dòng và dấu phân cách quan sát được, không bịa tọa độ. Không đổi parser XML, Final/V8 hoặc đường fallback.
- Dùng lại kiểm tra số học Decimal của parser để thêm cảnh báo sau hợp nhất. Giữ các luật validation/VAT/ITEM-SUM hiện hành; không nới quy tắc, bù tổng, phân bổ tiền hoặc tự tính VAT/giảm giá/phụ phí. Quan sát điều chỉnh và nhiều mức thuế của Final vẫn nằm trong evidence/findings, không tạo cột/API mới. Điều chỉnh đã in có thể giải thích chênh lệch nhưng chưa tự làm validation PASS.
- Adapter không retry ngay khi 429, timeout, thiếu SDK hoặc JSON không hợp lệ; chỉ tối đa một retry thêm cho 500/502/503/504. Không log thông điệp lỗi chứa nội dung. Đề xuất từng trường sai không làm mất những trường OCR đang đúng; bảng không đủ bằng chứng giữ bảng OCR.
- `web/src/ocrRuntimeInfo.js`, `web/src/InvoiceDetailPage.jsx`: thêm thông báo chưa kích hoạt/không khả dụng/giữ OCR, và nhãn dễ hiểu cho cảnh báo trường/dòng. Tái sử dụng API và khu vực cảnh báo hiện có; không đổi bố cục, route, phân quyền hoặc Task 1/Task 3.

Lưu trữ riêng dự kiến trong `_ocr.llm`: `ocr_baseline`, `proposal`, `sources`, `agreements`, `field_decisions`, `applied_fields`, `applied_cells`. Các mục này dùng cơ chế lưu ExtractionRun hiện có; chưa truy cập Database để xác minh. API vẫn chỉ trả bản tóm tắt LLM và findings theo quyền sẵn có. Có chữ khớp OCR hoặc hai phương án đồng ý không chứng minh đúng ngữ nghĩa/accuracy. Mọi đề xuất vẫn cần xem xét; TBD-02 chưa duyệt nên confidence giữ null, approval/lookup độc lập.

**Giới hạn model:** giữ nguyên cấu hình người dùng `gemini-3.5-flash`, không sửa `.env`. [Tài liệu Google hiện tại](http<LOCAL_PATH>`gemini-3.6-flash`. Mã ứng dụng không tự đổi model; chưa gọi API nên không xác minh model thực thi, hạn mức hay tính tương thích runtime. Structured output/streaming được đối chiếu với tài liệu và mã SDK chính thức; không coi đó là một lần gọi thành công.

**CODE COMPLETE – PENDING CONFIGURATION/ACCEPTANCE** cho các điểm hợp nhất và tích hợp đã sửa. SDK vẫn chỉ được khai báo, quyền truyền dữ liệu/tham chiếu phê duyệt còn chờ; không tự bật Gemini. Chưa chứng minh khả năng đọc chính xác mọi bố cục. Gate G13, pipeline mặc định, Hybrid frozen, confidence TBD-02, NFR01 và các bằng chứng cũ giữ nguyên; không có Final PASS mới. Không commit/push hoặc thay stash/backup.

## FR10 — Tích hợp Google Gemini API · 23/11/2026

**CODE COMPLETE – PENDING CONFIGURATION/ACCEPTANCE** trong phạm vi adapter Gemini và tích hợp đã được phê duyệt. Chỉ đọc/chỉnh mã nguồn; chưa xác minh thực thi. Các nhận định chưa có provider/adapter ở mục ngày 22/11 là trạng thái trước lượt này.

### Mã nguồn và luồng xử lý

- `backend/app/ocr_llm.py`: thêm `GeminiProvider` sử dụng SDK chính thức, lazy import/client, endpoint Gemini Developer API cố định, model cấu hình bắt buộc, không tự chuyển sang Vertex AI/khóa Google khác/model dự phòng. Chỉ gửi văn bản OCR theo nguồn và yêu cầu schema; không tải file gốc lên Gemini, không cung cấp tools hoặc truy xuất tài liệu ngoài.
- `backend/app/core.py`: hai cờ opt-in mặc định false, API key dạng SecretStr không đưa vào repr, model/tham chiếu phê duyệt và giới hạn output token. Không sửa `.env`.
- `backend/app/main.py`: lifespan đăng ký adapter khi đủ điều kiện, giữ trạng thái đăng ký không chứa bí mật ở `app.state.ocr_llm_configuration`; startup không gọi Gemini. Không thay endpoint, request hoặc response của API.
- `backend/requirements.txt`: khai báo `google-genai==1.55.0`, chưa cài đặt. Triển khai dựa trên [SDK Google Gen AI chính thức](http<LOCAL_PATH>

Điểm nối đã có được tái sử dụng: upload → tiền xử lý OpenCV/OCR current hoặc Hybrid được cho phép → `_complete_ocr_result` → `refine_with_llm` → Gemini nếu được cấu hình → JSON schema/evidence/mapper → confidence → lưu `ExtractionRun`/dòng hàng, validation → API chi tiết và Website. Không cần sửa `ocr_runtime.py`, `extraction.py`, API serializer hoặc Website trong lượt này. XML tiếp tục bỏ qua LLM và giữ parser hiện có.

Giá trị đề xuất phải khớp span nguồn; ô sản phẩm phải thuộc đúng dòng/trang, không dùng một span cho nhiều ô. Chỉ bổ sung trường thiếu và bảng đang trống; giữ OCR khi có bất đồng kèm cảnh báo. Không tính lại số tiền thiếu, không suy diễn VAT/MST/ngày. Kiểm span chứng minh nguồn ký tự, **không bảo đảm gán đúng ngữ nghĩa** hoặc độ chính xác tuyệt đối. Đề xuất LLM luôn cần xem xét.

Giới hạn mỗi lần gọi: timeout HTTP SDK 30 giây, kiểm thời gian khi đọc stream, đầu vào/đầu ra tối đa 1 MB (lớp chung còn giới hạn 120.000 ký tự nguồn), một candidate và số output token theo cấu hình. SDK không tự retry; lớp chung hiện cho tối đa hai lần thử. Chỉ chấp nhận stream kết thúc STOP, có JSON đầy đủ; không nhận nội dung bị chặn/cắt, non-text hoặc vượt giới hạn. Đóng stream/client khi xong/lỗi; không log khóa, prompt, phản hồi hoặc thông điệp lỗi chứa dữ liệu. Lỗi chỉ ghi tên loại exception qua cơ chế chung.

Thiếu cấu hình/SDK, lỗi transport/provider/schema/span/mapper hoặc không có đầu vào phù hợp đều giữ kết quả OCR. Dự phòng Final → snapshot V8 → current vẫn thuộc cơ chế cũ và không bị thay đổi bởi Gemini.

### Điều kiện kích hoạt, chưa áp dụng trong lượt này

| Biến môi trường | Yêu cầu |
| --- | --- |
| `GEMINI_ENABLED` | `true` để chọn adapter; mặc định `false`. |
| `GEMINI_ALLOW_EXTERNAL_TRANSFER` | `true` chỉ sau khi cho phép gửi nội dung OCR ra Google; mặc định `false`. Việc chọn provider chưa thay cho quyền truyền dữ liệu. |
| `GEMINI_PAID_TIER_CONFIRMED` | Giữ false theo quyết định Free-only mới; true bị chặn. |
| `GEMINI_PAID_TIER_REFERENCE` | Cấu hình lịch sử, không cần cho Free Tier. |
| `GEMINI_DATA_PROCESSING_APPROVED` | Mặc định false; phê duyệt dữ liệu không nhạy cảm theo phạm vi Free Tier, kèm manifest từng file. |
| `GEMINI_FREE_TIER_CONFIRMED`, `GEMINI_BILLING_DISABLED_CONFIRMED` | Xác nhận Free/Billing tắt thực tế theo quyết định mới; mặc định false. |
| `GEMINI_FREE_TIER_REFERENCE`, `GEMINI_FREE_TIER_MANIFEST` | Tham chiếu project Free và danh sách SHA-256/phê duyệt từng file; xem mục mới nhất đầu báo cáo. |
| `GEMINI_API_KEY` | Khóa hợp lệ do người dùng cung cấp; không ghi giá trị trong tài liệu/source/log. |
| `GEMINI_MODEL` | Model được người dùng chọn, hỗ trợ structured JSON/streaming và giới hạn token đã cấu hình; không có model mặc định. |
| `GEMINI_APPROVAL_REFERENCE` | Tham chiếu quyết định cho phép sử dụng provider và truyền dữ liệu. |
| `GEMINI_MAX_OUTPUT_TOKENS` | Tùy chọn, mặc định 8192; giới hạn cấu hình 256–32768, cần phù hợp model/hạn mức được duyệt. Không tự kích hoạt thanh toán. |

SDK đã khai báo phải có trong môi trường trước khi sử dụng; không cài trong lượt này. Sau khi cấu hình hợp lệ và Backend khởi động lại, chỉ các lượt OCR mới mới đi qua adapter; không tự xử lý lại hóa đơn đã lưu. Tắt `GEMINI_ENABLED` và khởi động lại để quay về OCR không gọi Gemini. Không thay đổi `.env` hiện tại hoặc lựa chọn model/khóa/quyền truyền dữ liệu thay người dùng.

### Giới hạn và trạng thái nghiệm thu

FR12 giữ policy TBD-02: chưa có công thức/ngưỡng được duyệt nên score=null, trạng thái confidence undetermined và validation cần xem xét; approval/lookup độc lập. Gemini không tự cấp score hoặc xác nhận verified. Chưa cài SDK, không gọi Gemini/API, OCR, test, benchmark, build hoặc Database; không có kết quả PASS thực thi mới. Không sửa Task 1/Task 3, thuật toán Hybrid V8 Final/V8, pipeline mặc định current, validator hay Gate G13. Manifest/bằng chứng Gate cũ không chứng minh phiên bản bổ sung này. **Final và NFR01 vẫn chưa nghiệm thu.** Không phát hiện thêm điểm nối mã nguồn còn thiếu qua rà soát tĩnh trong phạm vi adapter; khả năng hoạt động với model/SDK/runtime cụ thể chưa được xác minh.

## Bổ sung trực tiếp FR08 FR10 FR12 ngày 22/11/2026

**Đã triển khai mã nguồn tích hợp còn thiếu trong lượt này. Chưa xác minh thực thi.** Bảng đối chiếu SRS bên dưới mô tả trạng thái trước lượt bổ sung này.

| Yêu cầu | Mã đã triển khai | Điều kiện còn thiếu |
| --- | --- | --- |
| FR08 | Module OpenCV xử lý EXIF, tăng tương phản bằng CLAHE khi dải tương phản thấp, đo góc từ các đoạn thẳng gần ngang và chỉnh nghiêng nhỏ khi các quan sát đồng thuận. Giới hạn pixel/canvas, fallback về Pillow kèm metadata khi OpenCV thiếu/lỗi. Nhánh current gọi trước OCR; nhánh Final dùng hook dưới khóa raster hiện có trước khi nhận diện và ghi tọa độ. | Đã khai báo opencv-python-headless trong requirements. Chưa cài hoặc xác minh thư viện trong môi trường hiện tại; chưa đo hiệu quả OCR. Các tham số ảnh là giới hạn thuật toán, không phải ngưỡng confidence TBD-02. |
| FR10 | Provider protocol, đăng ký provider có tham chiếu phê duyệt và ranh giới local/external; chưa có provider tự động. Schema Pydantic cho trường/dòng hàng, giá trị nullable, evidence span theo source/trang/dòng. Từ chối JSON trùng khóa/non-finite, kiểu/cột không tương thích và giá trị không khớp OCR. Tối đa hai lần gọi, kiểm giới hạn đầu vào/đầu ra, giữ OCR khi lỗi. Chỉ bổ sung trường thiếu; giữ giá trị OCR mâu thuẫn và cảnh báo. Dòng hàng chỉ được nhận khi có evidence riêng và bảng OCR đang trống. | Chưa có provider/model được phê duyệt hoặc adapter transport cụ thể. API nội bộ configure_llm_provider là điểm cấu hình startup cần được nối khi provider được chọn. Adapter phải thực thi deadline truyền vào và giới hạn phản hồi tại transport. Chưa có LLM inference được kích hoạt hoặc xác minh. |
| FR12 | Cấu trúc confidence có score/status/threshold/policy/approval/evidence và tham chiếu bằng chứng từng trường. Không có policy thì score=null, trạng thái undetermined, cần xem xét. Policy được đăng ký chỉ khi có tham chiếu phê duyệt và ngưỡng hữu hạn hợp lệ; không có công thức mặc định. Điểm thấp/không xác định thêm luật CONFIDENCE khiến validation_status=needs_review. API và Web hiển thị rõ điểm chưa xác định. | TBD-02 chưa có công thức/ngưỡng được phê duyệt; chưa có policy tính điểm thực được cấu hình. Do đó chưa có điểm confidence đã hiệu chuẩn để báo cáo. |

### Luồng đã nối trong mã nguồn

Upload → extract_document → OCR/current hoặc Final và snapshot V8 → lớp LLM theo provider được cấu hình → kiểm schema/evidence/mapper → đánh giá confidence → Invoice/InvoiceItem/ExtractionRun → validation → API detail → Web. XML bỏ qua hai lớp LLM/confidence mới và dùng hợp đồng parser trước đó.

LLM chỉ nhận văn bản OCR theo nguồn và JSON schema. Không có transport mạng hoặc lời gọi mô hình được cài mặc định. Đăng ký provider ngoài local đòi hỏi external_transfer_approved cùng tham chiếu phê duyệt; không có cấu hình như vậy trong lượt này. Evidence span chỉ chứng minh nguồn ký tự, không chứng minh mô hình gán đúng ngữ nghĩa seller/buyer hay cột. Vì vậy luôn có cảnh báo cần đối chiếu cho đề xuất LLM.

Confidence ban đầu lưu trong _ocr.confidence của ExtractionRun. Mỗi lần validation lại dùng dữ liệu hiện tại để đánh giá bằng policy nếu có, lưu assessment theo validation_round trong message JSON của luật CONFIDENCE hiện có. API chọn assessment vòng mới nhất; không sửa dữ liệu ExtractionRun gốc để che thay đổi. Approval và Lookup không được suy ra từ confidence. Chỉnh sửa thủ công không tự tạo điểm; evidence OCR cũ vẫn được ghi nhận là lịch sử.

Hóa đơn OCR tạo mới với policy chưa cấu hình sẽ có confidence=null và needs_review, dù các kiểm tra số học đạt. Hóa đơn cũ không có metadata confidence tiếp tục đi theo hành vi trước đó. Mã nhánh current giữ completeness cũ trong metadata riêng và không trình bày nó thành điểm tin cậy.

### Tệp chức năng của lượt bổ sung

- Mới: backend/app/ocr_preprocessing.py, backend/app/ocr_llm.py, backend/app/ocr_confidence.py.
- Sửa: backend/app/extraction.py, backend/app/ocr_runtime.py, backend/app/main.py, backend/requirements.txt.
- Sửa phần hiển thị confidence thuộc Task 2: web/src/ocrRuntimeInfo.js, web/src/InvoiceDetailPage.jsx.
- Tài liệu: báo cáo này, CODEX_HANDOFF.md và OCR_PHASE13_CHECKPOINT.md.

### Giới hạn bàn giao

Chỉ đọc/chỉnh source; không chạy test, benchmark, OCR, API, Database hoặc build. Chưa cài OpenCV, chưa chọn hay gọi LLM, chưa tự đặt policy TBD-02. Không thay .env, mặc định current hoặc điều kiện testing của Final. Gate đang dùng giữ nguyên; manifest đề xuất G13 trước lượt này chưa bao phủ các hash/tệp mới và không cấp phép mã mới. Không cập nhật hash để giả đạt.

**Trạng thái lập trình.** Đã hoàn thiện lớp tích hợp FR08, giao diện và cơ chế xử lý FR10 khi chưa có provider được duyệt, cùng cấu trúc/policy/luồng lưu và trạng thái FR12 theo yêu cầu lượt này. FR10 chưa có adapter cho mô hình cụ thể và FR12 chưa có policy tính điểm cụ thể, vì hai lựa chọn đó chưa được phê duyệt. Chưa thể gọi toàn bộ Task 2 đã vận hành đầy đủ theo SRS hoặc nghiệm thu đạt. Không có Final PASS/NFR01 PASS mới.

## Kết luận đối chiếu SRS gốc ngày 22/11/2026

**Đính chính kết luận chốt trước. Phần OCR/parser Hybrid V8 Final đã được tích hợp, nhưng chưa thể xác nhận hoàn thành toàn bộ Task 2 theo nguyên văn FR08–FR13.** FR10 còn thiếu LLM trong luồng trích xuất; FR12 còn thiếu cơ chế confidence và xử lý confidence thấp thống nhất. Các mục chốt trước bên dưới ghi nhận phạm vi OCR/parser đã triển khai ở thời điểm đó.

### Tài liệu làm căn cứ

Đọc trực tiếp nội dung DOCX trong thư mục `<LOCAL_PATH>`:

- `C1SE_86_SRS_FINTECH_OCR_v1_0.docx`, bảng FR08–FR13, UC04–UC06/UC08, BR04–BR10 và TBD-02.
- `C1SE_86_User_Story_FINTECH_OCR_v1.0.docx`, Employee PB03, PB04, PB05, PB06, PB07 và PB08. PB25 là câu chuyện giải thích cảnh báo có ưu tiên thấp, không dùng để mở rộng Task 2 trong lượt này.
- `C1SE86_ProjectPlan_FINTECH_OCR_ver1.2.docx`, deliverable OCR/AI Extraction and Validation, WBS 3.1.6.3 và 3.1.6.4. Kế hoạch nêu kết hợp OCR, regex và LLM. WBS đánh giá accuracy là công việc nghiệm thu, không phải lý do phát triển thêm phiên bản Hybrid.

### Ma trận yêu cầu và mã nguồn

| Yêu cầu SRS | Phần có trong mã nguồn hiện tại | Khoảng thiếu hoặc khác biệt | Trạng thái triển khai |
| --- | --- | --- | --- |
| FR08 — Tiền xử lý và OCR Việt–Anh | `extraction.py` và `pipeline_v4.py` có chỉnh nghiêng, tăng tương phản, OCR Tesseract vie+eng, PDF có chữ và PDF scan. Upload gọi qua `ocr_runtime.extract_document`. | Tiền xử lý dùng Pillow; SRS/UC04 nêu OpenCV. Chức năng tiền xử lý đã có, cần ghi nhận khác biệt công nghệ. Chất lượng và độ tương đương trên bản hiện tại chưa xác minh. | Có luồng chức năng; còn khác biệt công nghệ với nguyên văn SRS |
| FR09 — Parse XML trực tiếp | Parser XML lấy trường và dòng hàng, kiểm cấu trúc; nhánh XML sử dụng parser hiện có và lưu kết quả, không gọi OCR ảnh. | Không phát hiện khoảng thiếu ở nhánh parse XML trực tiếp. So sánh XML–PDF của PB24 là phạm vi đối chiếu mở rộng riêng. | Đã có mã nguồn và tích hợp |
| FR10 — Dùng LLM trích xuất JSON chuẩn | Parser hiện có trả số/ngày/ký hiệu, seller/buyer/MST, dòng hàng và số tiền; bridge kiểm trường, kiểu và JSON trước lưu. | Không có lời gọi mô hình LLM trong đường upload/extraction hiện tại. Regex, tọa độ OCR và thuật toán Hybrid không đáp ứng riêng điều kiện dùng LLM ghi ở FR10/UC04. Chưa có nhánh kiểm schema/retry dành cho đầu ra LLM. | PARTIAL; còn chức năng bắt buộc theo SRS gốc |
| FR11 — Validation theo luật | `extraction.validate` có kiểm số/ngày, MST seller/buyer, thuế suất 0/5/8/10, ITEM-SUM, VAT-ARITH và ARITH với sai số hiện có. `main.validators` lưu từng vòng. | Kiểm toán học chạy khi các đầu vào tương ứng có dữ liệu. Không suy ra các kiểm tra đã có đầu vào đầy đủ chỉ từ việc không thấy lỗi; chất lượng bản hiện tại chưa xác minh. | Đã có luật và đường lưu/gọi lại |
| FR12 — Confidence, validation_status và warnings độc lập | Có valid/needs_review/error, warnings, trạng thái approval/lookup riêng, điểm OCR theo token và cảnh báo thử nghiệm. Pipeline current tính tỷ lệ đầy đủ các trường. | Hybrid chủ động trả `confidence_score=None`. Điểm token và completeness chưa phải cơ chế confidence theo BR09. `validators` chỉ xét luật; không có nhánh confidence thấp chuyển needs_review dù mọi luật pass theo UC06. SRS TBD-02 chưa chốt công thức/ngưỡng; không được tự tạo điểm hoặc ngưỡng để đánh dấu đủ. | PARTIAL; còn quy tắc nghiệp vụ và triển khai liên quan |
| FR13 — Lưu chứng từ và kết quả | `main.upload_invoice` lưu nguyên bytes, checksum, Invoice/InvoiceItem, ExtractionRun raw/JSON/evidence, ValidationResult và audit; models có ba trạng thái và lịch sử. API detail và original-file có kiểm quyền. | Kết quả PostgreSQL/UI lịch sử không xác minh bản sửa mới. Phần lịch/notification/workflow liên quan được giữ theo source hiện có. | Đã có mã nguồn và tích hợp; chưa nghiệm thu bản mới |

### User Story thuộc luồng Task 2

- PB03 và PB07 cung cấp upload/list/detail đã có, là điểm nối với Task 1; không sửa Task 1.
- PB04 đã có OCR và trích xuất tự động bằng parser; phần LLM nêu cụ thể trong SRS vẫn thiếu.
- PB05 đã có parse XML trực tiếp.
- PB06 đã có kết quả validation/warnings; phần confidence của Hybrid còn thiếu như FR12.
- PB08 đã có chứng từ gốc cạnh dữ liệu, edit theo quyền, lưu correction và validation lại. Không phát hiện thêm chức năng lập trình bắt buộc ở nhánh review/edit trong phạm vi này.

### Khoảng thiếu và giới hạn xử lý trong lượt này

Việc chốt tên Hybrid V8 Final hoặc bật làm mặc định không thay thế FR10/FR12. SRS không yêu cầu tên phiên bản Hybrid cụ thể; Gate G13 vẫn là kiểm soát triển khai đang áp dụng.

Đã xác định khoảng thiếu LLM, nhưng chưa có mô hình/provider, tài nguyên hoặc cấu hình LLM được chọn và cho phép sử dụng trong luồng này. Gemini trước đây được tạm hoãn; không có provider sẵn có để tái sử dụng. Không tạo adapter rỗng hoặc output giả rồi đánh dấu đã triển khai FR10. Việc tự tải mô hình lớn, chọn API trả phí hoặc gửi chứng từ ra ngoài cũng vượt quyền đã có.

FR12 cần công thức và ngưỡng confidence được chốt theo TBD-02 trước khi hiện thực đầy đủ. Không thay điểm null bằng giá trị tùy ý, không đánh đồng completeness với xác suất đúng và không đổi nghiệp vụ validation bằng một ngưỡng tự đặt.

Lượt này chỉ cập nhật kết luận trong tài liệu, không sửa source chức năng vì các khoảng thiếu trên cần lựa chọn mô hình/quy tắc chưa được xác định. Giữ XML, API hiện có, Task 1/3, dữ liệu, Gate, backup và stash.

**Kết luận cuối theo SRS.** Có thể chốt phần lập trình OCR/parser và tích hợp đã bàn giao. Chưa thể chốt toàn bộ Task 2 đáp ứng SRS gốc vì FR10/FR12 còn thiếu và FR08 có khác biệt công nghệ cần được chấp thuận. Đây là khoảng thiếu triển khai/đặc tả, tách với bằng chứng nghiệm thu chưa có. NFR01 gốc yêu cầu field accuracy ít nhất 85% trên 100–500 hóa đơn mẫu và gắn cờ hóa đơn có lỗi chủ ý; chưa đủ bằng chứng xác nhận. Không có Final PASS hoặc NFR01 PASS mới. Không đề xuất thêm vòng sửa theo từng mẫu hoặc giai đoạn Hybrid.

<a id="dieu-kien-kich-hoat"></a>

## Quyết định kích hoạt pipeline mặc định · 22/11/2026

**Chưa chuyển Hybrid V8 Final thành mặc định của dự án chính.** Lượt này đọc mã nguồn, cấu hình chọn lọc và đối chiếu hash tệp. Không thực thi ứng dụng, OCR, test, benchmark hoặc truy vấn Database.

| Điểm kiểm tra | Kết quả thực tế |
| --- | --- |
| Mặc định `Settings.ocr_pipeline` và `extract_document` | `current` |
| `backend/.env` | Có `APP_ENV=development`, không khai báo `OCR_PIPELINE`. Biến môi trường của Backend đang chạy chưa được xác minh. |
| Ràng buộc cấu hình | `experimental_ocr_requires_testing` chỉ chấp nhận Hybrid khi `APP_ENV=testing`. Đổi mặc định sang Final với cấu hình development hiện tại sẽ bị validator từ chối. |
| Gate G13 | Trạng thái lịch sử `PASS_TECHNICAL_REGRESSION_NOT_NFR`; 5/8 tệp không khớp SHA-256. Launcher kiểm hash trước khi khởi động Final. |
| API và Website | Upload gọi bridge theo cấu hình. Trường hóa đơn/dòng hàng được ánh xạ vào cấu trúc hiện có. Bằng chứng lưu ở `ExtractionRun`, findings được API trả và Web hiển thị. |
| Dự phòng | Bước Final lỗi giữ kết quả V8 có sẵn của cùng lần xử lý. Lỗi engine hoặc dữ liệu V8 không dùng được có thể chuyển về `current` nếu `OCR_HYBRID_FALLBACK` được bật. |

Năm tệp lệch hash so với Gate G13 gồm `backend/app/main.py`, `backend/app/ocr_runtime.py`, `backend/tools/ocr_benchmark/refine_v8.py`, `backend/tools/ocr_benchmark/hybrid_v8_final.py` và `web/src/ocrRuntimeInfo.js`. Gate được giữ nguyên với SHA-256 `c78250c6c4ea5dfc2f240a2a031e107268e296311697e16919e96571b4aab2a5`.

**Điều kiện còn thiếu để kích hoạt chính thức.** Cần bằng chứng xác minh kỹ thuật và hồ sơ Gate hợp lệ cho đúng bản mã dự định vận hành. Để dùng mặc định ngoài testing, cần quyết định cho phép thay đổi giới hạn môi trường hiện có. Những điều kiện này chưa được đáp ứng trong lượt chỉ đọc cấu hình và hash. NFR01 độc lập vẫn chưa nghiệm thu; trạng thái Gate lịch sử cũng chỉ xác nhận phạm vi kỹ thuật của phiên bản cũ.

Không xác định thêm chức năng OCR bắt buộc cần lập trình trong phạm vi đã chốt. Công việc đổi mặc định/cấu hình triển khai còn chờ các điều kiện trên. Lượt này chỉ cập nhật ba tài liệu bàn giao; mã nguồn, cấu hình, Gate và dữ liệu được giữ nguyên.

## Đính chính phạm vi chốt sau rà soát mã nguồn · 22/11/2026

Rà soát trước đã bỏ sót việc nối cảnh báo OCR vào giao diện chi tiết. Backend trả `ocr.findings`, nhưng Web mới hiển thị cảnh báo validation và thông báo chung. Lượt này đã thêm vùng mở xem các ghi nhận OCR, gồm mã, trang/dòng khi có và nội dung JSON mà API đã trả. Các quan sát giảm giá/phụ phí và giá trị mâu thuẫn nhờ đó có đường hiển thị. Bằng chứng đầy đủ như raw OCR, tọa độ và điểm từ OCR vẫn được lưu trong `ExtractionRun`; giao diện này chỉ hiển thị phần findings được API công khai theo quyền hóa đơn.

Đã bổ sung thông báo rõ khi Final giữ snapshot V8, dùng `reason=v8_baseline_retained` hiện có. Sửa bộ đọc tiền của Final để nhận dấu cách thường giữa các nhóm ba chữ số, vì bước ghép nhãn/văn bản có thể chuẩn hóa NBSP thành dấu cách thường. Không tính toán bù số tiền hoặc điền giá trị thiếu.

Ba tệp chức năng sửa trong lượt này gồm `web/src/InvoiceDetailPage.jsx`, `web/src/ocrRuntimeInfo.js` và `backend/tools/ocr_benchmark/document_fields_v8_final.py`. Cùng với báo cáo này, cập nhật `CODEX_HANDOFF.md` và `docs/OCR_PHASE13_CHECKPOINT.md`. Commit cục bộ trước sửa là `26bc332`; sửa bổ sung chưa commit.

**Kết luận về triển khai.** Đã có đường xử lý từ upload tới OCR Tesseract/PDF text, Hybrid V8 Final, ánh xạ trường và dòng hàng, lưu kết quả/bằng chứng, API chi tiết và review/edit. Các bước runtime dùng dữ liệu chứng từ đầu vào, không trả fixture hoặc kết quả benchmark cho upload. Snapshot V8 là kết quả nhận diện của cùng lần xử lý, được dùng khi bước Final lỗi. XML sử dụng parser đã có. Không phát hiện thêm chức năng bắt buộc chưa nối trong phạm vi rà soát tĩnh.

**Giới hạn.** Không chạy test, benchmark, OCR, API, Database, build hoặc trình duyệt trong lượt này. Kết luận triển khai không xác nhận độ chính xác hoặc khả năng thực thi bản sửa. Gate G13 và NFR01 vẫn chưa xác minh cho phiên bản hiện tại. Các kết quả PASS lịch sử bên dưới thuộc bản nguồn đã đo lúc đó.

<a id="chot-ma-nguon"></a>

## Chốt bàn giao mã nguồn ngày 22/11/2026

**Đã hoàn tất lập trình Task 2 Hybrid V8 Final trong phạm vi G1–G13.** Đối chiếu các điểm gọi dưới đây với hồ sơ bàn giao và checkpoint không phát hiện chức năng bắt buộc nào còn thiếu. Lượt chốt chỉ đọc mã nguồn và thông tin Git, sau đó cập nhật tài liệu.

| Chức năng đã tích hợp trong mã nguồn | Tệp liên quan |
| --- | --- |
| Upload đơn/lô, kiểm tra PDF/JPG/JPEG/PNG/XML, chọn pipeline theo cấu hình. PDF có chữ dùng lớp văn bản, ảnh và PDF scan đi qua OCR Tesseract. XML dùng parser hiện có. | `backend/app/core.py`, `main.py`, `extraction.py`, `ocr_runtime.py`. Các engine kế thừa nằm trong `backend/tools/ocr_benchmark/`, gồm `pipeline_v4.py` và `hybrid_v8.py`. |
| Phân loại chứng từ, trích xuất người bán, người mua, MST, số, ký hiệu, ngày và các trường tài chính. Giữ bằng chứng các quan sát VAT, giảm giá, phụ phí và các giá trị mâu thuẫn. | `hybrid_v8_final.py`, `refine_v8.py`, `document_fields_v8_final.py`, `source_links_v8_final.py` trong `backend/tools/ocr_benchmark/`. |
| Đối chiếu dòng theo mô tả, vị trí và trang, xử lý đơn vị, số lượng, đơn giá, thành tiền và bảng tiếp trang. Phát sinh cảnh báo để rà soát, giữ kết quả V8 khi bước Final gặp lỗi và có snapshot hợp lệ. | `table_state_v8_final.py`, `review_v8_final.py`, bộ điều phối Final và `backend/app/ocr_runtime.py`. |
| Lưu trường hóa đơn, dòng hàng, văn bản và bằng chứng trích xuất. API chi tiết trả dữ liệu, Web hiển thị và cho phép chỉnh sửa theo quyền. Lưu lịch sử sửa và gọi lại validation. | `backend/app/models.py`, `backend/app/main.py`, `web/src/InvoiceDetailPage.jsx`, `web/src/ocrRuntimeInfo.js`. |

**Bản bàn giao trên đĩa.** Nhánh `feature/thien`, HEAD `eafbc47`, đi trước tham chiếu cục bộ `origin/feature/thien` 10 commit. Git báo 6 tệp đã theo dõi có sửa đổi, 82 tệp chưa được theo dõi, 0 tệp staged và 3 stash. Các module Final và `ocr_runtime.py` nằm trong nhóm chưa được theo dõi. Chỉ lấy nội dung ở HEAD sẽ thiếu phần triển khai này.

**Giới hạn nghiệm thu.** Runtime, kết quả lưu/hiển thị và độ chính xác của bản mã sau cập nhật chưa được xác minh. Dấu tiếng Việt, dòng sát nhau, bảng nhiều trang và chất lượng của nhánh dự phòng còn giới hạn. Gate G13 đối chiếu hash của phiên bản lịch sử và chưa cho phép launcher chạy bản Final hiện tại. Chưa có Final PASS mới hoặc nghiệm thu độc lập NFR01. Mặc định hệ thống vẫn là `current`.

### Hồ sơ lịch sử G13 ngày 20/11/2026

Ngày 20/11/2026 (Asia/Ho_Chi_Minh). Giai đoạn 13 theo yêu cầu người dùng; repository `FINTECH_OCR_GitHub`, nhánh `feature/thien`.

**Trạng thái triển khai kỹ thuật Task 2: ĐÃ CHỐT trong phạm vi mã nguồn và kiểm thử bên dưới, kèm lỗi OCR còn biết. Nghiệm thu độc lập/NFR01: CHƯA ĐẠT ĐỦ BẰNG CHỨNG.** Không tự tuyên bố OCR chính xác 100%, không chuyển sang G14. Runtime mới là `hybrid_v8_final`, tên hiển thị “Hybrid V8 — bản hoàn thiện kỹ thuật”; đây là lớp hoàn thiện V8, không phải V9. Current, V6, V7 và V8 gốc vẫn có thể chọn để rollback.

## 1. Kế thừa và phạm vi

Đã đọc hồ sơ G9–G12: V7 còn sai supplier/line items; G10 có UAT thật nhưng chất lượng chưa đạt; G11 V8 cải thiện bảng/PDF và có412 Backend/36 Web tests; G12 kiểm kê/backup/regression nhưng nghiệm thu độc lập BLOCKED vì chưa có bộ thật A/B. Không làm lại các giai đoạn cũ hoặc dùng bộ24 G7 để tinh chỉnh.

G13 sử dụng đúng file gốc của invoice48–53 từ PostgreSQL test và đối chiếu checksum, raw OCR, boxes/confidence, parser output, ExtractionRun, InvoiceItem, API và UI. Tất cả sáu nguồn ghi rõ DEMO/giả lập/không có giá trị thanh toán: **dữ liệu phát triển/tổng hợp, không phải sáu hóa đơn thật độc lập**. Tên file không quyết định dữ liệu: UAT tự chọn lại file storage UUID, nội dung bytes mới được đưa qua OCR.

Không gửi chứng từ tới dịch vụ ngoài, không cài engine/model/dependency mới. Tesseract vie+eng vẫn là OCR thực; native PDF text giữ provenance riêng, không giả OCR confidence. PaddleOCR và bộ benchmark cũ không bị xóa hoặc thay làm mặc định.

## 2. Nguyên nhân và sửa lỗi

| Lỗi | Nguyên nhân thực tế | Sửa tổng quát |
|---|---|---|
| #49/#50 supplier là dòng cảnh báo | Candidate có nhãn người bán rõ nhưng gate giữ dấu ưu tiên tên cũ sai; warning nhiều dấu được xem như tên tốt | Phân vai seller/buyer theo nhãn, ưu tiên explicit label, loại disclaimer/chữ ký/title khỏi seller; chỉ giữ literal OCR/text có evidence |
| #51 tên thiếu dấu; #52 nhận warning | Nhánh header không phân biệt metadata/tagline và cửa hàng; đọc lại vùng cũ dựa tên sai | Chọn candidate header hợp lệ, OCR lại đúng vùng đã quan sát; không dùng tên doanh nghiệp từ dataset/từ điển để sửa |
| #49 mất4 hàng | Header bị OCR ngắt; footer zone bắt ở metadata thanh toán phía trên bảng | Dùng header có tọa độ từ các read sẵn có, chỉ cho footer bắt đầu bên dưới header; ghép giá/SL/name theo cột |
| Bill #51–53 dùng “q unit × price” làm description | Parser headerless chưa nhận quan hệ name ở dòng trước và biểu thức giá ở dòng sau | Grammar q/unit×price/amount với evidence từng ô, ghép tên nhiều dòng, không lấy model/tiền khách đưa/tổng kết làm sản phẩm |
| Thiếu3 dòng khác ở #52/#53 | Cắt vùng sớm và chọn vùng tiền thiếu; amount119000 trên #52 mâu thuẫn read110000 | Tái ghép hàng theo hình học; chỉ chọn bộ q/price/amount **đã được OCR quan sát** có phép tính phù hợp; không chia tổng/ép cân tiền |
| Đơn vị và dấu tiếng Việt | Phân đoạn/đọc dấu trên dòng nhỏ; alias đơn vị hữu hạn | Giữ literal, chuẩn hóa đơn vị có bằng chứng; reread bounded khi cần; Cuốn/Cuộn, Tờ/Tô không được coi là cùng đơn vị khi chấm |
| Hồi quy phát hiện trong phát triển | Tái parse sinh thêm dòng rác; tagline thay seller; nhiều dấu hơn có thể làm sai mã viết tắt | Chỉ thêm dòng có cấu trúc/evidence, giữ ô baseline đã quan sát, không cho unlabelled candidate thay danh tính hợp lệ; giữ text baseline và ghi alternative thay vì tự thêm dấu vào model/viết tắt |

Không hardcode tên nhà cung cấp, số chứng từ, hàng hóa hoặc số tiền của sáu DEMO trong parser. Runtime không đọc nhãn/fixture/reference. Bản V8 gốc và current extraction không bị sửa. Sửa giới hạn tại lớp mới và bridge config; không đổi schema/migration/validator, không nới ITEM-SUM và không thêm quyền Accountant/Admin.

## 3. Chức năng đã hoàn thiện

- JPG/PNG và PDF scan thực sự qua Tesseract; native PDF text dùng text/boxes; PDF nhiều trang giữ các khả năng V8 đã có, kiểm lại trên fixture nhiều trang.
- Trích xuất/ánh xạ loại, người bán/người mua, MST theo nhãn, số hóa đơn hoặc số phiếu phù hợp bill, ngày, tiền hàng/VAT/tổng và line items theo cấu trúc hiện tại.
- Bill không MST giữ null; trường không in/không đọc được không bị suy từ tổng. Giá trị0 khác null. QR/XML, currencies và mapper giữ contract hiện có; XML dùng parser current, không gọi engine ảnh.
- Dòng có tên nhiều dòng/model, đơn vị, số lượng/giá/amount; các dòng tổng, discount, cash/change không thành sản phẩm. Discount/VAT theo nhóm giữ trong evidence khi đọc được; không thêm cột discount/VAT cấp hàng vào schema hiện có.
- Cảnh báo/evidence gồm text, tọa độ, OCR word scores, lựa chọn ô và baseline/alternatives. `requires_review=true`; confidence field chưa hiệu chuẩn, không gán accuracy100%.
- Upload → extraction → validation → lưu DB → API → Invoice Detail → sửa → lưu lại/F5/restart hoạt động trên môi trường test. Không dùng ảnh/fixture hay output lưu sẵn làm câu trả lời cho upload mới.
- Fallback current khi final gặp exception; file gốc và lịch sử được giữ. Mode gốc `hybrid_v8` vẫn là rollback trước lớp hoàn thiện; current vẫn mặc định source.

## 4. Kết quả đối chiếu sáu DEMO, trước correction

Nhãn tham khảo đọc trực tiếp sáu nguồn và ảnh render/zoom, **AI visual development reference, chưa phải ground truth A/B**. Một lỗi chép nhãn mới ở #50 (Cuộn/Cuốn) được kiểm lại bằng zoom gốc: nguồn in **Cuốn**. Lưu bản đầu và [REFERENCE_REVIEW_AUDIT.json](../../ocr_task2_final/REFERENCE_REVIEW_AUDIT.json), [ảnh zoom](../../ocr_task2_final/unit50_visual_zoom.png); không sửa ground truth cũ hoặc parser để khớp nhãn. Scorer giữ Cuốn/Cuộn khác nhau.

So trước bằng ExtractionRun gốc, không dùng Invoice đã sửa. Sau bằng OCR chạy từ bytes và HTTP response nguyên bản trước correction. So Unicode NFC/casefold/whitespace; giữ dấu tiếng Việt và leading zero. Numeric equality dùng Decimal. Alias unit chỉ dùng nhóm đã quy định, không gộp các đơn vị khác nghĩa. Không cộng null/vắng vào accuracy dương; VAT chỉ có mẫu số3 nguồn có VAT.

| Chỉ tiêu trên 6 DEMO | V8 gốc (#48–53) | V8 hoàn thiện, trước sửa tay (#54–59) |
| --- | --- | --- |
| Tên người bán | 2/6 | 6/6 |
| Số hóa đơn/số phiếu | 3/6 | 6/6 |
| Ngày lập | 6/6 | 6/6 |
| Tiền hàng/subtotal in trên nguồn | 6/6 | 6/6 |
| VAT amount có in trên 3 mẫu VAT | 3/3 | 3/3 |
| Tổng thanh toán | 6/6 | 6/6 |
| Phân loại chứng từ | 6/6 | 6/6 |
| Số dòng phát hiện | 21/28 (thiếu7) | 28/28, không dư |
| Tên hàng đúng | 7/28 | 27/28 |
| Đơn vị đúng | 7/28 | 28/28 |
| Số lượng đúng | 7/28 | 28/28 |
| Đơn giá đúng | 7/28 | 28/28 |
| Thành tiền đúng | 16/28 | 28/28 |
| Dòng khớp đủ5ô | 7/28 | 27/28 |
| Tổng ô đúng | 44/140 | 139/140 |

Một lỗi còn lại: tên “Mì gói **vị** bò” trên nguồn #53 thành “Mì gói **vi** bò”. Word confidence có thể0.96 nhưng vẫn sai dấu; không sửa bằng bảng thay tên sản phẩm. UI được test sửa riêng lỗi này ở **invoice mới59**; không tính correction vào điểm OCR. Trước correction,5/6 bảng khớp đủ, bảng siêu thị còn1ô mô tả sai; financial rows28/28 đúng.

Bằng chứng: [DEMO_VISUAL_REFERENCE.json](../../ocr_task2_final/DEMO_VISUAL_REFERENCE.json), [COMPARISON.json](../../ocr_task2_final/COMPARISON.json), [WEB_OCR_COMPARISON.json](../../ocr_task2_final/uat/WEB_OCR_COMPARISON.json). Sáu file khác SHA; không đếm bản upload lại thành chứng từ độc lập mới. Đây không chứng minh khả năng xử lý mọi hóa đơn mới hoặc đạt NFR01.

### Từng dòng OCR thực qua Web (trước sửa tay)

Đơn giá/thành tiền tính bằng VND. “PASS” chỉ so với bản đọc nguồn trong bộ DEMO này.

| Mẫu gốc/dòng | Mô tả OCR | ĐVT | SL | Đơn giá | Thành tiền | So nguồn |
| --- | --- | --- | --- | --- | --- | --- |
| 48/1 | Giấy in A4 80 gsm | Ram | 5 | 72.000 | 360.000 | PASS |
| 48/2 | Bút bi xanh 0.5 mm | Hộp | 3 | 48.000 | 144.000 | PASS |
| 48/3 | Bìa hồ sơ nhựa A4 | Cái | 12 | 15.000 | 180.000 | PASS |
| 48/4 | Mực in laser mẫu | Hộp | 2 | 350.000 | 700.000 | PASS |
| 49/1 | Bàn phím có dây | Cái | 3 | 240.000 | 720.000 | PASS |
| 49/2 | Chuột quang | Cái | 4 | 160.000 | 640.000 | PASS |
| 49/3 | Cáp USB 2 mét | Sợi | 6 | 55.000 | 330.000 | PASS |
| 49/4 | Túi đựng laptop | Cái | 2 | 185.000 | 370.000 | PASS |
| 50/1 | Dịch vụ in tài liệu | Bộ | 10 | 45.000 | 450.000 | PASS |
| 50/2 | Đóng gáy tài liệu | Cuốn | 5 | 30.000 | 150.000 | PASS |
| 50/3 | Bìa màu | Tờ | 20 | 5.000 | 100.000 | PASS |
| 51/1 | Sổ tay A5 | Quyển | 2 | 35.000 | 70.000 | PASS |
| 51/2 | Bút dạ quang | Cây | 3 | 12.000 | 36.000 | PASS |
| 51/3 | Băng keo trong | Cuộn | 1 | 16.000 | 16.000 | PASS |
| 52/1 | Cơm gà / Chicken rice | Phần | 2 | 55.000 | 110.000 | PASS |
| 52/2 | Mì xào bò | Phần | 1 | 65.000 | 65.000 | PASS |
| 52/3 | Nước cam | Ly | 2 | 28.000 | 56.000 | PASS |
| 52/4 | Trà đá | Ly | 3 | 5.000 | 15.000 | PASS |
| 53/1 | Sữa tươi 180 ml | Hộp | 4 | 8.000 | 32.000 | PASS |
| 53/2 | Mì gói vi bò | Gói | 5 | 6.500 | 32.500 | FAIL dấu: vi ≠ vị |
| 53/3 | Bánh quy bơ | Hộp | 2 | 42.000 | 84.000 | PASS |
| 53/4 | Nước khoáng 500 ml | Chai | 6 | 6.000 | 36.000 | PASS |
| 53/5 | Gạo thơm 1 kg | Túi | 2 | 29.000 | 58.000 | PASS |
| 53/6 | Táo đỏ | Kg | 1 | 48.000 | 48.000 | PASS |
| 53/7 | Dầu ăn 1 L | Chai | 1 | 58.000 | 58.000 | PASS |
| 53/8 | Trứng gà 10 quả | Hộp | 1 | 38.000 | 38.000 | PASS |
| 53/9 | Khăn giấy | Gói | 2 | 15.000 | 30.000 | PASS |
| 53/10 | Sữa chua | Hộp | 4 | 7.000 | 28.000 | PASS |

Đối chiếu financial đúng nghĩa: #52 goods246000 − discount10000 = payable236000; #53 goods444500 − discount20000 = payable424500. Không ép tổng dòng bằng payable, không tự điền VAT0 cho bill. Discount được ghi theo nguồn/evidence, không tự phân bổ vào giá hàng.

## 5. Website/Uvicorn/PostgreSQL thực tế

Tự chạy Playwright Chromium local headless, Vite/React thật, FastAPI/Uvicorn thật và PostgreSQL test thật; Tesseract thật. Không mock API hoặc OCR output. Người dùng không phải upload lại/kiểm từng trường. Ảnh/PDF gốc hiển thị, mọi input field/item được so với API và F5. Phiên bản mới xác nhận qua used_pipeline/method/evidence, không chỉ /health.

| Nguồn gốc → invoice mới | Định dạng | Dòng | HTTP | Giây HTTP | Kết quả |
| --- | --- | --- | --- | --- | --- |
| #48 → #54 | PDF | 4 | 201 | 1.811 | PASS nội dung |
| #49 → #55 | PDF | 4 | 201 | 14.405 | PASS nội dung |
| #50 → #56 | JPG | 3 | 201 | 15.966 | PASS nội dung |
| #51 → #57 | PNG | 3 | 201 | 9.560 | PASS nội dung |
| #52 → #58 | JPG | 4 | 201 | 10.506 | PASS nội dung |
| #53 → #59 | JPG | 10 | 201 | 12.124 | PARTIAL: 1 dấu trong mô tả |

**#48–53 được giữ nguyên** để đối chiếu. Muốn xem kết quả mới mở #54–59, ví dụ [invoice55](htt<LOCAL_PATH>

- 20 checks login/GET/RBAC/workflow PASS,0 JavaScript errors. Employee không approve/lookup403, không sửa approved400; Accountant không edit403; Employee không xem hóa đơn người khác404. Các trường/nullable cells API ↔ UI khớp.
- Sửa “vi” → “vị” bằng giao diện trên #59, PUT200; một correction old/new/actor/time, validation chạy lại. Không sửa số tiền; ExtractionRun giữ output OCR gốc. F5/restart giữ bản chỉnh sửa.
- Employee submit #57 → Accountant approve; Employee submit #58 → Admin reject với lý do thử nghiệm. Validation và Lookup không tự đổi theo Approval. Sau restart #57 approved, #58 rejected, các bản khác draft; bill lookupnot_applicable, ba VAT not_checked. Không gán verified cho chứng từ giả lập.
- Reports/Schedule/Profile/Notifications/Audit được hồi quy tự động; GET liên quan theo role chạy trên browser. Không thực hiện CRUD Schedule/User hoặc Tax Lookup thật để giả lập nghiệm thu ngoài phạm vi Task 2.
- Một controlled engine fault ở process phụ8011 tạo **#60**, HTTP201, used_pipeline=current/fallbacktrue/banner đúng; current thực sự OCR lại. Current trả5 hàng trên nguồn3 hàng, **FAIL chất lượng**, không dùng nó vào điểm V8. Đây là PASS cơ chế phục hồi, không bảo đảm kết quả fallback đúng. Fault seam chỉ nằm trong process test, không sửa engine.
- Đã dừng đúng processfault8011 và restart Backend chính test, đọc lại #54–59 và lịch sử fallback#60 thành công. Correction, trạng thái, items và file/checksum tồn tại sau restart.

Bằng chứng: [BROWSER_UAT.json](../../ocr_task2_final/uat/BROWSER_UAT.json), [RESTART_BROWSER.json](../../ocr_task2_final/uat/RESTART_BROWSER.json), [fault](../../ocr_task2_final/uat/BROWSER_FAULT_engine.json); screenshot [PDF scan55](../../ocr_task2_final/uat/demo_49_detail.png), [correction59](../../ocr_task2_final/uat/demo_53_corrected.png), [approve57](../../ocr_task2_final/uat/accountant_approved.png), [reject58](../../ocr_task2_final/uat/admin_rejected.png). Các screenshot khác nằm cùng thư mục; không lưu JWT/password/network trace chứa Authorization vào báo cáo.

## 6. Regression và chất lượng kỹ thuật

| Kiểm thử cuối | Kết quả | Phạm vi |
|---|---|---|
| Backend toàn bộ | **441 PASS,0FAIL,0SKIP**,71.76s | Tăng29 test so baseline412; giữ toàn bộ test/assertion cũ |
| Frontend toàn bộ | **37 PASS,0FAIL** | Tăng1 test so36; các test khác giữ |
| Production build | **PASS**,6.05s | Còn warning chunk>500kB sẵn có |
| Tám nguồn development/regression cũ | **0 giá trị trước đúng bị mất/sai** theo bộ tham khảo G11; không dòng dư | 3 ảnh development +5synthetic; không G7, không gọi independent |
| Sáu DEMO offline thực | 6/6 xử lý,28 dòng,139/140ô khớp | Có1 lỗi dấu; không phải OCR chính xác 100% |
| Browser thực + persistence | PASS giới hạn như mục5 | Không thay UAT sign-off của con người |
| Fallback | PASS unitException/NaN/XML và cơ chế Browserenginefault | Không đo timeout tự nhiên/SLA trong lượt này |

Full Backend dùng thư mục tạm/SQLite/fixture cô lập, không PostgreSQL hoặc file SQLite test cũ; không xóa DB cũ để làm PASS. Có test Tesseract thật cho nguồn không in amount dòng: items phải rỗng, không dùng tổng để bịa dòng. Những lỗi kỳ vọng mới trong quá trình viết test đã được đối chiếu lại nguồn fixture; không sửa assertion cũ/validator. Có27 warning thư viện deprecation.

Hồi quy đã phát hiện và sửa trước triển khai: giữ supplier baseline khi candidate chỉ là tagline; giữ ô đã quan sát khi tái parse thiếu; chặn dòng rác và không thêm dấu vào abbreviation/model chỉ vì nhiều dấu hơn. Phiên bản thăm dò giữ riêng ở `pilot_before_regression_guard/`; kết quả cuối mới dùng cho gate. Không đổi nhãn G11/G7/G3.5/G12 để tăng điểm.

[backend-tests.xml](../../ocr_task2_final/backend-tests.xml), [backend log](../../ocr_task2_final/backend-tests.log), [Web tests](../../ocr_task2_final/web-tests.log), [build](../../ocr_task2_final/build.log), [OFFLINE_GATE.json](../../ocr_task2_final/OFFLINE_GATE.json). Gate là **PASS_TECHNICAL_REGRESSION_NOT_NFR**, không phải nghiệm thu accuracy.

HTTP sáu upload mới trung bình 10.729s, từ1.811 đến15.966s. Đây là quan sát trên6 DEMO gồmOCR/API/DB/UI, không benchmark latency độc lập hoặc SLA. Các lượt offline có thời điểm chạy cùng regression, không dùng để tuyên bố speedup so G11.

## 7. An toàn dữ liệu và backup

Chỉ `fintech_ocr_rbac_test`, APP_ENVtesting, upload tuyệt đối `backend/uploads_rbac_test`. Kiểm current_database READ ONLY ngay trong process, đối chiếu PID/command/source/JS API target. Không kết nối `fintech_ocr`, không sửa `.env`/CORS/cổng/schema, không migration/seed/reset/restore/xóa dữ liệu.

Trước UAT:53invoices/53files/64items/53runs/41corrections/477validations/101notifications/170audits/18schedules; toàn bộ53file khớpchecksum. Schema đủcột, PostgreSQLHealthy/UTF8.

- Backup trước ghi: `<LOCAL_PATH>` — 1,685,232bytes; SHA256 `3ead059a5c5888a7a3568e9d20e01a0c78dca1bf3db774a320789361ba74ed97`; pg_restorelist0.
- Backup sau UAT/bàn giao: `<LOCAL_PATH>` — 2,647,063bytes; SHA256 `f9f3eb10bf9411aef21f9bb605bfdeeed7bac1bc01c2cf2e527a3c5c5a23423e`; pg_restorelist0.

Hậu kiểm mọi bảng public xác nhận **1154 bản ghi ngoài users có trước UAT giữ nguyên hash**, gồm #1–53 và mọi extraction/items/correction/approval/lookup/report/schedule cũ. Bảng users11hàng chỉ3 tài khoản đăng nhập đổi last_login_at/updated_at; tất cả cột khác so strict với backup,8user khác nguyên. Không viết “toàn DB không đổi” vì auth timestamps được cập nhật đúng logic. pg_restore chỉ xuất SQL users ra bộ nhớ để so, không restore vàoDB hoặc in passwordhash.

Sau UAT/restart:

| Bảng theo snapshot nghiệp vụ | Số bản ghi cuối |
| --- | --- |
| invoices | 60 |
| invoice_files | 60 |
| invoice_items | 97 |
| extraction_runs | 60 |
| invoice_corrections | 42 |
| validation_results | 534 |
| notifications | 114 |
| audit_logs | 182 |
| schedules | 18 |

Tổng20bảng public1306hàng, giữ Reports12 và Schedules18. Chỉ tạo hóa đơn #54–60 và dữ liệu kèm theo đúng thao tác test; correction1 trên #59, workflow mới trên #57/#58. Không xóa hoặc cập nhật nguồn cũ. Tất cả60file checksum đúng; duplicate-file warning cho các bản test cùng bytes là dự kiến, không tắt nó.

[DB_AFTER_RESTART.json](../../ocr_task2_final/uat/DB_AFTER_RESTART.json), [DB_FINAL_CHECK.json](../../ocr_task2_final/uat/DB_FINAL_CHECK.json), [backup trước](../../ocr_task2_final/uat/BACKUP.json), [backup bàn giao](../../ocr_task2_final/handoff/BACKUP.json). Không commit/push/pull/merge/reset/add, không đổi branch hoặc xóa3stash.

## 8. Tệp thay đổi của G13

| Tệp | Thay đổi |
| --- | --- |
| backend/tools/ocr_benchmark/refine_v8.py | Mới: nhãn/ngữ cảnh supplier-buyer-MST, số phiếu, cấu trúc q×price, vùng bảng, nguồn quan sát, bảo toàn baseline |
| backend/tools/ocr_benchmark/hybrid_v8_final.py | Mới: lớp hoàn thiện V8 độc lập, đọc lại có giới hạn, evidence/finding và rollback |
| backend/app/core.py | Thêm lựa chọn hybrid_v8_final chỉ testing; current vẫn mặc định |
| backend/app/ocr_runtime.py | Lazy dispatch final qua mapper/fallback đang có, giữ API contract |
| backend/app/main.py | Nhận diện mode final trong nhánh lỗi extraction hiện có |
| backend/tests/test_ocr_v8_final.py | 29 test mới cho cấu trúc, dữ liệu thiếu/0, nhãn, reg baseline, runtime, RBAC, correction, XML, Tesseract thật |
| web/src/ocrRuntimeInfo.js | Tên/cảnh báo mode final; không đổi layout/CSS/route |
| web/tests/ocrRuntimeInfo.test.js | Thêm test banner final/fallback/error, không tuyên bố nghiệm thu |
| docs/OCR_TASK2_FINAL_REPORT.md | Báo cáo/chốt kỹ thuật hiện tại |
| docs/OCR_PHASE13_CHECKPOINT.md | Checkpoint bàn giao; không thay đổi hồ sơ các giai đoạn cũ |

Các thay đổi Task 2 cũ còn hiện trong git status được giữ nguyên, không coi toàn bộ diff từ HEAD là thay đổi G13. Snapshot trước chứng minh chỉ5file đã có được sửa, cộng 3 file code/test mới, báo cáo này và checkpoint G13. V6/V7/V8 gốc/current extraction/models/validators/ground truth/env giữ nguyên byte. Ngoài repo: `ocr_task2_final` chứa helpers, snapshot, raw/boxes/output, so sánh, logs và UAT; không là thành phần tạo dữ liệu giả cho runtime.

## 9. Cách chạy và rollback an toàn

Website hiện tại: **htt<LOCAL_PATH>

- PID Backend theo proof bàn giao: **17148**.
- APP_ENV=testing; databasefintech_ocr_rbac_test; upload `<LOCAL_PATH>`.
- OCR_PIPELINE=hybrid_v8_final; OCR_HYBRID_FALLBACK=true. Source default vẫncurrent, không bật bản mới mặc định/production.

Không khởi động thêm process nếu8000/5173 đã có dịch vụ. Khi cần restart chính process test, helper kiểm PID/DB/upload/idle/backup/source trước khi dừng:

```powershell
& '<LOCAL_PATH>
```

Rollback OCR mà không đổi dữ liệu:

```powershell
& '<LOCAL_PATH>
# Hoặc -Pipeline current, hybrid_v6, hybrid_v7.
```

Helper được kiểm cú pháp, startup/restartV8final và fallbackcurrent đã chạy thật; không tự nhận đã switch lại mọi mode trong G13. Helper từ chối nếu PID/source/backup lệch hoặc còn request. Không kill process khác. Không chạy Uvicorn trần thiếu env vì có thể vào DB chính.

Nếu dịch vụ đã dừng và8000trống, terminal Backend:

```powershell
Set-Location '<LOCAL_PATH>
$env:PHASE13_EVIDENCE_DIR = '<LOCAL_PATH>
.\.venv\Scripts\python.exe -X utf8 '<LOCAL_PATH>
```

Terminal Web, chỉ khi5173trống:

```powershell
Set-Location '<LOCAL_PATH>
$env:VITE_API_URL = 'htt<LOCAL_PATH>
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Các lệnh chỉ đặt env của process, không sửa file.env. Backup/guard/rootpath phải giữ cùng hồ sơ; khi source hoặc schema thay đổi thì kiểm preflight mới, không bỏ guard. Vite hiện có được giữ, không sửa Sidebar/Header/CSS/route của thành viên khác.

## 10. Hạn chế và nghiệm thu độc lập

| Hạng mục | Trạng thái chốt |
|---|---|
| Triển khai kỹ thuật/lưu/API/UI/edit/workflow/RBAC/fallback trong phạm vi test | **ĐÃ CHỐT / PASS phạm vi có bằng chứng** |
| Sáu DEMO: fields chính/28ô quantity-price-amount-unit | **PASS trên DEMO**, không suy rộng |
| Toàn bộ mô tả OCR | **PARTIAL/FAIL1ô dấu**,27/28; giữ raw trước correction |
| Chất lượng OCRcurrent khi fallback | **FAIL trên nguồn fault**,5row thay3; cơ chế vẫnPASS |
| Hóa đơn thật mới/độc lập/A-B/NFR01 | **BLOCKED/chưa đủ bằng chứng** |
| CER/WER/row polygon F1, ảnh nhăn/che nặng/mixedPDF/thực nhiều VAT/discount đa dạng | **NOT TESTED đủ coverage độc lập** |
| Confidence field và SLA hiệu năng | **Chưa hiệu chuẩn/chưa có nghiệm thu** |
| Tax Lookup thật/giá trị pháp lý | **BLOCKED**, không có verified giả |

Các DEMO có MST giả lập in trên giấy. “valid” của validator chỉ là quy tắc kỹ thuật hiện có, không phải chứng từ hợp pháp/được xác minh thuế. Cần human review với dữ liệu mới; không tự sửa số tiền hoặc tự sinh trường thiếu. Danh mục alias unit hữu hạn, chữ nhỏ/tone/viết tắt và các bố cục chưa gặp vẫn có thể sai.

Bộ24G7 vẫn draft/không benchmark; không tự kýA/B hoặc sửa ground truth. Còn thiếu bộ hóa đơn thật độc lập có đáp án người xác minh và tiêu chí chấm chốt trước inference; NFR01>=85% trên100–500 không được xác nhận từ6DEMO. Không gọi441+37testsPASS là độ chính xác OCR thực tế. Không mở thêm giai đoạn triển khai; tài liệu này là điểm chốt kỹ thuật Task 2, phần nghiệm thu độc lập được ghi là còn thiếu. **Dừng G13, không triển khai G14.**

[Checkpoint Giai đoạn 13](OCR_PHASE13_CHECKPOINT.md).
