# Lời thuyết trình (tiếng Việt) — phần của Nguyễn Công Huy, bản 8 phút

> Đi kèm `slides/HK253-DATN-078_2113499.pdf`. Số slide theo đúng số trang PDF (slide 1–20). Phần kết luận (gồm
> slide "Project timeline") ghi theo tên slide vì số trang tùy cách ghép với slide của bạn Cường. Phần II (từ
> slide 21) và các cột Part II do bạn Cường trình bày nên không có ở đây.
>
> **Ngân sách thời gian (tổng 20 phút):** slide của Huy **khoảng 7 phút 55 giây** (mở đầu 1:35, Part I 5:40, kết
> luận 0:40) · demo ứng dụng **6 phút** · còn lại khoảng 6 phút cho bạn Cường và chuyển lời.
>
> **Cách đọc:** chữ trong ngoặc vuông `[...]` là thao tác, không đọc ra. Xưng "em", gọi "quý Thầy Cô". Tốc độ
> tham khảo khoảng 3 tiếng mỗi giây; mỗi đoạn đã được đếm để vừa thời gian ghi trong ngoặc.
>
> **Nguyên tắc rút gọn:** các màn hình (slide 13–17) sẽ được trình diễn lại trong phần demo, nên lời nói ở đó chỉ
> giữ một câu cho mỗi slide; chi tiết để dành cho demo.

---

## Mở đầu (1:35)

### Slide 1 — Bìa (0:10)

Em kính chào quý Thầy Cô. Em là Nguyễn Công Huy, cùng bạn Nguyễn Hữu Cường, xin trình bày đề tài "Phát triển
hệ thống tìm kiếm người dựa trên mô tả đa phương thức".

### Slide 2 — Outline (0:10)

[Bấm sang slide 2] Em trình bày phần mở đầu và phần ứng dụng; bạn Cường trình bày phần nghiên cứu cải thiện tìm
kiếm bằng văn bản.

### Slide 3 — Bài toán (0:30)

[Bấm sang slide 3] Việt Nam ước tính có hơn hai mươi triệu camera giám sát, và khi có hình ảnh hữu ích, tỉ lệ
vụ việc được giải quyết tăng từ khoảng hai mươi lên năm mươi phần trăm. Nhưng tìm một người vẫn phải xem lại
video thủ công, trong khi thông tin ban đầu chỉ là một tấm ảnh hay vài câu mô tả. Câu hỏi là: người này xuất
hiện ở camera nào, lúc nào?

### Slide 4 — Mục tiêu và phạm vi (0:30)

[Bấm sang slide 4] Mục tiêu là xây dựng ứng dụng tìm người từ nhiều cách mô tả; hệ thống xếp hạng, người dùng
quyết định. Phần ứng dụng có năm mục tiêu, từ lập chỉ mục dữ liệu camera, tìm kiếm, lưu hồ sơ, phân quyền tới
đánh giá mô hình. Phạm vi: chỉ tìm người, truy vấn tiếng Anh, bảy camera giả lập bằng RTSP, chạy trên máy chỉ có
CPU.

### Slide 5 — "Đa phương thức" nghĩa là gì (0:25)

[Bấm sang slide 5] Người dùng có ba cách mô tả: một ảnh cắt sẵn, một câu tiếng Anh, hoặc chọn thuộc tính; thuộc
tính được ghép thành câu. Cả ba được mô hình RaSa đưa về cùng một không gian vector để so khớp với các lần xuất
hiện đã lập chỉ mục.

---

## Phần I — Ứng dụng (5:40)

### Slide 6 — Chuyển phần (0:05)

[Bấm sang slide 6] Sau đây là phần ứng dụng.

### Slide 7 — Các hệ thống liên quan (0:25)

[Bấm sang slide 7] Ba sản phẩm thương mại đều hỗ trợ tìm theo thuộc tính và ảnh, nhưng chỉ Verkada cho tìm bằng
câu mô tả, và cả ba gắn với GPU, thiết bị hoặc đám mây của hãng. Hệ thống của em gộp cả ba cách mô tả và chạy
tại chỗ với camera RTSP bất kỳ.

