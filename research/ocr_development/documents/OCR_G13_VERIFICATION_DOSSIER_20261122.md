# Hồ sơ đề xuất xác minh Gate G13 cho Task 2



**PENDING APPROVAL · 22/11/2026 · Chưa cấp phép kích hoạt.**



Repository `<LOCAL_PATH>`. Nhánh `feature/thien`, HEAD `26bc332ae5954da7149ab3904f97d4b6313d6ab2`. Đối tượng xem xét là bytes working tree, gồm sửa bổ sung chưa commit. Chỉ đọc source/bằng chứng đã lưu và tính SHA-256.



## 1. Tám tệp thuộc Gate G13



Gate hiện dùng `<LOCAL_PATH>`. SHA-256 của Gate `c78250c6c4ea5dfc2f240a2a031e107268e296311697e16919e96571b4aab2a5`.



| Tệp | Đối chiếu | Mục đích và ảnh hưởng |

| --- | --- | --- |

| `backend/app/core.py` | MATCH | Cấu hình pipeline và validator chỉ cho Hybrid trong testing. Giữ current mặc định; chặn Final ngoài testing. |

| `backend/app/main.py` | CHANGED | Nhận JPEG qua nhánh JPG; điều phối upload và trả metadata. Gọi OCR theo cấu hình, lưu Invoice/InvoiceItem/ExtractionRun. |

| `backend/app/ocr_runtime.py` | CHANGED | Ánh xạ kết quả, kiểm tra JSON; phục hồi snapshot V8 nếu đầu ra Final lỗi. Giữ V8 hợp lệ; ghi used_pipeline/reason; dự phòng ngoài cùng về current khi được bật. |

| `backend/tools/ocr_benchmark/refine_v8.py` | CHANGED | Nối helper nhãn, nguồn, vai trò MST, chọn trường và ghép dòng. Kiểm soát liên kết dòng/trang, giữ null và cảnh báo mâu thuẫn. |

| `backend/tools/ocr_benchmark/hybrid_v8_final.py` | CHANGED | Điều phối theo trang, kiểm tra frame, giữ baseline, thu bằng chứng. Lỗi Final giữ V8 của cùng tài liệu hoặc từng trang. |

| `backend/tests/test_ocr_v8_final.py` | MATCH | Mã kiểm thử G13 có sẵn; hash vẫn khớp baseline. Chưa chứng minh bao phủ đủ nhánh Final bổ sung sau G13. |

| `web/src/ocrRuntimeInfo.js` | CHANGED | Thông báo mới khi Final giữ kết quả V8. Hiển thị lý do v8_baseline_retained; chưa xác minh Browser bản mới. |

| `web/tests/ocrRuntimeInfo.test.js` | MATCH | Mã kiểm thử thông báo cũ; hash vẫn khớp baseline. Chưa có bằng chứng xác minh nhánh thông báo V8 mới. |



### backend/app/core.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `ee4293f0160b634527a82266b5305104c6425eb3356d40013e7560a7b9b72015`.

- SHA-256 hiện tại `ee4293f0160b634527a82266b5305104c6425eb3356d40013e7560a7b9b72015`.

- Mục đích. Cấu hình pipeline và validator chỉ cho Hybrid trong testing.

- Ảnh hưởng. Giữ current mặc định; chặn Final ngoài testing.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### backend/app/main.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `3946f5cb5e12b1abbf8d557aaf74d6879bf39e3a1dac950110fc76f0ba9737a4`.

- SHA-256 hiện tại `2750d0dc9c012ecaca0f5c35ecf019da51b88a83cdbdf717a78f46f4a7203c55`.

- Mục đích. Nhận JPEG qua nhánh JPG; điều phối upload và trả metadata.

- Ảnh hưởng. Gọi OCR theo cấu hình, lưu Invoice/InvoiceItem/ExtractionRun.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### backend/app/ocr_runtime.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `7644ad0c7ed8595726858679dd8acc9977d077a0a5dea548ed53db6d5286d8f0`.

- SHA-256 hiện tại `2c63fbfa8ab8c992d55fb9cc5a3eae4c1e0cf266d366adc916abc7201c28a893`.

