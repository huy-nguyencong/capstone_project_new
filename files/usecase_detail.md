# Chi tiết Use Case

> **Quy ước hiển thị kết quả tìm kiếm:** Ở tầng giao diện và nghiệp vụ, hệ thống chỉ hiển thị **Điểm phù hợp (Matching Score)** để hỗ trợ người dùng xếp hạng và đánh giá kết quả. Các giá trị confidence nội bộ của Detector hoặc các thành phần AI khác, nếu có, chỉ phục vụ xử lý backend và không hiển thị cho người dùng.

## UC-01 – Đăng nhập hệ thống

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-01 |
| **Tên use-case** | Đăng nhập hệ thống |
| **Actors** | Admin, Operator, Viewer |
| **Mục đích** | Cho phép người dùng xác thực tài khoản để truy cập vào hệ thống và sử dụng các chức năng phù hợp với vai trò và phạm vi quyền được cấp. |
| **Tiền điều kiện** | Người dùng đã có tài khoản hợp lệ trong hệ thống và tài khoản đang ở trạng thái hoạt động. |
| **Hậu điều kiện** | Người dùng đăng nhập thành công, hệ thống tạo phiên đăng nhập và cho phép truy cập các chức năng tương ứng với vai trò và quyền của tài khoản. |
| **Luồng chính** | 1. Người dùng truy cập vào trang đăng nhập của hệ thống.<br>2. Hệ thống hiển thị biểu mẫu đăng nhập.<br>3. Người dùng nhập tên đăng nhập và mật khẩu.<br>4. Người dùng gửi yêu cầu đăng nhập.<br>5. Hệ thống kiểm tra thông tin đăng nhập.<br>6. Hệ thống xác định tài khoản hợp lệ, đang hoạt động và lấy thông tin vai trò, quyền truy cập của người dùng.<br>7. Hệ thống tạo phiên đăng nhập cho người dùng.<br>8. Hệ thống chuyển người dùng đến giao diện chính phù hợp với vai trò của tài khoản. |
| **Ngoại lệ** | **E1 – Sai thông tin đăng nhập:** Nếu tên đăng nhập hoặc mật khẩu không chính xác, hệ thống thông báo đăng nhập không thành công và yêu cầu người dùng nhập lại.<br><br>**E2 – Tài khoản bị khóa hoặc ngừng hoạt động:** Hệ thống từ chối đăng nhập và thông báo tài khoản không có quyền truy cập hệ thống.<br><br>**E3 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình xác thực hoặc truy cập dữ liệu tài khoản, hệ thống thông báo không thể đăng nhập tại thời điểm hiện tại. |
| **Luồng thay thế** | Không có. |

### Ghi chú

- Sau khi đăng nhập thành công, các chức năng hiển thị và dữ liệu người dùng có thể truy cập phụ thuộc vào vai trò và phạm vi quyền được cấp.
- Admin, Operator và Viewer sử dụng cùng một chức năng đăng nhập; hệ thống phân quyền sau khi quá trình xác thực hoàn tất.

---

## UC-02 – Quản lý tài khoản người dùng

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-02 |
| **Tên use-case** | Quản lý tài khoản người dùng |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin tạo, cập nhật, khóa/mở khóa, xóa hoặc ngừng hoạt động tài khoản người dùng; gán vai trò phù hợp và gán khu vực giám sát cho Operator. Việc xóa hoặc ngừng hoạt động tài khoản chỉ ảnh hưởng đến quyền truy cập của tài khoản và không làm xóa dữ liệu nghiệp vụ đã được tạo trước đó. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền quản lý tài khoản người dùng. |
| **Hậu điều kiện** | Thông tin tài khoản người dùng được tạo mới, cập nhật, khóa, xóa hoặc thay đổi vai trò theo thao tác của Admin; các thay đổi được lưu lại trong hệ thống. |
| **Luồng chính** | 1. Admin truy cập chức năng quản lý tài khoản người dùng.<br>2. Hệ thống hiển thị danh sách các tài khoản hiện có cùng các thông tin cơ bản như tên tài khoản, vai trò và trạng thái hoạt động.<br>3. Admin lựa chọn thao tác quản lý phù hợp đối với tài khoản người dùng.<br>4. Hệ thống hiển thị biểu mẫu hoặc thông tin tương ứng với thao tác được lựa chọn.<br>5. Admin nhập hoặc cập nhật các thông tin cần thiết và xác nhận thao tác.<br>6. Hệ thống kiểm tra tính hợp lệ của dữ liệu và quyền thực hiện của Admin.<br>7. Hệ thống thực hiện thay đổi đối với tài khoản người dùng.<br>8. Hệ thống lưu thông tin thay đổi và cập nhật lại danh sách tài khoản.<br>9. Hệ thống thông báo thao tác được thực hiện thành công. |
| **Ngoại lệ** | **E1 – Thông tin tài khoản không hợp lệ:** Nếu dữ liệu được nhập thiếu, sai định dạng hoặc không đáp ứng yêu cầu của hệ thống, hệ thống từ chối lưu và yêu cầu Admin kiểm tra lại thông tin.<br><br>**E2 – Tên đăng nhập đã tồn tại:** Khi tạo tài khoản mới, nếu tên đăng nhập đã được sử dụng, hệ thống thông báo và yêu cầu Admin lựa chọn tên đăng nhập khác.<br><br>**E3 – Không tìm thấy tài khoản:** Nếu tài khoản cần cập nhật, khóa hoặc xóa không còn tồn tại, hệ thống thông báo không thể thực hiện thao tác.<br><br>**E4 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình lưu hoặc cập nhật dữ liệu, hệ thống thông báo thao tác không thành công và không áp dụng thay đổi chưa hoàn tất.<br><br>**E5 – Khu vực của Operator không hợp lệ:** Khi tạo hoặc chỉnh sửa Operator, nếu chưa gán khu vực hoặc yêu cầu gán nhiều khu vực, hệ thống từ chối lưu và yêu cầu Admin chọn đúng một khu vực. |
| **Luồng thay thế** | **A1 – Tạo tài khoản mới:** Admin lựa chọn tạo tài khoản, nhập thông tin người dùng, thiết lập thông tin đăng nhập và gán vai trò Operator hoặc Viewer. Nếu là Operator, Admin phải gán đúng một khu vực giám sát; hệ thống kiểm tra dữ liệu và tạo tài khoản mới.<br><br>**A2 – Cập nhật tài khoản:** Admin lựa chọn một tài khoản hiện có, chỉnh sửa các thông tin được phép thay đổi và lưu lại. Nếu chỉnh sửa Operator, hệ thống yêu cầu tài khoản tiếp tục có đúng một khu vực giám sát; hệ thống cập nhật thông tin tài khoản.<br><br>**A3 – Khóa hoặc mở khóa tài khoản:** Admin thay đổi trạng thái hoạt động của tài khoản. Tài khoản bị khóa không thể đăng nhập cho đến khi được mở khóa.<br><br>**A4 – Thay đổi vai trò người dùng:** Admin thay đổi vai trò của tài khoản giữa Operator và Viewer; quyền truy cập của người dùng được cập nhật theo vai trò mới.<br><br>**A5 – Xóa/Ngừng hoạt động tài khoản:** Admin lựa chọn tài khoản không còn sử dụng và thực hiện xóa hoặc ngừng hoạt động theo chính sách của hệ thống. Tài khoản không còn có thể đăng nhập hoặc thực hiện nghiệp vụ mới. Các dữ liệu nghiệp vụ đã được tạo trước đó, bao gồm Case, kết quả tìm kiếm đã lưu và audit log, vẫn được giữ nguyên và tiếp tục có thể được truy xuất theo quyền của các tài khoản khác.<br><br>**A6 – Gán khu vực giám sát:** Khi tạo hoặc chỉnh sửa Operator, Admin gán đúng một khu vực giám sát cho tài khoản. Hệ thống không cho phép gán nhiều khu vực và sử dụng khu vực này để xác định các camera mà Operator được phép tìm kiếm và các kết quả có thể được hiển thị. |

### Ghi chú

