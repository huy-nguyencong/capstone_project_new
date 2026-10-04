# Lời thuyết trình (tiếng Việt) — phần của Nguyễn Công Huy, bản 8 phút

> Đi kèm `slides/HK253-DATN-078_2113499.pdf`. Số slide theo PDF sau khi thêm trang chuyển phần Introduction ở vị trí 3 (phần của Huy là slide 1–21). Phần kết luận (gồm
> slide "Project timeline") ghi theo tên slide vì số trang tùy cách ghép với slide của bạn Cường. Phần II (từ
> slide 22) và các cột Part II do bạn Cường trình bày nên không có ở đây.
>
> **Ngân sách thời gian (tổng 20 phút):** slide của Huy **khoảng 8 phút**, demo ở slide 59 do Huy trình diễn (mở đầu 1:38, Part I 5:40, kết
> luận 0:43) · demo ứng dụng **6 phút** · còn lại khoảng 6 phút cho bạn Cường và chuyển lời.
>
> **Cách đọc:** chữ trong ngoặc vuông `[...]` là thao tác, không đọc ra. Xưng "em", gọi "quý Thầy Cô". Tốc độ
> tham khảo khoảng 3 tiếng mỗi giây; mỗi đoạn đã được đếm để vừa thời gian ghi trong ngoặc.
>
> **Nguyên tắc rút gọn:** các màn hình (slide 13–17) sẽ được trình diễn lại trong phần demo, nên lời nói ở đó chỉ
> giữ một câu cho mỗi slide; chi tiết để dành cho demo.

---

## Mở đầu (1:38)

### Slide 1 — Bìa (0:10)

Em kính chào quý Thầy Cô. Em là Nguyễn Công Huy, cùng bạn Nguyễn Hữu Cường, xin trình bày đề tài "Phát triển
hệ thống tìm kiếm người dựa trên mô tả đa phương thức".

### Slide 2 — Outline (0:10)

Em trình bày phần mở đầu và phần ứng dụng; bạn Cường trình bày phần nghiên cứu cải thiện tìm
kiếm bằng văn bản.

### Slide 3 — Chuyển phần: Introduction (0:03)

Trước hết là phần mở đầu.

### Slide 4 — Bài toán (0:30)

Việt Nam ước tính có hơn hai mươi triệu camera giám sát, và khi có hình ảnh hữu ích, tỉ lệ
vụ việc được giải quyết tăng từ khoảng hai mươi lên năm mươi phần trăm. Nhưng tìm một người vẫn phải xem lại
video thủ công, trong khi thông tin ban đầu chỉ là một tấm ảnh hay vài câu mô tả. Câu hỏi là: người này xuất
hiện ở camera nào, lúc nào?

### Slide 5 — Mục tiêu và phạm vi (0:30)

Mục tiêu là xây dựng ứng dụng tìm người từ nhiều cách mô tả; hệ thống xếp hạng, người dùng
quyết định. Phần ứng dụng có năm mục tiêu, từ lập chỉ mục dữ liệu camera, tìm kiếm, lưu hồ sơ, phân quyền tới
đánh giá mô hình. Phạm vi: chỉ tìm người, truy vấn tiếng Anh, bảy camera giả lập bằng RTSP, chạy trên máy chỉ có
CPU.

### Slide 6 — "Đa phương thức" nghĩa là gì (0:25)

Người dùng có ba cách mô tả: một ảnh cắt sẵn, một câu tiếng Anh, hoặc chọn thuộc tính; thuộc
tính được ghép thành câu. Cả ba được mô hình RaSa đưa về cùng một không gian vector để so khớp với các lần xuất
hiện đã lập chỉ mục.

---

## Phần I — Ứng dụng (5:40)

### Slide 7 — Chuyển phần (0:05)

Sau đây là phần ứng dụng.

### Slide 8 — Các hệ thống liên quan (0:25)

