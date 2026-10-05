# Lời thuyết trình (tiếng Việt) — phần của Nguyễn Công Huy, bản 6,5 phút + video demo 5 phút

> Đi kèm `slides/HK253-DATN-078_2113499_2252098-Slides.pdf` (60 slide). Phần của Huy là slide 1–21 (mở đầu và
> Phần I), slide 55–58 (kết luận, cột Part I), slide 59 (video demo) và slide 60. Phần II (slide 22–54) và các
> cột Part II do bạn Cường trình bày nên không có ở đây. Cập nhật 2026-10-05 theo số liệu hiện hành của báo cáo.
>
> **Ngân sách thời gian (tổng 20 phút):**
>
> | Phần | Người nói | Thời gian |
> | --- | --- | --- |
> | Mở đầu, slide 1–6 | Huy | 1:38 |
> | Phần I, slide 7–21 | Huy | 4:25 |
> | Phần II, slide 22–54 | Cường | 6:00 |
> | Kết luận, slide 55–58 | Huy và Cường | 0:45 (phần của Huy) |
> | Video demo, slide 59 | Huy thuyết minh | 5:00 |
> | Chuyển lời, mở video, dự phòng | | khoảng 2:10 |
>
> **Cách đọc:** chữ trong ngoặc vuông `[...]` là thao tác, không đọc ra. Xưng "em", gọi "quý Thầy Cô". Tốc độ
> tham khảo khoảng 3 tiếng mỗi giây; thời gian trong ngoặc là ước lượng, cần bấm giờ lại khi tập.
>
> **Nguyên tắc rút gọn:** thầy hướng dẫn yêu cầu ưu tiên phần có đóng góp, không trình bày chi tiết mọi tính
> năng. Các màn hình (slide 14–18) đã có trong video demo, nên ở đó chỉ nói một câu rồi bấm qua. Thời gian dành
> cho kiến trúc, hai luồng xử lý (slide 10–12) và đánh giá (slide 20–21).

---

## Mở đầu (1:38)

### Slide 1 — Bìa (0:10)

Em kính chào quý Thầy Cô. Em là Nguyễn Công Huy, cùng bạn Nguyễn Hữu Cường, xin trình bày đề tài "Phát triển
hệ thống tìm kiếm người dựa trên mô tả đa phương thức".

### Slide 2 — Outline (0:10)

Em trình bày phần mở đầu và phần ứng dụng; bạn Cường trình bày phần nghiên cứu cải thiện tìm kiếm bằng văn
bản; cuối cùng là kết luận và video demo.

### Slide 3 — Chuyển phần: Introduction (0:03)

Trước hết là phần mở đầu.

### Slide 4 — Bài toán (0:30)

Việt Nam ước tính có hơn hai mươi triệu camera giám sát, và khi có hình ảnh hữu ích, tỉ lệ
vụ việc được giải quyết tăng từ khoảng hai mươi lên năm mươi phần trăm. Nhưng tìm một người vẫn phải xem lại
video thủ công, trong khi thông tin ban đầu chỉ là một tấm ảnh hay vài câu mô tả. Câu hỏi là: người này xuất
hiện ở camera nào, lúc nào?

### Slide 5 — Mục tiêu và phạm vi (0:25)

Mục tiêu là xây dựng ứng dụng tìm người từ nhiều cách mô tả; hệ thống xếp hạng, người dùng
quyết định. Phần ứng dụng có năm mục tiêu, từ lập chỉ mục dữ liệu camera, tìm kiếm, lưu hồ sơ, phân quyền tới
đánh giá mô hình. Phạm vi: chỉ tìm người, truy vấn tiếng Anh, bảy camera giả lập bằng RTSP, trên máy chỉ có CPU.

### Slide 6 — "Đa phương thức" nghĩa là gì (0:20)

Người dùng có ba cách mô tả: một ảnh cắt sẵn, một câu tiếng Anh, hoặc chọn thuộc tính để hệ thống ghép thành
câu. Cả ba được mô hình RaSa đưa về cùng một không gian vector để so khớp với các lần xuất hiện đã lập chỉ mục.

---

## Phần I — Ứng dụng (4:25)

### Slide 7 — Chuyển phần (0:05)

Sau đây là phần ứng dụng.

### Slide 8 — Các hệ thống liên quan (0:15)