- Use case này tập trung vào quản lý tài khoản, vai trò và khu vực giám sát mà Operator được phép sử dụng khi tìm kiếm; không bao gồm cơ chế phân quyền tùy chỉnh ở mức từng chức năng nếu hệ thống chưa triển khai.
- Admin là actor duy nhất được phép thực hiện use case này.
- Việc khóa tài khoản nên được ưu tiên trong các trường hợp cần ngăn người dùng truy cập nhưng vẫn cần giữ lại lịch sử hoạt động của tài khoản.
- Dữ liệu nghiệp vụ tồn tại độc lập với vòng đời tài khoản người dùng.
- Việc xóa hoặc ngừng hoạt động tài khoản không làm xóa Case, kết quả tìm kiếm đã lưu, audit log hoặc dữ liệu lịch sử do tài khoản đó tạo ra.
- Các bản ghi lịch sử vẫn giữ thông tin định danh cần thiết của người thực hiện tại thời điểm phát sinh để phục vụ truy vết.
- Khi tạo hoặc chỉnh sửa Operator, Admin phải gán đúng **một khu vực giám sát** cho tài khoản đó; không có thao tác gán nhiều khu vực. Khu vực này được dùng để giới hạn camera và dữ liệu tìm kiếm mà Operator được phép truy cập.
- Khu vực giám sát được gán cho Operator là cơ sở phân quyền cho chức năng tìm kiếm: hệ thống chỉ cho phép truy cập camera và kết quả tìm kiếm thuộc khu vực đó.
- Khu vực là thông tin gắn với camera và Operator để đối chiếu phạm vi tìm kiếm. Phiên bản này không đặt ra danh mục khu vực dùng chung hoặc use case quản lý khu vực độc lập; cách tạo và duy trì thông tin khu vực chưa được đặc tả.
- Nếu tài khoản Operator là người phụ trách một hoặc nhiều Case bị khóa, xóa hoặc ngừng hoạt động, các Case đó vẫn được giữ nguyên cùng thông tin Operator phụ trách tại thời điểm tạo/quản lý. Phiên bản hiện tại không tự động chuyển Case cho Operator khác; Viewer vẫn có thể xem các Case này.

---

## UC-03 – Quản lý camera

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-03 |
| **Tên use-case** | Quản lý camera |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin quản lý các camera được sử dụng trong hệ thống, bao gồm thêm mới, cập nhật thông tin, loại camera khỏi vận hành và kiểm tra khả năng kết nối tới luồng RTSP. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền quản lý camera. |
| **Hậu điều kiện** | Thông tin camera được tạo mới, cập nhật hoặc chuyển sang trạng thái không còn vận hành theo thao tác của Admin; trạng thái kết nối RTSP của camera được hệ thống ghi nhận và hiển thị. |
| **Luồng chính** | 1. Admin truy cập chức năng quản lý camera.<br>2. Hệ thống hiển thị danh sách các camera hiện có cùng các thông tin cơ bản như tên camera, khu vực, địa chỉ RTSP và trạng thái kết nối.<br>3. Admin lựa chọn thao tác quản lý phù hợp đối với camera.<br>4. Hệ thống hiển thị biểu mẫu hoặc thông tin tương ứng với thao tác được lựa chọn.<br>5. Admin nhập hoặc cập nhật các thông tin cần thiết của camera.<br>6. Hệ thống kiểm tra tính hợp lệ của dữ liệu được cung cấp.<br>7. Hệ thống kiểm tra khả năng kết nối tới luồng RTSP của camera khi cần thiết và xác định trạng thái kết nối.<br>8. Nếu kết nối không thành công, hệ thống hiển thị cảnh báo nhưng vẫn cho phép Admin lưu camera ở trạng thái Offline/Chưa xác minh.<br>9. Hệ thống thực hiện thao tác quản lý camera theo yêu cầu của Admin.<br>10. Hệ thống lưu thay đổi và cập nhật lại danh sách camera.<br>11. Hệ thống thông báo kết quả thực hiện cho Admin. |
| **Ngoại lệ** | **E1 – Thông tin camera không hợp lệ:** Nếu thiếu thông tin bắt buộc hoặc dữ liệu không đúng định dạng, hệ thống từ chối lưu và yêu cầu Admin kiểm tra lại.<br><br>**E2 – Không thể kết nối tới luồng RTSP:** Nếu hệ thống không thể kết nối tới camera do địa chỉ RTSP, thông tin xác thực, trạng thái camera hoặc kết nối mạng, hệ thống hiển thị cảnh báo. Admin có thể chỉnh sửa cấu hình và thử lại hoặc vẫn lưu camera ở trạng thái Offline/Chưa xác minh để kiểm tra lại sau.<br><br>**E3 – Camera đã tồn tại:** Nếu camera hoặc địa chỉ RTSP đã được đăng ký trong hệ thống theo chính sách kiểm tra trùng lặp, hệ thống thông báo và không tạo bản ghi mới.<br><br>**E4 – Không tìm thấy camera:** Nếu camera cần cập nhật hoặc loại khỏi vận hành không còn tồn tại trong hệ thống, hệ thống thông báo không thể thực hiện thao tác.<br><br>**E5 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình kiểm tra kết nối hoặc lưu dữ liệu, hệ thống thông báo thao tác không thành công và không áp dụng thay đổi chưa hoàn tất. |
| **Luồng thay thế** | **A1 – Thêm camera mới:** Admin lựa chọn thêm camera, nhập tên camera, địa chỉ RTSP, thông tin xác thực, khu vực lắp đặt và các thông tin cần thiết khác. Hệ thống kiểm tra tính hợp lệ của dữ liệu và thử kết nối tới luồng RTSP. Nếu kết nối thành công, camera được lưu với trạng thái hoạt động phù hợp; nếu kết nối không thành công, Admin có thể lựa chọn lưu camera ở trạng thái Offline/Chưa xác minh để kiểm tra lại sau.<br><br>**A2 – Cập nhật thông tin camera:** Admin lựa chọn một camera hiện có, chỉnh sửa các thông tin được phép thay đổi và lưu lại. Nếu thông tin kết nối RTSP thay đổi, hệ thống thực hiện kiểm tra kết nối lại trước khi lưu.<br><br>**A3 – Kiểm tra kết nối camera:** Admin yêu cầu kiểm tra kết nối đối với một camera. Hệ thống thử kết nối tới luồng RTSP bằng cấu hình hiện tại và trả về trạng thái kết nối cho Admin.<br><br>**A4 – Loại camera khỏi vận hành:** Admin lựa chọn camera cần ngừng vận hành và xác nhận thao tác. Hệ thống loại camera khỏi vận hành nhưng vẫn giữ dữ liệu lịch sử theo chính sách dữ liệu của hệ thống. |

### Ghi chú

- Camera trong phạm vi dự án được kết nối với hệ thống thông qua luồng RTSP.
- Việc không kết nối được RTSP tại thời điểm cấu hình không ngăn Admin lưu camera; camera được đánh dấu Offline/Chưa xác minh cho đến khi kết nối được kiểm tra thành công.
- Khi camera bị loại khỏi vận hành, hệ thống **không hard-delete dữ liệu lịch sử** đã được tạo từ camera đó.
- Các Person Embedding, frame toàn cảnh, bounding box, kết quả tìm kiếm đã lưu trong Case và metadata liên quan tiếp tục được giữ lại để bảo toàn lịch sử nghiệp vụ.
- Camera đã bị loại khỏi vận hành không tiếp tục tạo dữ liệu AI mới và không được chọn cho các truy vấn mới.
- Thông tin xác thực RTSP phải được lưu trữ an toàn và không hiển thị trực tiếp cho người dùng không có quyền quản trị.
- Camera cần có thông tin khu vực lắp đặt để đối chiếu với khu vực giám sát của Operator khi tìm kiếm; cách nhập và duy trì khu vực chưa được đặc tả.

---

## UC-04 – Quản lý xử lý AI trên camera

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-04 |
| **Tên use-case** | Quản lý xử lý AI trên camera |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin xác định camera nào được đưa vào quá trình phân tích AI bằng cách bật hoặc tắt xử lý AI cho từng camera. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền quản lý xử lý AI; camera cần cấu hình đã được thêm vào hệ thống và có cấu hình RTSP hợp lệ. |
| **Hậu điều kiện** | Trạng thái xử lý AI của camera được cập nhật theo lựa chọn của Admin; hệ thống khởi động hoặc dừng tiến trình xử lý AI tương ứng. |
| **Luồng chính** | 1. Admin truy cập chức năng quản lý xử lý AI trên camera.<br>2. Hệ thống hiển thị danh sách camera cùng trạng thái xử lý AI hiện tại.<br>3. Admin lựa chọn camera cần thay đổi trạng thái xử lý AI.<br>4. Admin bật hoặc tắt xử lý AI cho camera.<br>5. Admin xác nhận thay đổi.<br>6. Hệ thống kiểm tra trạng thái camera và cấu hình mô hình AI hiện hành.<br>7. Hệ thống lưu trạng thái xử lý AI mới.<br>8. Hệ thống khởi động hoặc dừng tiến trình xử lý AI tương ứng.<br>9. Hệ thống cập nhật trạng thái và thông báo kết quả cho Admin. |
| **Ngoại lệ** | **E1 – Camera không khả dụng:** Nếu camera đang mất kết nối hoặc luồng RTSP không thể truy cập khi Admin bật xử lý AI, hệ thống không khởi động tiến trình phân tích và thông báo cho Admin.<br><br>**E2 – Mô hình AI chưa sẵn sàng:** Nếu bộ mô hình AI hiện hành chưa được cấu hình đầy đủ hoặc không khả dụng, hệ thống không thể bật xử lý AI và thông báo cho Admin.<br><br>**E3 – Không thể khởi động tiến trình AI:** Nếu tiến trình xử lý AI không thể khởi động do lỗi tài nguyên hoặc lỗi thành phần xử lý, hệ thống giữ trạng thái không hoạt động và thông báo lỗi cho Admin.<br><br>**E4 – Camera không còn được vận hành:** Nếu camera đã bị loại khỏi vận hành, hệ thống không cho phép bật/tắt xử lý AI và thông báo không thể thực hiện thao tác.<br><br>**E5 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình lưu hoặc áp dụng thay đổi, hệ thống thông báo thao tác không thành công và giữ lại trạng thái hợp lệ gần nhất. |
| **Luồng thay thế** | **A1 – Bật xử lý AI cho camera:** Admin bật trạng thái xử lý AI. Hệ thống kiểm tra camera và bộ mô hình AI hiện hành, sau đó khởi động tiến trình phân tích nếu các điều kiện hợp lệ.<br><br>**A2 – Tắt xử lý AI cho camera:** Admin tắt trạng thái xử lý AI. Hệ thống dừng tiến trình phân tích của camera nhưng vẫn giữ thông tin camera và dữ liệu đã được phân tích trước đó. |

