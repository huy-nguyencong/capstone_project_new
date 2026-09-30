# Kịch bản thuyết trình bảo vệ PRISM

Tệp này đi kèm `slide_canva.md`, dùng cùng số thứ tự slide. Mỗi slide có ba phần:

- **Lời nói**: câu nói trước Hội đồng, xưng "em", gọi "quý Thầy Cô". Khi luyện nên nói tự nhiên theo ý, không đọc thuộc lòng.
- **Giải thích chi tiết**: kiến thức nền để bạn hiểu rõ điều mình nói. Phần này không đọc ra.
- **Nếu bị hỏi**: câu hỏi có thể gặp và hướng trả lời, bám theo báo cáo.

**Thời lượng dự kiến:** khoảng 12 phút, chưa tính demo. Lời nói chỉ giữ ý chính; khi Hội đồng hỏi sâu, dùng phần giải thích.

---

## Slide 1 — Trang bìa (≈ 20 giây)

**Lời nói**

> Em kính chào quý Thầy Cô. Em là Nguyễn Công Huy, mã số sinh viên 2113499. Em xin trình bày đề tài "Phát triển hệ thống tìm kiếm người dựa trên mô tả đa phương thức", với sản phẩm là ứng dụng PRISM.

**Giải thích chi tiết**

- **PRISM là tên hiển thị của ứng dụng;** tên đề tài chính thức vẫn giữ nguyên. Nên nói tên đề tài trước, sau đó mới giới thiệu PRISM.
- **"Đa phương thức"** là trục chính của cả bài: người dùng mô tả người cần tìm bằng **ảnh**, **câu văn bản** hoặc **thuộc tính**, và cả ba được đưa về cùng một không gian vector. Nên thuộc câu định nghĩa này, vì Hội đồng thường hỏi "đa phương thức ở đây là gì".

---

## Slide 2 — Bối cảnh và vấn đề (≈ 40 giây)

**Lời nói**

> Việt Nam ước tính có hơn 20 triệu camera giám sát, và giá trị lớn nhất của camera là truy vết sau sự việc: khi có hình ảnh hữu ích, tỉ lệ vụ việc được giải quyết tăng từ khoảng 20% lên 50%. Nhưng hiện nay, tìm một người vẫn phải xem lại video thủ công, trong khi thông tin ban đầu thường chỉ là một tấm ảnh, một câu mô tả hay vài đặc điểm trang phục. Bài toán đặt ra là: người này xuất hiện ở camera nào, lúc nào?

**Giải thích chi tiết**

- **Số 20 triệu camera** là **ước tính** cho năm 2025, lấy từ VnExpress ngày 26/08/2024, dẫn số liệu Tổng cục Hải quan qua Bộ TT&TT. Báo cáo còn nêu thêm: hơn 16 triệu camera được nhập khẩu trong 5 năm.
- **Nghiên cứu Ashby (2017)** dựa trên 251.195 vụ việc của Cảnh sát Giao thông Đường sắt Anh. Số liệu này dùng để nói rằng giá trị của camera nằm ở **khả năng tìm lại hình ảnh**, không nằm ở số lượng camera.
- **Cách chuyển sang slide sau:** câu hỏi cuối slide chính là bài toán mà slide 3 trả lời.

**Nếu bị hỏi**

- *"Số liệu Việt Nam có đáng tin không?"* → Đây là số của Tổng cục Hải quan do Bộ TT&TT công bố và báo chí dẫn lại. Em chỉ dùng để minh họa quy mô, không dùng làm căn cứ kỹ thuật.

---

## Slide 3 — Mục tiêu, phạm vi và đóng góp (≈ 50 giây)

**Lời nói**

> Đề tài xây dựng ứng dụng hỗ trợ tìm người trong dữ liệu camera bằng ảnh, câu mô tả hoặc thuộc tính; hệ thống xếp hạng, người dùng quyết định. Kết quả được lưu thành hồ sơ vụ việc và dữ liệu được phân quyền theo khu vực giám sát.
>
> Về phạm vi: chỉ tìm người, không nhận dạng khuôn mặt; truy vấn tiếng Anh; bảy camera giả lập bằng luồng RTSP; dùng mô hình có sẵn trên máy chỉ có CPU. Đóng góp chính là một ứng dụng hoàn chỉnh, trong đó ba hình thức truy vấn dùng chung một không gian vector, kèm số liệu thực nghiệm trên CPU.

**Giải thích chi tiết**

- **"Lần xuất hiện" (track)** là đơn vị kết quả: một người đi qua một camera trong một khoảng thời gian liên tục tạo ra một track. Hệ thống không trả từng khung hình, nhờ vậy tránh được hàng chục kết quả lặp lại của cùng một người.
- **Vì sao chỉ hỗ trợ tiếng Anh:** RaSa được huấn luyện trên CUHK-PEDES, bộ dữ liệu có câu mô tả tiếng Anh. Hệ thống không có bước dịch tự động.
- **Vì sao xử lý lần lượt từng camera:** máy chỉ có CPU, xử lý chậm hơn thời gian thực khoảng 7 lần, nên không thể phân tích đồng thời bảy luồng. Giảng viên hướng dẫn đã xác nhận xử lý tuần tự là chấp nhận được.
- **Cách nói về đóng góp:** đây là đóng góp **về mặt xây dựng ứng dụng**, không phải đóng góp về mô hình AI. Đừng nói "đề xuất phương pháp mới".

**Nếu bị hỏi**

- *"Đóng góp khoa học của em là gì?"* → Đề tài tập trung vào xây dựng ứng dụng. Điểm mới nằm ở cách tích hợp: dùng bộ mã hóa ảnh của RaSa cho cả truy vấn ảnh→ảnh (bài báo gốc chỉ đánh giá văn bản→ảnh), gộp ba hình thức truy vấn vào một vector cho mỗi track, và đánh giá thực nghiệm để chỉ ra giới hạn của văn bản→ảnh khi chuyển sang miền dữ liệu camera thật.

---

## Slide 4 — Các hệ thống liên quan (≈ 40 giây)