- Mục đích. Ánh xạ kết quả, kiểm tra JSON; phục hồi snapshot V8 nếu đầu ra Final lỗi.

- Ảnh hưởng. Giữ V8 hợp lệ; ghi used_pipeline/reason; dự phòng ngoài cùng về current khi được bật.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### backend/tools/ocr_benchmark/refine_v8.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `857ff8e1f4362af617f89c84ca870d8a0dff0b6d4248cad47a6b04a836844cea`.

- SHA-256 hiện tại `d4b3a9e47867c639a52f87377394d33bc7193eff88e14d789d3eb2f9d5b4564d`.

- Mục đích. Nối helper nhãn, nguồn, vai trò MST, chọn trường và ghép dòng.

- Ảnh hưởng. Kiểm soát liên kết dòng/trang, giữ null và cảnh báo mâu thuẫn.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### backend/tools/ocr_benchmark/hybrid_v8_final.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `740345d1e97e508b188b8bebec5bc2f59928a81f6fde36d1c73a62dcf036ddd6`.

- SHA-256 hiện tại `fcf6515ab710504e63e8b8999cda4b6b1f1664dc920355441592c97b5284a813`.

- Mục đích. Điều phối theo trang, kiểm tra frame, giữ baseline, thu bằng chứng.

- Ảnh hưởng. Lỗi Final giữ V8 của cùng tài liệu hoặc từng trang.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### backend/tests/test_ocr_v8_final.py



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `80901f1702cc389499f6f56b5ce6eef3c23501103765377ac5b0c3fa66b46dad`.

- SHA-256 hiện tại `80901f1702cc389499f6f56b5ce6eef3c23501103765377ac5b0c3fa66b46dad`.

- Mục đích. Mã kiểm thử G13 có sẵn; hash vẫn khớp baseline.

- Ảnh hưởng. Chưa chứng minh bao phủ đủ nhánh Final bổ sung sau G13.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### web/src/ocrRuntimeInfo.js



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `0728109483b91618201eecb57ed898d7aec4111fb2936469757a0cfcc0826d76`.

- SHA-256 hiện tại `545f5450ea5d70432b958e300febaadce19eb8a748a66076c0b5aa0afca4359b`.

- Mục đích. Thông báo mới khi Final giữ kết quả V8.

- Ảnh hưởng. Hiển thị lý do v8_baseline_retained; chưa xác minh Browser bản mới.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



### web/tests/ocrRuntimeInfo.test.js



- Đường dẫn tuyệt đối `<LOCAL_PATH>`.

- SHA-256 baseline `e452f8eae62405b90f94b97375cff186a19b1a22671af9a9b6c340d70c96d815`.

- SHA-256 hiện tại `e452f8eae62405b90f94b97375cff186a19b1a22671af9a9b6c340d70c96d815`.

- Mục đích. Mã kiểm thử thông báo cũ; hash vẫn khớp baseline.

- Ảnh hưởng. Chưa có bằng chứng xác minh nhánh thông báo V8 mới.

- Bằng chứng. Báo cáo G13, báo cáo tiếp tục/triển khai ngày 22/11 và source hiện tại ghi nhận thay đổi. Bằng chứng chạy cũ chưa xác minh các thay đổi sau G13.



## 2. Phụ thuộc cần bổ sung vào phạm vi



Các tệp dưới đây có hash hiện tại nhưng không có baseline trong danh sách tám hash cũ. null trong JSON ghi đúng khoảng thiếu đó; không lấy hash HEAD thay baseline cũ.



| Tệp | Nhóm | SHA-256 hiện tại |

| --- | --- | --- |

| `backend/tools/ocr_benchmark/source_links_v8_final.py` | NEW FINAL DEPENDENCY | `378807d024db69abbab92a96d69b76f896030b4912f9faead52035d10d58dfaf` |

| `backend/tools/ocr_benchmark/document_fields_v8_final.py` | NEW FINAL DEPENDENCY | `de5f7c2c3dc4a30955d1984075d531edcb810d0c840af217914839fc4d6203c9` |

| `backend/tools/ocr_benchmark/table_state_v8_final.py` | NEW FINAL DEPENDENCY | `35fb31e36875bdb3bf19e075c76cedf85476f4c9736e594037346b18ddec00fe` |