### Ghi chú

- Use case này chỉ quản lý trạng thái bật hoặc tắt xử lý AI cho từng camera.
- Việc lựa chọn Detector và Tracker được thực hiện trong UC-05 – Cấu hình mô hình AI. Image Encoder và Text Encoder là các thành phần cố định của hệ thống.
- Khi tắt xử lý AI, hệ thống ngừng tạo dữ liệu phân tích mới từ camera nhưng không mặc định xóa dữ liệu đã được tạo trước đó.
---

## UC-05 – Cấu hình mô hình AI

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-05 |
| **Tên use-case** | Cấu hình mô hình AI |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin lựa chọn và áp dụng các mô hình xử lý AI có thể cấu hình trong hệ thống, gồm Detector và Tracker. Image Encoder và Text Encoder là các thành phần cố định của hệ thống và không cho phép thay đổi từ giao diện quản trị. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền cấu hình mô hình AI; hệ thống đã đăng ký sẵn các Detector và Tracker được hỗ trợ. |
| **Hậu điều kiện** | Bộ mô hình AI được lựa chọn được lưu thành cấu hình hiện hành của hệ thống; các tiến trình xử lý AI sử dụng cấu hình mới sau khi cấu hình được áp dụng thành công. |
| **Luồng chính** | 1. Admin truy cập chức năng cấu hình mô hình AI.<br>2. Hệ thống hiển thị Detector và Tracker đang được sử dụng.<br>3. Hệ thống hiển thị danh sách các Detector và Tracker đã được đăng ký sẵn và được phép lựa chọn.<br>4. Admin lựa chọn Detector và/hoặc Tracker cần sử dụng.<br>5. Hệ thống kiểm tra tính hợp lệ và khả năng tương thích giữa Detector và Tracker được lựa chọn.<br>6. Admin xác nhận áp dụng cấu hình mới.<br>7. Hệ thống lưu cấu hình và cập nhật các tiến trình xử lý AI liên quan.<br>8. Hệ thống thông báo kết quả cho Admin. |
| **Ngoại lệ** | **E1 – Mô hình không khả dụng:** Nếu Detector hoặc Tracker được lựa chọn bị thiếu, không thể tải hoặc không ở trạng thái sẵn sàng, hệ thống từ chối áp dụng và thông báo cho Admin.<br><br>**E2 – Detector và Tracker không tương thích:** Nếu tổ hợp được lựa chọn không đáp ứng yêu cầu tương thích của pipeline, hệ thống không cho phép áp dụng và yêu cầu Admin lựa chọn cấu hình khác.<br><br>**E3 – Không thể áp dụng cấu hình:** Nếu xảy ra lỗi khi cập nhật mô hình cho tiến trình AI, hệ thống thông báo lỗi và tiếp tục sử dụng cấu hình hợp lệ trước đó.<br><br>**E4 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình đọc, lưu hoặc kiểm tra cấu hình, hệ thống thông báo thao tác không thành công. |
| **Luồng thay thế** | **A1 – Thay đổi Detector:** Admin lựa chọn Detector khác trong danh sách được hỗ trợ. Hệ thống kiểm tra tính tương thích với Tracker hiện tại trước khi cho phép áp dụng.<br><br>**A2 – Thay đổi Tracker:** Admin lựa chọn Tracker khác trong danh sách được hỗ trợ. Hệ thống kiểm tra tính tương thích với Detector hiện tại trước khi cho phép áp dụng.<br><br>**A3 – Thay đổi đồng thời Detector và Tracker:** Admin lựa chọn một cặp Detector và Tracker mới. Hệ thống kiểm tra tính tương thích của cặp mô hình trước khi áp dụng. |

### Ghi chú

- Admin chỉ được cấu hình **Detector** và **Tracker**.
- **Image Encoder** và **Text Encoder** là thành phần cố định của phiên bản hệ thống hiện tại và không được thay đổi từ giao diện quản trị.
- Detector và Tracker phục vụ Camera Processing Pipeline: `RTSP → Detector → Tracker → Image Encoder`.
- Image Encoder vẫn có hai vai trò cố định:
  - `Frame + Bounding Box → vùng người tạm thời → Image Encoder → Stored Person Embedding`
  - `Query Crop → Image Encoder → Query Embedding`
- Text Encoder cố định được sử dụng cho tìm kiếm bằng mô tả văn bản và câu mô tả được sinh từ bộ lọc thuộc tính.
- Use case này không bao gồm tải lên hoặc huấn luyện mô hình mới.
- Vùng người đưa vào Image Encoder chỉ được tạo tạm thời từ frame và bounding box trong quá trình xử lý; hệ thống không lưu person crop như một ảnh độc lập.

---

## UC-06 – Theo dõi trạng thái hệ thống

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-06 |
| **Tên use-case** | Theo dõi trạng thái hệ thống |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin theo dõi tình trạng hoạt động của các camera, luồng RTSP và các tiến trình xử lý AI nhằm kịp thời phát hiện các thành phần đang gặp sự cố hoặc không hoạt động bình thường. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền theo dõi trạng thái hệ thống; các camera và tiến trình AI liên quan đã được cấu hình trong hệ thống. |
| **Hậu điều kiện** | Admin nắm được trạng thái hoạt động hiện tại của các thành phần hệ thống; các trạng thái bất thường được hệ thống hiển thị để phục vụ việc kiểm tra và xử lý sự cố. |
| **Luồng chính** | 1. Admin truy cập chức năng theo dõi trạng thái hệ thống.<br>2. Hệ thống hiển thị danh sách các camera cùng trạng thái kết nối hiện tại.<br>3. Hệ thống hiển thị trạng thái luồng RTSP của từng camera.<br>4. Hệ thống hiển thị trạng thái tiến trình xử lý AI tương ứng với từng camera đang được bật phân tích.<br>5. Hệ thống hiển thị các thông tin kỹ thuật cần thiết để Admin đánh giá tình trạng hoạt động.<br>6. Admin theo dõi và xác định các camera hoặc tiến trình đang ở trạng thái bất thường.<br>7. Admin có thể làm mới dữ liệu trạng thái để kiểm tra lại tình trạng hiện tại.<br>8. Hệ thống cập nhật và hiển thị trạng thái mới nhất cho Admin. |
| **Ngoại lệ** | **E1 – Không lấy được trạng thái camera:** Nếu hệ thống không thể xác định trạng thái của một camera, trạng thái của camera được hiển thị là không xác định hoặc không khả dụng.<br><br>**E2 – Luồng RTSP bị gián đoạn:** Nếu luồng RTSP không thể truy cập hoặc bị mất kết nối, hệ thống hiển thị camera ở trạng thái lỗi kết nối.<br><br>**E3 – Tiến trình AI không hoạt động:** Nếu tiến trình AI của một camera bị dừng hoặc gặp lỗi, hệ thống hiển thị trạng thái xử lý AI bất thường để Admin nhận biết.<br><br>**E4 – Không thể tải dữ liệu trạng thái:** Nếu xảy ra lỗi khi lấy thông tin trạng thái hệ thống, hệ thống thông báo cho Admin và giữ lại dữ liệu gần nhất nếu có.<br><br>**E5 – Lỗi hệ thống:** Nếu thành phần giám sát trạng thái gặp lỗi, hệ thống thông báo không thể cung cấp đầy đủ thông tin tại thời điểm hiện tại. |
| **Luồng thay thế** | **A1 – Xem trạng thái theo camera:** Admin lựa chọn một camera cụ thể để xem chi tiết trạng thái kết nối RTSP và trạng thái tiến trình AI liên quan.<br><br>**A2 – Lọc theo trạng thái:** Admin lọc danh sách để chỉ hiển thị các camera hoặc tiến trình đang ở trạng thái lỗi, mất kết nối hoặc ngừng xử lý.<br><br>**A3 – Làm mới trạng thái:** Admin yêu cầu cập nhật lại trạng thái hệ thống; hệ thống thực hiện kiểm tra lại và hiển thị dữ liệu mới nhất. |

