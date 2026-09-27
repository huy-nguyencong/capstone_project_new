# Project Requirements — PRISM

> Đây là tài liệu yêu cầu chính thức của dự án. Ba tài liệu đặc tả nguồn là `project_requirements.md` (tài liệu này), `usecase_detail.md` và `architect.md` (kiến trúc chung). Các file `backend_implementation_plan.md`, `storage_database_implementation_plan.md` và `ai_worker_implementation_plan.md` là kế hoạch thực thi chi tiết được xây dựng dựa trên ba tài liệu nguồn; chúng không được thay đổi hoặc ghi đè yêu cầu ở đây. Các roadmap hoặc tài liệu theo dõi tiến độ nằm ngoài thư mục `files/`, bao gồm `docs/api-roadmap.md`, chỉ dùng để theo dõi thực hiện.

## Bối cảnh dự án

Trong thực tế, các hệ thống camera giám sát ngày càng được triển khai rộng rãi tại các tòa nhà, khu dân cư, doanh nghiệp, nhà máy và nhiều khu vực công cộng. Số lượng camera lớn và thời gian ghi hình liên tục tạo ra một lượng dữ liệu hình ảnh đáng kể, khiến việc tìm kiếm một người cụ thể bằng phương pháp quan sát thủ công trở nên mất nhiều thời gian và phụ thuộc nhiều vào người vận hành. Đặc biệt, khi người dùng chỉ có một số thông tin ban đầu như hình ảnh của người cần tìm, đặc điểm trang phục hoặc mô tả bằng ngôn ngữ tự nhiên, việc xác định thời điểm và camera mà người đó xuất hiện là một bài toán khó nếu chỉ sử dụng hệ thống camera truyền thống.

Xuất phát từ nhu cầu đó, dự án hướng đến xây dựng một hệ thống ứng dụng trí tuệ nhân tạo hỗ trợ tìm kiếm người trong dữ liệu thu thập từ các luồng camera RTSP. Hệ thống tiếp nhận và phân tích hình ảnh từ camera, phát hiện và theo dõi người, tạo đặc trưng hình ảnh phục vụ lập chỉ mục, từ đó cho phép Operator tìm kiếm người bằng ảnh crop, câu mô tả văn bản **tiếng Anh** hoặc bộ lọc thuộc tính **tiếng Anh**. Bộ lọc thuộc tính chỉ đóng vai trò hỗ trợ người dùng xây dựng nhanh câu mô tả; hệ thống chuyển các thuộc tính được lựa chọn thành câu tiếng Anh có cấu trúc rồi xử lý bằng Text Encoder. Danh sách kết quả ban đầu hiển thị ảnh người được crop động từ **frame toàn cảnh + bounding box**, cùng camera phát hiện, khu vực, thời điểm xuất hiện và Điểm phù hợp. Khi bấm vào ảnh người, hệ thống hiển thị frame toàn cảnh và vẽ bounding box của người trên frame để người dùng đánh giá trong ngữ cảnh.

Ứng dụng có tên hiển thị **PRISM — Person Retrieval via Image & Semantic Matching**. Dự án là đồ án tốt nghiệp, trọng tâm là xây dựng ứng dụng; các mô hình AI được sử dụng sẵn, không nghiên cứu mô hình mới và không nhằm triển khai thương mại. Trong phạm vi đồ án, hệ thống camera được **giả lập bằng các luồng RTSP** phát từ 7 video của bộ dữ liệu WILDTRACK; mỗi luồng tương ứng một camera logic.

## 1. Chức năng của tài khoản quản trị viên