| `backend/tools/ocr_benchmark/review_v8_final.py` | NEW FINAL DEPENDENCY | `0cb4384518bd1755e9f9e667e6f36ef6defc38d0b154f0361efcdc9b89d98ec2` |

| `backend/tools/ocr_benchmark/__init__.py` | RUNTIME DEPENDENCY | `980ccf2960c85f8a290c6a6170e3726480cca87328661fad66e951763c0d3654` |

| `backend/tools/ocr_benchmark/hybrid_v6.py` | RUNTIME DEPENDENCY | `b78198d551f0fb326e3a7ae1e4e189cdce1d73d3886369a3e6699dc1f6abd36c` |

| `backend/tools/ocr_benchmark/hybrid_v7.py` | RUNTIME DEPENDENCY | `f548f47781bc5c03875536db9ebff968c6993524ac41546c9bcd406075f66586` |

| `backend/tools/ocr_benchmark/hybrid_v8.py` | RUNTIME DEPENDENCY | `b66fddadc8d2adee89890ac6272a0438533ad0eb8303886f4636e50563aac43d` |

| `backend/tools/ocr_benchmark/pipeline_v4.py` | RUNTIME DEPENDENCY | `19998bc1dd0c24adf1323e268fc3d736efc0d8f509632883ce3309474d0a5961` |

| `backend/tools/ocr_benchmark/pipeline_v5.py` | RUNTIME DEPENDENCY | `4c0ea2e5b6594aa8cafd01084dfe1d272b8bcd7c6069cbb9d63e81744a3daa90` |

| `backend/tools/ocr_benchmark/fields_v7.py` | RUNTIME DEPENDENCY | `f8e79ac85bd8d6f13a195a503812d4d116978f5e108c33dbb59c8ee9c62ff9bc` |

| `backend/tools/ocr_benchmark/fields_v8.py` | RUNTIME DEPENDENCY | `2f84c227940a5e0eb1bfc29b378d6e8a2d0a542ee07d12bcd396861b2ebc74d5` |

| `backend/tools/ocr_benchmark/table_v3.py` | RUNTIME DEPENDENCY | `3bdaced70ac55603fe2bba9bb1156e1b91e474e3cdd071979f7231d85bafa621` |

| `backend/tools/ocr_benchmark/table_v6.py` | RUNTIME DEPENDENCY | `1bad31c95d961601e50d543a52197fa7bb0496b688d211812b3905548294608e` |

| `backend/tools/ocr_benchmark/table_v7.py` | RUNTIME DEPENDENCY | `f2d0c5f36f67e37c0f8445d82c42f303f8610ea471b641b1084bfd7ba8cf57c9` |

| `backend/tools/ocr_benchmark/table_v8.py` | RUNTIME DEPENDENCY | `663b9e7faf730f9cc1bc19377add9d993ef101f530941332cce97f7b01c5f8b8` |

| `backend/tools/ocr_benchmark/layout.py` | RUNTIME DEPENDENCY | `1e6fd82c395806a719857a754c912186842050efb57b9cbc1112d101ecbf446d` |

| `backend/tools/ocr_benchmark/preprocess_v8.py` | RUNTIME DEPENDENCY | `011aa3ce1ff987f23589907f3ad3495a0a15906edac67eea98d0735025826af8` |

| `backend/tools/ocr_benchmark/profiling.py` | RUNTIME DEPENDENCY | `f1168d8b14eaac4c44cad1eec532290014330541a0f6f2d8860d7fdb6db179fd` |

| `backend/app/extraction.py` | BACKEND CONTRACT | `c878ec80cb32e1d2f8dada0329e70c6bf4eed708246dcef0ef1b108c094c3218` |

| `backend/app/models.py` | BACKEND CONTRACT | `15c4672f1fcb6437be3d55b04cd5e220736acdc7f134ceebcb2dc27a3d045f46` |

| `backend/requirements.txt` | BACKEND CONTRACT | `b199aa7ede4751492287a22f7f8cb10558cb927355d9ccc7a3b6f73acd42c7e5` |