### Ghi chú

- Use case này tập trung vào việc quan sát và nhận biết trạng thái hoạt động của hệ thống, không bao gồm thao tác kiểm tra chi tiết chất lượng đầu ra của mô hình AI.
- Việc xác minh AI có tiếp nhận và xử lý hình ảnh đúng hay không thuộc UC-07 – Kiểm tra hoạt động của AI.
- Trạng thái hệ thống có thể bao gồm các mức như hoạt động bình thường, mất kết nối, ngừng xử lý, lỗi hoặc không xác định tùy theo thiết kế triển khai.

---

## UC-07 – Kiểm tra hoạt động của AI

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-07 |
| **Tên use-case** | Kiểm tra hoạt động của AI |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin kiểm tra độc lập hai nhóm thành phần AI của hệ thống: Camera Processing Pipeline và Search Components, nhằm xác minh từng nhóm đang hoạt động đúng theo cấu hình hiện tại. |
| **Tiền điều kiện** | Admin đã đăng nhập và có quyền kiểm tra hoạt động AI; các mô hình cần thiết đã được cấu hình. Đối với kiểm tra Camera Processing Pipeline, camera phải được cấu hình và bật xử lý AI. Đối với kiểm tra Search Components, không yêu cầu lựa chọn camera. |
| **Hậu điều kiện** | Admin nhận được kết quả kiểm tra cho biết pipeline AI đang hoạt động bình thường hoặc xác định được thành phần gặp lỗi để phục vụ quá trình xử lý sự cố. |
| **Luồng chính** | 1. Admin truy cập chức năng kiểm tra hoạt động của AI.<br>2. Hệ thống hiển thị hai nhóm kiểm tra: **Camera Processing Pipeline** và **Search Components**.<br>3. Admin lựa chọn nhóm cần kiểm tra.<br>4. Hệ thống thực hiện luồng kiểm tra tương ứng với nhóm được lựa chọn.<br>5. Hệ thống tổng hợp trạng thái của từng thành phần trong nhóm kiểm tra.<br>6. Hệ thống hiển thị kết quả cho Admin, bao gồm thành phần hoạt động bình thường và thành phần gặp lỗi. |
| **Ngoại lệ** | **E1 – Không nhận được khung hình từ camera:** Áp dụng khi kiểm tra Camera Processing Pipeline. Nếu hệ thống không lấy được dữ liệu từ RTSP, hệ thống thông báo lỗi nguồn dữ liệu và không tiếp tục các bước phụ thuộc vào frame.<br><br>**E2 – Detector không hoạt động:** Nếu Detector không thể được tải hoặc thực thi, hệ thống thông báo lỗi thành phần phát hiện.<br><br>**E3 – Tracker không hoạt động:** Nếu Tracker không thể khởi tạo hoặc xử lý dữ liệu từ Detector, hệ thống thông báo lỗi thành phần theo dõi.<br><br>**E4 – Image Encoder không hoạt động:** Nếu Image Encoder không thể được tải hoặc thực thi trong Camera Processing Pipeline hoặc Search Components, hệ thống thông báo lỗi tương ứng.<br><br>**E5 – Text Encoder không hoạt động:** Áp dụng khi kiểm tra Search Components. Nếu Text Encoder không thể được tải hoặc thực thi, hệ thống thông báo lỗi tương ứng.<br><br>**E6 – Không có người trong khung hình kiểm tra:** Nếu camera đang hoạt động nhưng khung hình hiện tại không chứa người, hệ thống thông báo chưa thể xác minh đầy đủ Detector/Tracker/Image Encoder nhưng không kết luận pipeline bị lỗi.<br><br>**E7 – Lỗi hệ thống:** Nếu xảy ra lỗi ngoài các trường hợp trên, hệ thống dừng kiểm tra và thông báo cho Admin. |
| **Luồng thay thế** | **A1 – Kiểm tra Camera Processing Pipeline:** Admin lựa chọn một camera đang bật xử lý AI. Hệ thống lần lượt kiểm tra khả năng nhận dữ liệu RTSP, Detector, Tracker và Image Encoder theo luồng `RTSP → Detector → Tracker → Image Encoder`. Kết quả được hiển thị theo từng thành phần.<br><br>**A2 – Kiểm tra Search Components:** Admin không cần lựa chọn camera. Hệ thống kiểm tra khả năng tải và thực thi của Image Encoder và Text Encoder bằng dữ liệu kiểm tra phù hợp, sau đó hiển thị trạng thái của từng encoder.<br><br>**A3 – Kiểm tra lại sau khi thay đổi Detector/Tracker hoặc cấu hình camera:** Admin thực hiện lại **A1 – Kiểm tra Camera Processing Pipeline** để xác nhận hệ thống hoạt động đúng với cấu hình mới. A2 chỉ được dùng khi Admin muốn kiểm tra độc lập Search Components. |

### Ghi chú

- UC-07 phục vụ mục đích kỹ thuật và chẩn đoán, không phải chức năng tìm kiếm người của Operator.
- **Camera Processing Pipeline:** `RTSP → Detector → Tracker → Image Encoder`.
- **Search Components:** `Image Encoder` và `Text Encoder`.
- Text Encoder không phụ thuộc camera, vì vậy việc kiểm tra Search Components không yêu cầu Admin chọn camera.
- Image Encoder xuất hiện ở cả hai nhóm vì trong pipeline camera nó nhận vùng người được tạo tạm thời từ frame + bounding box để sinh Person Embedding, còn trong tìm kiếm bằng ảnh nó tạo Query Embedding từ ảnh truy vấn do Operator cung cấp.
- Kết quả kiểm tra chỉ phản ánh trạng thái hoạt động của thành phần, không dùng để đánh giá độ chính xác của mô hình AI.

---

## UC-08 – Xem nhật ký hệ thống

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-08 |
| **Tên use-case** | Xem nhật ký hệ thống |
| **Actors** | Admin |
| **Mục đích** | Cho phép Admin xem và tra cứu audit log của các thao tác quản trị và sự kiện kỹ thuật quan trọng trong hệ thống để phục vụ kiểm tra, truy vết và bảo trì. |
| **Tiền điều kiện** | Admin đã đăng nhập vào hệ thống và có quyền xem nhật ký hệ thống; hệ thống đã ghi nhận dữ liệu nhật ký. |
| **Hậu điều kiện** | Admin xem được các bản ghi nhật ký phù hợp với điều kiện tra cứu; không làm thay đổi dữ liệu hoặc trạng thái vận hành của hệ thống. |
| **Luồng chính** | 1. Admin truy cập chức năng xem nhật ký hệ thống.<br>2. Hệ thống hiển thị danh sách các bản ghi nhật ký gần nhất.<br>3. Admin thiết lập các điều kiện tra cứu nếu cần, chẳng hạn khoảng thời gian, loại sự kiện, người dùng hoặc thành phần hệ thống.<br>4. Admin gửi yêu cầu tra cứu.<br>5. Hệ thống kiểm tra các điều kiện tìm kiếm.<br>6. Hệ thống truy xuất các bản ghi nhật ký phù hợp.<br>7. Hệ thống hiển thị danh sách kết quả theo thứ tự thời gian.<br>8. Admin lựa chọn một bản ghi để xem thông tin chi tiết khi cần.<br>9. Hệ thống hiển thị nội dung chi tiết của bản ghi được lựa chọn. |
| **Ngoại lệ** | **E1 – Không có dữ liệu phù hợp:** Nếu không có bản ghi nào thỏa mãn điều kiện tra cứu, hệ thống thông báo không tìm thấy dữ liệu.<br><br>**E2 – Điều kiện tra cứu không hợp lệ:** Nếu khoảng thời gian hoặc tham số lọc không hợp lệ, hệ thống yêu cầu Admin điều chỉnh lại điều kiện.<br><br>**E3 – Không thể truy xuất nhật ký:** Nếu hệ thống không thể đọc dữ liệu nhật ký tại thời điểm tra cứu, hệ thống thông báo thao tác không thành công.<br><br>**E4 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình tải hoặc hiển thị dữ liệu, hệ thống thông báo cho Admin và không làm thay đổi dữ liệu nhật ký hiện có. |
| **Luồng thay thế** | **A1 – Lọc theo người dùng:** Admin lựa chọn một người dùng cụ thể để xem các thao tác của tài khoản đã được hệ thống ghi nhận trong audit log.<br><br>**A2 – Lọc theo loại sự kiện:** Admin lựa chọn loại sự kiện như đăng nhập, quản lý tài khoản, thay đổi cấu hình camera, thay đổi cấu hình AI hoặc lỗi hệ thống để thu hẹp kết quả.<br><br>**A3 – Lọc theo khoảng thời gian:** Admin chỉ định khoảng thời gian cần kiểm tra; hệ thống chỉ trả về các bản ghi phát sinh trong khoảng thời gian đó.<br><br>**A4 – Xem chi tiết sự kiện:** Admin lựa chọn một bản ghi trong danh sách để xem các thông tin chi tiết như thời gian, người thực hiện, hành động, đối tượng bị tác động và trạng thái kết quả. |