**Lời nói**

> Em khảo sát ba sản phẩm thương mại. BriefCam và Avigilon hỗ trợ tìm theo thuộc tính và ảnh mẫu, nhưng cần GPU hoặc thiết bị của hãng. Verkada gần đề tài nhất vì cho tìm bằng câu mô tả tự do, nhưng chạy trên đám mây của hãng. PRISM kết hợp cả ba hình thức trong một không gian biểu diễn, bổ sung hồ sơ vụ việc và phân quyền theo khu vực, và chạy tại chỗ không cần GPU.

**Giải thích chi tiết**

- **Mọi nhận định về sản phẩm** đều lấy từ trang chính thức của hãng (báo cáo Mục 2.1). Ảnh chụp cũng lấy từ website của hãng.
- **Không so sánh độ chính xác** với sản phẩm thương mại, vì các hãng không công bố số liệu.
- **Cụm "không cần GPU rời" là thế mạnh về triển khai,** không phải về tốc độ. Chính vì chỉ có CPU nên PRISM chậm (xem slide 17). Đừng nói PRISM nhanh hơn các sản phẩm này.
- **Avigilon có kết hợp đặc trưng khuôn mặt;** PRISM không dùng khuôn mặt. Đây là một điểm khác biệt về quyền riêng tư.

**Nếu bị hỏi**

- *"Vì sao không dùng luôn CLIP như Verkada?"* → CLIP là mô hình tổng quát, kém phân biệt các chi tiết nhỏ về trang phục (cùng áo khoác nhưng khác màu quần). RaSa được thiết kế riêng cho bài toán tìm người bằng văn bản, và dùng một vector chung cho cả ba hình thức truy vấn. RaSa cũng là mô hình giảng viên hướng dẫn đề xuất.

---

## Slide 5 — Cơ sở lý thuyết và hướng tiếp cận (≈ 1 phút)

**Lời nói**

> Hệ thống dựa trên bốn kỹ thuật nối tiếp nhau. YOLO11n phát hiện người trong khung hình. ByteTrack theo vết, gom các khung của cùng một người thành một track. RaSa đưa ảnh và câu mô tả vào cùng một không gian vector 256 chiều. Milvus tìm các vector gần nhất, có lọc theo camera và khu vực trước khi lấy top-k. Trước bước phát hiện, hệ thống chỉ lấy 1 trong 20 khung hình để giảm chi phí.
>
> Hướng tiếp cận là lập chỉ mục trước, truy vấn sau: video chỉ phân tích một lần, mỗi lần tìm chỉ cần mã hóa truy vấn.

**Giải thích chi tiết**

- **Phát hiện một giai đoạn và hai giai đoạn.** Faster R-CNN làm hai giai đoạn: đề xuất vùng trước, phân loại sau, nên chính xác nhưng chậm. YOLO dự đoán trực tiếp khung bao và lớp trong một lần chạy, nhanh hơn nhiều, phù hợp với máy chỉ có CPU.
- **IoU và NMS.**
  - IoU (Intersection over Union) = diện tích phần giao chia cho diện tích phần hợp của hai khung bao.
  - NMS (Non-Maximum Suppression) giữ khung có độ tin cậy cao nhất, rồi bỏ các khung khác có IoU lớn hơn 0,7 so với khung đó.
- **Cấu hình YOLO11n trong hệ thống.**
  - Chỉ lấy lớp *person*, ngưỡng tin cậy 0,1.
  - YOLO11n có 2,6 triệu tham số, đạt mAP 39,5 trên COCO, mất khoảng 56 ms mỗi ảnh trên CPU theo tài liệu Ultralytics.
- **Vì sao ngưỡng Detector thấp (0,1).**
  - ByteTrack cần các phát hiện điểm thấp cho bước liên kết lần hai. Nếu Detector lọc ở 0,25 thì bước này bị vô hiệu.
  - Vì vậy Detector lấy ngưỡng 0,1, bằng ngưỡng thấp của Tracker. Tracker chỉ **khởi tạo** track mới từ phát hiện có độ tin cậy ≥ 0,25, nên phần lớn phát hiện sai sẽ bị loại ở bước theo vết.
- **ByteTrack, liên kết hai bước.**
  - Bước 1: ghép các phát hiện có độ tin cậy cao (≥ 0,25) với các track, dùng IoU giữa khung bao dự đoán bởi Kalman và khung bao phát hiện, rồi giải bài toán ghép cặp bằng thuật toán Hungary.
  - Bước 2: các track chưa được ghép tiếp tục được ghép với các phát hiện điểm thấp (0,1 đến 0,25). Người bị che khuất một phần thường có điểm thấp, nên bước này giúp track không bị đứt.
- **Vòng đời track.**
  - Một track được xác nhận khi có ít nhất 2 quan sát.
  - Track kết thúc khi mất dấu quá 3 khung hình được xử lý, hoặc quá 2 giây theo thời gian nguồn.
  - ID của track chỉ có ý nghĩa trong một camera và một phiên; hệ thống **không** liên kết cùng một người giữa các camera.
- **BoT-SORT** là tracker thay thế, đã tích hợp. BoT-SORT có thể dùng ReID và bù chuyển động camera, nhưng em tắt cả hai vì camera cố định và để giảm tải cho CPU.
- **RaSa.**
  - Xây dựng trên ALBEF, gồm bộ mã hóa ảnh 12 lớp transformer, bộ mã hóa văn bản 6 lớp và bộ mã hóa đa phương thức 6 lớp.
  - *Relation-aware:* phân biệt câu mô tả viết cho đúng ảnh này với câu viết cho ảnh khác của cùng người.
  - *Sensitivity-aware:* nhận ra khi một từ quan trọng bị thay, ví dụ "áo đỏ" thành "áo xanh".
  - *Học tương phản trong cùng phương thức:* các ảnh của cùng một người được kéo lại gần nhau. Đây là **cơ sở để dùng RaSa cho tìm ảnh→ảnh**.
  - Ảnh đầu vào được đưa về 384×384. Trên CUHK-PEDES, RaSa đạt Rank-1 76,51%.