Ba sản phẩm thương mại đều hỗ trợ tìm theo thuộc tính và ảnh, nhưng chỉ Verkada cho tìm bằng
câu mô tả, và cả ba gắn với GPU, thiết bị hoặc đám mây của hãng. Hệ thống của em gộp cả ba cách mô tả và chạy
tại chỗ với camera RTSP bất kỳ.

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
từng kết quả. Không dùng ngưỡng điểm, và điểm không được lưu.

### Slide 13 — Ba kho lưu trữ (0:20)

Ba kho liên kết qua cùng một track_id. [Chỉ hình phải] Một lần xuất hiện chỉ chuyển sang sẵn
sàng khi đã ghi đủ; ghi lỗi thì thử lại hoặc chuyển sang lỗi, không bao giờ hiện thành kết quả.

### Slide 14 — Giám sát viên tìm bằng ảnh (0:25)

Đây là màn hình tìm bằng ảnh: chỉ camera trong khu vực được giao, chọn bốn đến mười sáu kết
quả; người đeo ba lô cam kéo vali xuất hiện trên nhiều camera khác nhau.

### Slide 15 — Xem trong ngữ cảnh và lưu vụ việc (0:20)

Bấm vào kết quả để xem khung hình gốc có đánh dấu người, rồi lưu vào vụ việc mới hoặc vụ việc
đang xử lý.

### Slide 16 — Màn hình Quản lý (0:10)

Quản lý xem tổng quan toàn hệ thống và đọc mọi vụ việc, nhưng không sửa.

### Slide 17 — Quản trị viên chọn mô hình (0:15)

Quản trị viên chọn Detector và Tracker; hệ thống nạp thử mô hình trước khi áp dụng, còn bộ
mã hóa RaSa thì cố định.

### Slide 18 — Kiểm tra hoạt động AI (0:15)

Kiểm tra AI chạy trên khung hình thật của camera, báo kết quả và thời gian từng bước.
Các màn hình này em sẽ trình diễn trực tiếp trong phần demo.

### Slide 19 — Kiểm thử (0:20)

Hệ thống qua 713 kiểm thử đơn vị, 37 kiểm thử tích hợp, hai kiểm thử đầu cuối, kiểm thử giao
diện ở ba cỡ màn hình, và kịch bản demo chạy tự động hai lần đều đạt.

### Slide 20 — Hiệu năng (0:25)

Trên máy chỉ có CPU, xử lý chậm hơn thời gian thực khoảng bảy lần, nên các camera được xử lý
lần lượt. Tìm bằng ảnh mất khoảng 1,3 giây, bằng văn bản khoảng 0,1 giây; khi xử lý dùng khoảng 8 GiB bộ nhớ.

### Slide 21 — Chất lượng tìm kiếm (0:30)

Tìm bằng ảnh tốt: từ top tám mọi truy vấn đều có kết quả đúng. Tìm bằng văn bản và thuộc
tính thì chưa, do ảnh camera đông người khác xa dữ liệu huấn luyện của RaSa. [Chỉ ô xanh lá] Đây là điểm yếu
nhất, và là xuất phát điểm cho phần của bạn Cường. Em xin mời bạn Cường.

---

[**Bạn Cường trình bày phần II, từ slide 22.**]



---

## Kết luận (0:43)

### Slide "Conclusion" — Chuyển phần kết luận (0:03)

[Huy trình bày] Cuối cùng là phần kết luận.

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

### Slide 59 — Demo (6 phút)