Ba sản phẩm thương mại đều tìm được theo thuộc tính và ảnh, nhưng gắn với thiết bị hoặc đám mây của hãng. Hệ
thống của em gộp cả ba cách mô tả và chạy tại chỗ với camera RTSP bất kỳ.

### Slide 9 — Vai trò và phân quyền (0:25)

Có ba vai trò: Quản trị viên lo kỹ thuật, Giám sát viên tìm kiếm và lập vụ việc, Quản lý chỉ
đọc. [Chỉ ô dưới] Mỗi Giám sát viên có một khu vực; máy chủ lọc theo khu vực ngay trong truy vấn, trước khi chọn
kết quả.

### Slide 10 — Kiến trúc (0:35)

[Chỉ số 1] Bảy video WILDTRACK được phát thành bảy luồng RTSP. [Chỉ số 2] Tiến trình nền chạy
tách khỏi máy chủ: lấy mẫu, phát hiện bằng YOLO11n, theo vết bằng ByteTrack, mã hóa bằng RaSa. [Chỉ số 3] Máy
chủ Flask lo phân quyền và tìm kiếm. [Chỉ số 4] Dữ liệu nằm ở PostgreSQL, Milvus và MinIO.

### Slide 11 — Pipeline lập chỉ mục (0:30)

Bốn quyết định chính: chỉ một trong hai mươi khung hình đi vào Detector; mỗi kết quả là một
lần xuất hiện chứ không phải từng khung hình; mỗi lần xuất hiện giữ một khung hình đại diện; và chỉ tìm được khi
cả ba kho đã ghi xong.

### Slide 12 — Luồng tìm kiếm (0:30)

Truy vấn được kiểm tra rồi mã hóa thành vector. [Chỉ ngoặc cam] Milvus lọc theo khu vực,
camera và thời gian ngay trong truy vấn, nên top-k chỉ chọn trong phạm vi được phép; máy chủ còn kiểm tra lại
từng kết quả. Không dùng ngưỡng điểm, và điểm không được lưu. Riêng truy vấn văn bản có thêm một bước xếp hạng
lại tùy chọn, em sẽ nói ở phần đánh giá.

### Slide 13 — Ba kho lưu trữ (0:10)

Ba kho liên kết qua cùng một track_id; một lần xuất hiện chỉ tìm được khi cả ba kho đã ghi xong.

### Slide 14 — Giám sát viên tìm bằng ảnh (0:15)

Đây là màn hình tìm bằng ảnh của Giám sát viên: chỉ camera trong khu vực được giao, kết quả là các lần xuất
hiện trên nhiều camera.

### Slide 15, 16, 17 — Xem chi tiết, Quản lý, chọn mô hình (bấm qua, 0:05)

[Bấm qua ba slide, không nói.]

### Slide 18 — Kiểm tra hoạt động AI (0:10)

Các màn hình xem chi tiết, lưu vụ việc, Quản lý và Quản trị viên có trong video demo cuối buổi, nên em xin
lướt qua.

### Slide 19 — Kiểm thử (0:15)

Hệ thống qua 740 kiểm thử đơn vị, 37 kiểm thử tích hợp, hai kiểm thử đầu cuối, và kịch bản demo chạy tự động
hai lần đều đạt.

### Slide 20 — Hiệu năng (0:25)

Trên máy chỉ có CPU, xử lý chậm hơn thời gian thực khoảng bảy lần, nên các camera được xử lý
lần lượt. Tìm bằng ảnh mất khoảng 1,3 giây, bằng văn bản khoảng 0,1 giây. Khi đang xử lý, ứng dụng dùng khoảng
4,3 GiB bộ nhớ, nhờ bộ mã hóa chỉ nạp phần dùng cho suy luận.

### Slide 21 — Chất lượng tìm kiếm (0:45)

Trên 26 truy vấn, tìm bằng ảnh tốt: 23 truy vấn có kết quả đúng trong tám kết quả đầu. Tìm bằng văn bản và
thuộc tính chỉ bằng vector thì gần như không hiệu quả. [Chỉ ô Why] Em đo được hai nguyên nhân: độ chính xác của
RaSa nằm ở bước xếp hạng lại mà tìm kiếm vector không dùng, và ảnh camera khác xa dữ liệu huấn luyện. [Chỉ ô
xanh lá] Em cũng đo hai cách sửa: bật xếp hạng lại thì Recall ở top tám lên 0,42 nhưng mất 17 giây mỗi truy
vấn; đổi sang CLIP thì văn bản cũng đạt 0,42 nhưng tìm bằng ảnh kém hẳn. Bạn Cường nghiên cứu hướng thứ ba. Em
xin mời bạn Cường.