- **Chuẩn hóa L2.** Khi ‖u‖ = ‖v‖ = 1 thì cos(u, v) = uᵀv. Vì vậy Milvus dùng độ đo tích vô hướng (inner product). **Không viết tắt là "IP"**, vì dễ nhầm với địa chỉ IP.
- **HNSW (Hierarchical Navigable Small World).** Các vector được nối thành đồ thị nhiều tầng: tầng trên thưa để "nhảy xa", tầng dưới dày để tìm chính xác. Việc tìm kiếm đi tham lam từ tầng trên xuống, với độ phức tạp gần logarit theo số vector. Kết quả là gần đúng, đổi lại tốc độ rất nhanh.
- **Lọc trước (pre-filtering).**
  - Nếu tìm top-k trước rồi mới lọc theo khu vực, có thể còn lại ít hơn k kết quả, thậm chí 0.
  - Lọc trước bảo đảm k kết quả đều thuộc phạm vi được phép, đồng thời không làm lộ sự tồn tại của dữ liệu ngoài quyền.
- **Lấy mẫu 1/N.** Video khoảng 60 khung/giây. Với N = 20, hệ thống xử lý khoảng 3 khung/giây, hai khung liên tiếp cách nhau khoảng 0,33 giây.
  - Giải mã video vẫn phải thực hiện cho **mọi** khung, vì H.264 nén khung P/B dựa trên các khung trước.
  - Lấy mẫu chỉ giảm số lần chạy mô hình, không giảm công giải mã.

**Nếu bị hỏi**

- *"Tại sao dùng một mô hình cho cả ảnh→ảnh, trong khi RaSa chỉ công bố văn bản→ảnh?"* → Đây là lựa chọn của đề tài, dựa trên tính chất học tương phản trong cùng phương thức của RaSa. Em đã đo thực nghiệm: tìm bằng ảnh đạt Recall@8 = 1,0 ở lần đo 1.
- *"Lấy mẫu thưa có làm mất người không?"* → Có. Người xuất hiện ngắn hơn khoảng 2 khoảng lấy mẫu (khoảng 0,7 giây với N = 20) có thể không được xác nhận thành track. Đây là đánh đổi để giảm chi phí tính toán; so sánh N = 10 và N = 20 ở slide 17.

---

## Slide 6 — Tác nhân và chức năng chính (≈ 30 giây)

**Lời nói**

> Hệ thống có ba vai trò. Quản trị viên quản lý tài khoản, camera và cấu hình AI, nhưng không được tìm kiếm. Giám sát viên tìm người trong khu vực được giao và quản lý vụ việc của mình. Quản lý xem tổng quan và mọi vụ việc ở chế độ chỉ đọc. Tổng cộng có 15 use case.

**Giải thích chi tiết**

- **Tách quyền kỹ thuật và quyền nghiệp vụ.** Quản trị viên không được tìm người, để người quản trị hạ tầng không thể tự ý tra cứu dữ liệu hình ảnh (nguyên tắc đặc quyền tối thiểu).
- **Sơ đồ use case.** Tác nhân trừu tượng "Người dùng" được tổng quát hóa thành ba vai trò, dùng chung UC-01 (đăng nhập) và UC-15 (đăng xuất).
- **Danh sách 15 use case.**
  - Quản trị viên: 7 use case (UC-02 đến UC-08).
  - Giám sát viên: 3 use case (UC-09 tìm kiếm, UC-10 đánh giá kết quả, UC-11 quản lý vụ việc).
  - Quản lý: 3 use case (UC-12 đến UC-14).

**Nếu bị hỏi**

- *"Tài khoản Giám sát viên bị khóa thì vụ việc của người đó ra sao?"* → Vụ việc vẫn giữ nguyên cùng thông tin người phụ trách, và Quản lý vẫn xem được. Hệ thống không tự chuyển vụ việc cho người khác; dữ liệu nghiệp vụ độc lập với vòng đời tài khoản.

---

## Slide 7 — Các quy tắc nghiệp vụ quan trọng (≈ 45 giây)

**Lời nói**

> Có năm quy tắc nghiệp vụ chính. Mỗi Giám sát viên chỉ tìm được trên camera của khu vực mình, và máy chủ kiểm tra điều này ở mọi yêu cầu. Mỗi kết quả là một lần xuất hiện, không phải một khung hình. Số kết quả chỉ là 4, 8, 12 hoặc 16, không lọc theo ngưỡng điểm. Vụ việc thuộc một Giám sát viên, có trạng thái Đang xử lý hoặc Hoàn thành. Điểm phù hợp chỉ dùng để xếp hạng, không được lưu và không phải kết luận về danh tính.

**Giải thích chi tiết**

- **Vì sao khu vực của camera không đổi được.** Nếu đổi, dữ liệu cũ của camera sẽ bị chuyển sang khu vực khác, khiến Giám sát viên của khu vực mới thấy hình ảnh quay trước khi họ có quyền. Ràng buộc này được đặt cả trong CSDL.
- **Camera ngừng vận hành.** Hệ thống không xóa dữ liệu cũ, chỉ tạm ẩn khỏi tìm kiếm cho tới khi camera được đưa vào vận hành trở lại. Kết quả đã lưu trong vụ việc vẫn xem được.
- **Vì sao không lưu ảnh cắt.** Cắt động từ khung toàn cảnh cho phép nới vùng cắt theo tỉ lệ khung hiển thị, đánh dấu người được tìm thấy và làm tối phần còn lại. Cách này cũng tránh lưu trùng dữ liệu.
- **Vì sao không dùng ngưỡng điểm.**
  - Điểm cosine là điểm **tương đối**, thay đổi theo từng truy vấn. Một ngưỡng cố định sẽ loại mất kết quả đúng ở truy vấn khó.
  - Thay vì dùng ngưỡng, hệ thống trả top-k để người dùng tự đánh giá.