> Rút gọn từ `files/demo-script.md` (mục 4) cho vừa 6 phút: giữ G2, G3, G4, G7, G8, Q1–Q2, A1, A2, A3, A6; bỏ
> G5 (Quản lý sẽ thấy lại vụ việc), G6 (gộp vào G7), A4 kiểm tra AI và A5 đổi mô hình (chờ gần 1 phút mỗi bước,
> đã có trên slide 17–18). Thứ tự Giám sát viên → Quản lý → Quản trị viên: bật AI để cuối, vì khi tiến trình nền
> đang chạy thì tìm bằng ảnh chậm từ khoảng 1,3 giây lên khoảng 8 giây.
>
> **Chuẩn bị:** làm đủ mục 3 của `files/demo-script.md` (khởi động, **làm nóng tìm kiếm bằng `WT-Q006.jpg`**).
> Mở sẵn ba cửa sổ đã đăng nhập: Edge thường `operator`, Edge InPrivate `viewer`, Chrome `admin` (khỏi mất thời
> gian đăng nhập). Để sẵn trên desktop: ảnh `WT-Q006.jpg`, một tệp ghi chú chứa câu truy vấn G7 và URL
> `rtsp://<IP>:8554/cam2` để dán.

**0:00–0:15 · Mở đầu** [cửa sổ `operator`, trang Tìm kiếm người]

Sau đây em xin trình diễn trực tiếp ứng dụng. Em đang đăng nhập với vai trò Giám sát viên của khu vực Gate A;
danh sách camera chỉ gồm các camera thuộc khu vực này.

**0:15–0:45 · Tìm bằng ảnh (G2)** [tab Hình ảnh → kéo `WT-Q006.jpg` vào ô ảnh → số kết quả 8 → Tìm kiếm]

Em tìm bằng một ảnh crop của người đội mũ len, mang túi hoa. Tám kết quả đều là người này, xuất hiện trên năm
camera khác nhau. Điểm chỉ dùng để xếp hạng, người dùng là người kết luận.