- **Quản lý tài khoản người dùng:** Quản trị viên có quyền tạo mới, cập nhật, khóa/mở khóa, xóa hoặc ngừng hoạt động tài khoản người dùng; gán vai trò Operator hoặc Viewer. Khi tạo hoặc chỉnh sửa Operator, Admin gán đúng **một khu vực giám sát** cho tài khoản đó. Khu vực này được dùng để giới hạn các camera và dữ liệu tìm kiếm mà Operator được phép truy cập; không có thao tác gán nhiều khu vực cho một Operator. Việc xóa hoặc ngừng hoạt động tài khoản không làm xóa dữ liệu nghiệp vụ đã được tạo trước đó. Nếu Operator đang phụ trách Case bị khóa, xóa hoặc ngừng hoạt động, các Case đó vẫn được giữ nguyên cùng thông tin Operator phụ trách; hệ thống không tự động chuyển Case cho Operator khác.
- **Khu vực giám sát:** Khu vực là thông tin gắn với camera và Operator để xác định phạm vi tìm kiếm. Phiên bản này không có chức năng quản lý (CRUD) khu vực độc lập: danh mục khu vực được khai báo sẵn khi triển khai (mã ổn định và tên hiển thị), Admin chọn khu vực từ danh mục này khi tạo camera hoặc gán cho Operator.

- **Quản lý camera:** Quản trị viên có thể thêm mới, cập nhật, loại camera khỏi vận hành hoặc đưa camera vận hành trở lại. Khi thêm camera, quản trị viên cấu hình tên camera, địa chỉ RTSP, thông tin xác thực và khu vực lắp đặt; khu vực này được dùng để đối chiếu với khu vực giám sát của Operator và không thể thay đổi sau khi tạo camera. Nếu chưa thể kết nối RTSP tại thời điểm cấu hình, hệ thống vẫn có thể lưu camera ở trạng thái Offline/Chưa xác minh để kiểm tra lại sau. Khi camera bị loại khỏi vận hành, hệ thống ngừng nhận luồng camera vào để xử lý và lưu trữ (không tạo dữ liệu AI mới) nhưng không hard-delete dữ liệu lịch sử. Các Person Embedding, frame toàn cảnh, bounding box và metadata đã tạo trước đó tiếp tục được giữ lại nhưng **tạm thời không được tìm kiếm** (không xuất hiện trong kết quả, không chọn làm bộ lọc, không thêm mới vào Case) cho đến khi camera được đưa vào vận hành trở lại. Kết quả đã lưu trong Case trước đó vẫn được xem bình thường.
- **Kiểm tra kết nối camera:** Quản trị viên có thể kiểm tra khả năng kết nối đến luồng RTSP của từng camera và theo dõi trạng thái hoạt động nhằm phát hiện camera mất kết nối hoặc luồng video không khả dụng.

- **Quản lý xử lý AI trên camera:** Quản trị viên có thể bật hoặc tắt chức năng xử lý AI đối với từng camera. Khi bật, hệ thống sử dụng bộ mô hình AI hiện hành để phân tích dữ liệu từ camera; khi tắt, hệ thống ngừng tạo dữ liệu phân tích mới từ camera đó. Camera có RTSP đang mất kết nối (lần kiểm tra gần nhất thất bại) không được bật xử lý AI. Với camera đang bật AI và có RTSP, worker tự tạo lần lượt các phiên xử lý có giới hạn số frame, xoay vòng giữa các camera. Camera không cấu hình RTSP chỉ được xử lý bằng tệp video tải lên (đường dự phòng).

- **Lựa chọn mô hình AI:** Quản trị viên chỉ có thể lựa chọn các Detector và Tracker đã được hệ thống đăng ký sẵn. Hệ thống kiểm tra tính tương thích giữa Detector và Tracker trước khi áp dụng. **Image Encoder và Text Encoder là thành phần cố định của hệ thống và không cho phép thay đổi từ giao diện quản trị**.
- **Theo dõi trạng thái hệ thống:** Quản trị viên có thể theo dõi tình trạng camera, luồng RTSP và tiến trình xử lý AI nhằm phát hiện các thành phần đang mất kết nối, ngừng xử lý hoặc gặp lỗi.