### Ghi chú

- Audit log tối thiểu ghi nhận các nhóm sự kiện sau:
  - đăng nhập/đăng xuất và đăng nhập thất bại;
  - tạo, cập nhật, khóa/mở khóa, ngừng hoạt động hoặc xóa tài khoản;
  - thay đổi vai trò hoặc khu vực giám sát của Operator;
  - thêm, cập nhật, kiểm tra kết nối hoặc loại camera khỏi vận hành;
  - bật/tắt xử lý AI trên camera;
  - thay đổi Detector hoặc Tracker;
  - thao tác tạo hoặc cập nhật Case;
  - lỗi kỹ thuật quan trọng liên quan đến RTSP hoặc pipeline AI.
- Audit log chỉ phục vụ tra cứu và không được chỉnh sửa trực tiếp qua giao diện quản trị.
- Mỗi bản ghi log nên lưu tối thiểu thời gian, người thực hiện, loại sự kiện, đối tượng bị tác động và kết quả thao tác.
- Thao tác tìm kiếm người của Operator không được ghi nhận trong audit log của phiên bản hiện tại.

---

## UC-09 – Tìm kiếm người bằng AI

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-09 |
| **Tên use-case** | Tìm kiếm người bằng AI |
| **Actors** | Operator |
| **Mục đích** | Cho phép Operator tìm kiếm một người xuất hiện trong dữ liệu đã được hệ thống AI phân tích bằng ba phương thức tương tác: ảnh crop chứa người do Operator tải lên, mô tả bằng văn bản hoặc bộ lọc thuộc tính ngoại hình. Phạm vi tìm kiếm được hệ thống tự động giới hạn theo **khu vực giám sát** đã được gán cho tài khoản Operator; Operator chỉ có thể lọc thêm theo các camera thuộc khu vực giám sát đó và khoảng thời gian. |
| **Tiền điều kiện** | Operator đã đăng nhập vào hệ thống và có quyền sử dụng chức năng tìm kiếm; tài khoản Operator đã được Admin gán đúng một khu vực giám sát; hệ thống đã có dữ liệu người được phân tích từ ít nhất một camera thuộc khu vực giám sát được gán cho Operator; các thành phần AI cần thiết cho phương thức tìm kiếm đang ở trạng thái khả dụng. |
| **Hậu điều kiện** | Hệ thống trả về tối đa số lượng kết quả Operator chọn (`top_k`) có mức phù hợp cao nhất trong phạm vi tìm kiếm hợp lệ, sắp xếp theo **Điểm phù hợp (Matching Score)** để Operator tự quan sát và đánh giá. |
| **Luồng chính** | 1. Operator truy cập chức năng tìm kiếm người.<br>2. Hệ thống hiển thị giao diện tìm kiếm và các phương thức tìm kiếm được hỗ trợ.<br>3. Operator lựa chọn một phương thức tìm kiếm và cung cấp thông tin về người cần tìm.<br>4. Hệ thống tự động giới hạn phạm vi tìm kiếm theo khu vực đã gán cho tài khoản; Operator có thể tiếp tục lọc theo camera thuộc khu vực giám sát đó hoặc khoảng thời gian nếu cần.<br>5. Operator chọn số lượng kết quả muốn hiển thị (`top_k`) và gửi yêu cầu tìm kiếm.<br>6. Hệ thống kiểm tra tính hợp lệ của dữ liệu truy vấn và `top_k`, rồi chỉ thực hiện tìm kiếm trên các camera thuộc khu vực giám sát đã gán cho tài khoản Operator.<br>7. Hệ thống xử lý truy vấn bằng Image Encoder đối với tìm kiếm bằng ảnh hoặc Text Encoder đối với tìm kiếm bằng văn bản và tìm kiếm thông qua bộ lọc thuộc tính.<br>8. Hệ thống so sánh truy vấn với dữ liệu người đã được phân tích và lưu trữ.<br>9. Hệ thống tính toán **Điểm phù hợp (Matching Score)** giữa truy vấn và các dữ liệu trong phạm vi tìm kiếm.<br>10. Hệ thống sắp xếp kết quả theo Điểm phù hợp từ cao xuống thấp.<br>11. Hệ thống lấy tối đa `top_k` kết quả có Điểm phù hợp cao nhất trong phạm vi hợp lệ.<br>12. Hệ thống hiển thị ban đầu ảnh người được crop động từ frame toàn cảnh và bounding box cho từng kết quả, cùng thông tin camera, khu vực, thời gian và Điểm phù hợp để Operator quan sát và đánh giá. |
| **Ngoại lệ** | **E1 – Dữ liệu truy vấn không hợp lệ:** Nếu ảnh, văn bản hoặc thuộc tính được cung cấp không hợp lệ, hệ thống thông báo và yêu cầu Operator điều chỉnh dữ liệu đầu vào.<br><br>**E2 – Không có dữ liệu trong phạm vi tìm kiếm:** Nếu không có dữ liệu đã được phân tích trong camera được chọn hoặc khoảng thời gian được lựa chọn trong khu vực của Operator, hệ thống thông báo không có dữ liệu phù hợp để thực hiện tìm kiếm.<br><br>**E3 – Mô hình AI cần thiết không khả dụng:** Nếu Image Encoder, Text Encoder hoặc thành phần liên quan đến phương thức tìm kiếm không hoạt động, hệ thống thông báo không thể thực hiện truy vấn tại thời điểm hiện tại.<br><br>**E4 – Không có dữ liệu có thể truy vấn:** Nếu phạm vi tìm kiếm hợp lệ nhưng không có Person Embedding khả dụng để thực hiện so sánh, hệ thống thông báo không có dữ liệu để trả kết quả.<br><br>**E5 – Lỗi xử lý truy vấn:** Nếu xảy ra lỗi trong quá trình tạo đặc trưng, truy vấn dữ liệu hoặc xếp hạng kết quả, hệ thống thông báo tìm kiếm không thành công.<br><br>**E6 – Yêu cầu ngoài phạm vi khu vực:** Nếu request trực tiếp chứa camera không thuộc khu vực giám sát đã gán cho Operator, backend từ chối truy vấn ngoài quyền và không trả về dữ liệu ngoài khu vực.<br><br>**E7 – Số lượng kết quả không hợp lệ:** Nếu `top_k` không phải số nguyên dương hoặc vượt giới hạn hợp lệ của hệ thống, backend từ chối yêu cầu và yêu cầu Operator chọn lại. Giá trị tối đa cụ thể chưa được quy định. |
| **Luồng thay thế** | **A1 – Tìm kiếm bằng hình ảnh:** Operator chọn phương thức tìm kiếm bằng hình ảnh và tải lên ảnh đã crop chứa người cần tìm. Hệ thống kiểm tra ảnh đầu vào, sử dụng Image Encoder để trích xuất đặc trưng hình ảnh và sử dụng đặc trưng này làm truy vấn tìm kiếm.<br><br>**A2 – Tìm kiếm bằng mô tả văn bản:** Operator chọn phương thức tìm kiếm bằng văn bản và nhập câu hoặc đoạn mô tả đặc điểm của người cần tìm, ví dụ “người mặc áo đỏ, quần đen, mang ba lô”. Hệ thống sử dụng Text Encoder để mã hóa nội dung mô tả và sử dụng biểu diễn thu được làm truy vấn tìm kiếm.<br><br>**A3 – Tìm kiếm theo thuộc tính:** Operator chọn phương thức tìm kiếm theo thuộc tính và thiết lập các thuộc tính được hệ thống hỗ trợ như màu áo, màu quần, loại trang phục hoặc có mang ba lô. Hệ thống chuyển các thuộc tính đã lựa chọn thành một câu mô tả văn bản có cấu trúc. Câu mô tả này được đưa vào Text Encoder để tạo biểu diễn truy vấn và thực hiện tìm kiếm tương tự phương thức tìm kiếm bằng mô tả văn bản.<br><br>**A4 – Tìm kiếm với phạm vi giới hạn:** Operator kết hợp phương thức tìm kiếm với một hoặc nhiều camera thuộc khu vực giám sát của tài khoản và khoảng thời gian. Hệ thống chỉ thực hiện tìm kiếm trong phạm vi này. |

### Ghi chú