---

[**Bạn Cường trình bày Phần II, slide 22–54 (6 phút).**]

---

## Kết luận (0:45)

### Slide 55 — Chuyển phần kết luận (0:03)

[Huy trình bày] Cuối cùng là phần kết luận.

### Slide 56 — Project timeline (0:15)

[Huy trình bày] Nhóm bắt đầu từ 15 tháng 6, qua bốn giai đoạn: phân tích và thiết kế, hiện thực, kiểm thử, rồi
báo cáo. Em làm ứng dụng, bạn Cường làm nghiên cứu; [chỉ các dòng Both] hai bạn cùng chốt pipeline chung từ đầu
và cùng viết phần chung của báo cáo.

### Slide 57 — What the project achieved, cột Part I (0:12)

[Huy nói cột trái] Phần ứng dụng đã hoàn chỉnh cho ba vai trò; tìm bằng ảnh tốt, còn tìm bằng văn bản yếu khi
chỉ dùng vector và em đã đo hai cách khắc phục.

[Bạn Cường nói cột phải.]

### Slide 58 — Limitations and future work, cột Part I (0:15)

[Huy nói cột trái] Hạn chế chính là tìm bằng văn bản và tốc độ trên CPU. Hướng tiếp theo là làm nhanh bước xếp
hạng lại hoặc thêm một vector CLIP cho mỗi lần xuất hiện, và tăng tốc bằng OpenVINO hoặc GPU.

[Bạn Cường nói cột giữa và cột phải.]

---

## Slide 59 — Video demo (5:00)

> Video ghi trước theo mục 4.0 của `files/demo-script.md`, không lồng tiếng; Huy thuyết minh trực tiếp. Mỗi cảnh
> nói một ý chính, không đọc lại chữ trên màn hình. Mốc thời gian dưới đây theo thời lượng dự kiến của từng
> cảnh; sau khi dựng xong video, chỉnh lại mốc cho khớp và tập nói theo video ít nhất hai lần.
>
> **Trước giờ bảo vệ:** làm đủ mục 3 của `files/demo-script.md` (khởi động hệ thống, làm nóng tìm kiếm bằng
> `WT-Q006.jpg`) và để sẵn cửa sổ `operator` đã đăng nhập, phòng khi hội đồng muốn xem trực tiếp.

**Mở video (0:10)** [bấm phát video]

Sau đây là video demo ứng dụng, em ghi trước để kịp thời gian; hệ thống vẫn đang chạy trên máy nếu quý Thầy Cô
muốn xem trực tiếp.

**0:00–0:20 · Cảnh 1, phạm vi** [màn hình Tìm kiếm người của Giám sát viên]

Em đăng nhập với vai trò Giám sát viên của khu vực Gate A; danh sách camera chỉ gồm camera của khu vực này.

**0:20–1:40 · Cảnh 2, tìm bằng ảnh và xem chi tiết** [kéo ảnh vào ô, kết quả hiện ra, mở một kết quả]

Em tìm bằng một ảnh crop của người đội mũ len, mang túi hoa. Kết quả về sau hơn một giây: tám kết quả đều là
người này, trên năm camera khác nhau. Bấm vào một kết quả, hệ thống mở khung hình gốc có viền đánh dấu người,
kèm camera, khu vực và thời gian. Điểm chỉ dùng để xếp hạng, không có ngưỡng; người dùng là người kết luận.