- **Kiểm tra hoạt động của AI:** Quản trị viên có thể kiểm tra độc lập hai nhóm thành phần. Camera Processing Pipeline gồm `RTSP → Detector → Tracker → Image Encoder` và yêu cầu lựa chọn camera; Search Components gồm `Image Encoder` và `Text Encoder` và không phụ thuộc vào camera. Chức năng này phục vụ mục đích kỹ thuật, không phải chức năng tìm kiếm người của Operator.

- **Xem nhật ký hệ thống:** Quản trị viên có thể xem audit log phục vụ kiểm tra, truy vết và bảo trì. Log tối thiểu ghi nhận đăng nhập/đăng xuất và đăng nhập thất bại; tạo/cập nhật/khóa/mở khóa/ngừng hoạt động/xóa tài khoản; thay đổi vai trò hoặc khu vực giám sát của Operator; thêm/cập nhật/kiểm tra kết nối/loại camera khỏi vận hành/đưa camera vận hành trở lại; bật/tắt xử lý AI; thay đổi Detector/Tracker; thao tác tạo/cập nhật Case, đánh dấu Case hoàn thành hoặc mở lại Case; và các lỗi kỹ thuật quan trọng của RTSP hoặc pipeline AI. Hệ thống không ghi nhận thao tác tìm kiếm người của Operator trong phiên bản hiện tại.

## 2. Chức năng của tài khoản Operator
- **Thực hiện tìm kiếm người bằng AI:** Operator sử dụng chức năng tìm kiếm để tìm người trong dữ liệu camera đã được hệ thống AI phân tích. Phiên bản ban đầu chỉ hỗ trợ tìm kiếm người, chưa hỗ trợ phương tiện hoặc các loại đối tượng khác.

- **Lựa chọn phạm vi tìm kiếm:** Hệ thống tự động giới hạn tìm kiếm theo **khu vực giám sát** đã được gán cho tài khoản Operator. Operator chỉ có thể lọc thêm theo các camera thuộc khu vực đó và khoảng thời gian. Backend không truy vấn hoặc trả về dữ liệu từ camera ngoài khu vực được gán.
- **Enforce phạm vi tìm kiếm:** Mọi truy vấn tìm kiếm của Operator phải được backend đối chiếu với khu vực giám sát đã được Admin gán cho Operator. Nếu request chứa camera hoặc khu vực ngoài quyền, hệ thống phải từ chối truy vấn đối với dữ liệu đó và không trả về kết quả ngoài phạm vi được cấp.

- **Tìm kiếm người bằng hình ảnh:** Operator đưa vào ảnh đã được crop chứa người cần tìm bằng cách chọn tệp, kéo thả tệp, dán ảnh (Ctrl+V), hoặc kéo một kết quả tìm kiếm vào ô tìm bằng ảnh để tìm tiếp bằng chính người đó (hệ thống dùng ảnh crop khít bounding box của kết quả làm truy vấn). Hệ thống sử dụng Image Encoder để tạo biểu diễn truy vấn và so sánh với dữ liệu embedding đã được lập chỉ mục.

- **Tìm kiếm người bằng mô tả văn bản:** Operator nhập câu hoặc đoạn mô tả **bằng tiếng Anh** về đặc điểm người cần tìm, ví dụ “a person wearing a red shirt, black pants, and a backpack”. Hệ thống sử dụng Text Encoder để mã hóa mô tả thành biểu diễn truy vấn và thực hiện tìm kiếm. Phiên bản hiện tại không hỗ trợ truy vấn văn bản bằng tiếng Việt và không thực hiện dịch tự động sang tiếng Anh.