| `web/src/InvoiceDetailPage.jsx` | WEB CONTRACT | `8d8537567508f17aa42104edeeb03dec1edae97946cdb6b4852f79cc6ff3fd9d` |

| `web/src/InvoiceDetailPage.css` | WEB CONTRACT | `9e07d470093df7b353c75e216ac32879bc98a848d8cdd6ba10e89069479e6341` |

| `web/src/viewUtils.js` | WEB CONTRACT | `bc43633718f91ed15fb12de1fa04acf0d2c896ca7900f9a2335d9f1132006a53` |

| `web/src/api.js` | WEB CONTRACT | `f527400d83087090c9cfa364853cbfd07a19fba37b95dc71f75fc90f57eda1e3` |

| `web/src/lookupUtils.js` | WEB CONTRACT | `6313fa220cc4e3452a677ebd365268f37ba9d93d91fbf2d91ad01cfc1b9fa5b7` |

| `web/package.json` | WEB CONTRACT | `2153c8f9fa5153ce4fd5655c3475806a7f725e8149454f7c5363a125a2e3b825` |

| `web/package-lock.json` | WEB CONTRACT | `e5da0a1627e4412d72c04bff93c8158b774a0fe34b6993038044b5cf767456b4` |

| `backend/tests/test_ocr_final_source_links.py` | VERIFICATION SUPPORT | `36429b45b689508b19dc56a31caf9dc018642042f8af378156733c46ad1dfae2` |

| `backend/tests/test_ocr_runtime.py` | VERIFICATION SUPPORT | `79185a6c150027d2e7f2ac9b0b0106f2863298a3285d2cb3df85d2e0b4450f91` |

| `backend/tests/test_phase8_runtime_api.py` | VERIFICATION SUPPORT | `4d078005a8ebe36f8940541a8039b226950e9fba38fa40c85fbd7436fbdea5a9` |

| `backend/tests/test_phase9_runtime_api.py` | VERIFICATION SUPPORT | `e97ccb97a3b833272d8fde7d7d1237fd353858b8cbc945585ab4f66071df781e` |

| `backend/tests/test_phase11_runtime_api.py` | VERIFICATION SUPPORT | `8f7201a8e446637203ee4aa25495cdd0dd27838dbeac69dfc81a0f1e74c7c9fc` |

| `backend/tests/test_phase2_api.py` | VERIFICATION SUPPORT | `29ed5b5872d1ac476830958f968cb4ac63a26ba1e310f5d1ff9be4a82d573835` |

| `backend/tests/test_extraction.py` | VERIFICATION SUPPORT | `d0050b807cb94434dc7e3c77fa834eca1a5ce43a068e9e9a26de32a7c8965225` |

| `backend/tests/fixtures/uat9f.xml` | VERIFICATION SUPPORT | `a2dc7df221e5ebb7a0efed14061f19e580c2e7c0cd717db96fa5e3f052c62b70` |



Bốn helper Final mới được lớp refine/bộ điều phối gọi trực tiếp. V8/V7/V6/V4/V5, table, layout và preprocessing là chuỗi kế thừa ảnh hưởng kết quả. Trang chi tiết và các helper import ảnh hưởng hiển thị bằng chứng/giá trị. Nhóm hỗ trợ xác minh định danh mã kiểm thử hiện có, không phải kết quả đã chạy.



## 3. Bằng chứng hiện có



- Gate lịch sử ghi 441 Backend, 37 Web/build PASS, 28 dòng tài chính và 27 dòng khớp toàn bộ, còn một lỗi mô tả. Những số liệu này thuộc phiên bản cũ trên development/DEMO.

- Hồ sơ Browser/Database G13 lưu kết quả của phiên bản lúc đó. Không suy ra bản working tree đã được thực thi.

- Báo cáo ngày 22/11 và audit commit hỗ trợ truy nguyên/bảo toàn source. Commit 26bc332 chứa 58 tệp đã chọn; sửa bổ sung vẫn ở working tree. Audit bảo toàn không thay bằng chứng thực thi.

- Hai tệp test cũ vẫn khớp hash không chứng minh đã bao phủ các nhánh mới.



