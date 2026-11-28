# Lưu trữ phát triển Upload và OCR

Đây là mã nguồn nghiên cứu chưa hoàn thiện, được lưu để tiếp tục phát triển và phục vụ báo cáo. **Không phải pipeline được kích hoạt của ứng dụng.**

## Phiên bản đang hoạt động

Các thư mục `backend/app`, `backend/tools/ocr_benchmark` và `web/src` ở gốc repository tiếp tục sử dụng phiên bản đã tích hợp qua PR #26 và #27. Không thay đổi cấu hình Gemini, Gate G13, chính sách confidence hoặc database khi lưu trữ các nguồn bên dưới.

## Nội dung

- `current/`: nguồn phát triển mới nhất lấy từ working tree gốc, gồm Upload/Invoice Review, parser PDF/ảnh/XML, OpenCV, Hybrid V8 Final, trích xuất bảng nhiều trang, Evidence Merge, confidence và worker PaddleOCR cục bộ. Giữ cấu trúc đường dẫn để đối chiếu; không chép đè lên runtime.
- `variants/ollama/`: adapter Ollama đã viết trước đây, lấy từ phần untracked của stash tương ứng. Chưa được đăng ký vào runtime hiện tại; không tải model hoặc gọi dịch vụ khi lưu trữ.
- Lịch sử patch và các tài liệu kiểm thử/checkpoint trung gian đã được dọn khỏi cây thư mục hiện tại. Bản lưu trữ trước dọn dẹp vẫn truy xuất được tại [commit 2fc6983](https://github.com/C1SE-86-FINTECH-OCR/FINTECH_OCR/tree/2fc6983b9148224f37bc2cdc50f6baea4cd077f3/research/ocr_development).
- `documents/`: giữ báo cáo kỹ thuật, kết quả benchmark và tài liệu nghiên cứu có giá trị cho việc tiếp tục phát triển. Các liên kết lịch sử tới hồ sơ đã dọn hoặc dữ liệu cục bộ có thể không còn trong cây hiện tại; xem commit lưu trữ ở trên. Các kết quả lịch sử không phải bằng chứng nghiệm thu hiện tại.
- `inventory.json`: danh mục nguồn nghiên cứu còn giữ, checksum và danh sách 55 đường dẫn đã dọn trước đó; hồ sơ đối chiếu chi tiết nằm tại commit lưu trữ trước dọn dẹp.

## Dependency và giới hạn

- Runtime đang dùng dependency tại `backend/requirements.txt`, `web/package.json` và lockfile ở gốc repository.
- Bản nghiên cứu PaddleOCR dùng môi trường Python riêng; kết quả lịch sử ghi nhận PaddleOCR 3.3.1, PaddlePaddle CPU 3.3.0 và PaddleX 3.3.13. Không thêm các gói này vào môi trường Backend chính và không đóng gói trọng số model.
- Ollama cần dịch vụ/model được cài và cấu hình riêng. Nguồn được lưu không đồng nghĩa đã có model, đã kiểm thử trên máy mới hoặc đã được cho phép truyền dữ liệu.
- Chưa xác nhận độ chính xác OCR, hiệu năng, G13 hoặc NFR01 cho các bản nghiên cứu. Các quy tắc confidence thử nghiệm không phải chính sách TBD-02 được duyệt.
- Không sử dụng các bản `main.py`, `core.py` hoặc cấu hình mẫu trong `current/` để thay thế trực tiếp bản đang chạy: chúng là snapshot phát triển, có thể thiếu các sửa lỗi tích hợp mới trên main.

## Dọn dẹp được phê duyệt

55 đường dẫn đã xóa có chủ đích được liệt kê trong `inventory.json`. So với nền main khi lưu trữ, 38 file còn tồn tại được xóa; 17 file vốn đã vắng mặt. Không khôi phục các file này từ stash hoặc backup. Fixture API thực sự còn được sử dụng được tách thành `backend/tests/api_support.py`; không khôi phục bộ kiểm thử cũ dưới tên khác.

Không chứa `.env` thật, chứng từ, database, model, thư viện cài sẵn hoặc dữ liệu kiểm thử cá nhân. Bản sao đầy đủ chưa chỉnh sửa vẫn được bảo vệ ngoài repository cùng Git bundle và các stash gốc.