- **Tìm kiếm người theo thuộc tính:** Operator lựa chọn nhanh các thuộc tính (tên nhóm hiển thị bằng tiếng Việt, **giá trị lựa chọn bằng tiếng Anh**) gồm giới tính, loại và màu trang phục phía trên, loại và màu trang phục phía dưới, và vật mang theo (ba lô, túi xách). Bộ lọc không có lựa chọn phủ định (ví dụ "không mang ba lô") vì Text Encoder xử lý phủ định kém. Bộ lọc thuộc tính là UX helper/prompt builder, không phải mô hình AI riêng. Giá trị lựa chọn và câu mô tả có cấu trúc được sinh ra dùng tiếng Anh (tên nhóm thuộc tính chỉ là nhãn giao diện và hiển thị bằng tiếng Việt); câu này được đưa vào Text Encoder để thực hiện tìm kiếm giống với tìm kiếm bằng mô tả văn bản.

- **Lưu trữ hình ảnh kết quả:** Hệ thống không lưu person crop như một ảnh độc lập. Đối với mỗi lần xuất hiện/track, hệ thống lưu frame toàn cảnh đại diện, bounding box của người trên frame và metadata liên quan. Danh sách kết quả dùng frame + bounding box để crop động ảnh người; khi người dùng bấm vào ảnh, hệ thống hiển thị full frame và vẽ bounding box trên đó. Ảnh người trong danh sách được dựng động từ frame toàn cảnh + bounding box: vùng cắt được nới rộng theo tỉ lệ khung hiển thị bằng chính phần cảnh xung quanh trên frame (không kéo giãn, không cắt vào người), người được tìm thấy được đánh dấu bằng khung viền và phần cảnh xung quanh được làm tối để phân biệt khi trong khung có nhiều người.

- **Xem và đánh giá kết quả tìm kiếm:** Operator chọn số lượng kết quả muốn hiển thị (`top_k`) trong các mốc **4, 8, 12 hoặc 16** khi gửi yêu cầu tìm kiếm. Hệ thống kiểm tra `top_k` hợp lệ và trả về tối đa số lượng đó trong tập kết quả có **Điểm phù hợp (Matching Score)** cao nhất, sắp xếp từ cao xuống thấp. Danh sách ban đầu hiển thị ảnh người crop động từ frame toàn cảnh và bounding box, camera phát hiện, khu vực, thời gian xuất hiện và Điểm phù hợp. Khi Operator bấm vào ảnh người, hệ thống hiển thị frame toàn cảnh và vẽ bounding box của người trên frame để Operator đánh giá bằng mắt. Phiên bản hiện tại không dùng ngưỡng Matching Score để tự động loại kết quả. Mỗi kết quả đại diện cho một lần xuất hiện/track của một người trên một camera, sử dụng một frame toàn cảnh đại diện và bounding box; hệ thống không tạo một kết quả riêng cho từng frame của cùng track.

- **Nguyên tắc trả kết quả:** Hệ thống không dùng ngưỡng Matching Score để quyết định một kết quả có được hiển thị hay không. Hệ thống trả về tối đa `top_k` kết quả có điểm cao nhất trong phạm vi tìm kiếm theo số lượng Operator chọn; `top_k` chỉ nhận một trong các giá trị `{4, 8, 12, 16}` và được backend kiểm tra; giá trị khác bị từ chối. Điểm phù hợp chỉ phục vụ xếp hạng và hỗ trợ Operator đánh giá bằng mắt trong **lượt tìm kiếm hiện tại**; không được lưu vào Case hoặc hiển thị lại khi xem Case.