| Bằng chứng ngoài repository, đường dẫn tính từ workspace | SHA-256 |

| --- | --- |

| `ocr_task2_final/OFFLINE_GATE.json` | `c78250c6c4ea5dfc2f240a2a031e107268e296311697e16919e96571b4aab2a5` |

| `ocr_task2_final/STATUS.json` | `b2a631c19ef7f5e7c8ed26e3b425ff1efdddbfc11a5bb8a8904745437890eb15` |

| `ocr_task2_final/COMPARISON.json` | `4970be12a10852edc551be036ed01c627b2d3756c7b4fb2101d28f0ae021d25c` |

| `ocr_task2_final/backend-tests.xml` | `7504a61937cdb1353beba7dd4dfd64b2237ccc8ea4be6c80ed070e79aff53af0` |

| `ocr_task2_final/backend-tests.log` | `851d9bf66fc61f198c77b0e1c078ae73bb7d340905385dff8cfcdc07b9bd869c` |

| `ocr_task2_final/web-tests.log` | `9aae33a1b28c48b67621f6c65cf0da4c343333b0358875aa0aeda41322b64a27` |

| `ocr_task2_final/build.log` | `36e562b2e2d1bfaf15608df7a11103695142fe3fde4fdc3c2a83eb747d16eee2` |

| `ocr_task2_final/uat/BROWSER_UAT.json` | `2915ef83778c13805fd4991914c8e994603d8728e0db6b58b4f0652ccfe4041f` |

| `ocr_task2_final/uat/DB_FINAL_CHECK.json` | `7f601a17881d76c3bf0d984e406c544503cf3cc374190a809aaa376c1420e258` |

| `ocr_task2_continuation_20261122/IMPLEMENTATION_REVIEW.json` | `f5df35d3c0970e7bc9a6a969af2ad25d45c2dbb34bd1468e3ff19c04cfcbb898` |

| `ocr_task2_implementation_20261122/IMPLEMENTATION_STATUS.json` | `1b28eebc2b614918b6de02f04d9befbdfff2d9ae95401885e1bff8cfe5df9d3c` |

| `TASK2_COMMIT_AUDIT_20261122/AFTER.json` | `db573171d3e99a471203827b1efba3a666933fc57d8ccbc363b70716f0a52771` |



## 4. Điều kiện xác minh và phê duyệt baseline



1. Người chịu trách nhiệm chốt phạm vi nguồn, phụ thuộc và tiêu chí chấp nhận cho phiên bản này. Cố định snapshot bytes; thay source tiếp thì hồ sơ và bằng chứng phải trỏ đúng phiên bản sau sửa.

2. Cần bằng chứng thực thi kỹ thuật cho đúng snapshot về trường/dòng hàng, XML, ảnh/PDF, nhiều trang, null/0, giữ V8 khi Final lỗi, nhánh current khi baseline không dùng được, API/UI và độc lập trạng thái nghiệp vụ. Bằng chứng cho bản hiện tại đang thiếu. Không thực hiện các xác minh này trong lượt lập hồ sơ.

3. Đối chiếu coverage của bằng chứng với từng thay đổi. Giữ lỗi/giới hạn thực tế. Không dùng số 441/37 hay kết quả DEMO cũ làm kết quả của bản mới. Tiêu chí cần được duyệt; số bài test lịch sử không tự trở thành yêu cầu cố định cho phiên bản mới.

4. Người phê duyệt xem hash, danh tính snapshot, bằng chứng và giới hạn; ghi người duyệt, thời điểm, quyết định. Chỉ sau đó mới có thể phát hành baseline mới theo quy trình được cho phép, bảo toàn baseline cũ. Hồ sơ hiện để trống các thông tin duyệt.

5. Loader phải kiểm đúng hash của bản đã được duyệt. Chỉ đổi hash để khớp source hiện tại không tạo ra bằng chứng xác minh.



## 5. Điều kiện kích hoạt development



- Hiện source mặc định current; validator chỉ chấp nhận Hybrid khi APP_ENV=testing. APP_ENV=development kết hợp OCR_PIPELINE=hybrid_v8_final bị từ chối. Không có tổ hợp biến môi trường hợp lệ nào bật Final trong development với nguyên validator này.

