# Hướng dẫn dựng slide bảo vệ (bản tiếng Anh, Canva)

> **Dùng để làm gì:** dựng slide trên Canva mà không phải tự nghĩ nội dung hay bố cục. Mỗi slide ghi sẵn
> layout, vị trí từng khối (tính bằng pixel trên khổ 1920×1080), chữ tiếng Anh để dán nguyên văn, hình
> cần chèn và người trình bày.
> **Nguồn nội dung:** báo cáo `report/thesis-en/` (bản gộp hai sinh viên). Mọi con số dưới đây lấy
> từ báo cáo; không tự sửa số khi dựng.
> **Thời lượng:** 20 phút, chưa tính demo và hỏi đáp. 33 slide chính (gồm 15b, 15c), 1 slide demo tùy chọn và các slide
> dự phòng.

---

## 0. Cách dùng tài liệu này

1. Làm Mục 1 trước (tạo khung Canva một lần), rồi dựng từng slide theo Mục 3.
2. Mỗi slide có các trường:
   - **Người nói / Thời gian**: Huy hay Cường trình bày, thời gian dự kiến.
   - **Layout**: một trong 7 mẫu ở Mục 1.4. Nhân bản trang mẫu tương ứng rồi thay nội dung.
   - **Nhãn phần**: dòng chữ nhỏ viết hoa phía trên tiêu đề.
   - **Tiêu đề**, **Nội dung**: dán nguyên văn phần trong khung trích dẫn (`>`).
   - **Hình**: đường dẫn tệp, vị trí `x, y` (góc trên trái), kích thước `rộng × cao`.
   - **Ý chính để nói**: một câu để nhớ khi trình bày. Câu này không đưa lên slide.
3. Đường dẫn hình tính từ thư mục gốc repo. Có hai thư mục:
   - `report/thesis-en/images/`: 11 ảnh chụp màn hình **đầy đủ** (2560×1440, đúng 16:9) và logo.
   - `report/thesis-en/figures/`: sơ đồ H1–H12, ảnh chụp màn hình **đã cắt** (`*-cat.png`), ảnh sản
     phẩm thương mại, và `figures/research/` (hình của Part II).
4. Trước khi dựng, tải tất cả các hình được nhắc trong Mục 2 lên mục **Uploads** của Canva.

---

## 1. Thiết lập khung Canva (làm một lần)

### 1.1. Tạo thiết kế

- Canva → **Create a design** → **Presentation (16:9)**, kích thước 1920 × 1080 px.
- Bật lưới: **File → Settings → Show rulers and guides**. Kéo các đường gióng sau:
  - dọc: `x = 80` và `x = 1840` (lề trái, phải);
  - ngang: `y = 64` (đỉnh nhãn phần), `y = 190` (đỉnh vùng nội dung), `y = 1000` (đáy vùng nội dung).

### 1.2. Màu (dán vào **Brand Kit** hoặc bảng màu của thiết kế)

| Tên | Mã | Dùng cho |
| --- | --- | --- |
| Nền | `#FFFFFF` | nền mọi slide nội dung |
| Nền phụ | `#F4F5FA` | thẻ, khung chữ, nền bảng xen kẽ |
| Viền | `#E3E5EF` | viền thẻ và khung hình 1 px |
| Chữ chính | `#1B1F3B` | tiêu đề, thân bài |
| Chữ phụ | `#5B6178` | chú thích, nguồn, chân trang |
| Nhấn Part I | `#6D5BD0` (tím, trùng màu giao diện PRISM) | nhãn phần, số thứ tự, viền nhấn của Mở đầu và Part I |
| Nhấn Part II | `#0F8B8D` (xanh mòng két) | nhãn phần, số, viền nhấn của Part II |
| Cảnh báo / hạn chế | `#D9822B` (cam) | ô hạn chế, kết quả xấu |
| Tốt | `#2E9E5B` (xanh lá) | kết quả tốt, "rescued" |
| Nền tối | `#1B1F3B` | slide bìa, slide chuyển phần, slide cảm ơn |

### 1.3. Chữ

| Vai trò | Font | Cỡ | Kiểu |
| --- | --- | --- | --- |
| Tiêu đề slide | Montserrat | 36 | Bold, màu chữ chính |
| Nhãn phần | Montserrat | 14 | Bold, viết hoa, giãn chữ 150, màu nhấn |
| Thân bài | Inter (hoặc Open Sans) | 22 (tối thiểu 18) | Regular; nhấn bằng Semibold |
| Chữ trong thẻ / bảng | Inter | 18–20 | |
| Chú thích, nguồn | Inter | 14 | màu chữ phụ |
| Số lớn | Montserrat | 64–80 | ExtraBold, màu nhấn |

### 1.4. Bảy layout mẫu

Dựng 7 trang mẫu dưới đây, đặt ở cuối thiết kế, rồi nhân bản (**Duplicate page**) khi cần. Mọi trang
nội dung (L3–L7) đều có:

- **Nhãn phần:** hộp chữ tại `x 80, y 64`, rộng 1200.
- **Tiêu đề:** hộp chữ tại `x 80, y 92`, rộng 1760, tối đa 1 dòng (cùng lắm 2 dòng).
- **Vạch nhấn:** hình chữ nhật 64 × 6 px, màu nhấn, tại `x 80, y 158`.
- **Chân trang:** trái `x 80, y 1030`: `PRISM · Capstone Project · HCMUT 2026` (14 pt, chữ phụ); phải
  `x 1840` canh phải: số trang (Canva: **Text → Page number**).
- **Vùng nội dung:** `x 80–1840`, `y 190–1000` (1760 × 810).

| Mã | Tên | Bố cục |
| --- | --- | --- |
| **L1** | Bìa | Nền tối toàn trang. Chữ trắng. Chi tiết ở Slide 1. |
| **L2** | Chuyển phần | Nền tối. Bên trái: số phần cỡ 120 (màu nhấn của phần) tại `x 160, y 360`; tên phần cỡ 56 trắng ngay dưới; tên người trình bày cỡ 24 màu `#B9BCD0`. Bên phải: 3–4 dòng "In this part" cỡ 22, tại `x 1000, y 380`. |
| **L3** | Chia đôi hình–chữ | Hình chiếm cột trái `x 80, rộng 1000`; chữ cột phải `x 1140, rộng 700`. Có thể lật (chữ trái, hình phải). |
| **L4** | Hình lớn + chú thích số | Hình lớn chiếm phần lớn vùng nội dung. Bên phải hoặc dưới là 3–4 chú thích, mỗi chú thích gồm vòng tròn 40 px màu nhấn có số trắng và 1–2 dòng chữ. Trên hình đặt vòng tròn cùng số tại chỗ cần chỉ. |
| **L5** | Thẻ | 3 hoặc 4 thẻ cùng cỡ xếp ngang, nền phụ, viền 1 px, bo góc 16, đệm trong 28. Mỗi thẻ: biểu tượng hoặc số ở trên, tiêu đề thẻ 22 Semibold, 2–4 dòng chữ 18. |
| **L6** | Bảng + kết luận | Bảng rộng 1760 ở trên (Canva: **Elements → Tables**). Hàng tiêu đề nền màu nhấn chữ trắng; hàng xen kẽ nền phụ. Dưới bảng là một ô kết luận rộng 1760, viền trái 6 px màu nhấn. |
| **L7** | Số lớn | 3 cột số lớn (mỗi cột rộng 560, cách nhau 40). Mỗi cột: số lớn, nhãn 20 Semibold, 1 dòng điều kiện đo 14 chữ phụ. |

### 1.5. Quy tắc chèn hình

- **Sơ đồ** (nền trắng): đặt trong thẻ nền trắng, viền 1 px `#E3E5EF`, bo góc 12, đệm 16 px. Không
  kéo méo: luôn kéo bằng góc, giữ tỉ lệ.
- **Ảnh chụp màn hình** (giao diện tối): bo góc 12, đổ bóng nhẹ (**Edit image → Shadows → Glow**, độ mờ
  thấp) hoặc viền 1 px.
- **Giao diện ứng dụng bằng tiếng Việt.** Slide tiếng Anh nên đặt nhãn chú thích tiếng Anh lên ảnh
  (vòng tròn số + chữ ở cột bên), và ghi một lần ở chân slide đầu tiên có ảnh giao diện:
  `UI language: Vietnamese (labels translated on the slide).`