- **Quản lý hồ sơ vụ việc:** Khi xem một kết quả tìm kiếm, Operator có hai lựa chọn: **Tạo Case mới** hoặc **Thêm vào Case đã có**. Mỗi Case có đúng **một Operator phụ trách**. Khi tạo Case, hệ thống tự động lấy Operator đang đăng nhập làm người phụ trách; Operator không chọn người phụ trách trong biểu mẫu và không thể chỉ định người khác qua request. Khi thêm vào Case đã có, hệ thống chỉ hiển thị và cho phép thao tác trên các Case do chính Operator đó phụ trách. Phiên bản hiện tại không hỗ trợ chuyển quyền phụ trách Case sang Operator khác. Case không gắn với khu vực. Mỗi Case có một **trạng thái**: **Đang xử lý** (mặc định khi tạo) hoặc **Hoàn thành**. Operator phụ trách đánh dấu Case hoàn thành khi xử lý xong; Case đã hoàn thành bị khóa (không thêm/loại kết quả, không sửa tiêu đề và ghi chú) và không xuất hiện trong danh sách **Thêm vào Case đã có**, cho đến khi Operator **mở lại** Case. Nội dung nghiệp vụ của Case gồm **tiêu đề**, **ghi chú**, **trạng thái** và **các kết quả tìm kiếm đã lưu**. Mỗi kết quả giữ tham chiếu tới frame toàn cảnh, bounding box và metadata; không lưu person crop riêng. Một Case có thể chứa nhiều kết quả tìm kiếm; khu vực chỉ dùng để giới hạn dữ liệu tìm kiếm mà Operator được phép truy cập, không dùng để ràng buộc Case.
## 3. Chức năng của tài khoản Viewer

Viewer được định nghĩa là người dùng ở vai trò quản lý như **Manager hoặc Director**, có nhu cầu theo dõi kết quả nghiệp vụ nhưng không trực tiếp thực hiện tìm kiếm AI hoặc cấu hình hệ thống.

- **Xem thông tin tổng quan:** Viewer có thể xem dashboard trên toàn hệ thống với các nội dung tối thiểu gồm **tổng số Case**, **số Case đang xử lý và đã hoàn thành**, **tổng số kết quả tìm kiếm đã được lưu vào Case** và **danh sách các Case gần đây** kèm trạng thái.
- **Xem hồ sơ vụ việc:** Viewer có thể xem toàn bộ Case trong hệ thống. Mỗi Case hiển thị tiêu đề, ghi chú, trạng thái, Operator phụ trách và các kết quả tìm kiếm đã lưu; Viewer có thể lọc Case theo trạng thái và luôn ở chế độ chỉ đọc.
- **Xem thông tin kết quả tìm kiếm đã lưu:** Viewer có thể xem ảnh người được dựng từ frame toàn cảnh và bounding box, camera phát hiện, khu vực và thời gian phát hiện của các kết quả đã được Operator lưu trong Case. **Matching Score không được lưu và không hiển thị lại trong Case.**

- **Hạn chế quyền thao tác:** Viewer chỉ có quyền đọc; không được thực hiện tìm kiếm AI, tạo hoặc chỉnh sửa Case, thay đổi kết quả tìm kiếm, quản lý camera, quản lý người dùng hoặc cấu hình mô hình AI.

Dữ liệu nghiệp vụ được quản lý độc lập với vòng đời tài khoản người dùng; việc xóa hoặc ngừng hoạt động tài khoản không kéo theo việc xóa Case, kết quả đã lưu hoặc audit log.

## 4. Phân biệt vai trò giữa các loại tài khoản

Trong hệ thống, ba loại tài khoản được phân chia theo trách nhiệm khác nhau. **Admin** chịu trách nhiệm quản trị kỹ thuật, bao gồm người dùng, camera RTSP, trạng thái xử lý AI, lựa chọn mô hình và theo dõi vận hành. Admin không mặc định có quyền tìm kiếm người trên toàn bộ dữ liệu camera.

**Operator** là người trực tiếp sử dụng chức năng nghiệp vụ chính của hệ thống. Mỗi Operator được gán đúng một khu vực giám sát; hệ thống dùng khu vực này để giới hạn camera và dữ liệu tìm kiếm mà Operator được phép truy cập. Mỗi Case có đúng một Operator phụ trách; Operator chỉ quản lý các Case do chính mình phụ trách. Case không gắn với khu vực; Operator dùng Case để lưu tiêu đề, ghi chú và các kết quả tìm kiếm đã chọn, và đánh dấu Case **Đang xử lý** hoặc **Hoàn thành**.