- Cần quyết định cho phép Final ngoài testing. Sửa validator/default sau phê duyệt tạo snapshot mới; core.py đang thuộc Gate nên bằng chứng/baseline phải bao phủ đúng bản sau sửa.

- Cấu hình mục tiêu khi được cho phép là APP_ENV=development, OCR_PIPELINE=hybrid_v8_final, OCR_HYBRID_FALLBACK=true. Tesseract/ngôn ngữ, thư viện, API/Web và upload directory phải được định danh trong cấu hình runtime được phép. Chưa xác minh runtime ở lượt này.

- Gate hiện nằm trong launcher serve_test.py, không kiểm ở mọi cách khởi động Uvicorn. Launcher G13 ép testing, PostgreSQL test và upload test; chưa có đường development tương đương được xác minh. Cần đường khởi động development được phê duyệt có kiểm Gate, điều kiện backup và phạm vi dữ liệu hợp lệ. Không gọi Uvicorn trực tiếp để tránh guard.

- PROTECTED_FILES.json và hồ sơ backup/runtime là các kiểm soát bổ sung ngoài tám hash. Cần xem tính phù hợp của chúng khi có thay đổi môi trường được duyệt; không sửa để vượt chặn. Lượt này không thực hiện preflight có truy cập Database.

- Final giữ kết quả V8 của cùng tài liệu khi bước bổ sung lỗi. Nếu chính V8/engine lỗi, dự phòng ngoài cùng có thể là current khi bật fallback; không bảo đảm V8 thành công khi baseline đó đã lỗi.



## 6. Kết luận



Phần chức năng Task 2 đã tích hợp theo hồ sơ hiện tại. Quyết định vận hành vẫn PENDING APPROVAL/BLOCKED. Đây chỉ là đề xuất; không thay OFFLINE_GATE.json, không Final PASS, không NFR01 PASS. NFR01 độc lập vẫn thiếu bằng chứng và được tách khỏi gate hồi quy kỹ thuật.



Chỉ tạo hai tài liệu mới. Không thực thi test, benchmark, OCR, API, Database hoặc sửa .env, validator, source chức năng, Task 1/3, nhánh và stash.

## 7. Hoàn thiện hồ sơ cho người xét duyệt · 22/11/2026

**Đầy đủ để xem xét hồ sơ với các mục mở. Chưa đủ để phê duyệt Gate đạt hoặc cho phép development.**
Đã đọc toàn bộ hồ sơ và cấu trúc đề xuất. 45/45 tệp nguồn/phụ thuộc vẫn khớp manifest; 12/12 tệp bằng chứng khớp hash. Đối chiếu baseline cũ vẫn là 3 khớp, 5 khác. Khớp hash chỉ xác nhận danh tính và tính nguyên vẹn.

### 7.1. Đối chiếu thay đổi với bằng chứng mã nguồn