- Ba phương thức tìm kiếm bằng hình ảnh, mô tả văn bản và thuộc tính là ba cách tương tác của người dùng trong cùng một use case, không được tách thành các use case độc lập.
- Bộ lọc thuộc tính chỉ là UX helper/prompt builder. Hệ thống không sử dụng mô hình thuộc tính hoặc cơ chế tìm kiếm riêng cho phương thức này; các thuộc tính được chuyển thành câu mô tả và xử lý bằng Text Encoder.
- Trong phạm vi phiên bản ban đầu, hệ thống chỉ hỗ trợ tìm kiếm người và chưa bao gồm tìm kiếm phương tiện hoặc các loại đối tượng khác.
- Kết quả tìm kiếm ban đầu hiển thị ảnh người crop động từ **frame toàn cảnh + bounding box**, cùng camera phát hiện, khu vực, thời điểm xuất hiện và Điểm phù hợp. Khi bấm vào ảnh, hệ thống hiển thị frame toàn cảnh và vẽ bounding box của người trên frame.
- Việc xem và đánh giá chi tiết các kết quả tìm kiếm thuộc UC-10 – Xem và đánh giá kết quả tìm kiếm.
- Điểm phù hợp chỉ là thông tin hỗ trợ xếp hạng và đánh giá kết quả; người dùng vẫn cần quan sát ảnh để xác định kết quả phù hợp và hệ thống không xem điểm này là kết luận chắc chắn về danh tính.
- Một **kết quả tìm kiếm** đại diện cho **một lần xuất hiện/track của một người trên một camera**, không phải một frame riêng lẻ.
- Mỗi track lưu một frame toàn cảnh đại diện, bounding box của người trên frame đó và các metadata như camera, khu vực, thời gian xuất hiện. Khi hiển thị, hệ thống dùng frame + bounding box để tạo ảnh người; không lưu person crop riêng.
- Việc gom dữ liệu theo track giúp tránh trả về nhiều kết quả lặp lại cho cùng một người trong các frame liên tiếp.
- Backend phải bắt buộc kiểm tra và enforce khu vực giám sát của Operator ở mọi yêu cầu tìm kiếm; không được chỉ dựa vào việc ẩn camera/khu vực trên giao diện.
- Operator không được truy vấn dữ liệu từ camera ngoài khu vực đã được gán cho tài khoản, kể cả khi cố tình gửi request trực tiếp tới API.
- Phiên bản hiện tại **không sử dụng ngưỡng Matching Score để loại kết quả**. Operator chọn `top_k` khi tìm kiếm; backend kiểm tra số nguyên dương và giới hạn hợp lệ rồi trả tối đa `top_k` kết quả có điểm cao nhất để Operator tự đánh giá bằng mắt. Giới hạn tối đa cụ thể chưa được quy định.
- **Điểm phù hợp chỉ dùng để xếp hạng và hỗ trợ đánh giá**, không được xem là kết luận rằng kết quả chắc chắn là cùng một người.
- Toàn bộ kết quả trả về phải thuộc các camera nằm trong khu vực giám sát được gán cho Operator. Dữ liệu ngoài khu vực này không được hiển thị hoặc trả về qua API.
- Sau khi có kết quả tìm kiếm, Operator có thể chọn một kết quả để **tạo Case mới** hoặc **thêm kết quả vào một Case đã có** trong UC-11 – Quản lý hồ sơ vụ việc.
- Hệ thống không lưu ảnh crop của kết quả tìm kiếm. Dữ liệu hình ảnh được lưu là **frame toàn cảnh** và **bounding box**; ảnh người chỉ được tạo khi cần hiển thị.

---

## UC-10 – Xem và đánh giá kết quả tìm kiếm

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-10 |
| **Tên use-case** | Xem và đánh giá kết quả tìm kiếm |
| **Actors** | Operator |
| **Mục đích** | Cho phép Operator xem chi tiết các kết quả do hệ thống trả về sau khi tìm kiếm người bằng AI, đánh giá mức độ phù hợp của từng kết quả và xác định các kết quả liên quan đến người cần tìm. |
| **Tiền điều kiện** | Operator đã đăng nhập vào hệ thống; Operator đã thực hiện UC-09 – Tìm kiếm người bằng AI và hệ thống đã trả về ít nhất một kết quả tìm kiếm. |
| **Hậu điều kiện** | Operator đã xem và đánh giá kết quả; đối với kết quả muốn lưu lại, Operator có thể tạo Case mới hoặc thêm kết quả vào một Case đã có. Dữ liệu kết quả gốc không bị thay đổi. |
| **Luồng chính** | 1. Hệ thống hiển thị danh sách kết quả sau khi hoàn tất tìm kiếm.<br>2. Operator xem các thông tin tổng quan của từng kết quả, bao gồm ảnh người được crop động từ frame toàn cảnh và bounding box, camera phát hiện, khu vực, thời gian xuất hiện và Điểm phù hợp.<br>3. Operator bấm vào ảnh người của một kết quả cần xem chi tiết.<br>4. Hệ thống hiển thị frame toàn cảnh đại diện của kết quả và vẽ bounding box của người trên frame, cùng các thông tin chi tiết của kết quả.<br>5. Operator đối chiếu ảnh và các thông tin của kết quả với tiêu chí tìm kiếm ban đầu.<br>6. Operator đánh giá kết quả có phù hợp với người cần tìm hay không.<br>7. Operator có thể tiếp tục xem các kết quả khác trong danh sách để so sánh.<br>8. Operator xác định một hoặc nhiều kết quả phù hợp để sử dụng cho bước xử lý tiếp theo.<br>9. Với một kết quả muốn lưu, Operator lựa chọn **Tạo Case mới** hoặc **Thêm vào Case đã có**.<br>10. Hệ thống chuyển sang luồng tương ứng của UC-11 – Quản lý hồ sơ vụ việc. |
| **Ngoại lệ** | **E1 – Kết quả không còn khả dụng:** Nếu dữ liệu của một kết quả không thể truy xuất hoặc đã bị loại bỏ theo chính sách lưu trữ, hệ thống thông báo kết quả không còn khả dụng.<br><br>**E2 – Không thể dựng ảnh kết quả:** Nếu frame toàn cảnh hoặc bounding box của kết quả không còn khả dụng, hệ thống vẫn hiển thị các metadata còn lại và thông báo không thể dựng ảnh người.<br><br>**E3 – Lỗi tải dữ liệu:** Nếu xảy ra lỗi khi truy xuất thông tin chi tiết của kết quả, hệ thống thông báo và cho phép Operator thử lại. |
| **Luồng thay thế** | **A1 – Sắp xếp kết quả:** Operator thay đổi cách sắp xếp danh sách theo điểm phù hợp hoặc thời gian xuất hiện để thuận tiện cho việc đánh giá.<br><br>**A2 – Lọc lại danh sách kết quả:** Operator áp dụng thêm các điều kiện lọc trên tập kết quả hiện tại, chẳng hạn camera hoặc khoảng thời gian, để thu hẹp danh sách cần xem.<br><br>**A3 – Tạo Case mới từ kết quả:** Operator chọn một kết quả và chọn **Tạo Case mới**. Hệ thống chuyển sang UC-11 với kết quả đó được chọn sẵn để đưa vào Case mới.<br><br>**A4 – Thêm kết quả vào Case đã có:** Operator chọn một kết quả và chọn **Thêm vào Case đã có**. Hệ thống chỉ hiển thị các Case do chính Operator hiện tại phụ trách và chuyển sang UC-11 sau khi Operator chọn Case. |

### Ghi chú

- Use case này bắt đầu sau khi UC-09 – Tìm kiếm người bằng AI đã trả về kết quả.
- Việc đánh giá kết quả là quyết định nghiệp vụ của Operator; danh sách ban đầu hiển thị ảnh người crop động từ frame và bounding box. Khi bấm vào ảnh, hệ thống hiển thị full frame kèm bounding box được vẽ lên để cung cấp ngữ cảnh; thông tin camera, thời gian xuất hiện và điểm phù hợp cũng hỗ trợ đánh giá.
- Operator không được chỉnh sửa trực tiếp dữ liệu AI gốc của một kết quả tìm kiếm.
- Với một kết quả được chọn, Operator có thể tạo Case mới hoặc thêm kết quả vào Case đã có trong UC-11 – Quản lý hồ sơ vụ việc.
- Mỗi kết quả tương ứng với một track/lần xuất hiện của một người trên một camera, lưu frame toàn cảnh đại diện và bounding box; hệ thống không tạo một kết quả riêng cho từng frame của cùng track.
- Điểm phù hợp không phải là quyết định tự động của hệ thống; Operator chịu trách nhiệm quan sát ảnh và thông tin liên quan để xác định kết quả nào thực sự phù hợp.

---