- Kích thước ghi trong Mục 3 đã tính theo tỉ lệ thật của tệp. Nếu Canva hiển thị lệch vài pixel thì
  giữ tỉ lệ và canh theo `x, y`.

---

## 2. Danh sách hình sẽ dùng

| Tệp | Tỉ lệ | Slide chính | Ghi chú |
| --- | --- | --- | --- |
| `report/thesis-en/images/Logo_BK.png` | 1,10 | 1, 31 | |
| `report/thesis-en/images/H10a-tim-kiem-anh.png` | 16:9 | 13 | ảnh đầy đủ |
| `report/thesis-en/figures/H10c-chi-tiet-ket-qua-cat.png` | 1,95 | 1, 14 | dùng cắt nền cho bìa |
| `report/thesis-en/figures/H10d-tao-vu-viec-cat.png` | 1,09 | 14 | |
| `report/thesis-en/figures/H10f-tong-quan-cat.png` | 3,83 | 15 | |
| `report/thesis-en/figures/H10h-mo-hinh-ai-cat.png` | 2,31 | 15 | |
| `report/thesis-en/figures/H10k-kiem-tra-ai-cat.png` | 2,58 | 15 | |
| `report/thesis-en/figures/briefcam.png`, `avigilon.png`, `verkada.png` | 1,49 / 0,95 / 1,55 | 7 | |
| `report/thesis-en/figures/H2-kien-truc-slide.png` | 1,89 | 9 | bản ngang riêng cho slide; bản dọc `H2-kien-truc.png` chỉ dùng trong báo cáo |
| `report/thesis-en/figures/H3-luu-do-xu-ly-camera.png` | 1,17 | 10 | |
| `report/thesis-en/figures/S11-luong-tim-kiem.png` | 5,11 | 11 | chỉ dùng cho slide |
| `report/thesis-en/figures/S12-track-id.png` | 0,76 | 12 | chỉ dùng cho slide |
| `report/thesis-en/figures/H6-trang-thai-lan-xuat-hien.png` | 1,82 | 12 | |
| `report/thesis-en/figures/research/overall-000.png` | 1,74 | 19 | |
| `report/thesis-en/figures/research/offline-000.png` | 1,43 | 21 | |
| `report/thesis-en/figures/research/online_full-000.png` | 3,17 | 21 | |
| `report/thesis-en/figures/research/reasoning-000.png` | 1,86 | 23 | |
| `report/thesis-en/figures/research/case_rescued.png` | 0,95 | 26 | |

Hình chỉ dùng ở slide dự phòng: H1, H4, H5, H7, H8, H12, H10b, H10e, H10i, H10j, `zara-000.png`,
`selector-000.png`, `case_lost.png`, `case_lost_fixed.png`.