| Mã | Nội dung có căn cứ nguồn | Vị trí nguồn | Bằng chứng còn thiếu |
| --- | --- | --- | --- |
| C01 | JPEG được chuẩn hóa về JPG rồi đi qua kiểm chữ ký và upload hiện có. | backend/app/main.py:490 | Biên nhận upload JPEG, kiểu tệp, metadata và kết quả đọc lại đúng phiên bản. |
| C02 | Mapper/JSON lỗi ở Final dùng snapshot V8 có sẵn; used_pipeline và reason phản ánh giữ baseline. | backend/app/ocr_runtime.py:95; backend/app/ocr_runtime.py:136 | Bằng chứng các nhánh thành công, dữ liệu Final không lưu được, snapshot hợp lệ/không hợp lệ, fallback bật/tắt. |
| C03 | Chọn trường theo nhãn và bằng chứng, xử lý xung đột và liên kết dòng một-một. | backend/tools/ocr_benchmark/refine_v8.py:168; backend/tools/ocr_benchmark/source_links_v8_final.py:120 | Kết quả cho nhãn tách dòng, vai trò MST/cột, dòng lặp, mã model, cùng amount khác sản phẩm và xung đột bằng chứng ngang nhau. |
| C04 | Điều phối theo trang, đối chiếu raster và cột tiếp trang, giữ V8 theo trang/toàn tài liệu. | backend/tools/ocr_benchmark/hybrid_v8_final.py:173; backend/tools/ocr_benchmark/table_state_v8_final.py:16 | Bằng chứng PDF text/scan hỗn hợp, thứ tự/trùng trang, thay frame/số chứng từ, lỗi riêng Final và giữ bảng không đếm hai lần. |
| C05 | Nhãn tài chính, tiền phân nhóm nghìn bằng dấu cách, khoản điều chỉnh có nguồn; null không tự đổi thành 0. | backend/tools/ocr_benchmark/document_fields_v8_final.py:58; backend/tools/ocr_benchmark/document_fields_v8_final.py:102; backend/tools/ocr_benchmark/review_v8_final.py:8 | Bằng chứng chuẩn hóa tiền/ngày, không gộp hai số cạnh nhau; nhiều VAT, discount/phụ phí không đổi sai tổng hoặc dòng hàng. |
| C06 | Trang chi tiết hiển thị findings đã được API trả và thông báo giữ V8. | web/src/InvoiceDetailPage.jsx:108; web/src/ocrRuntimeInfo.js:6 | Bằng chứng hợp đồng API, hiển thị findings và reason giữ V8, null/0, dữ liệu sau lưu/tải lại và quyền truy cập đúng snapshot. |

Các thay đổi C01–C06 phù hợp phạm vi Task 2 theo mục đích và lời gọi trong source. Chưa có kết luận hiệu quả thực thi hoặc phê duyệt thay đổi. 37 tệp phụ thuộc là phạm vi đề xuất; người xét duyệt cần chốt ranh giới runtime và hỗ trợ xác minh. Cả 45 bản ghi JSON đã bổ sung kết quả đối chiếu hash và vị trí đọc source.

### 7.2. Danh mục bằng chứng còn thiếu

| Mã | Hồ sơ cần có | Khoảng thiếu cụ thể | Trạng thái |
| --- | --- | --- | --- |
| E01 | Định danh môi trường và phiên bản thực thi | Hash nguồn đúng snapshot, phiên bản Python/Node/Tesseract, vie/eng và gói đã cài. requirements Backend dùng khoảng phiên bản; hash tệp requirements chưa xác định gói thực tế. | MISSING |
| E02 | Kết quả xác minh các thay đổi C01–C06 | Kết quả có đầu vào/expected/actual, phạm vi, thời điểm và hash snapshot; gồm đường thành công và lỗi/fallback. Kết quả 441/37 cũ không đại diện bản mới. | MISSING |
| E03 | Đối chiếu kỳ vọng mã kiểm thử với logic hiện tại | Giải quyết hoặc được xem xét có lưu vết bất đồng R01 trước khi coi bộ bằng chứng hỗ trợ bản mới là đầy đủ. | OPEN |
| E04 | Bằng chứng tích hợp API/lưu/UI cho snapshot hiện tại | Invoice/InvoiceItem/ExtractionRun, findings, used_pipeline, correction và trạng thái độc lập. Hash browser/database cũ chỉ chứng minh tệp bằng chứng nguyên vẹn. | MISSING |
| E05 | Phạm vi và tiêu chí kỹ thuật được người có thẩm quyền chốt | Xác định tệp runtime cần khóa, hỗ trợ xác minh, tiêu chí chấp nhận và xử lý rủi ro tồn đọng. Danh sách 37 là đề xuất phạm vi, chưa được ký duyệt. | PENDING APPROVAL |
| E06 | Phương án và bằng chứng vận hành development | Quyết định cho phép development; phiên bản validator/loader được phép sau sửa, bằng chứng kiểm Gate, backup, upload và phạm vi dữ liệu. Chưa có bản sau sửa để xác minh. | MISSING |
| E07 | Quyết định phê duyệt baseline và kích hoạt | Người duyệt, thời điểm, quyết định, phạm vi/giới hạn, tham chiếu bằng chứng và hash của phiên bản được duyệt. | NOT GRANTED |

### 7.3. Rủi ro chưa giải quyết