### Slide 8 — Vai trò và phân quyền (0:25)

[Bấm sang slide 8] Có ba vai trò: Quản trị viên lo kỹ thuật, Giám sát viên tìm kiếm và lập vụ việc, Quản lý chỉ
đọc. [Chỉ ô dưới] Mỗi Giám sát viên có một khu vực; máy chủ lọc theo khu vực ngay trong truy vấn, trước khi chọn
kết quả.

### Slide 9 — Kiến trúc (0:35)

[Bấm sang slide 9] [Chỉ số 1] Bảy video WILDTRACK được phát thành bảy luồng RTSP. [Chỉ số 2] Tiến trình nền chạy
tách khỏi máy chủ: lấy mẫu, phát hiện bằng YOLO11n, theo vết bằng ByteTrack, mã hóa bằng RaSa. [Chỉ số 3] Máy
chủ Flask lo phân quyền và tìm kiếm. [Chỉ số 4] Dữ liệu nằm ở PostgreSQL, Milvus và MinIO.

### Slide 10 — Pipeline lập chỉ mục (0:30)

[Bấm sang slide 10] Bốn quyết định chính: chỉ một trong hai mươi khung hình đi vào Detector; mỗi kết quả là một
lần xuất hiện chứ không phải từng khung hình; mỗi lần xuất hiện giữ một khung hình đại diện; và chỉ tìm được khi
cả ba kho đã ghi xong.

### Slide 11 — Luồng tìm kiếm (0:30)

[Bấm sang slide 11] Truy vấn được kiểm tra rồi mã hóa thành vector. [Chỉ ngoặc cam] Milvus lọc theo khu vực,
camera và thời gian ngay trong truy vấn, nên top-k chỉ chọn trong phạm vi được phép; máy chủ còn kiểm tra lại
từng kết quả. Không dùng ngưỡng điểm, và điểm không được lưu.

### Slide 12 — Ba kho lưu trữ (0:20)

[Bấm sang slide 12] Ba kho liên kết qua cùng một track_id. [Chỉ hình phải] Một lần xuất hiện chỉ chuyển sang sẵn
sàng khi đã ghi đủ; ghi lỗi thì thử lại hoặc chuyển sang lỗi, không bao giờ hiện thành kết quả.

### Slide 13 — Giám sát viên tìm bằng ảnh (0:25)

[Bấm sang slide 13] Đây là màn hình tìm bằng ảnh: chỉ camera trong khu vực được giao, chọn bốn đến mười sáu kết
quả; người đeo ba lô cam kéo vali xuất hiện trên nhiều camera khác nhau.

### Slide 14 — Xem trong ngữ cảnh và lưu vụ việc (0:20)

[Bấm sang slide 14] Bấm vào kết quả để xem khung hình gốc có đánh dấu người, rồi lưu vào vụ việc mới hoặc vụ việc
đang xử lý.

### Slide 15 — Màn hình Quản lý (0:10)

[Bấm sang slide 15] Quản lý xem tổng quan toàn hệ thống và đọc mọi vụ việc, nhưng không sửa.

### Slide 16 — Quản trị viên chọn mô hình (0:15)

[Bấm sang slide 16] Quản trị viên chọn Detector và Tracker; hệ thống nạp thử mô hình trước khi áp dụng, còn bộ
mã hóa RaSa thì cố định.

### Slide 17 — Kiểm tra hoạt động AI (0:15)

[Bấm sang slide 17] Kiểm tra AI chạy trên khung hình thật của camera, báo kết quả và thời gian từng bước.
Các màn hình này em sẽ trình diễn trực tiếp trong phần demo.

### Slide 18 — Kiểm thử (0:20)

[Bấm sang slide 18] Hệ thống qua 713 kiểm thử đơn vị, 37 kiểm thử tích hợp, hai kiểm thử đầu cuối, kiểm thử giao
diện ở ba cỡ màn hình, và kịch bản demo chạy tự động hai lần đều đạt.

### Slide 19 — Hiệu năng (0:25)