**0:45–1:05 · Xem chi tiết (G3)** [bấm kết quả #1 → bấm mũi tên sang #2]

Bấm vào một kết quả, hệ thống mở khung hình gốc có viền đánh dấu người, kèm camera, khu vực và thời gian xuất
hiện.

**1:05–1:40 · Lưu vụ việc (G4)** [Tạo vụ việc mới → tiêu đề `Tìm người mang túi hoa, giày trắng` → bật
**Đánh dấu vụ việc đã hoàn thành** → Tạo vụ việc → đóng cửa sổ]

Em lưu kết quả này vào một vụ việc mới và đánh dấu hoàn thành ngay khi lưu. Vụ việc hoàn thành sẽ bị khóa cho
tới khi mở lại.

**1:40–2:30 · Từ văn bản sang ảnh (G7)** [tab Văn bản → dán `A man carrying an orange backpack and pulling a
black suitcase.` → Tìm kiếm → sang tab Hình ảnh → kéo kết quả #1 vào ô ảnh → Tìm kiếm]

Với mô tả tiếng Anh, kết quả khoanh vùng được người đeo ba lô cam kéo vali. Thấy đúng người, em kéo kết quả đó
sang tìm bằng ảnh: lần này tám kết quả đều là người đó. Văn bản dùng để khoanh vùng, ảnh dùng để xác định chính
xác.

**2:30–3:00 · Tìm theo thuộc tính (G8)** [tab Thuộc tính → chọn `Woman`, `Coat`, `Black` → chỉ vào câu sinh ra
→ Tìm kiếm]

Với thuộc tính, em chỉ cần chọn; hệ thống ghép thành câu tiếng Anh "A woman wearing a black coat" rồi tìm như
văn bản.

**3:00–3:35 · Quản lý (Q1–Q2)** [chuyển sang cửa sổ `viewer` → Tổng quan → bấm Làm mới → mở vụ việc vừa tạo]

Ở vai trò Quản lý, trang tổng quan có số vụ việc theo trạng thái; vụ việc vừa tạo nằm đầu danh sách. Mở ra là
hồ sơ chỉ đọc, có ảnh kết quả và không có nút sửa.

**3:35–4:15 · Thêm camera RTSP (A1)** [chuyển sang cửa sổ `admin` → Camera → Thêm camera: mã `DEMO-RTSP`, tên
`Camera sảnh chính (RTSP)`, khu vực Gate A, dán URL → Lưu và kiểm tra RTSP]

Ở vai trò Quản trị viên, em thêm một camera RTSP vào khu vực Gate A và kiểm tra kết nối: camera trực tuyến.

**4:15–4:35 · Bật xử lý AI (A2)** [Xử lý AI → bật công tắc camera mới → Bật xử lý AI]

Em bật xử lý AI cho camera vừa thêm; cấu hình đang dùng là YOLO11n và ByteTrack.

**4:35–5:10 · Tiến trình nền tự xử lý (A3)** [Trạng thái hệ thống → nói trong lúc chờ → bấm Làm mới sau khoảng
15 giây]

Em không cần thao tác gì thêm: tiến trình nền tự nhận camera mới và bắt đầu xử lý luồng. Sau vài giây, camera
chuyển sang "Đang xử lý".

**5:10–5:35 · Nhật ký hệ thống (A6)** [Nhật ký hệ thống]

Các thao tác vừa thực hiện, từ tạo vụ việc, thêm camera đến bật AI, đều được ghi nhật ký kèm người thực hiện và
thời gian.

**5:35–6:00 · Kết thúc (A7, nếu còn thời gian)** [Xử lý AI → tắt công tắc camera mới]

Em tắt xử lý AI; dữ liệu đã phân tích vẫn được giữ nguyên. Phần trình diễn của em đến đây là hết.

**Nếu bị chậm:**
- Quá 3:15 mà chưa xong phần Giám sát viên: bỏ G8 (thuộc tính đã có trên slide 6).
- A3 sau 25 giây chưa lên "Đang xử lý": nói "tiến trình nền sẽ nhận camera trong vài chục giây" rồi chuyển sang
  A6, không đứng chờ.
- Tìm kiếm quay lâu: gần như chắc chắn là chưa làm nóng; chờ khoảng 1 phút rồi tìm lại.
- Máy hoặc mạng hỏng hẳn: chiếu video dự phòng (mục 2 của `files/demo-script.md`).

Sau mỗi lần tập: tắt API và worker, chạy `scripts/demo-reset.ps1` để xóa camera `DEMO-RTSP` và vụ việc vừa tạo.

### Slide 60 — Thank you (0:05)

Em xin cảm ơn quý Thầy Cô đã lắng nghe.

---

## Lưu ý khi luyện

- **Bấm giờ từng đoạn.** Nếu tập thử vẫn quá 8 phút, rút tiếp theo thứ tự: bỏ lời ở slide 16 và slide 17 (chỉ
  bấm qua, vì demo sẽ trình diễn), rồi gộp slide 13 vào một câu ở slide 12. Giữ nguyên slide 10, 12 và 21.
- **Số liệu phải đúng điều kiện:** Recall tìm bằng ảnh là lần đo sáu truy vấn ở ngưỡng 0,25; không nói "hệ thống
  chính xác 83 phần trăm" chung chung. Nếu Hội đồng hỏi, nói rõ điều kiện đo.
- **Không nói hệ thống chạy thời gian thực**, và không nói nhanh hơn các sản phẩm thương mại.
- **Không nói "đề xuất phương pháp mới"** ở phần ứng dụng; đóng góp của phần một là xây dựng ứng dụng và đánh
  giá mô hình có sẵn.
- **Chi tiết đã lược khỏi lời nói** (để trả lời khi bị hỏi): top-k chỉ nhận 4, 8, 12, 16; văn bản tiếng Việt bị
  từ chối; khung hình đại diện chọn trong tối đa ba ứng viên; Milvus được hỏi lại tối đa ba lượt khi thiếu kết
  quả; mỗi lần tải ảnh đều kiểm tra quyền; lấy mẫu N = 20 giảm khoảng một phần tư thời gian CPU so với N = 10.