| Mã | Mức | Nội dung |
| --- | --- | --- |
| R01 | HIGH | Bất đồng tĩnh giữa kỳ vọng ca xung đột ngang bằng và logic chọn trường. Ca kiểm thử tìm V8_FINAL_FIELD_CONFLICT/selected; nhánh ngang bằng hiện tạo V8_FINAL_FIELD_UNRESOLVED/retained và giữ baseline. Có nguy cơ kỳ vọng cũ không còn phù hợp. Chưa chạy, không ghi kết quả FAIL từ phân tích này. |
| R02 | HIGH | Gate chỉ nằm ở launcher G13; launcher này ép testing/test DB/upload. Chưa có đường development tương đương được xác minh.  |
| R03 | HIGH | 5/8 hash lệch baseline đang dùng. 37 tệp thêm chưa có baseline G13 riêng; hash hiện tại chỉ định danh source.  |
| R04 | MEDIUM | Snapshot chứa thay đổi chưa commit; commit 26bc332 chưa đại diện toàn bộ phiên bản. Không bắt buộc commit trong lượt này, nhưng mọi bằng chứng/phê duyệt phải dùng cùng manifest bytes.  |
| R05 | HIGH | Chất lượng current fallback từng không đạt trên mẫu fault G13; phục hồi V8 không bảo đảm nếu chính baseline/engine lỗi. Không có chứng minh chất lượng cho bản hiện tại.  |
| R06 | MEDIUM | Thiếu dấu/bảng phức tạp/nhiều trang/VAT-discount và confidence chưa hiệu chuẩn; NFR01 thiếu tập độc lập và hồ sơ A/B.  |
| R07 | MEDIUM | Gói Backend và Tesseract/traineddata thực tế chưa được định danh trong manifest nguồn. Thư viện dùng khoảng phiên bản, có thể đổi hành vi.  |
| R08 | MEDIUM | evaluate.py lịch sử gắn cứng 441 bài và số liệu DEMO, tạo trực tiếp OFFLINE_GATE.json. Không dùng nó như thủ tục phát hành baseline mới chưa được phê duyệt.  |

R01 được xác định qua đọc test_ocr_final_source_links.py:126–133 và refine_v8.py, nhánh len(leaders)>1. Đây là bất đồng kỳ vọng cần xem xét; không phải kết quả chạy test. Không sửa test hoặc parser trong lượt hoàn thiện hồ sơ.

### 7.4. Quyết định cần người có thẩm quyền ghi nhận

- Chốt phạm vi nguồn/phụ thuộc, snapshot và tiêu chí chấp nhận.
- Đánh giá tính phù hợp của bằng chứng hiện có, khoảng thiếu E01–E07 và cách xử lý R01–R08.
- Ghi nhận riêng quyết định thay đổi điều kiện môi trường cho development.
- Chỉ cấp phép baseline đạt và kích hoạt khi có căn cứ cho đúng phiên bản được duyệt. Có thể xem xét phạm vi/tiêu chí lúc này; hồ sơ hiện tại chưa đủ cấp Gate PASS.
- Người duyệt, vai trò, thời điểm và quyết định còn để trống trong JSON. Không giả ký hoặc giả xác nhận.

### 7.5. Điều kiện tối thiểu để kích hoạt development

1. Có quyết định cho phép development và phạm vi/tiêu chí kỹ thuật được duyệt.
2. Có validator và đường startup được cho phép kiểm đúng Gate trong development. Hiện validator từ chối, launcher ép testing. Chỉ đặt biến môi trường chưa đủ.
3. Có bằng chứng xác minh đúng snapshot sau các thay đổi cần thiết, cùng xử lý bất đồng R01 có lưu vết.
4. Có baseline được phê duyệt cho snapshot đó và điều kiện runtime, backup, upload, phạm vi dữ liệu phù hợp. NFR01 vẫn được quản lý như nghiệm thu độc lập riêng.

Lượt này chỉ cập nhật hai hồ sơ đề xuất. Trạng thái vẫn PENDING APPROVAL, Final NOT VERIFIED, NFR01 NOT INDEPENDENTLY ACCEPTED. Gate đang sử dụng, source chức năng và cấu hình được giữ nguyên.