[Bấm sang slide 19] Trên máy chỉ có CPU, xử lý chậm hơn thời gian thực khoảng bảy lần, nên các camera được xử lý
lần lượt. Tìm bằng ảnh mất khoảng 1,3 giây, bằng văn bản khoảng 0,1 giây; khi xử lý dùng khoảng 8 GiB bộ nhớ.

### Slide 20 — Chất lượng tìm kiếm (0:30)

[Bấm sang slide 20] Tìm bằng ảnh tốt: từ top tám mọi truy vấn đều có kết quả đúng. Tìm bằng văn bản và thuộc
tính thì chưa, do ảnh camera đông người khác xa dữ liệu huấn luyện của RaSa. [Chỉ ô xanh lá] Đây là điểm yếu
nhất, và là xuất phát điểm cho phần của bạn Cường. Em xin mời bạn Cường.

---

[**Bạn Cường trình bày phần II, từ slide 21.**]

[**Demo ứng dụng, 6 phút:** đặt ở vị trí mà nhóm thống nhất (sau phần II hoặc sau slide 17). Thao tác theo
`files/demo-script.md`, ưu tiên: tìm bằng ảnh → xem chi tiết → lưu vụ việc → Quản lý xem tổng quan → Quản trị
viên thêm camera RTSP, bật AI, kiểm tra AI.]

---

## Kết luận (0:40)

### Slide "Project timeline" — Quá trình thực hiện (0:15)

[Huy trình bày] Nhóm bắt đầu từ 15 tháng 6, qua bốn giai đoạn: phân tích và thiết kế, hiện thực, kiểm thử, rồi
báo cáo. Em làm ứng dụng, bạn Cường làm nghiên cứu; [chỉ các dòng Both] hai bạn cùng chốt pipeline chung từ đầu
và cùng viết phần chung của báo cáo.

### Slide "What the project achieved" — cột Part I (0:10)

[Huy nói cột trái] Phần ứng dụng đã hoàn chỉnh cho ba vai trò; tìm bằng ảnh tốt, tìm bằng văn bản là điểm yếu.

[Bạn Cường nói cột phải.]

### Slide "Limitations and future work" — cột Part I (0:10)

[Huy nói cột trái] Hướng phát triển là cải thiện tìm bằng văn bản và tăng tốc bằng OpenVINO hoặc GPU.

[Bạn Cường nói cột giữa và cột phải.]

### Slide "Thank you" — Cảm ơn (0:05)

[Bấm sang slide cảm ơn] Em xin cảm ơn quý Thầy Cô đã lắng nghe.

---

## Lưu ý khi luyện

- **Bấm giờ từng đoạn.** Nếu tập thử vẫn quá 8 phút, rút tiếp theo thứ tự: bỏ lời ở slide 15 và slide 16 (chỉ
  bấm qua, vì demo sẽ trình diễn), rồi gộp slide 12 vào một câu ở slide 11. Giữ nguyên slide 9, 11 và 20.
- **Số liệu phải đúng điều kiện:** Recall tìm bằng ảnh là lần đo sáu truy vấn ở ngưỡng 0,25; không nói "hệ thống
  chính xác 83 phần trăm" chung chung. Nếu Hội đồng hỏi, nói rõ điều kiện đo.
- **Không nói hệ thống chạy thời gian thực**, và không nói nhanh hơn các sản phẩm thương mại.
- **Không nói "đề xuất phương pháp mới"** ở phần ứng dụng; đóng góp của phần một là xây dựng ứng dụng và đánh
  giá mô hình có sẵn.
- **Chi tiết đã lược khỏi lời nói** (để trả lời khi bị hỏi): top-k chỉ nhận 4, 8, 12, 16; văn bản tiếng Việt bị
  từ chối; khung hình đại diện chọn trong tối đa ba ứng viên; Milvus được hỏi lại tối đa ba lượt khi thiếu kết
  quả; mỗi lần tải ảnh đều kiểm tra quyền; lấy mẫu N = 20 giảm khoảng một phần tư thời gian CPU so với N = 10.