- **Vì sao không lưu Điểm phù hợp vào vụ việc.** Điểm chỉ có nghĩa khi so với các kết quả khác trong cùng lượt tìm. Lưu lại dễ khiến người xem hiểu nhầm đó là "độ chắc chắn".
- **Vì sao vụ việc không gắn khu vực.** Khi Giám sát viên được chuyển khu vực, họ vẫn phải xem được vụ việc cũ của mình. Quyền xem vụ việc dựa trên **người phụ trách**, còn quyền tìm kiếm mới dựa trên **khu vực hiện tại**.
- **Mỗi lần lưu tạo một mục mới** (cho phép cùng một track xuất hiện nhiều lần trong một vụ việc). Đây là quyết định của đặc tả để đơn giản hóa thao tác.

---

## Slide 8 — Kiến trúc tổng thể (≈ 45 giây)

**Lời nói**

> Bảy video được phát thành luồng RTSP, đóng vai trò camera. Tiến trình xử lý nền chạy riêng, phân tích lần lượt từng camera. Máy chủ Flask lo phân quyền, tìm kiếm và vụ việc. Dữ liệu nằm ở ba kho: PostgreSQL cho nghiệp vụ, Milvus cho vector, MinIO cho khung hình. Kiến trúc theo hai nguyên tắc: tách việc chậm khỏi API, và mọi ảnh phải qua máy chủ kiểm tra quyền.

**Giải thích chi tiết**

- **Vì sao tách tiến trình xử lý nền khỏi Flask.**
  - Phân tích một phiên mất vài phút, trong khi một request HTTP không nên chạy lâu.
  - Nếu AI chạy trong API thì một lỗi hoặc tình trạng tràn bộ nhớ sẽ kéo sập cả hệ thống.
  - Hai tiến trình liên lạc với nhau qua **bảng hàng đợi trong PostgreSQL**, không gọi trực tiếp.
- **Vì sao ba kho.** Mỗi loại dữ liệu có công cụ phù hợp:
  - dữ liệu quan hệ cần ràng buộc và giao dịch → PostgreSQL;
  - vector cần tìm gần đúng kèm lọc → Milvus;
  - tệp ảnh cần lưu trữ đối tượng → MinIO.

  Ba kho được liên kết với nhau bằng `track_id`.
- **Nguồn sự thật về quyền và trạng thái là PostgreSQL.** Milvus chỉ trả danh sách ứng viên, và mỗi ứng viên được đối chiếu lại với PostgreSQL.
- **MinIO dùng chung một instance với Milvus** nhưng tách bucket. Bucket của ứng dụng không công khai.
- **Hạ tầng triển khai.** PostgreSQL, Milvus (cùng etcd), MinIO và MediaMTX chạy trong Docker Compose. Flask, tiến trình xử lý nền và ứng dụng web chạy trực tiếp trên máy.

**Nếu bị hỏi**

- *"Vì sao không dùng pgvector cho gọn?"* → Đề tài cần lọc trước khi tìm, lưu trữ bền vững và tách collection theo phiên bản bộ mã hóa. Milvus đáp ứng tốt các yêu cầu này; đây cũng là công nghệ em đã học.
- *"Tiến trình xử lý nền chết giữa chừng thì sao?"* → Công việc có thời hạn giữ chỗ 60 giây, được gia hạn định kỳ. Nếu tiến trình chết, thời hạn trôi qua và công việc được nhận lại để chạy tiếp.

---

## Slide 9 — Luồng xử lý dữ liệu camera (≈ 45 giây)

**Lời nói**

> Bộ lập lịch lần lượt tạo cho mỗi camera một phiên khoảng 30 giây video. Trong phiên, cứ 20 khung lấy một khung cho qua YOLO11n và ByteTrack; khi một người rời khỏi khung hình, hệ thống chọn khung thấy người đó rõ nhất. Hết phiên, vùng người được RaSa mã hóa thành vector rồi ghi vào ba kho. Chỉ khi ghi đủ, track mới tìm được.

**Giải thích chi tiết**

- **Bộ chọn khung hình đại diện.**
  - Hệ thống loại trước các khung không đạt yêu cầu tối thiểu, ví dụ người quá nhỏ hoặc bị cắt ở mép.
  - Các khung còn lại được chấm điểm theo độ phân giải, độ nét, độ đầy đủ cơ thể, độ ổn định và mức bị che khuất. Hệ thống chỉ giữ 3 ứng viên điểm cao nhất để giới hạn bộ nhớ.
  - Cách chọn này deterministic: cùng đầu vào luôn cho cùng kết quả.
- **Vùng cắt khi mã hóa** được nới rộng mỗi phía 5% kích thước khung bao. Ảnh cắt chỉ tồn tại trong bộ nhớ, không được lưu.
- **Vòng đời công việc (H7).** Công việc đi qua các trạng thái Chờ → Đang xử lý → Hoàn thành, Thất bại hoặc Đã hủy.
  - Lỗi tạm thời được thử lại sau một khoảng chờ, tối đa 3 lần.
  - Công việc bị hủy khi Quản trị viên yêu cầu, khi camera bị tắt AI hoặc bị ngừng vận hành giữa chừng. Công việc bị hủy trong lúc đọc và phân tích thì không ghi track nào, nên không có dữ liệu dở dang.
- **Mỗi track ghi kèm** phiên bản cấu hình Detector/Tracker, phiên bản bộ mã hóa và N. Nhờ vậy, khi đổi mô hình vẫn truy vết được track nào tạo bởi cấu hình nào.
- **Hạn chế đã biết.** Với RTSP, dữ liệu được ghi theo phiên, nên một người xuất hiện trước camera chỉ tìm được sau khi phiên đó xong (trễ ít nhất vài phút trên CPU).

**Nếu bị hỏi**

- *"Vì sao không ghi ngay khi track kết thúc?"* → Thiết kế hiện tại mã hóa theo lô ở cuối công việc cho đơn giản và nhất quán. Bước ghi ba kho vốn đã xử lý riêng từng track, nên nếu máy đủ nhanh để xử lý liên tục, chỉ cần sửa quy trình phân tích để ghi ngay (đã nêu ở hướng phát triển).