**1:40–2:40 · Cảnh 3, văn bản khoanh vùng, ảnh xác định** [gõ câu mô tả, kéo kết quả #1 sang ô ảnh, tìm lại]

Khi chỉ có lời mô tả, em gõ một câu tiếng Anh. Kết quả văn bản chỉ khoanh vùng được người đeo ba lô cam kéo
vali. Thấy đúng người, em kéo kết quả đó sang ô ảnh và tìm lại: lần này tám kết quả đều là người đó. Văn bản
dùng để khoanh vùng, ảnh dùng để xác định.

> Cảnh 3 phải thử lại trước khi ghi hình (ghi chú 05/10 trong `files/demo-script.md`): số kết quả đúng của câu
> vali có thể đã đổi sau khi đổi bộ tách từ. Sửa lời theo kết quả thật trong video.

**2:40–3:30 · Cảnh 4, lưu vụ việc** [tạo vụ việc mới, mở Vụ việc của tôi]

Em lưu kết quả vào một vụ việc mới và đánh dấu hoàn thành; vụ việc hoàn thành bị khóa cho tới khi mở lại.
Trong Vụ việc của tôi, kết quả được lưu kèm camera, khu vực và thời gian.

**3:30–4:00 · Cảnh 5, Quản lý** [cửa sổ Quản lý: Tổng quan, mở vụ việc vừa tạo]

Ở vai trò Quản lý, trang tổng quan có vụ việc vừa tạo ở đầu danh sách; mở ra là hồ sơ chỉ đọc, không có nút
sửa hay tìm kiếm.

**4:00–5:00 · Cảnh 6, từ camera đến kết quả** [thêm camera RTSP, bật AI, phiên xử lý chạy, tìm trên camera mới]

Ở vai trò Quản trị viên, em thêm một camera RTSP vào khu vực Gate A, kiểm tra kết nối và bật xử lý AI. Tiến
trình nền tự nhận camera và xử lý luồng; đoạn này em tua nhanh vì máy chỉ có CPU chậm hơn thời gian thực khoảng
bảy lần. Khi phiên kết thúc, Giám sát viên tìm ngay được những người vừa đi qua camera này: từ luồng camera đến
kết quả tìm kiếm không cần thao tác tay nào. Phần demo của em đến đây là hết.

**Nếu có sự cố:**
- Hội đồng ngắt lời để hỏi: dừng video, trả lời, rồi phát tiếp.
- Video không phát được trong slide: mở tệp MP4 để sẵn trên desktop.
- Hội đồng muốn xem trực tiếp, hoặc cả hai cách phát đều lỗi: chuyển sang cửa sổ `operator` đã làm nóng, làm
  cảnh 2 (kéo `WT-Q006.jpg`, mở một kết quả) trong khoảng 30 giây. Các bước khác theo mục 4.1–4.3 của
  `files/demo-script.md`.
- Hết giờ: dừng sau cảnh 5 và nói một câu về cảnh 6.

### Slide 60 — Thank you (0:05)

Em xin cảm ơn quý Thầy Cô đã lắng nghe.

---

## Câu hỏi dự kiến

**Vì sao tìm bằng văn bản yếu?** Em đã kiểm tra để loại trừ lỗi hiện thực: trên chính dữ liệu CUHK-PEDES mà RaSa
được huấn luyện, tìm ảnh bằng ảnh đạt Recall ở hạng 1 là 1,0, còn tìm bằng văn bản chỉ bằng vector đạt Recall ở
top 10 là 0,18. Khi thêm bước xếp hạng lại trên 32 ứng viên, Recall ở hạng 1 tăng từ 0,05 lên 0,65. Vậy nguyên
nhân thứ nhất là độ chính xác công bố của RaSa nằm ở bước xếp hạng lại, không nằm ở vector. Nguyên nhân thứ hai
là khác biệt miền dữ liệu: kể cả ảnh cắt chọn tay từ WILDTRACK cũng chỉ đạt Recall ở top 16 là 0,19.

**Vì sao không bật xếp hạng lại mặc định?** Vì chi phí: mỗi ứng viên cần một lượt suy luận, nên 128 ứng viên
mất khoảng 17 giây và 64 ứng viên khoảng 9 giây trên CPU. Ứng dụng có bước này ở dạng tùy chọn. Để dùng hằng
ngày cần tính sẵn token ảnh lúc lập chỉ mục và chạy trên GPU, khi đó 128 ứng viên mất chưa tới một giây.

**Vì sao chọn RaSa mà không phải CLIP?** RaSa cho một vector phục vụ cả ba hình thức và là đề xuất của thầy hướng
dẫn. Sau đó em đo lại trên cùng dữ liệu: với ảnh, RaSa đạt 0,89 còn CLIP chỉ 0,35 đến 0,42; với văn bản thì
ngược lại, CLIP đạt 0,35 đến 0,42 còn vector RaSa đạt 0. Kết luận là một không gian vector dùng chung tốt cho
ảnh và kém cho văn bản; hướng hợp lý là giữ RaSa cho ảnh và thêm một vector kiểu CLIP cho văn bản.

**Vì sao ứng dụng dùng nhiều bộ nhớ (câu thầy đã hỏi về 8 GB)?** Lúc đầu ứng dụng dùng 7,9 GiB khi xử lý. Em tìm
ra ba nguyên nhân: checkpoint công bố của RaSa là bản huấn luyện 1,9 GB, chứa cả bản sao momentum và hàng đợi;
mã nạp khởi tạo trọng số ngẫu nhiên rồi mới chép checkpoint vào nên đỉnh bộ nhớ gần 4 GiB; và giao diện chạy
bằng máy chủ phát triển. Em sửa bằng cách chỉ nạp các phần dùng cho suy luận, mỗi bộ mã hóa giảm từ 2,2 xuống
0,9 GiB với vector giống hệt, và để máy chủ phục vụ bản build của giao diện. Hiện ứng dụng dùng 4,3 GiB khi xử
lý. Phần còn lại lớn nhất là máy chủ và tiến trình nền mỗi bên giữ một bản bộ mã hóa, khoảng 1 GiB mỗi bản.

**Hệ thống có chạy thời gian thực không?** Không. Trên máy chỉ có CPU, xử lý chậm hơn khoảng bảy lần, phần lớn
thời gian nằm ở bộ mã hóa ảnh, khoảng 1,85 giây mỗi lần xuất hiện. Vì vậy các camera được xử lý lần lượt. Hướng
tăng tốc là OpenVINO hoặc GPU.

**26 truy vấn có đủ tin cậy không?** Mỗi truy vấn tương ứng 3,8 điểm Recall, nên em báo kèm khoảng tin cậy 95%:
Recall ở top 8 của tìm bằng ảnh nằm trong khoảng 0,71 đến 0,96. Khoảng cách giữa ảnh và văn bản lớn hơn nhiều so
với độ rộng của khoảng này.

**Độ chính xác phát hiện 0,43 có thấp không?** Con số đó là cận dưới: nhãn của WILDTRACK chỉ bao phủ người trong
vùng quan tâm, còn camera thấy nhiều người hơn, nên phát hiện đúng những người không có nhãn bị tính là thừa.
Con số có ý nghĩa là độ phủ 0,64.

**Vì sao demo bằng video?** Để kịp 20 phút: một phiên xử lý luồng RTSP mất ba đến bốn phút. Hệ thống đang chạy
sẵn trên máy và em có thể thao tác trực tiếp.

---

## Lưu ý khi luyện

- **Bấm giờ từng đoạn.** Nếu phần slide vẫn quá 6,5 phút, rút tiếp theo thứ tự: bỏ lời slide 13, rút slide 8
  còn một câu, rút slide 9 còn câu về khu vực. Giữ nguyên slide 10, 12 và 21.
- **Số liệu phải đúng điều kiện:** Recall đo trên 26 truy vấn ở cấu hình hiện hành (ngưỡng tin cậy 0,1), tập
  1.526 lần xuất hiện. Nói "23 trên 26 truy vấn có kết quả đúng trong top 8", không nói "hệ thống chính xác 89
  phần trăm". Con số 0,42 của xếp hạng lại là với 128 ứng viên, đo ngoại tuyến.
- **Không nói hệ thống chạy thời gian thực**, và không nói nhanh hơn các sản phẩm thương mại.
- **Không nói "đề xuất phương pháp mới"** ở phần ứng dụng; đóng góp của Phần I là xây dựng ứng dụng hoàn chỉnh,
  đánh giá mô hình có sẵn và truy nguyên vì sao tìm bằng văn bản yếu.
- **Trên slide và trong báo cáo chỉ có số hiện hành** (4,3 GiB). Con số 7,9 GiB lúc đầu chỉ nêu khi được hỏi.
- **Chi tiết đã lược khỏi lời nói** (để trả lời khi bị hỏi): top-k chỉ nhận 4, 8, 12, 16; văn bản tiếng Việt bị
  từ chối; khung hình đại diện chọn trong tối đa ba ứng viên; Milvus được hỏi lại tối đa ba lượt khi thiếu kết
  quả; mỗi lần tải ảnh đều kiểm tra quyền; lấy mẫu N = 20 giảm khoảng một phần tư thời gian CPU so với N = 10;
  mốc thời gian của khung hình RTSP lấy từ dấu thời gian của luồng nên quy tắc kết thúc track không phụ thuộc
  tốc độ xử lý.