## UC-11 – Quản lý hồ sơ vụ việc

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-11 |
| **Tên use-case** | Quản lý hồ sơ vụ việc |
| **Actors** | Operator |
| **Mục đích** | Cho phép Operator tạo và quản lý các Case do chính mình phụ trách để lưu các kết quả tìm kiếm liên quan đến một sự việc, kèm theo tiêu đề và ghi chú. |
| **Tiền điều kiện** | Operator đã đăng nhập. Đối với thao tác thêm kết quả, kết quả phải là dữ liệu mà Operator có quyền truy cập từ chức năng tìm kiếm. |
| **Hậu điều kiện** | Case được tạo hoặc cập nhật, có đúng một Operator phụ trách và gồm ba loại nội dung nghiệp vụ chính: **tiêu đề**, **ghi chú** và **các kết quả tìm kiếm đã lưu**. |
| **Luồng chính** | 1. Operator thực hiện tìm kiếm và chọn một kết quả muốn lưu.<br>2. Hệ thống cung cấp hai lựa chọn: **Tạo Case mới** hoặc **Thêm vào Case đã có**.<br>3. Nếu Operator chọn **Tạo Case mới**, hệ thống yêu cầu nhập tiêu đề và ghi chú; kết quả đang chọn được đưa vào Case mới; hệ thống tự động lấy Operator đang đăng nhập làm người phụ trách Case, không yêu cầu chọn người phụ trách.<br>4. Nếu Operator chọn **Thêm vào Case đã có**, hệ thống chỉ hiển thị các Case do chính Operator hiện tại phụ trách.<br>5. Operator chọn một Case; hệ thống thêm kết quả tìm kiếm đang chọn vào Case đó.<br>6. Operator có thể tiếp tục thêm các kết quả tìm kiếm khác vào Case trong các lần tìm kiếm tiếp theo.<br>7. Operator có thể cập nhật tiêu đề hoặc ghi chú của Case.<br>8. Hệ thống lưu thay đổi. |
| **Ngoại lệ** | **E1 – Kết quả không còn khả dụng:** Nếu kết quả được chọn không thể truy xuất tại thời điểm lưu vào Case, hệ thống thông báo và không thêm kết quả đó.<br><br>**E2 – Kết quả ngoài quyền truy cập:** Nếu request trực tiếp cố thêm một kết quả mà Operator không có quyền truy cập, hệ thống từ chối thao tác.<br><br>**E3 – Case không còn khả dụng:** Nếu Case được chọn không thể truy xuất tại thời điểm thêm kết quả hoặc cập nhật, hệ thống thông báo và tải lại danh sách các Case do Operator hiện tại phụ trách.<br><br>**E4 – Lỗi lưu dữ liệu:** Nếu xảy ra lỗi khi tạo hoặc cập nhật Case, hệ thống thông báo thao tác không thành công và không ghi nhận thay đổi chưa hoàn tất. |
| **Luồng thay thế** | **A1 – Tạo Case mới từ kết quả tìm kiếm:** Operator chọn **Tạo Case mới**, nhập tiêu đề và ghi chú. Hệ thống tạo Case, tự động lấy Operator đang đăng nhập làm người phụ trách và lưu kết quả đang chọn vào Case; không cho phép chỉ định người phụ trách khác qua biểu mẫu hoặc request.<br><br>**A2 – Thêm kết quả vào Case đã có:** Operator chọn **Thêm vào Case đã có**; hệ thống chỉ hiển thị các Case do chính Operator hiện tại phụ trách. Operator chọn một Case và hệ thống thêm kết quả đang chọn vào Case đó.<br><br>**A3 – Cập nhật Case:** Operator thay đổi tiêu đề hoặc ghi chú của Case và lưu lại.<br><br>**A4 – Loại kết quả khỏi Case:** Operator loại bỏ một kết quả tìm kiếm khỏi Case. Dữ liệu kết quả gốc trong hệ thống không bị xóa. |

### Ghi chú

- Case không có trạng thái xử lý.
- Case không gắn với khu vực.
- Mỗi Case do **một Operator** quản lý; khi tạo Case, hệ thống tự động gán Operator đang đăng nhập làm owner dựa trên phiên xác thực. Khi thêm vào Case đã có, Operator chỉ nhìn thấy và có quyền thao tác trên các Case do chính mình quản lý.
- Nội dung nghiệp vụ của Case gồm **tiêu đề**, **ghi chú** và **các kết quả tìm kiếm đã lưu**.
- Mỗi kết quả tìm kiếm giữ tham chiếu tới **frame toàn cảnh, bounding box và metadata** của lần xuất hiện; hệ thống không lưu person crop riêng trong Case.
- Khi hiển thị danh sách kết quả trong Case, hệ thống crop động ảnh người từ frame toàn cảnh và bounding box; khi bấm vào ảnh, hệ thống hiển thị full frame và vẽ bounding box của người trên đó.
- Một Case có thể chứa nhiều kết quả tìm kiếm khác nhau.
- Khu vực chỉ được dùng để giới hạn dữ liệu tìm kiếm mà Operator có quyền truy cập; không dùng để ràng buộc Case.
- Dữ liệu kết quả gốc không bị thay đổi khi được thêm vào hoặc loại khỏi Case.
- Viewer (Manager/Director) có thể xem toàn bộ Case nhưng không được chỉnh sửa.
- Mỗi Case có đúng **một Operator phụ trách**.
- Operator chỉ được xem và quản lý các Case do chính mình phụ trách.
- Phiên bản hiện tại không hỗ trợ chuyển quyền phụ trách Case sang Operator khác.
- Nếu tài khoản Operator phụ trách Case bị khóa, xóa hoặc ngừng hoạt động, Case vẫn được giữ nguyên cùng thông tin Operator phụ trách; Viewer vẫn có thể xem Case.

---

## UC-12 – Xem thông tin tổng quan

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-12 |
| **Tên use-case** | Xem thông tin tổng quan |
| **Actors** | Viewer |
| **Mục đích** | Cho phép Viewer, với vai trò là Manager hoặc Director, xem nhanh thông tin tổng quan về các Case và kết quả đã được lưu trên toàn hệ thống mà không thực hiện thao tác tìm kiếm hoặc chỉnh sửa dữ liệu. |
| **Tiền điều kiện** | Viewer đã đăng nhập vào hệ thống và có quyền truy cập giao diện tổng quan. |
| **Hậu điều kiện** | Viewer xem được các chỉ số tổng quan và danh sách Case gần đây trên toàn hệ thống; không có dữ liệu nào bị thay đổi sau khi thực hiện use case. |
| **Luồng chính** | 1. Viewer truy cập giao diện tổng quan của hệ thống.<br>2. Hệ thống tổng hợp dữ liệu Case và kết quả đã lưu trên toàn hệ thống.<br>3. Hệ thống hiển thị tổng số Case.<br>4. Hệ thống hiển thị tổng số kết quả tìm kiếm đã được lưu vào Case.<br>5. Hệ thống hiển thị danh sách các Case gần đây, bao gồm tối thiểu tiêu đề Case, Operator phụ trách và thời gian cập nhật gần nhất.<br>6. Viewer lựa chọn một Case trong danh sách gần đây nếu muốn xem chi tiết.<br>7. Hệ thống chuyển sang UC-13 – Xem hồ sơ vụ việc. |
| **Ngoại lệ** | **E1 – Chưa có dữ liệu Case:** Nếu hệ thống chưa có Case nào, các chỉ số được hiển thị bằng 0 và danh sách Case gần đây hiển thị trạng thái không có dữ liệu.<br><br>**E2 – Không thể tải dữ liệu tổng quan:** Nếu hệ thống gặp lỗi khi tổng hợp hoặc truy xuất dữ liệu, hệ thống thông báo không thể tải thông tin tại thời điểm hiện tại và không làm thay đổi dữ liệu.<br><br>**E3 – Case trong danh sách gần đây không thể truy xuất:** Nếu Case không thể truy xuất khi Viewer lựa chọn, hệ thống thông báo không thể mở Case tại thời điểm hiện tại và tải lại danh sách. |
| **Luồng thay thế** | **A1 – Xem Case gần đây:** Viewer lựa chọn một Case trong danh sách Case gần đây; hệ thống chuyển sang UC-13 – Xem hồ sơ vụ việc.<br><br>**A2 – Làm mới dữ liệu tổng quan:** Viewer yêu cầu làm mới; hệ thống tổng hợp lại các chỉ số và danh sách Case gần đây từ dữ liệu hiện tại. |

### Ghi chú

- Dashboard của Viewer hiển thị dữ liệu trên toàn hệ thống.
- Bộ chỉ số tối thiểu gồm: **tổng số Case, tổng số kết quả đã lưu và danh sách Case gần đây**.
- Use case này chỉ phục vụ mục đích tổng quan và điều hướng; Viewer không được tìm kiếm AI, tạo Case hoặc chỉnh sửa dữ liệu.

---

