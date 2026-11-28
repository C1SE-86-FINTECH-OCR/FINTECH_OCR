# Lưu trữ phát triển Upload và OCR

Đây là mã nguồn nghiên cứu chưa hoàn thiện, được lưu để tiếp tục phát triển và phục vụ báo cáo. **Không phải pipeline được kích hoạt của ứng dụng.**

## Phiên bản đang hoạt động

Các thư mục `backend/app`, `backend/tools/ocr_benchmark` và `web/src` ở gốc repository tiếp tục sử dụng phiên bản đã tích hợp qua PR #26 và #27. Không thay đổi cấu hình Gemini, Gate G13, chính sách confidence hoặc database khi lưu trữ các nguồn bên dưới.

## Nội dung

- `current/`: nguồn phát triển mới nhất lấy từ working tree gốc, gồm Upload/Invoice Review, parser PDF/ảnh/XML, OpenCV, Hybrid V8 Final, trích xuất bảng nhiều trang, Evidence Merge, confidence và worker PaddleOCR cục bộ. Giữ cấu trúc đường dẫn để đối chiếu; không chép đè lên runtime.
- `variants/ollama/`: adapter Ollama đã viết trước đây, lấy từ phần untracked của stash tương ứng. Chưa được đăng ký vào runtime hiện tại; không tải model hoặc gọi dịch vụ khi lưu trữ.
- `history/`: năm patch khác nhau của các thay đổi OCR trong bảy stash. Các stash có nội dung giống nhau được tham chiếu chung, không áp dụng nối tiếp. Không chứa nội dung các file đã quyết định xóa.
- `documents/`: tài liệu kỹ thuật, checkpoint và kết quả nghiên cứu lịch sử. Đường dẫn máy và địa chỉ email đã được lược bỏ. Đây không phải bằng chứng nghiệm thu phiên bản hiện tại; liên kết đến dữ liệu cục bộ hoặc kiểm thử đã xóa chỉ còn giá trị lịch sử.
- `inventory.json`: nguồn gốc, checksum, phân loại thay đổi và quyết định đối với từng stash. Hash ở đây dùng để kiểm tra nguồn lưu trữ, không thay thế baseline G13 đã được phê duyệt.

## Dependency và giới hạn

- Runtime đang dùng dependency tại `backend/requirements.txt`, `web/package.json` và lockfile ở gốc repository.
- Bản nghiên cứu PaddleOCR dùng môi trường Python riêng; kết quả lịch sử ghi nhận PaddleOCR 3.3.1, PaddlePaddle CPU 3.3.0 và PaddleX 3.3.13. Không thêm các gói này vào môi trường Backend chính và không đóng gói trọng số model.
- Ollama cần dịch vụ/model được cài và cấu hình riêng. Nguồn được lưu không đồng nghĩa đã có model, đã kiểm thử trên máy mới hoặc đã được cho phép truyền dữ liệu.
- Chưa xác nhận độ chính xác OCR, hiệu năng, G13 hoặc NFR01 cho các bản nghiên cứu. Các quy tắc confidence thử nghiệm không phải chính sách TBD-02 được duyệt.
- Không sử dụng các bản `main.py`, `core.py` hoặc cấu hình mẫu trong `current/` để thay thế trực tiếp bản đang chạy: chúng là snapshot phát triển, có thể thiếu các sửa lỗi tích hợp mới trên main.

## Dọn dẹp được phê duyệt

55 đường dẫn đã xóa có chủ đích được liệt kê trong `inventory.json`. So với nền main khi lưu trữ, 38 file còn tồn tại được xóa; 17 file vốn đã vắng mặt. Không khôi phục các file này từ stash hoặc backup. Fixture API thực sự còn được sử dụng được tách thành `backend/tests/api_support.py`; không khôi phục bộ kiểm thử cũ dưới tên khác.

Không chứa `.env` thật, chứng từ, database, model, thư viện cài sẵn hoặc dữ liệu kiểm thử cá nhân. Bản sao đầy đủ chưa chỉnh sửa vẫn được bảo vệ ngoài repository cùng Git bundle và các stash gốc.