---

## Slide 10 — Luồng tìm kiếm người (≈ 45 giây)

**Lời nói**

> Khi có truy vấn, máy chủ kiểm tra đầu vào, lấy khu vực từ tài khoản đăng nhập chứ không tin dữ liệu gửi lên, rồi mã hóa truy vấn. Thuộc tính được ghép thành một câu tiếng Anh, ví dụ "A woman wearing a red jacket and blue jeans, carrying a handbag". Milvus tìm có lọc trước, sau đó từng kết quả được đối chiếu lại với PostgreSQL. Ảnh của mỗi kết quả cũng được kiểm tra quyền trước khi trả về.

**Giải thích chi tiết**

- **Vì sao phải đối chiếu lại với PostgreSQL** dù Milvus đã lọc.
  - Milvus có thể tạm lệch với PostgreSQL, ví dụ camera vừa bị ngừng vận hành hoặc track vừa lỗi.
  - PostgreSQL là nguồn sự thật, nên kết quả nào không tồn tại, không ở trạng thái Sẵn sàng hoặc ngoài phạm vi đều bị loại.
- **Truy vấn bù (tìm gấp đôi).** Khi có kết quả bị loại ở bước đối chiếu, danh sách có thể còn ít hơn k. Hệ thống tìm lại với k × 2, tối đa 3 lượt; nếu dữ liệu thật sự ít hơn k thì trả đúng số có được.
- **Bộ thuộc tính.**
  - Gồm giới tính, loại và màu trang phục trên, loại và màu trang phục dưới, vật mang theo (ba lô, túi xách).
  - Tên nhóm hiển thị tiếng Việt, giá trị lựa chọn bằng tiếng Anh.
  - **Không có lựa chọn phủ định** (ví dụ "không mang ba lô"), vì mô hình ảnh–văn bản hiểu phủ định kém (Alhamoud et al., CVPR 2025).
- **Bộ lọc thuộc tính không phải mô hình riêng.** Đây chỉ là *prompt builder*: ghép các lựa chọn thành câu tiếng Anh rồi đưa vào Text Encoder.
- **Tìm kiếm có giới hạn tần suất theo tài khoản.** Thao tác tìm kiếm **không** được ghi nhật ký, theo đặc tả.

**Nếu bị hỏi**

- *"Giám sát viên sửa request để gửi camera của khu vực khác thì sao?"* → Máy chủ từ chối, vì tập camera hợp lệ được tính từ khu vực trong phiên đăng nhập. Kiểm thử đầu cuối đã xác nhận Giám sát viên ở khu vực khác không tìm thấy và không mở được khung hình của track đó.

---

## Slide 11 — Dữ liệu và tính nhất quán (≈ 40 giây)

**Lời nói**

> Một track được ghi vào ba kho, nhưng ba kho không có giao dịch chung. Em dùng thứ tự ghi cố định: PostgreSQL tạo bản ghi Chờ cùng sự kiện outbox, rồi ghi MinIO, rồi Milvus, cuối cùng mới chuyển sang Sẵn sàng. Nhờ vậy, dữ liệu dở dang không bao giờ xuất hiện khi tìm kiếm, và lỗi tạm thời được thử lại mà không cần chạy lại AI.

**Giải thích chi tiết**

- **Transactional outbox.** Ý định ghi sang hệ thống khác được lưu **cùng giao dịch** với dữ liệu chính. Vì outbox chứa đủ dữ liệu, việc thử lại không cần chạy lại AI.
- **Vì sao ghi PostgreSQL trước.**
  - Mọi khung hình và vector ở MinIO/Milvus đều đối chiếu được với một bản ghi đã biết.
  - Phần nào ở MinIO/Milvus mà không có bản ghi tương ứng là dữ liệu mồ côi, và công cụ đối soát phát hiện được.
- **Ghi lặp lại an toàn (idempotent).** Khóa đối tượng MinIO xác định theo track, Milvus dùng upsert, nên ghi lại nhiều lần không tạo bản sao.
- **Chính sách thử lại.** Lần chờ đầu 2 giây, sau mỗi lần tăng gấp đôi, tối đa 300 giây. Sau 5 lần thất bại, hoặc khi gặp lỗi không phục hồi được (ví dụ xung đột mã băm), bản ghi chuyển sang FAILED và sự cố được ghi nhật ký.
- **Các lệnh bảo trì** (`reconcile`, `retry-outbox`…) hiện chạy thủ công.
- **Ràng buộc CSDL tiêu biểu.**
  - Tài khoản Giám sát viên luôn có khu vực.
  - `closed_at` chỉ có giá trị khi vụ việc ở trạng thái CLOSED.
  - Chỉ một cấu hình AI ở trạng thái ACTIVE.
  - Track READY phải có đủ khóa đối tượng, mã băm và thời điểm ghi vector.
  - Tài khoản và camera không bị xóa dòng mà được chuyển trạng thái (`INACTIVE`, `RETIRED`).
- **Chống ghi đè đồng thời:** các bảng `users`, `cameras`, `cases` có cột số phiên bản (optimistic locking).

**Nếu bị hỏi**

- *"Sao không dùng giao dịch phân tán (2PC)?"* → MinIO và Milvus không hỗ trợ tham gia giao dịch hai pha. Outbox kết hợp với trạng thái PENDING/READY là mẫu thiết kế phổ biến cho trường hợp này.

---

## Slide 12 — Công nghệ và hiện thực (≈ 30 giây)

**Lời nói**

> Giao diện dùng React; máy chủ dùng Flask, cùng ngôn ngữ Python với các mô hình AI. Mô hình chỉ được chọn khi đã kiểm tra mã băm, giấy phép và nạp thử thành công. Hàng đợi công việc đặt ngay trong PostgreSQL để tiết kiệm tài nguyên.

**Giải thích chi tiết**