## UC-13 – Xem hồ sơ vụ việc

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-13 |
| **Tên use-case** | Xem hồ sơ vụ việc |
| **Actors** | Viewer |
| **Mục đích** | Cho phép Viewer, với vai trò là Manager hoặc Director, xem các hồ sơ vụ việc (Case) đã được Operator tạo, bao gồm tiêu đề, ghi chú và các kết quả tìm kiếm đã được lưu trong hồ sơ. |
| **Tiền điều kiện** | Viewer đã đăng nhập vào hệ thống và có quyền xem hồ sơ vụ việc. |
| **Hậu điều kiện** | Viewer xem được thông tin chi tiết của Case và các kết quả liên quan; không có dữ liệu nào bị thay đổi sau khi thực hiện use case. |
| **Luồng chính** | 1. Viewer truy cập chức năng xem hồ sơ vụ việc.<br>2. Hệ thống hiển thị danh sách các Case hiện có trong hệ thống.<br>3. Viewer lựa chọn một Case cần xem.<br>4. Hệ thống hiển thị thông tin chi tiết của Case, bao gồm tiêu đề, ghi chú, Operator phụ trách và thời gian tạo.<br>5. Hệ thống hiển thị danh sách các kết quả tìm kiếm đã được lưu trong Case.<br>6. Viewer xem nội dung Case và các kết quả liên quan.<br>7. Viewer có thể lựa chọn một kết quả để xem chi tiết nếu cần. |
| **Ngoại lệ** | **E1 – Không có Case khả dụng:** Nếu hệ thống chưa có Case nào, hệ thống hiển thị trạng thái không có dữ liệu.<br><br>**E2 – Case không thể truy xuất:** Nếu Case không thể truy xuất tại thời điểm yêu cầu, hệ thống thông báo không thể hiển thị hồ sơ.<br><br>**E3 – Không thể tải dữ liệu Case:** Nếu xảy ra lỗi khi truy xuất thông tin Case hoặc danh sách kết quả liên quan, hệ thống thông báo cho Viewer và cho phép thử lại.<br><br>**E4 – Một số kết quả trong Case không còn khả dụng:** Hệ thống vẫn hiển thị Case và các dữ liệu còn lại, đồng thời đánh dấu những kết quả không thể truy xuất. |
| **Luồng thay thế** | **A1 – Xem Case từ màn hình tổng quan:** Viewer lựa chọn một Case được hiển thị trong UC-12 – Xem thông tin tổng quan; hệ thống mở trực tiếp nội dung chi tiết của Case.<br><br>**A2 – Xem chi tiết kết quả trong Case:** Viewer lựa chọn một kết quả đã được lưu trong Case; hệ thống chuyển sang UC-14 – Xem thông tin kết quả tìm kiếm đã lưu.<br><br>**A3 – Lọc danh sách Case:** Viewer lọc danh sách Case theo khoảng thời gian hoặc Operator phụ trách để dễ tra cứu. |

### Ghi chú

- Viewer chỉ có quyền xem Case và không được thay đổi tiêu đề, ghi chú hoặc danh sách kết quả đã lưu.
- Nội dung Case được tạo và quản lý bởi Operator trong UC-11 – Quản lý hồ sơ vụ việc.
- Viewer được định nghĩa là Manager hoặc Director và có quyền xem toàn bộ Case trong hệ thống. Viewer chỉ có quyền đọc và không được thay đổi nội dung Case.

---

## UC-14 – Xem thông tin kết quả tìm kiếm đã lưu

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-14 |
| **Tên use-case** | Xem thông tin kết quả tìm kiếm đã lưu |
| **Actors** | Viewer |
| **Mục đích** | Cho phép Viewer xem chi tiết các kết quả tìm kiếm đã được Operator lựa chọn và lưu vào Case, bao gồm ảnh người được dựng từ frame toàn cảnh và bounding box, camera phát hiện, khu vực, thời gian xuất hiện và Điểm phù hợp của kết quả. |
| **Tiền điều kiện** | Viewer đã đăng nhập vào hệ thống; kết quả tìm kiếm đã được Operator lưu vào một Case. |
| **Hậu điều kiện** | Viewer xem được thông tin chi tiết của kết quả tìm kiếm đã lưu; dữ liệu kết quả không bị thay đổi sau khi thực hiện use case. |
| **Luồng chính** | 1. Viewer mở một Case trong UC-13 – Xem hồ sơ vụ việc.<br>2. Hệ thống hiển thị danh sách các kết quả tìm kiếm đã được lưu trong Case.<br>3. Viewer lựa chọn một kết quả cần xem chi tiết.<br>4. Hệ thống truy xuất thông tin chi tiết của kết quả được lựa chọn.<br>5. Hệ thống hiển thị ảnh người crop động từ frame toàn cảnh và bounding box, tên camera, khu vực, thời gian phát hiện và Điểm phù hợp.<br>6. Khi Viewer bấm vào ảnh người, hệ thống hiển thị frame toàn cảnh và vẽ bounding box của người trên frame; Viewer xem thông tin chi tiết của kết quả.<br>7. Viewer có thể quay lại Case để tiếp tục xem các kết quả khác. |
| **Ngoại lệ** | **E1 – Kết quả không còn khả dụng:** Nếu kết quả đã bị loại bỏ hoặc dữ liệu tương ứng không còn tồn tại, hệ thống thông báo không thể hiển thị kết quả.<br><br>**E2 – Không thể dựng ảnh người:** Nếu frame toàn cảnh hoặc bounding box không còn khả dụng, hệ thống vẫn hiển thị các metadata còn lại và thông báo không thể dựng ảnh người.<br><br>**E3 – Lỗi tải dữ liệu:** Nếu xảy ra lỗi khi truy xuất thông tin kết quả, hệ thống thông báo và cho phép Viewer thử lại. |
| **Luồng thay thế** | **A1 – Chuyển sang kết quả tiếp theo:** Viewer lựa chọn kết quả kế tiếp trong cùng Case; hệ thống tải và hiển thị thông tin chi tiết tương ứng.<br><br>**A2 – Quay lại hồ sơ vụ việc:** Viewer quay lại UC-13 – Xem hồ sơ vụ việc để tiếp tục xem thông tin tổng thể của Case và danh sách các kết quả đã lưu. |

### Ghi chú

- Viewer được định nghĩa là Manager hoặc Director, có quyền xem các kết quả đã được lưu trong tất cả Case nhưng không được thay đổi, đánh giá lại hoặc xóa dữ liệu kết quả.
- Kết quả được hiển thị trong use case này là các kết quả đã được Operator lựa chọn và lưu vào Case.
- Dữ liệu hiển thị có thể bao gồm ảnh người crop động từ frame và bounding box, camera, khu vực, thời gian phát hiện và điểm phù hợp tùy theo dữ liệu thực tế mà hệ thống đã lưu. Khi Viewer bấm vào ảnh người, hệ thống hiển thị full frame và vẽ bounding box lên frame.

---

## UC-15 – Đăng xuất hệ thống

| Thành phần | Mô tả |
|---|---|
| **Mã use-case** | UC-15 |
| **Tên use-case** | Đăng xuất hệ thống |
| **Actors** | Admin, Operator, Viewer |
| **Mục đích** | Cho phép người dùng kết thúc phiên làm việc hiện tại và rời khỏi hệ thống một cách an toàn. |
| **Tiền điều kiện** | Người dùng đã đăng nhập vào hệ thống và đang có phiên làm việc hợp lệ. |
| **Hậu điều kiện** | Phiên đăng nhập hiện tại của người dùng bị hủy hoặc vô hiệu hóa; người dùng không thể tiếp tục truy cập các chức năng yêu cầu xác thực bằng phiên đăng nhập cũ. |
| **Luồng chính** | 1. Người dùng lựa chọn chức năng đăng xuất.<br>2. Hệ thống tiếp nhận yêu cầu đăng xuất.<br>3. Hệ thống xác định phiên đăng nhập hiện tại của người dùng.<br>4. Hệ thống hủy hoặc vô hiệu hóa phiên đăng nhập.<br>5. Hệ thống xóa các thông tin xác thực tạm thời liên quan đến phiên làm việc trên phía người dùng nếu có.<br>6. Hệ thống chuyển người dùng về màn hình đăng nhập.<br>7. Hệ thống thông báo đăng xuất thành công nếu cần. |
| **Ngoại lệ** | **E1 – Phiên đăng nhập đã hết hạn:** Nếu phiên làm việc đã hết hạn trước khi người dùng thực hiện đăng xuất, hệ thống chuyển trực tiếp người dùng về màn hình đăng nhập.<br><br>**E2 – Không thể hủy phiên đăng nhập:** Nếu xảy ra lỗi trong quá trình vô hiệu hóa phiên ở phía máy chủ, hệ thống vẫn xóa thông tin xác thực cục bộ và yêu cầu người dùng đăng nhập lại khi truy cập hệ thống.<br><br>**E3 – Lỗi hệ thống:** Nếu xảy ra lỗi trong quá trình xử lý yêu cầu đăng xuất, hệ thống đảm bảo người dùng không tiếp tục sử dụng phiên cũ nếu cơ chế xác thực cho phép. |
| **Luồng thay thế** | **A1 – Tự động đăng xuất do hết phiên:** Khi phiên đăng nhập hết thời hạn, hệ thống tự động kết thúc phiên và chuyển người dùng về màn hình đăng nhập mà không cần thao tác đăng xuất thủ công. |

### Ghi chú

- Admin, Operator và Viewer sử dụng cùng một cơ chế đăng xuất.
- Use case này chỉ kết thúc phiên đăng nhập hiện tại, không làm thay đổi tài khoản, vai trò hoặc dữ liệu của người dùng.
- Cơ chế timeout phiên và thời gian hết hạn đăng nhập nên được xác định trong yêu cầu kỹ thuật hoặc cấu hình bảo mật của hệ thống.