**Không dùng** `pruning_work-000.png` và `selector_work-000.png` cho tới khi bạn Cường sửa lỗi số liệu
trong hai hình này (ví dụ khối bằng chứng ghi "long 2/10, linkage 0.57" nhưng ghi chú viết "skirt 2/10,
0.65"; "Male 60 %, Female 60%"). Chi tiết ở `report/thesis-en/MERGE_NOTES.md` mục 4. Trên slide 22 và 24
các nội dung này được dựng lại bằng chữ, nên không cần hai hình.

---

## 3. Từng slide

### Phân bổ thời gian

| Phần | Slide | Người nói | Thời gian |
| --- | --- | --- | --- |
| Mở đầu | 1–5 | Huy | 2:40 |
| Part I: ứng dụng | 6–18 (gồm 15b, 15c) | Huy | 8:50 |
| Part II: tầng suy luận | 19–28 | Cường | 6:40 |
| Kết luận | 29–31 | chia theo cột (29, 30), cả hai (31) | 1:30 |
| **Tổng** | | | **≈ 19:40** (dư khoảng 20 giây) |
| Demo (tùy chọn) | 32 | | ngoài 20 phút |

---

### Slide 1 — Bìa

- **Người nói / Thời gian:** Huy · 0:20
- **Layout:** L1

**Bố cục**

- Nền tối `#1B1F3B`.
- Bên phải: ảnh `H10c-chi-tiet-ket-qua-cat.png` cắt lấy vùng khung hình toàn cảnh (Canva: **Crop**),
  đặt tại `x 1060, y 0`, cỡ `860 × 1080`, độ trong suốt 35%. Phủ lên một dải chuyển màu từ `#1B1F3B`
  (trái) sang trong suốt (phải) để chữ bên trái dễ đọc.
- Logo `Logo_BK.png` tại `x 80, y 64`, cao 96. Bên phải logo (tại `x 196, y 72`), hai dòng chữ 16 pt màu
  trắng.
- Dòng "CAPSTONE PROJECT" tại `x 80, y 270`, Montserrat Bold 24, giãn chữ 200, màu `#A99CF0` (tím nhạt).
  Ngay dưới là vạch nhấn 64 × 6 px màu tím tại `y 312`.
- Tên đề tài tại `x 80, y 340`, rộng 1000, Montserrat ExtraBold 48, trắng, tối đa 3 dòng.
- Dòng ngành học ngay dưới tên đề tài (khoảng `y 560`), cỡ 22, màu `#B9BCD0`.
- Khối thông tin tại `x 80, y 700`, hai cột: trái (rộng 480) cho giảng viên và hội đồng, phải (rộng 480)
  cho sinh viên. Cỡ 20, trắng.
- Dòng cuối tại `x 80, y 980`, cỡ 16, màu `#B9BCD0`.

**Nội dung**

> HO CHI MINH CITY UNIVERSITY OF TECHNOLOGY
> Faculty of Computer Science and Engineering
>
> CAPSTONE PROJECT
> **DEVELOPING A PERSON SEARCH SYSTEM FROM MULTIMODAL DESCRIPTIONS**
> Major: Computer Science
>
> Supervisor: Dr. Le Thanh Sach
> Reviewer: Dr. Tran Tuan Anh
> Council: 1CC
>
> Nguyen Cong Huy — 2113499
> Nguyen Huu Cuong — 2252098
>
> Semester 253, Academic Year 2025–2026 · Ho Chi Minh City, October 2026

**Ý chính để nói:** chào Hội đồng, giới thiệu đề tài, hai thành viên và cách chia hai phần.

---

### Slide 2 — Outline

- **Người nói / Thời gian:** Huy · 0:15
- **Layout:** L5 (4 thẻ)
- **Nhãn phần:** `OUTLINE`
- **Tiêu đề:** `Outline`

**Bố cục:** 4 thẻ ngang, mỗi thẻ `410 × 420`, bắt đầu `x 80, y 300`, cách nhau 40. Trên mỗi thẻ là số
lớn 56 (thẻ 1–2 và 4 màu tím, thẻ 3 màu mòng két). Dưới thẻ, tên người trình bày cỡ 16 chữ phụ.

**Nội dung**

> **01 · Introduction** — Problem, objectives and scope · *Both*
> **02 · Part I: The Application** — Design, implementation and evaluation of PRISM · *Nguyen Cong Huy*
> **03 · Part II: Semantic Reasoning** — An LLM reasoning layer that re-ranks text-based search · *Nguyen Huu Cuong*
> **04 · Conclusion** — Results, limitations and future work · *Both*

---

### Slide 3 — Problem

- **Người nói / Thời gian:** Huy · 0:45
- **Layout:** L7 biến thể (2 số lớn bên trái, chữ bên phải)
- **Nhãn phần:** `INTRODUCTION`
- **Tiêu đề:** `Finding one person in hours of surveillance video`

**Bố cục**

- Cột trái `x 80, rộng 760`: hai khối số lớn xếp dọc, khối 1 tại `y 230`, khối 2 tại `y 520`. Mỗi khối
  gồm số 72 màu tím và nhãn 20 bên dưới. Nguồn 14 chữ phụ tại `y 900`.
- Cột phải `x 940, rộng 900`: 3 gạch đầu dòng 22 pt tại `y 240`; dưới cùng là ô câu hỏi tại
  `y 760`, cỡ `900 × 160`, nền phụ, viền trái 6 px tím, chữ 24 Semibold.

**Nội dung, cột trái**

> **> 20 million**
> surveillance cameras estimated in use in Vietnam by 2025
>
> **20% → 50%**
> share of cases solved when useful camera footage is available
>
> *Sources: VnExpress (2024), citing the General Department of Customs; Ashby (2017), 251,195 incidents, British Transport Police.*

**Nội dung, cột phải**

> - Reviewing every video of every camera by hand is slow and misses things
> - The first information is often only **an image**, **a sentence** or **a few clothing features**
> - Many users and many areas: access must be limited, and results must be kept as case files
>
> **Which camera, and at what time, did this person appear?**

**Ý chính để nói:** giá trị của camera nằm ở chỗ tìm lại được đúng đoạn hình; đó là bài toán của đề tài.

---

### Slide 4 — Objectives and scope

- **Người nói / Thời gian:** Huy · 0:45
- **Layout:** L5 (2 thẻ lớn) + dải phạm vi
- **Nhãn phần:** `INTRODUCTION`
- **Tiêu đề:** `Objectives and scope`

**Bố cục**

- Câu mục tiêu tổng quát tại `x 80, y 200`, rộng 1760, cỡ 22.
- Hai thẻ lớn tại `y 290`, mỗi thẻ `860 × 450`: thẻ trái viền trên 6 px tím (Part I), thẻ phải viền trên
  6 px mòng két (Part II).
- Dải phạm vi tại `y 780`, rộng 1760: tiêu đề "Scope" 18 Semibold, sau đó 6 "chip" (hộp bo tròn nền
  phụ, chữ 16) xếp ngang, tự xuống dòng.

**Nội dung**

> **Overall objective:** build an application that searches for people in camera data from several forms of description. The system proposes and ranks; the user decides.
>
> **Part I — The application**
> 1. Turn camera data into searchable appearances
> 2. Search by image, English sentence or attributes
> 3. Review results in context and save them into case files
> 4. Role- and area-based access, administration and monitoring
> 5. Assess existing AI models on commodity hardware
>
> **Part II — The research**
> 6. Study a reasoning layer that re-ranks text-based search from readable attribute evidence, and measure what it gains and what it costs
>
> **Scope:** People only, no face recognition · English queries only · 7 simulated RTSP cameras (WILDTRACK) · Cameras processed in turn · Existing models, no training · One CPU-only laptop

**Ý chính để nói:** Part I là ứng dụng hoàn chỉnh; Part II là nghiên cứu độc lập, chưa tích hợp vào ứng dụng.

---

### Slide 5 — What "multimodal" means

- **Người nói / Thời gian:** Huy · 0:35
- **Layout:** sơ đồ tự vẽ trong Canva
- **Nhãn phần:** `INTRODUCTION`
- **Tiêu đề:** `Three forms of description, one vector space`

**Bố cục (vẽ bằng Shapes và Lines của Canva)**

- Cột 1 (`x 80`, rộng 380): 3 hộp đầu vào xếp dọc tại `y 240`, `y 460`, `y 680`, mỗi hộp `380 × 160`,
  nền phụ, bo góc 16.
  - Hộp 1 "Image": chèn một ảnh crop nhỏ (cắt một người từ `images/H10a-tim-kiem-anh.png`, ô ảnh truy
    vấn bên trái), cao 120.
  - Hộp 2 "Sentence": chữ nghiêng `"A woman with long blonde hair wearing a black jacket."`
  - Hộp 3 "Attributes": 3 chip `Woman`, `Coat`, `Black`.
- Cột 2 (`x 560, y 680`): hộp `Prompt builder` (`300 × 160`) chỉ nối với hộp 3; dòng thứ hai trong hộp
  là câu sinh ra `"A woman wearing a black coat."`; từ hộp này có mũi tên tới `Text encoder`.
- Cột 3 (`x 980`): hai hộp mô hình `Image encoder` và `Text encoder` (`300 × 120`, viền tím). Biểu tượng
  bộ não (Canva: tìm "brain icon") đặt bên trái mỗi hộp.
- Cột 4 (`x 1400`): hình tròn đường kính 360 nền tím nhạt `#ECE9FB`, chữ ở giữa:
  `One 256-d vector space (RaSa)`. Bên trong vẽ khoảng 10 chấm nhỏ đại diện cho các appearance đã lập
  chỉ mục, và một chấm lớn màu cam cho truy vấn.
- Dòng chú thích dưới cùng tại `y 900`, cỡ 18.

**Nội dung, dòng chú thích**

> All three forms are encoded into the same space and compared with the vectors of the indexed appearances. Attributes are only a prompt builder: they become an English sentence for the text encoder.

**Ý chính để nói:** "đa phương thức" ở đây là ba cách mô tả, cùng đi vào một không gian vector.

---

### Slide 6 — Part I divider

- **Người nói / Thời gian:** Huy · 0:05
- **Layout:** L2 (màu nhấn tím)

**Nội dung** (số lớn bên trái là `I`)

> **Part I**
> The Person Search Application
> Nguyen Cong Huy
>
> In this part: related systems · analysis and design · implementation · testing and evaluation

---

### Slide 7 — Related systems

- **Người nói / Thời gian:** Huy · 0:40
- **Layout:** L5 (3 cột) + bảng nhỏ
- **Nhãn phần:** `PART I · RELATED SYSTEMS`
- **Tiêu đề:** `What commercial systems offer`

**Bố cục**

- 3 cột tại `y 200`, mỗi cột rộng 560, cách nhau 40.
- Mỗi cột: ảnh sản phẩm trong khung, cao 220 (BriefCam `328 × 220`, Avigilon `209 × 220`, Verkada
  `341 × 220`), canh giữa cột; dưới ảnh là tên sản phẩm 22 Semibold và 2 dòng mô tả 18.
- Bảng so sánh tại `y 640`, rộng 1760, 5 cột × 4 hàng. Hàng "PRISM" nền `#ECE9FB`, chữ đậm.
- Nguồn 14 pt tại `y 980`.

**Nội dung, ba cột**

> **BriefCam** — attribute filters and similar-appearance search; requires an NVIDIA GPU server
> **Avigilon Appearance Search** — search from an uploaded image or a sample in the video; vendor software and devices
> **Verkada AI-Powered Search** — free-text search with a CLIP-style shared space; vendor cloud

**Nội dung, bảng**

| | Attributes | Image | Free text | Deployment |
| --- | --- | --- | --- | --- |
| BriefCam | Yes | Sample in video | Not mentioned | On premises or cloud, NVIDIA GPU |
| Avigilon | Yes | Yes | Not mentioned | Vendor software and devices |
| Verkada | Yes | Yes | Yes | Vendor cloud |
| **PRISM** | **Yes** | **Yes** | **Yes (English)** | **On premises, no discrete GPU, any RTSP camera** |

> *Sources: vendors' official documentation (report Section 2.1).*

**Ý chính để nói:** cả ba hình thức mô tả đã là xu hướng; PRISM gom chúng vào một cơ chế và chạy tại chỗ. Không so sánh độ chính xác vì các hãng không công bố.

---

### Slide 8 — Users and access control

- **Người nói / Thời gian:** Huy · 0:40
- **Layout:** L5 (3 thẻ) + ô quy tắc
- **Nhãn phần:** `PART I · ANALYSIS`
- **Tiêu đề:** `Three roles, data limited by area`

**Bố cục**

- 3 thẻ tại `y 210`, mỗi thẻ `560 × 470`. Trên mỗi thẻ là biểu tượng người (Canva: "user icon") màu tím
  cao 64, sau đó tên vai trò 24 Semibold, tên trên giao diện 16 chữ phụ, rồi 3 gạch đầu dòng 18.
- Ô quy tắc tại `y 720`, `1760 × 230`, nền phụ, viền trái 6 px tím; bên trong 3 dòng 20.

**Nội dung**

> **Administrator** *(Quản trị viên)*
> - Accounts, cameras, RTSP, AI on/off
> - Detector/Tracker choice, status, AI diagnostics, audit log
> - No person search by default
>
> **Operator** *(Giám sát viên)*
> - Searches by image, text or attributes
> - Reviews results, saves them into cases
> - Owns their cases (Open / Closed)
>
> **Viewer** *(Quản lý)*
> - System-wide dashboard
> - Reads every case
> - Read-only
>
> **Area rule:** each Operator has exactly one surveillance area. The server takes the area from the session, filters the vector search **before** taking the top-k, and checks every image request. Requests for cameras outside the area are rejected.

**Ý chính để nói:** quyền kiểm tra ở backend cho từng request, không dựa vào việc ẩn trên giao diện.

---

### Slide 9 — Architecture

- **Người nói / Thời gian:** Huy · 0:55
- **Layout:** L4
- **Nhãn phần:** `PART I · DESIGN`
- **Tiêu đề:** `Architecture: AI worker separated from the application server`

**Bố cục**

- Dùng bản **nằm ngang dành cho slide** `figures/H2-kien-truc-slide.png` (tỉ lệ 1,59), không dùng
  `H2-kien-truc.png` của báo cáo (bản dọc, chèn vào slide ngang thì chữ chỉ còn khoảng một nửa). Nguồn:
  `figures/H2-kien-truc-slide.drawio`, sinh bằng `report/tools-en/h2_architecture_slide_drawio.py`;
  muốn chỉnh thì mở `.drawio`, sửa rồi xuất lại PNG (Zoom 200%, Border 20).
- Hình có đủ mọi khối, nhãn đầu ra và mũi tên của H2 trong báo cáo (đã đối chiếu từng mục); pipeline
  của tiến trình nền đi thành hai hàng: lấy mẫu → phát hiện → theo vết → bộ đệm track, rồi quay ngược
  sang trái: mã hóa ảnh → ghi dữ liệu.
- Hình tại `x 80, y 190`, cỡ `1290 × 810`, **không** đặt trong thẻ có viền (hình đã có các khung nét đứt).
- 4 vòng tròn số đặt ngay sau tên mỗi khung: (1) `x 270, y 191` sau "Camera data source"; (2) `x 282, y 381`
  sau "Background AI worker"; (3) `x 1245, y 385` trên thanh "Application server (Flask API)";
  (4) `x 210, y 839` sau "Storage layer".
- Cột chú thích tại `x 1410`, rộng 430, bắt đầu `y 230`, cách nhau 190; mỗi chú thích là vòng tròn số,
  tiêu đề 20 Semibold và 1–2 dòng 17 chữ phụ.

**Nội dung, chú thích**

> **1 · Simulated cameras** — 7 WILDTRACK videos as 7 RTSP streams; uploaded files are the fallback
> **2 · AI worker** — sample, detect, track, encode; one camera at a time
> **3 · Flask API** — access control, search, cases; same RaSa model for queries
> **4 · Three stores** — PostgreSQL, MinIO, Milvus linked by one `track_id`

**Ý chính để nói (theo thứ tự số):** (1) 7 video WILDTRACK được FFmpeg + MediaMTX phát thành 7 luồng
RTSP; tệp video tải lên là đường dự phòng. (2) Tiến trình nền lấy mẫu, phát hiện, theo vết, mã hóa, xử lý
từng camera một. (3) Máy chủ Flask lo xác thực, phân quyền, tìm kiếm, vụ việc; mã hóa truy vấn bằng cùng
mô hình RaSa. (4) PostgreSQL, Milvus, MinIO liên kết qua cùng một `track_id`. Ý chung: tách xử lý AI dài
khỏi request của API.

---

### Slide 10 — Indexing pipeline

- **Người nói / Thời gian:** Huy · 0:50
- **Layout:** L3 (hình trái)
- **Nhãn phần:** `PART I · DESIGN`
- **Tiêu đề:** `From a video stream to searchable appearances`

**Bố cục**

- Hình `figures/H3-luu-do-xu-ly-camera.png` tại `x 80, y 200`, cỡ `936 × 800`, trong thẻ trắng.
- Cột phải `x 1080`, rộng 760: 4 khối quyết định, mỗi khối có tiêu đề 20 Semibold màu tím và 1–2 dòng 18,
  cách nhau 30.

**Nội dung, cột phải**

> **Sample before detecting** — only 1 frame in every N (N = 20 by default) reaches the Detector and Tracker.
> **One result = one appearance** — a track of one person on one camera, not one frame. No duplicate results from consecutive frames.
> **One representative frame** — chosen by a quality score among at most 3 candidates; the person crop is never stored, it is cut on the fly from frame + box.
> **Consistent writes** — PENDING → READY: an appearance is searchable only after PostgreSQL, MinIO and Milvus are all written.

**Ý chính để nói:** bốn quyết định thiết kế giữ dữ liệu gọn và nhất quán.

---

### Slide 11 — Search flow

- **Người nói / Thời gian:** Huy · 0:45
- **Layout:** hình sơ đồ + 3 thẻ
- **Nhãn phần:** `PART I · DESIGN`
- **Tiêu đề:** `Search: filter by permission first, then rank`

**Bố cục**

- Hình `figures/S11-luong-tim-kiem.png` (tỉ lệ 5,11) tại `x 80, y 250`, cỡ `1760 × 344`, không đặt trong
  thẻ có viền. Nguồn: `figures/S11-luong-tim-kiem.drawio`, sinh bằng
  `report/tools-en/slide11_search_flow_drawio.py`; muốn chỉnh thì mở `.drawio`, sửa rồi xuất lại PNG
  (Zoom 200%, Border 20). Hình gồm đầu vào, 5 bước, đầu ra; trên mỗi bước có ký hiệu thành phần thực
  hiện (máy chủ Flask, bộ não RaSa, hình trụ PostgreSQL, hình trụ viền đậm Milvus); bước 3 và 4 viền cam,
  có ngoặc cam kèm chữ `filtered inside the search, before top-k`.
- Dưới hình, tại `y 660`, ba thẻ nhỏ `560 × 200` (L5), mỗi thẻ một tiêu đề và một dòng (gõ trong Canva).

**Nội dung trong hình, 5 bước** (đã có sẵn trong ảnh; bám theo code `api/v1/searches.py`,
`services/searches.py`, `services/track_search.py`)

> **1 Validate** — top-k, English text, image type
> **2 Encode** — RaSa → 256-d vector
> **3 Resolve scope** — cameras of the Operator's area
> **4 Vector search** — Milvus, inner product
> **5 Re-check** — READY and still in scope

**Nội dung, 3 thẻ**

> **No score threshold** — top-k only; the user decides.
> **Score not stored** — it exists in this search only.
> **Images re-checked** — every image request is authorised.

**Ý chính để nói (chi tiết không ghi lên slide):**
1. Kiểm tra top-k ∈ {4, 8, 12, 16}, văn bản chỉ nhận tiếng Anh, ảnh JPEG/PNG.
2. Thuộc tính được ghép thành câu tiếng Anh; ảnh hoặc câu qua RaSa thành vector 256 chiều.
3. Lấy các camera đang vận hành trong khu vực của Giám sát viên; chọn camera ngoài khu vực thì bị từ chối.
4. Milvus lọc khu vực, camera, thời gian **ngay trong truy vấn** rồi xếp hạng theo tích vô hướng, nên top-k
   chỉ chọn trong phạm vi được phép, không phải lấy rồi mới xóa bớt.
5. Máy chủ kiểm tra lại từng kết quả ở PostgreSQL (track `READY`, camera còn vận hành, còn thuộc khu vực);
   thiếu so với top-k thì hỏi lại Milvus với giới hạn gấp đôi, tối đa 3 lượt.
Ảnh crop và khung hình đầy đủ được tải bằng request riêng, mỗi request kiểm tra quyền lại.

---

### Slide 12 — Data across three stores

- **Người nói / Thời gian:** Huy · 0:35
- **Layout:** L3 (hai hình cạnh nhau)
- **Nhãn phần:** `PART I · DESIGN`
- **Tiêu đề:** `One track_id links three stores`

**Bố cục**

- Trái: hình `figures/S12-track-id.png` (cột hẹp, tỉ lệ 0,76) tại `x 80, y 230`, cỡ `489 × 640`, không đặt
  trong thẻ có viền. Nguồn: `figures/S12-track-id.drawio`, sinh bằng
  `report/tools-en/slide12_track_id_drawio.py`. Ô `track_id` màu tím ở góc trên, trục dọc bên trái rẽ vào ba
  kho xếp chồng; ký hiệu giống H2 (PostgreSQL hình trụ viền mảnh, MinIO hình xô, Milvus hình trụ viền đậm).
- Phải: hình `figures/H6-trang-thai-lan-xuat-hien.png` (tỉ lệ 1,82) tại `x 660, y 230`, cỡ `1180 × 647`.
- Dưới H6: khối chữ tại `x 660, y 905`, rộng 1180 (gõ trong Canva): tiêu đề in đậm và một câu, cỡ 19, tối
  đa 2 dòng.

**Nội dung trong hình bên trái** (đã có sẵn trong ảnh)

> **PostgreSQL** — accounts, areas, cameras, appearances, cases, audit log, job queue
> **MinIO** — one representative frame per appearance (~358 KB)
> **Milvus** — one 256-d RaSa vector + area, camera, time

**Nội dung, khối chữ dưới H6**

> **Searchable only when READY.** Writes go through an outbox with retries and reconciliation; a failed write never shows up as a search result.

---

### Slide 13 — Operator: search by image

- **Người nói / Thời gian:** Huy · 0:35
- **Layout:** L4
- **Nhãn phần:** `PART I · IMPLEMENTATION`
- **Tiêu đề:** `Operator: search by image`

**Bố cục**

- Ảnh `images/H10a-tim-kiem-anh.png` tại `x 80, y 190`, cỡ `1424 × 801`.
- Vòng tròn số trên ảnh: (1) ô ảnh truy vấn bên trái; (2) danh sách camera trong khu vực; (3) nhóm nút số
  kết quả 4/8/12/16; (4) lưới kết quả; (5) ô "Khu vực giám sát Gate A" góc trên phải.
- Chú thích tại `x 1540`, rộng 300, từ `y 220`, mỗi chú thích 2–3 dòng 16.
- Chân slide: `UI language: Vietnamese (labels translated on the slide).`

**Nội dung, chú thích**

> **1** Query image: pick, drag-and-drop, paste, or drag a result back in
> **2** Only cameras of the Operator's area
> **3** Number of results: 4 / 8 / 12 / 16
> **4** Ranked appearances, person boxed, surroundings dimmed
> **5** Assigned area, fixed by the server

**Ý chính để nói:** cùng một người kéo vali xuất hiện trên nhiều camera khác nhau.

---

### Slide 14 — Review in context and save a case

- **Người nói / Thời gian:** Huy · 0:35
- **Layout:** L3 (hình trái)
- **Nhãn phần:** `PART I · IMPLEMENTATION`
- **Tiêu đề:** `Review in the original frame, then save to a case`

**Bố cục**

- Ảnh `figures/H10c-chi-tiet-ket-qua-cat.png` tại `x 80, y 210`, cỡ `1170 × 600`.
- Cột phải `x 1300`, rộng 540: ảnh `figures/H10d-tao-vu-viec-cat.png` cỡ `400 × 367` tại `y 210`; dưới ảnh
  3 gạch đầu dòng 18 tại `y 610`.

**Nội dung, cột phải**

> - Full frame with the person boxed, camera, area, time and score
> - **Create a new case** or **add to an existing case** (only the Operator's open cases)
> - Option to mark the case **Closed** when saving; a closed case is locked until reopened

---

### Slide 15 — Viewer dashboard

- **Người nói / Thời gian:** Huy · 0:20
- **Layout:** L4 (một ảnh lớn + thẻ)
- **Nhãn phần:** `PART I · IMPLEMENTATION`
- **Tiêu đề:** `Viewer: system-wide overview, read-only`

**Bố cục**

- Ảnh `figures/H10f-tong-quan-cat.png` (tỉ lệ 3,83) tại `x 80, y 210`, cỡ `1760 × 460`, toàn bề ngang.
- 3 vòng tròn số trên ảnh: (1) `x 1096, y 340` ngay bên phải bốn ô số đếm; (2) `x 238, y 426` cạnh chữ
  "Vụ việc gần đây"; (3) `x 860, y 462` trên cột "Trạng thái".
- Dưới ảnh, tại `y 720`, ba thẻ `560 × 220` (L5), mỗi thẻ bắt đầu bằng vòng tròn số tương ứng.

**Nội dung, 3 thẻ**

> **1 Counters** — total cases, saved results, open and closed cases
> **2 Recent cases** — owner, status, number of results, last update
> **3 Read-only** — the Viewer opens every case but cannot edit or search

---

### Slide 15b — Administrator: AI model configuration

- **Người nói / Thời gian:** Huy · 0:25
- **Layout:** L4
- **Nhãn phần:** `PART I · IMPLEMENTATION`
- **Tiêu đề:** `Administrator: choose Detector and Tracker`

**Bố cục**

- Ảnh `figures/H10h-mo-hinh-ai-cat.png` (tỉ lệ 2,31) tại `x 80, y 200`, cỡ `1500 × 650`.
- 4 vòng tròn số trên ảnh: (1) `x 161, y 285` sau chữ "Detector"; (2) `x 900, y 285` sau chữ "Tracker";
  (3) `x 590, y 700` trong khung "Thành phần cố định"; (4) `x 1395, y 796` cạnh nút "Áp dụng cấu hình".
- Cột chú thích tại `x 1620`, rộng 220, bắt đầu `y 230`, cách nhau 150; mỗi chú thích là vòng tròn số và
  2–3 dòng chữ 17.
- Dòng cuối tại `x 80, y 890`, rộng 1760, chữ 17 màu chữ phụ.
- Chân slide: `UI language: Vietnamese (labels translated on the slide).`

**Nội dung, chú thích**

> **1** Detector from the registry; unavailable models greyed out
> **2** Tracker: ByteTrack or BoT-SORT
> **3** RaSa encoders fixed, not configurable
> **4** Apply: models are loaded and checked first

**Nội dung, dòng cuối**

> Other Administrator screens: cameras and RTSP check · AI on/off · system status · audit log

---

### Slide 15c — Administrator: AI diagnostics

- **Người nói / Thời gian:** Huy · 0:20
- **Layout:** L4 (ảnh toàn bề ngang + hàng chú thích)
- **Nhãn phần:** `PART I · IMPLEMENTATION`
- **Tiêu đề:** `Administrator: check the AI pipeline on a real camera`

**Bố cục**

- Ảnh `figures/H10k-kiem-tra-ai-cat.png` (tỉ lệ 2,58) tại `x 80, y 200`, cỡ `1760 × 682`.
- 4 vòng tròn số trên ảnh: (1) `x 925, y 300` ở mép phải thẻ "Camera Processing Pipeline"; (2) `x 565, y 470`
  cạnh nút "Chạy kiểm tra"; (3) `x 1110, y 545` bên phải cột "Hoạt động"; (4) `x 470, y 822` cạnh dòng
  "Tất cả thành phần hoạt động bình thường".
- Hàng chú thích tại `y 905`: 4 ô, mỗi ô rộng 420, cách nhau 27; mỗi ô là vòng tròn số và 1–2 dòng chữ 17.
- Chân slide: `UI language: Vietnamese (labels translated on the slide).`

**Nội dung, hàng chú thích**

> **1** Two groups: camera pipeline, search components
> **2** Pick a camera with AI on, run the check
> **3** Real RTSP frames: each step with result and time
> **4** Overall verdict: all components working

**Ý chính để nói:** kiểm tra chạy trên khung hình thật lấy từ luồng RTSP của camera được chọn, đi lần lượt
Detector → Tracker → Image Encoder; mỗi bước báo kết quả và thời gian. Kết quả chỉ cho biết thành phần có
hoạt động hay không, không đánh giá độ chính xác của mô hình.

**Ghi chú:** nếu demo trực tiếp, chèn phần demo ngay sau slide này (ngoài 20 phút).

---

### Slide 16 — Software testing

- **Người nói / Thời gian:** Huy · 0:35
- **Layout:** L6
- **Nhãn phần:** `PART I · EVALUATION`
- **Tiêu đề:** `Testing at five levels`

**Nội dung, bảng** (rộng 1760, cột 1 rộng 300, cột 3 rộng 520)

| Level | Scope | Result |
| --- | --- | --- |
| Unit | Server and worker components, API contracts, security, fault injection | **713 passed** |
| Integration | Real PostgreSQL, Milvus, MinIO, MediaMTX | **37 passed**, 1 skipped |
| End-to-end | Upload → indexing → search → case → Viewer, real models | **2 passed** |
| User interface | 20 screens × 3 widths (390, 768, 1440 px) | No overflow or errors; 3 bugs fixed |
| Demo script | All three roles, run automatically | **15/15 steps, twice in a row** |

**Nội dung, ô kết luận**

> Every API declares an access rule and is called with every role in the tests. Integration and E2E tests refuse to run on the demonstration database.

---

### Slide 17 — Performance on a CPU-only laptop

- **Người nói / Thời gian:** Huy · 0:40
- **Layout:** L7
- **Nhãn phần:** `PART I · EVALUATION`
- **Tiêu đề:** `Performance on a CPU-only laptop`

**Bố cục:** 3 cột số lớn tại `y 250`. Dưới 3 cột, tại `y 720`, một ô chữ rộng 1760 nền phụ.

**Nội dung**

> **≈ 7×** slower than real time
> *Indexing 1080p video; demo data indexed from files, cameras processed in turn*
>
> **1.27 s / 0.11 s**
> median search latency, image / text
> *30 calls per form, k = 8, 1,523 appearances, worker idle*
>
> **≈ 8 GiB** RAM while processing a job
> *≈ 3.7 GiB idle; 16 GB machine, Intel Core i5-11300H*
>
> Ô dưới: **Sampling N = 20 kept as default:** vs N = 10, CPU time −25%, image storage −⅓, about the same number of short (broken) tracks. Time drops only ~9% because the image encoder (~1.85 s per track) dominates.

**Ý chính để nói:** chạy được trên máy phổ thông, nhưng chậm; đó là lý do xử lý tuần tự và lập chỉ mục trước.

---

### Slide 18 — Search quality

- **Người nói / Thời gian:** Huy · 0:50
- **Layout:** L6
- **Nhãn phần:** `PART I · EVALUATION`
- **Tiêu đề:** `Search quality: image works, text does not yet`

**Bố cục:** bảng ở `y 200`, rộng 1760. Ô "Why" ở `y 620`, rộng 1100. Bên phải ô "Why", tại `x 1220`,
ô chuyển tiếp `620 × 300`, nền mòng két `#0F8B8D`, chữ trắng 22.

**Nội dung, bảng** (ô số 0 tô chữ cam, ô 0.833 và 1.0 tô chữ xanh lá)

| Form | R@4 | R@8 | R@16 | MRR |
| --- | --- | --- | --- | --- |
| By image | **0.833** | **1.0** | **1.0** | 0.867 |
| By text | 0 | 0 | 0 | 0.01 |
| By attributes | 0 | 0 | 0 | 0.005 |

> *6 queries on the WILDTRACK evaluation set, detector threshold 0.25, 1,552 appearances. A re-run of attribute search at threshold 0.1 (1,526 appearances) was also 0 at every k.*

**Nội dung, ô "Why"**

> **Why:** RaSa was trained on CUHK-PEDES — tidy single-person crops, each with a hand-written caption. WILDTRACK crops are cut automatically from crowded wide shots, with other viewpoints and frequent occlusion.
> Image search is the main form; text and attributes are supporting tools that need careful visual review.

**Nội dung, ô chuyển tiếp**

> Text search is the weakest point → **Part II** studies how to fix it.

**Ý chính để nói:** nói thẳng kết quả 0, giải thích nguyên nhân, rồi chuyển lời cho Cường.

---

### Slide 19 — Part II divider

- **Người nói / Thời gian:** Cường · 0:05
- **Layout:** L2 (màu nhấn mòng két)

**Nội dung** (số lớn bên trái là `II`)

> **Part II**
> Semantic Reasoning for Text-Based Person Search
> Nguyen Huu Cuong
>
> In this part: why a reasoning layer · attribute index · multi-agent funnel · results on Market-1501

---

### Slide 20 — Why a reasoning layer

- **Người nói / Thời gian:** Cường · 0:45
- **Layout:** L3 (hình trái)
- **Nhãn phần:** `PART II · MOTIVATION`
- **Tiêu đề:** `One opaque number is not enough`

**Bố cục**

- Hình `figures/research/overall-000.png` tại `x 80, y 230`, cỡ `1000 × 576`, trong thẻ trắng; chú thích 14
  dưới hình.
- Cột phải `x 1140`, rộng 700: 2 khối vấn đề (tiêu đề 22 Semibold màu cam, 2 dòng 18), rồi một khối hướng
  giải quyết (tiêu đề màu mòng két).

**Nội dung**

> Chú thích hình: *The pipeline as a template of replaceable blocks: offline indexing, online search.*
>
> **A single score cannot be questioned** — when the right person is ranked 37th, the cosine similarity does not say whether the colour, the sleeves or the gender was misread.
> **The track is ignored** — CLIP scores each crop alone and throws away the repeated views of one person.
> **Idea:** describe every crop with readable attributes, and let an LLM reason over that evidence across the frames of a track.

---

### Slide 21 — Where to improve, and ZARA

- **Người nói / Thời gian:** Cường · 0:40
- **Layout:** L6
- **Nhãn phần:** `PART II · MOTIVATION`
- **Tiêu đề:** `Why the search block, and what we borrow from ZARA`

**Nội dung, bảng** (hàng 3 nền `#E2F3F3`, chữ đậm)

| Block | Main requirement | Consideration |
| --- | --- | --- |
| Detection | Detect people correctly | Well studied; errors flow downstream |
| Tracking | Keep identity across frames | Well studied; errors can contaminate a track |
| **Encoders + search** | **Match the query to appearances** | **Must generalise semantically and tolerate every upstream error** |

**Nội dung, ô kết luận** (vẽ hai hàng chữ nối bằng mũi tên)

> **ZARA** (activity recognition): motion signals → statistical features → multi-sensor evidence → LLM reasoning
> **Ours:** person images → readable attributes → multi-frame track evidence → LLM aggregation → re-ranking
> *Kept from ZARA: textual evidence instead of raw numbers, and coarse-to-fine pruning.*

---

### Slide 22 — System overview

- **Người nói / Thời gian:** Cường · 0:40
- **Layout:** hai hình
- **Nhãn phần:** `PART II · METHOD`
- **Tiêu đề:** `Offline: two describers per crop · Online: CLIP pool, then reasoning`

**Bố cục**

- Trái: `figures/research/offline-000.png` tại `x 80, y 220`, cỡ `700 × 490`; nhãn "Offline indexing" 18
  Semibold phía trên hình.
- Phải: `figures/research/online_full-000.png` tại `x 840, y 300`, cỡ `1000 × 316`; nhãn "Online search"
  phía trên.
- Ô ghi nhớ tại `x 840, y 700`, `1000 × 240`, viền trái 6 px cam.
- Dòng mô hình tại `y 760` dưới hình trái, rộng 700, chữ 16.

**Nội dung**

> Dưới hình trái: **Models (none fine-tuned):** CLIP ViT-H/14 (laion2B) · Qwen2.5-VL-3B (attribute describer) · Gemini Flash-Lite (reasoning) · Milvus
>
> Ô ghi nhớ: **Hard ceiling:** the reasoning layer can only reorder what CLIP retrieved. Every recall is reported next to **cap@75** — how often the right person is in the 75-candidate pool at all.

**Cần xác nhận với Cường:** tên phiên bản Gemini. Báo cáo ghi "Flash-Lite 3.5" và "Flash 3.8" nhưng
MERGE_NOTES đề nghị kiểm tra lại. Slide tạm ghi "Gemini Flash-Lite" không kèm số.

---

### Slide 23 — The attribute index

- **Người nói / Thời gian:** Cường · 0:45
- **Layout:** L3 (2 bảng)
- **Nhãn phần:** `PART II · METHOD`
- **Tiêu đề:** `18 readable attributes, and why voting fails`

**Bố cục**

- Trái `x 80`, rộng 820: bảng 5 hàng "Region → attributes", rồi 1 dòng về chỉ số chất lượng.
- Phải `x 960`, rộng 880: bảng "One real track, 10 frames" (5 hàng), rồi 3 gạch đầu dòng.

**Nội dung, bảng trái**

| Region | Attributes |
| --- | --- |
| Whole | gender, build, height, carried items (list) |
| Head | age group, hair colour, hair style |
| Upper | inner / outer garment type and colour, sleeves, pattern |
| Lower | type, colour, length |
| Feet | shoes type and colour |

> Each body band also carries **sharpness, contrast, brightness, saturation**, so a disagreement can be explained by capture conditions.

**Nội dung, bảng phải**

| Attribute | Readings across 10 frames |
| --- | --- |
| gender | female 80%, male 20% |
| hair colour | black 40%, brown 30%, blonde 30% |
| hair style | short 50%, straight 30%, long+straight 20% |
| upper outer type | hoodie 20%, not visible 80% |
| upper inner colour | gray 40%, black 40% (tie) |

> - **Ties** make a majority vote arbitrary
> - **Near-synonyms** split the vote over vocabulary, not over the person
> - **"Not visible"** is a missing observation, not a value
> → An LLM told what each case means can tell them apart; a vote cannot.

---

### Slide 24 — The multi-agent funnel

- **Người nói / Thời gian:** Cường · 0:55
- **Layout:** L4
- **Nhãn phần:** `PART II · METHOD`
- **Tiêu đề:** `A four-stage funnel over two rounds`

**Bố cục**

- Hình `figures/research/reasoning-000.png` tại `x 80, y 210`, cỡ `1100 × 592`, trong thẻ trắng.
- Cột phải `x 1240`, rộng 600: một "phễu" vẽ bằng 3 hình thang chồng nhau (Canva: "trapezoid"), rộng dần
  thu hẹp, màu mòng két đậm dần; chữ trắng trong mỗi tầng: `75 candidates`, `25 after the coarse round`,
  `Top 10`. Dưới phễu, 4 dòng vai trò 18.
- Dòng Stage 0 tại `y 850`, rộng 1760, nền phụ.

**Nội dung, cột phải**

> **1 Selector** — chooses 4–10 attribute=value pairs worth checking
> **2A Evidence reader** — writes a short note per candidate per pair
> **2B Ranker** — orders candidates from the notes only
> **3–4** — the same steps again on the 25 survivors, renumbered
>
> Dòng dưới: **Stage 0 (before any candidate):** one call settles how each query word relates to each index value — exact, near, far, unrelated, neutral — and every later stage reuses it, so "navy read as black in a dim crop" is treated as a likely confusion, not a different person.

---

### Slide 25 — Rules that made it work

- **Người nói / Thời gian:** Cường · 0:45
- **Layout:** L5 (4 thẻ)
- **Nhãn phần:** `PART II · METHOD`
- **Tiêu đề:** `Each rule was added after a measured failure`

**Bố cục:** 4 thẻ `410 × 560` tại `y 230`. Mỗi thẻ: số đo lớn 40 màu mòng két ở trên, tên quy tắc 20
Semibold, mô tả 17.

**Nội dung**

> **19 → 0** · **Citation rule** — never name a cause without the figure that shows it. Invented causes in the evidence notes dropped from 19 to 0.
>
> **69 / 75** · **Reliability, not direction** — before the rule, 69 of 75 ranking reasons opened with attributes the whole pool shared, which ordered nothing.
>
> **Rarity table** · **What each query value is worth** — decisive (≥ 5× typical share), moderate (≥ 1.5×) or almost nothing; added after a rare green top lost to common colours.
>
> **AUC 0.601** · **CLIP score withheld from the ranker** — inside the pool CLIP barely separates the right person (adjacent ranks differ by 2.7% of one sd); passing it on would anchor the ranker.

---

### Slide 26 — Setup and main result

- **Người nói / Thời gian:** Cường · 0:50
- **Layout:** L6
- **Nhãn phần:** `PART II · RESULTS`
- **Tiêu đề:** `+23 points R@10 from re-ranking alone`

**Bố cục**

- Dải chip thiết lập tại `y 200` (6 chip).
- Bảng tại `y 300`, rộng 1100, bên trái. Ô `R@10 = 56.0%` tô nền xanh lá nhạt; ô `R@1 = 26.0%` của CLIP tô
  đậm.
- Bên phải (`x 1240`, rộng 600): 3 kết luận đánh số, chữ 19.

**Nội dung, chip**

> Market-1501 · 496 identities uniquely described by their attributes · 100 evaluated · pool of 75 → 25 → 10 · zero-shot · one phrasing per identity

**Nội dung, bảng**

| Method | R@1 | R@5 | R@10 |
| --- | --- | --- | --- |
| CLIP (baseline) | **26.0%** | 29.0% | 33.0% |
| Funnel, 2 stages | 23.0% | **46.0%** | 53.0% |
| Funnel, 4 stages | 15.0% | 38.0% | **56.0%** |

> *n = 100: one percentage point is one identity.*

**Nội dung, kết luận**

> 1. Better at depth: 56 vs 33 identities in the top 10, no fine-tuning, same retrieval.
> 2. Worse at rank 1: CLIP stays best at R@1.
> 3. The refine round trades precision for depth: +3 at R@10, −8 at R@1 and R@5.

**Ý chính để nói:** tập 496 dễ hơn bộ 1501 đầy đủ, không so với kết quả công bố trên Market-1501.

---

### Slide 27 — Rescued and lost

- **Người nói / Thời gian:** Cường · 0:40
- **Layout:** L3 (biểu đồ trái, hình phải)
- **Nhãn phần:** `PART II · RESULTS`
- **Tiêu đề:** `What the funnel rescues, and what it costs`

**Bố cục**

- Trái `x 80`, rộng 960: hai thanh ngang tự vẽ (hình chữ nhật ghép), cao 70, tại `y 260` và `y 430`.
  - Thanh 1 "Found by CLIP (33)": đoạn xanh lá dài 28 phần "kept 28", đoạn cam 5 phần "lost 5".
  - Thanh 2 "Missed by CLIP (67)": đoạn xanh lá 28 phần "rescued 28", đoạn xám `#C9CCD8` 36 phần
    "missed by both 36", đoạn xám đậm 3 phần "not in pool 3".
  - Độ dài theo tỉ lệ: 1 identity = 9 px (thanh 2 dài 603 px).
- Dưới hai thanh, tại `y 600`: kết luận 3 dòng 19.
- Phải: `figures/research/case_rescued.png` tại `x 1100, y 200`, cỡ `740 × 776`; chú thích 14 bên dưới.

**Nội dung, kết luận**

> - **42%** of the identities CLIP missed are rescued (28 / 67)
> - **15%** of those CLIP found are pushed out (5 / 33)
> - Only 3 / 100 never reached the pool → the remaining room is in **ranking**, not retrieval
>
> Chú thích hình: *A rescued case: outside CLIP's top 10, first after reasoning; the funnel also gathers several crops of the same person.*

---

### Slide 28 — Is the small model the bottleneck?

- **Người nói / Thời gian:** Cường · 0:35
- **Layout:** L6
- **Nhãn phần:** `PART II · RESULTS`
- **Tiêu đề:** `A larger ranker recovers 4 of the 5 losses`

**Nội dung, bảng**

| Lost identity | CLIP rank | Final rank before → after | Result |
| --- | --- | --- | --- |
| 1 | 1 | 16 → 8 | Fixed |
| 2 | 1 | cut at round 1 → 1 | Fixed |
| 3 | 1 | 15 → 1 | Fixed |
| 4 | 1 | 22 → 14 | Still wrong |
| 5 | 6 | cut at round 1 → 1 | Fixed |

> *Only the two ranking calls were switched to a larger Gemini model; the evidence notes were replayed unchanged.*

**Nội dung, ô kết luận** (viền trái cam)

> The evidence was sufficient; the small model did not use it well enough.
> **Caveat:** these 5 queries were chosen with the ground truth, so they must not be added to the main table — only a full sweep on the larger model can measure the system.

---

### Slide 29 — Achievements

- **Người nói / Thời gian:** Huy (cột trái), Cường (cột phải) · 0:40
- **Layout:** L5 (2 thẻ lớn)
- **Nhãn phần:** `CONCLUSION`
- **Tiêu đề:** `What the project achieved`

**Bố cục:** 2 thẻ `860 × 700` tại `y 220`, viền trên tím (trái) và mòng két (phải).

**Nội dung**

> **Part I — A complete application**
> - Camera stream → indexing → search → review → case files, for three roles
> - Image, text and attribute search in one vector space, scoped by area
> - 1,488 WILDTRACK appearances indexed without errors; 713 unit tests, 15/15 demo steps
> - Honest measurements: image search works, text search is the weak point
>
> **Part II — A reasoning layer for text search**
> - Readable attribute index + four-stage multi-agent funnel
> - R@10 33% → 56% on 100 Market-1501 identities, no fine-tuning
> - Rescues 28 of 67 misses, loses 5 of 33 hits
> - Every number reported with its ceiling (cap@75)

---

### Slide 30 — Limitations and future work

- **Người nói / Thời gian:** Huy (cột 1), Cường (cột 2, 3) · 0:40
- **Layout:** L5 (3 thẻ)
- **Nhãn phần:** `CONCLUSION`
- **Tiêu đề:** `Limitations and future work`

**Bố cục:** 3 thẻ `560 × 700` tại `y 220`. Trong mỗi thẻ: nửa trên "Limitations" (tiêu đề màu cam), nửa
dưới "Next" (tiêu đề màu xanh lá).

**Nội dung**

> **Part I**
> *Limitations:* text search ineffective on WILDTRACK · ~7× slower than real time · RTSP timestamps from the machine clock can split tracks · image/text recall at threshold 0.1 not re-measured
> *Next:* RaSa image–text re-ranking or same-domain fine-tuning · OpenVINO / GPU · stream timestamps · ByteTrack vs BoT-SORT
>
> **Part II**
> *Limitations:* small hosted model chosen for quota · 100 identities, easier subset · detection and tracking errors not measured · one phrasing per query
> *Next:* full sweep on a larger model · tracker-error analysis · handle mismatch cost of binary attributes (gender)
>
> **Bringing the two parts together**
> The funnel works on a candidate pool from vector search — exactly what PRISM already gets from Milvus. It could become an optional re-ranking step, given an attribute index built at indexing time, a decision on where the LLM runs on premises, and a measurement of the added latency.

---

### Slide 31 — Thank you

- **Người nói / Thời gian:** cả hai · 0:10
- **Layout:** L1 biến thể (nền tối)

**Bố cục:** logo `Logo_BK.png` cao 120 canh giữa tại `y 220`; chữ "Thank you" Montserrat ExtraBold 80 trắng
canh giữa tại `y 420`; dòng phụ 24 màu `#B9BCD0` tại `y 560`; tên hai sinh viên 20 tại `y 760`.

**Nội dung**

> **Thank you**
> Questions and discussion
>
> Nguyen Cong Huy — 2113499 · Nguyen Huu Cuong — 2252098

---

### Slide 32 — Demo (nếu có, ngoài 20 phút)

- **Layout:** L2 (màu tím)

**Nội dung**

> **Live demo**
> Operator: search by image → review → save a case · Viewer: dashboard · Administrator: add an RTSP camera, enable AI

Kịch bản thao tác ở `files/demo-script.md`. Nếu không demo trực tiếp, xóa slide này.

---

## 4. Slide dự phòng (đặt sau slide 32, dùng khi Hội đồng hỏi)

Mỗi slide dự phòng dùng layout L4: tiêu đề + một hình lớn canh giữa vùng nội dung (giữ tỉ lệ, cao tối đa
800) + 1–2 dòng chú thích. Nhãn phần là `BACKUP`.

| Mã | Tiêu đề (dán nguyên văn) | Hình | Dùng khi bị hỏi |
| --- | --- | --- | --- |
| B1 | `Use case diagram (15 use cases)` | `figures/H1-use-case.png` (cao 800, rộng 672) | chức năng cụ thể của từng vai trò |
| B2 | `Permission matrix` | bảng 8 hàng của Mục 4.6 báo cáo, dựng lại bằng bảng Canva | phân quyền chi tiết |
| B3 | `Entity-relationship diagram` | `figures/H8-erd.png` (rộng 1224, cao 800) | thiết kế CSDL |
| B4 | `Search sequence` | `figures/H4-tuan-tu-tim-kiem.png` (cao 800) | trình tự lọc quyền khi tìm kiếm |
| B5 | `Saving a result into a case` | `figures/H5-tuan-tu-vu-viec.png` (cao 800) | luồng lưu vụ việc |
| B6 | `Processing job states` | `figures/H7-trang-thai-cong-viec.png` (rộng 1064, cao 800) | worker, hủy job, thử lại |
| B7 | `Screen flow by role` | `figures/H12-luong-man-hinh.png` (rộng 984, cao 800) | giao diện tổng thể |
| B8 | `Search by attributes` | `images/H10b-tim-kiem-thuoc-tinh.png` (rộng 1422, cao 800) | prompt builder hoạt động thế nào |
| B9 | `Other screens` | `figures/H10e-vu-viec-cua-toi-cat.png`, `H10g-camera-cat.png`, `H10i-xu-ly-video-cat.png`, `H10j-trang-thai-he-thong-cat.png`; mỗi slide dự phòng một ảnh (B9a–B9d), không xếp lưới | các màn hình còn lại |
| B10 | `RTSP handling and memory` | bảng chữ, nội dung bên dưới | độ tin cậy RTSP, RAM |
| B11 | `ZARA and the selector` | `figures/research/zara-000.png` và `selector-000.png` xếp dọc | nguồn cảm hứng ZARA, stage 1 |
| B12 | `A lost case, before and after the larger ranker` | `figures/research/case_lost.png` và `case_lost_fixed.png` cạnh nhau (mỗi hình cao 780) | ca thất bại cụ thể |

**Nội dung B10**

> **RTSP (threshold 0.25, track counts indicative):** normal session 300 frames / 29 appearances; source cut for 5 s → 1 reconnect, 600 frames / 38 appearances; AI disabled mid-session → job Cancelled, no partial appearance. New RTSP camera picked up by the worker 13–24 s after AI is enabled.
> **Memory:** API 1,978 MiB after loading the query encoder; analysis pipeline up to 4,772 MiB while processing; ≈ 3.7 GiB idle, ≈ 8.0 GiB processing.

**Lưu ý B12:** báo cáo gọi truy vấn của ca này là "A teenage man…" trong khi ảnh đúng trông là nữ
(MERGE_NOTES mục 4). Hỏi lại Cường trước khi dùng; nếu chưa rõ thì bỏ B12.

---

## 5. Kiểm tra trước khi xuất

**Nội dung**

- [ ] Không có con số nào ngoài các số trong tài liệu này. Recall tìm bằng ảnh luôn đi kèm điều kiện
      "threshold 0.25, 6 queries, 1,552 appearances".
- [ ] Slide 4, 22 và 30 nói rõ Part II **chưa tích hợp** vào ứng dụng.
- [ ] Cường đã xác nhận tên phiên bản Gemini (slide 22, 28) và trạng thái hai hình `pruning_work`,
      `selector_work`.
- [ ] Không dùng chữ "IP" cho độ đo của Milvus; viết "inner product".
- [ ] Không viết "real-time" cho hệ thống; hệ thống chậm hơn thời gian thực khoảng 7 lần.

**Hình thức**

- [ ] Mọi hình giữ đúng tỉ lệ (không méo); sơ đồ đọc được chữ khi chiếu (thử xem ở chế độ
      **Present** từ cách màn hình 2 m).
- [ ] Ảnh chụp màn hình có chú thích tiếng Anh; slide 13 có dòng "UI language: Vietnamese".
- [ ] Số trang hiện đúng; slide bìa, chuyển phần và cảm ơn không có chân trang.
- [ ] Màu nhấn đúng phần: tím cho Mở đầu, Part I và Kết luận; mòng két cho Part II.

**Xuất tệp**

- Canva → **Share → Download → PDF Standard** để nộp hoặc dự phòng; **PPTX** nếu máy trình chiếu không
  có mạng (kiểm tra lại font sau khi mở bằng PowerPoint vì Montserrat/Inter có thể bị thay).
- Mang theo bản PDF trên USB.

**Luyện tập**

- Bấm giờ từng phần theo bảng ở đầu Mục 3. Nếu vượt quá 20 phút, cắt theo thứ tự: slide 21 (gộp ý ZARA vào
  slide 20) → slide 12 → slide 15 (giữ 15b, 15c).