- **Vì sao Flask thay vì FastAPI hoặc Django.**
  - Django nặng hơn nhu cầu của một máy chủ chỉ cung cấp API.
  - Lợi thế bất đồng bộ của FastAPI không đáng kể, vì tác vụ chậm nhất đã được tách sang tiến trình riêng.
  - Flask là công nghệ em đã học.
- **Hàng đợi trong PostgreSQL** dùng `SELECT … FOR UPDATE SKIP LOCKED` để nhận việc an toàn. Chỉ có một tiến trình xử lý nền nên không cần message broker.
- **Vì sao chọn YOLO11n thay vì bản lớn hơn.** YOLO11s chính xác hơn (mAP 47,0 so với 39,5) nhưng chậm hơn khoảng 1,6 lần trên CPU (90 ms so với 56 ms).
- **Giấy phép.** YOLO11 dùng giấy phép AGPL-3.0, chấp nhận được vì đồ án phi thương mại. YOLOX đã được đăng ký làm phương án dự phòng về giấy phép, nhưng chưa có trọng số nên hiển thị là không khả dụng.
- **Kiểm tra trước khi đổi cấu hình AI.** Khi Quản trị viên đổi Detector/Tracker, hệ thống nạp thử cả ba thành phần trước khi áp dụng. Nếu lỗi, hệ thống giữ cấu hình cũ. Cấu hình này dùng chung cho toàn hệ thống, không riêng từng camera.
- **Giám sát vận hành.** Nhật ký dạng JSON kèm mã yêu cầu, che các trường nhạy cảm; tiến trình xử lý nền gửi heartbeat định kỳ.

---

## Slide 13 — Giao diện và luồng sử dụng (≈ 20 giây)

**Lời nói**

> Đây là luồng màn hình của ba vai trò. Giao diện bằng tiếng Việt, được chặn theo vai trò, và dùng được cả trên điện thoại.

**Giải thích chi tiết**

- **Chặn đường dẫn ở giao diện** chỉ nhằm trải nghiệm người dùng. Bảo vệ thật sự nằm ở máy chủ: mọi API đều kiểm tra quyền.
- **Không có bản thiết kế Figma;** giao diện được thiết kế trực tiếp trên ứng dụng web. Nếu bị hỏi về wireframe, trả lời thẳng như vậy.
- **Trên điện thoại:** bộ lọc vuốt ngang, bảng giữ độ rộng tối thiểu và cuộn ngang, menu thu thành danh sách chọn.

---

## Slide 14 — Sản phẩm thực tế (≈ 30 giây, chưa tính demo)

**Lời nói**

> Đây là ứng dụng chạy thật trên dữ liệu WILDTRACK. Kết quả tìm kiếm được xếp theo Điểm phù hợp. Bấm vào một kết quả sẽ thấy khung hình toàn cảnh để đánh giá, rồi lưu vào vụ việc.
>
> *(Nếu có demo:)* Em xin phép trình diễn trực tiếp.

**Giải thích chi tiết**

- **Trước khi demo phải làm nóng:** thực hiện một lượt tìm kiếm trước buổi bảo vệ. Lần tìm đầu tiên sau khi khởi động máy chủ mất khoảng 31 giây để nạp bộ mã hóa; nếu chưa làm nóng mà tiến trình nền đang bận thì có thể mất khoảng 97 giây.
- **Đóng bớt ứng dụng** để còn RAM (xem slide 17), và không để máy vào chế độ ngủ trong lúc tiến trình nền đang chạy.
- **Kéo một kết quả vào ô tìm bằng ảnh** để "tìm tiếp bằng chính người đó" là thao tác gây ấn tượng tốt khi demo.
- **Dữ liệu demo:** 1.523 track, gồm 1.488 track từ tệp video và 35 track từ một phiên RTSP, cùng một vụ việc mẫu có 3 kết quả. Có thể khôi phục về mốc ban đầu trong khoảng 70 giây.

---

## Slide 15 — Kiểm thử phần mềm và kịch bản demo (≈ 35 giây)

**Lời nói**

> Hệ thống vượt qua 711 kiểm thử đơn vị, 37 kiểm thử tích hợp và 2 kiểm thử đầu cuối. Kịch bản trình diễn cho ba vai trò chạy tự động hai lần, cả hai lần đều đạt 15/15 bước. Về phân quyền, mọi API đều được kiểm thử với mọi vai trò, và mọi truy cập ngoài phạm vi đều bị từ chối.

**Giải thích chi tiết**

- **1 kiểm thử tích hợp bị bỏ qua** là bài chèn lỗi cần tắt hẳn một dịch vụ hạ tầng.
- **E2E 217 giây** là thời gian cho luồng AI với đoạn video 10 giây: nạp mô hình 44 giây, xử lý 154 giây, lần tìm bằng văn bản đầu tiên 16 giây.
- **3 lỗi giao diện đã sửa:** không chọn được mô hình; lần tìm đầu báo mất kết nối vì thời hạn chờ ngắn hơn thời gian nạp bộ mã hóa; trạng thái AI hiển thị sai trên màn hình camera.
- **Vì sao trả 404 thay vì 403.** Trả 403 đồng nghĩa xác nhận tài nguyên có tồn tại. Trả 404 không làm lộ việc vụ việc hay track đó có thật hay không.
- **Bảo mật khác** (báo cáo Mục 5.5):
  - mật khẩu băm bằng Argon2;
  - mã phiên 32 byte trong cookie HttpOnly, SameSite=Lax; CSDL chỉ lưu SHA-256 của mã phiên;
  - phiên hết hạn sau 30 phút không hoạt động hoặc 12 giờ;
  - chống SSRF: địa chỉ RTSP phải nằm trong dải mạng camera được khai báo, loopback và link-local bị từ chối;
  - thông tin xác thực RTSP được mã hóa khi lưu.
- **An toàn khi chạy kiểm thử:** bộ kiểm thử tự từ chối chạy nếu tên CSDL không có hậu tố dành cho kiểm thử, để không ghi nhầm vào dữ liệu demo.

**Nếu bị hỏi**