**Viewer** là Manager hoặc Director, có quyền xem toàn bộ Case và các kết quả đã được Operator lưu nhưng không thực hiện tìm kiếm hoặc thay đổi dữ liệu nghiệp vụ.

## 5. Luồng xử lý AI và tìm kiếm

### 5.1. Camera Processing Pipeline

```text
RTSP
  ↓
Detector
  ↓
Tracker
  ↓
Image Encoder
  ↓
Person Embedding
```

Camera Processing Pipeline chịu trách nhiệm tiếp nhận luồng RTSP, phát hiện người, theo dõi người giữa các frame và sử dụng Image Encoder để tạo embedding từ vùng người được tạo tạm thời theo bounding box. Hệ thống không lưu vùng crop này như một ảnh độc lập.

Image Encoder có hai vai trò: trong Camera Processing Pipeline, Image Encoder tạo Stored Person Embedding từ vùng người được cắt tạm thời theo bounding box trên frame; trong tìm kiếm bằng ảnh, Image Encoder tạo Query Embedding từ ảnh truy vấn do Operator cung cấp.

### 5.2. Search Components

```text
Tìm kiếm bằng ảnh crop
Ảnh crop
  ↓
Image Encoder
  ↓
Query Embedding
  ↓
Vector Search
```

```text
Tìm kiếm bằng mô tả văn bản
Mô tả văn bản
  ↓
Text Encoder
  ↓
Query Embedding
  ↓
Vector Search
```

```text
Tìm kiếm bằng bộ lọc thuộc tính
Thuộc tính được chọn
  ↓
Prompt Builder
  ↓
Câu mô tả văn bản
  ↓
Text Encoder
  ↓
Query Embedding
  ↓
Vector Search
```

Search Components gồm **Image Encoder** và **Text Encoder**. Hai encoder này được cố định trong phiên bản hiện tại và không phải là tham số cấu hình của Admin. Image Encoder được sử dụng cho truy vấn bằng ảnh crop; Text Encoder chỉ nhận truy vấn văn bản tiếng Anh và câu mô tả tiếng Anh được sinh từ bộ lọc thuộc tính.

Đơn vị kết quả tìm kiếm được xác định theo **track/lần xuất hiện**, không theo từng frame. Một track trên một camera được biểu diễn bằng **frame toàn cảnh đại diện + bounding box + Person Embedding + metadata** như camera, khu vực và thời gian xuất hiện. Ảnh người trong danh sách được crop động từ frame và bounding box; khi bấm vào ảnh, frame toàn cảnh được hiển thị cùng bounding box vẽ trên frame.


## 6. Quy ước hiển thị kết quả tìm kiếm

Hệ thống sử dụng một thông số chính trên giao diện kết quả của **lượt tìm kiếm hiện tại** là **Điểm phù hợp (Matching Score)**. Điểm này thể hiện mức độ phù hợp giữa truy vấn và kết quả, được sử dụng để **sắp xếp top kết quả** và hỗ trợ người dùng đánh giá bằng mắt. Điểm phù hợp không được xem là kết luận chắc chắn rằng hai hình ảnh thuộc cùng một người; người dùng vẫn cần quan sát ảnh và các thông tin liên quan để đưa ra đánh giá cuối cùng.

- Giao diện người dùng chỉ hiển thị **Điểm phù hợp (Matching Score)** cho mỗi kết quả trong lượt tìm kiếm hiện tại.
- Điểm phù hợp được sử dụng để xếp hạng và hỗ trợ người dùng đánh giá kết quả; không được xem là kết luận chắc chắn rằng hai hình ảnh thuộc cùng một người.
- Điểm phù hợp không được lưu vào `PersonTrack`, `Case` hoặc `CaseResult`, không xuất hiện trong API Case và không hiển thị lại cho Operator hoặc Viewer khi xem Case.
- Các giá trị confidence nội bộ của Detector hoặc các thành phần AI khác, nếu có, chỉ phục vụ xử lý backend và không được hiển thị trên giao diện/nghiệp vụ.