- *"Phiên 12 giờ có thật sự tuyệt đối không?"* → **Cẩn thận.** Hiện mỗi lần làm mới phiên lại cấp hạn 12 giờ mới, nên người dùng hoạt động liên tục sẽ không chạm mốc 12 giờ. Hướng sửa đã được quyết định (giữ hạn của phiên gốc khi làm mới) nhưng chưa được hiện thực. Nếu bị hỏi, trả lời trung thực; chỉ nói "đã sửa" khi code đã sửa.

---

## Slide 16 — Chất lượng tìm kiếm (≈ 50 giây)

**Lời nói**

> Em đánh giá với 6 truy vấn trên bảy camera WILDTRACK. Tìm bằng ảnh rất tốt: Recall@4 bằng 0,83, và trong top 8, mọi truy vấn đều có kết quả đúng. Văn bản và thuộc tính thì không có kết quả đúng nào trong top 16, kể cả khi đã mở rộng bộ thuộc tính.
>
> Nguyên nhân là khác biệt miền dữ liệu: RaSa học trên ảnh người đã cắt gọn, còn ảnh của hệ thống được cắt tự động từ cảnh đông người. Vì vậy, tìm bằng ảnh là hình thức chính, còn văn bản và thuộc tính là hình thức hỗ trợ.

**Giải thích chi tiết**

- **Cách gán nhãn để đánh giá.** Mỗi track được gán nhãn là người chiếm đa số, bằng cách đối chiếu khung bao với nhãn của WILDTRACK. Nhãn này chỉ dùng để đánh giá, không dùng trong ứng dụng.
- **Loại ảnh truy vấn khỏi tập tìm kiếm.** Nếu không loại thì ảnh truy vấn sẽ luôn khớp với chính nó ở hạng 1.
- **Recall@k và MRR.**
  - Recall@k = số truy vấn có kết quả đúng trong top-k, chia cho tổng số truy vấn.
  - MRR = trung bình của 1/hạng của kết quả đúng đầu tiên. Ví dụ MRR ảnh 0,867 nghĩa là kết quả đúng thường nằm ở hạng 1, đôi khi ở hạng 2.
- **Điều kiện đo, phải nói đúng.**
  - Lần 1: ngưỡng tin cậy 0,25, tập tìm kiếm 1.552 track, đo cả ba hình thức.
  - Lần 2: ngưỡng 0,1 (cấu hình hiện hành), 1.526 track, bộ thuộc tính mở rộng, **chỉ đo lại thuộc tính**.
  - Recall của ảnh và văn bản với ngưỡng 0,1 **chưa đo**. Không được nói "Recall ảnh 0,83 với cấu hình hiện tại".
- **Phát hiện người.** Lần 1 đạt precision 0,58, recall 0,54; lần 2 (ngưỡng 0,1) đạt precision 0,43, recall 0,64. Hạ ngưỡng giúp bỏ sót ít người hơn nhưng tạo thêm phát hiện sai, phần lớn bị loại ở bước theo vết. Hai lần đo khác nhau cả ngưỡng lẫn nhãn nên chỉ so sánh định tính.
- **6 truy vấn là tập nhỏ.** Hãy chủ động thừa nhận điều này nếu bị hỏi.

**Nếu bị hỏi**

- *"6 truy vấn có đủ tin cậy không?"* → Không đủ để kết luận thống kê chặt chẽ. Tuy vậy, chênh lệch giữa ảnh (Recall@8 = 1,0) và văn bản (Recall@16 = 0, kết quả đúng ở hạng hàng trăm) rất lớn và nhất quán qua hai lần đo. Mở rộng tập đánh giá nằm trong hướng phát triển.
- *"Sao không bật bước xếp hạng lại của RaSa?"* → Bước này chỉ áp dụng cho truy vấn văn bản, chạy bộ mã hóa đa phương thức trên khoảng 128 ứng viên nên rất tốn kém trên CPU, và chưa có số đo cho thấy nó cải thiện kết quả trên dữ liệu này. Đây là hướng phát triển ưu tiên.
- *"Sao không fine-tune?"* → Phạm vi đồ án là xây dựng ứng dụng với mô hình có sẵn. Hơn nữa, fine-tune cần câu mô tả gán nhãn cho ảnh cùng miền, là dữ liệu hiện không có.

---

## Slide 17 — Hiệu năng và các hạn chế (≈ 50 giây)

**Lời nói**

> Trên máy chỉ có CPU, lấy mẫu N bằng 20 giảm khoảng một phần tư thời gian CPU so với N bằng 10 mà track không bị đứt nhiều hơn. Tìm bằng văn bản mất khoảng 0,1 giây, tìm bằng ảnh khoảng 1,3 giây.
>
> Hệ thống có ba hạn chế chính: văn bản và thuộc tính còn kém; xử lý chậm hơn thời gian thực khoảng 7 lần nên phải luân phiên camera; và với RTSP, track dễ bị tách vì mốc thời gian lấy theo đồng hồ máy.

**Giải thích chi tiết**

- **Điều kiện đo của bảng N.**
  - Mỗi cấu hình chạy 3 lượt xen kẽ. Lượt đầu của N = 10 phải nạp mô hình (mất 178,5 giây) nên bị loại, và thời gian N = 10 là trung bình của 2 lượt còn lại.
  - Các ứng dụng khác không được đóng trong lúc đo, nên thời gian dao động khoảng ±12 giây.
  - CPU và RAM được lấy mẫu mỗi 0,25 giây, nên số đo là giá trị dưới của mức thực tế.
- **Vì sao thời gian gần như không giảm khi tăng N.**
  - Detector chỉ mất khoảng 0,16–0,23 giây mỗi khung được lấy mẫu, trong khi bộ mã hóa ảnh mất khoảng 1,85 giây cho mỗi track.
  - Vì vậy thời gian xử lý phụ thuộc chủ yếu vào **số người xuất hiện**, không phụ thuộc N.
- **Về con số "chậm khoảng 7 lần".**
  - Con số này đo khi lập chỉ mục dữ liệu demo: 7 camera × 60 giây video mất 55 phút, tức khoảng 7,9 lần; lần đo trước đó là khoảng 6,7 giây xử lý cho mỗi giây video 1080p60.
  - Đoạn benchmark 10 giây ở bảng N mất 132,6 giây, tức khoảng 13 lần, vì đoạn đó đông người. Nếu bị hỏi về chênh lệch này, trả lời rằng tốc độ phụ thuộc số người trong cảnh.
- **Bộ nhớ.**
  - Các thành phần khi rảnh: Docker 515 MiB, Flask 1.978 MiB (đã nạp bộ mã hóa truy vấn), tiến trình xử lý nền 338 MiB, máy chủ giao diện 318 MiB, FFmpeg 286 MiB.
  - Khi xử lý, quy trình phân tích dùng thêm tối đa 4.772 MiB (cận trên).
  - Nguyên nhân chính: máy chủ và tiến trình xử lý nền **mỗi bên nạp mô hình riêng** (khoảng 1,8 GiB và 4,2 GiB).
- **Vấn đề mốc thời gian RTSP.**
  - Với tệp video, mốc thời gian lấy theo PTS nên không phụ thuộc tốc độ máy.
  - Với RTSP, mốc thời gian lấy theo đồng hồ lúc đọc. Khi CPU chậm, hai khung được xử lý liên tiếp (cách nhau khoảng 0,33 giây trong video) có thể cách nhau khoảng 2,3 giây theo đồng hồ, vượt ngưỡng 2 giây, nên track bị kết thúc sớm và tách thành nhiều track.
  - Dữ liệu demo lập chỉ mục từ tệp video nên không bị ảnh hưởng.

**Nếu bị hỏi**

- *"Nếu có GPU thì sao?"* → Bộ mã hóa ảnh và Detector sẽ nhanh hơn nhiều lần, có thể theo kịp thời gian thực. Khi đó hệ thống có thể xử lý liên tục từng camera và ghi track ngay khi kết thúc. Kiến trúc không cần đổi, vì tiến trình xử lý nền đã tách riêng.

---

## Slide 18 — Kết quả đạt được và hướng phát triển (≈ 35 giây)

**Lời nói**

> Đề tài đã đạt năm mục tiêu đặt ra, trong đó chất lượng tìm bằng văn bản còn hạn chế. Hướng phát triển ưu tiên là bật bước xếp hạng lại của RaSa hoặc tinh chỉnh mô hình trên dữ liệu cùng miền, tăng tốc bằng OpenVINO hoặc GPU, và mở rộng sang liên kết một người giữa nhiều camera.

**Giải thích chi tiết**

- **Mục tiêu 2 nên đánh dấu ✔/△,** không đánh ✔ trọn vẹn. Việc thừa nhận hạn chế một cách trung thực thường được Hội đồng đánh giá cao.
- **OpenVINO** là bộ công cụ của Intel để tối ưu suy luận trên CPU và iGPU Intel. Máy triển khai có Iris Xe, nhưng **chưa đo** hiệu quả thực tế, nên chỉ nói là hướng thử.
- **Liên kết xuyên camera** (multi-camera tracking) cần ReID giữa camera và hiệu chỉnh vị trí camera. WILDTRACK có sẵn thông tin hiệu chỉnh này, nên đây là hướng mở rộng khả thi.

---

## Slide 19 — Cảm ơn và câu hỏi (≈ 10 giây)

**Lời nói**

> Em xin cảm ơn quý Thầy Cô đã lắng nghe, và rất mong nhận được câu hỏi, góp ý của Hội đồng.

**Giải thích chi tiết**

- **Khi nhận câu hỏi:** ghi lại câu hỏi, nhắc lại ngắn để xác nhận đã hiểu đúng, rồi mới trả lời. Nếu cần hình minh họa, mở slide dự phòng (H1, H5, H7, H8, các màn hình của Quản trị viên).
- **Khi không biết câu trả lời:** nói rõ phần nào đã làm hoặc đã đo, phần nào chưa, rồi nêu hướng kiểm chứng. Không đưa ra số liệu chưa đo.

---

## Phụ lục: bộ câu hỏi nhanh

| Câu hỏi | Ý trả lời chính |
| --- | --- |
| Hệ thống có nhận diện ai là ai không? | Không. Hệ thống chỉ xếp hạng theo ngoại hình tổng thể, không dùng khuôn mặt; người dùng quyết định. |
| Vì sao kết quả là track mà không phải khung hình? | Để tránh hàng chục kết quả lặp của cùng một người; mỗi track dùng 1 khung đại diện, 1 vector. |
| Hai Giám sát viên cùng khu vực có thấy vụ việc của nhau không? | Không. Vụ việc thuộc người phụ trách; chỉ Quản lý xem được tất cả. |
| Camera bị ngừng vận hành thì dữ liệu mất không? | Không mất; dữ liệu tạm ẩn khỏi tìm kiếm cho tới khi camera vận hành lại. Vụ việc đã lưu vẫn xem được. |
| Hai camera đăng ký trùng địa chỉ RTSP thì sao? | Hệ thống chỉ chặn trùng mã camera. Tránh trùng luồng là trách nhiệm của Quản trị viên, và mọi thao tác thêm/sửa camera đều ghi nhật ký. Đây là rủi ro đã được ghi nhận. |
| Đổi Detector/Tracker có ảnh hưởng dữ liệu cũ không? | Không. Track cũ giữ nguyên và ghi kèm phiên bản cấu hình; cấu hình mới chỉ áp dụng cho track mới. Nếu nạp thử lỗi, hệ thống giữ cấu hình cũ. |
| Đổi bộ mã hóa thì sao? | Mỗi phiên bản bộ mã hóa dùng một collection Milvus riêng, nên không trộn các không gian vector. Trong phiên bản hiện tại, bộ mã hóa là cố định. |
| Vì sao không dùng CLIP đa ngôn ngữ để hỗ trợ tiếng Việt? | CLIP kém phân biệt chi tiết trang phục; RaSa được giảng viên đề xuất và chuyên cho tìm người. Hỗ trợ tiếng Việt nằm trong hướng phát triển. |
