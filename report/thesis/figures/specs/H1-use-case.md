# H1 — Sơ đồ use case tổng thể

- **Vị trí:** Mục 4.4 (Sơ đồ use case tổng thể).
- **Chú thích hình (caption):** "Sơ đồ use case tổng thể của hệ thống".
- **Tệp:** `H1-use-case.drawio`, `H1-use-case.png`.
- **Loại sơ đồ:** **UML use case** → dùng **ký hiệu UML chuẩn** (README mục 2), **không** dùng bộ ký hiệu khối ở README mục 3, không tô màu theo bảng màu khối. Có thể để nền trắng toàn bộ, hoặc tô nhẹ một màu duy nhất cho các elip.
- **Nguồn:** `files/usecase_detail.md` (dòng **Actors** và các câu "chuyển sang UC-xx" của từng use case).
- **Mục đích:** cho người đọc thấy trong một hình: hệ thống có những tác nhân nào, mỗi tác nhân dùng những use case nào, và các use case nào nối tiếp nhau.

## 1. Ký hiệu UML dùng trong hình

| Thành phần | Ký hiệu | Trong draw.io |
| --- | --- | --- |
| Tác nhân | Hình người que, tên đặt **dưới** hình | UML → `Actor` |
| Tác nhân trừu tượng "Người dùng" | Hình người que, tên viết *nghiêng* | UML → `Actor`, chữ nghiêng |
| Use case | **Hình elip**, chữ bên trong: `UC-xx` xuống dòng + tên | UML → `Use Case` (Ellipse) |
| Ranh giới hệ thống | **Hình chữ nhật** bao quanh tất cả use case, tên ở góc trên: **Hệ thống PRISM** | General → `Rectangle`, nét liền |
| Liên kết tác nhân – use case | **Đường thẳng nét liền, không mũi tên** | Connector `none` ở cả hai đầu |
| Tổng quát hóa (generalization) | Nét liền, **đầu mũi tên tam giác rỗng** chỉ về tác nhân cha | Connector, endArrow = `block`, endFill = 0 |
| Quan hệ `«extend»` | **Nét đứt**, đầu mũi tên hở (`open`), nhãn `«extend»`; mũi tên đi **từ use case mở rộng tới use case gốc** | Connector dashed, endArrow = `open` |

Tác nhân đặt **ngoài** khung ranh giới hệ thống; mọi elip nằm **trong** khung.

## 2. Tác nhân

| ID | Nhãn hiển thị | Vị trí |
| --- | --- | --- |
| T0 | *Người dùng* (trừu tượng) | Phía trên, giữa, ngoài khung |
| T1 | Quản trị viên (Admin) | Bên trái, ngoài khung |
| T2 | Giám sát viên (Operator) | Bên phải, phía trên, ngoài khung |
| T3 | Quản lý (Viewer) | Bên phải, phía dưới, ngoài khung |

Ghi tên hai dòng: dòng 1 tên tiếng Việt, dòng 2 tên tiếng Anh trong ngoặc.

## 3. Use case (15 elip)

Chia khung thành ba vùng để các đường liên kết ngắn và không cắt nhau:

| Vùng trong khung | Use case |
| --- | --- |
| **Dải trên cùng** (gần T0) | UC-01 Đăng nhập hệ thống; UC-15 Đăng xuất hệ thống |
| **Cột trái** (gần T1), xếp dọc từ trên xuống | UC-02 Quản lý tài khoản người dùng; UC-03 Quản lý camera; UC-04 Quản lý xử lý AI trên camera; UC-05 Cấu hình mô hình AI; UC-06 Theo dõi trạng thái hệ thống; UC-07 Kiểm tra hoạt động của AI; UC-08 Xem nhật ký hệ thống |
| **Cột phải, nửa trên** (gần T2), xếp dọc | UC-09 Tìm kiếm người bằng AI; UC-10 Xem và đánh giá kết quả tìm kiếm; UC-11 Quản lý hồ sơ vụ việc |
| **Cột phải, nửa dưới** (gần T3), xếp dọc | UC-12 Xem thông tin tổng quan; UC-13 Xem hồ sơ vụ việc; UC-14 Xem thông tin kết quả tìm kiếm đã lưu |

Tên use case ghi **đúng nguyên văn** như trên (khớp `usecase_detail.md` và Bảng 4.2 trong báo cáo).

## 4. Đường nối

### 4.1. Tổng quát hóa (3 đường)

| Từ | Đến | Kiểu |
| --- | --- | --- |
| T1 Quản trị viên | T0 Người dùng | Tam giác rỗng chỉ về T0 |
| T2 Giám sát viên | T0 Người dùng | Tam giác rỗng chỉ về T0 |
| T3 Quản lý | T0 Người dùng | Tam giác rỗng chỉ về T0 |

Nếu đường từ T1 tới T0 phải vòng qua khung, cho đường đi **phía trên** khung, không cắt qua khung.

### 4.2. Liên kết tác nhân – use case (15 đường, nét liền, không mũi tên)

| Tác nhân | Nối tới |
| --- | --- |
| T0 Người dùng | UC-01, UC-15 |
| T1 Quản trị viên | UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08 |
| T2 Giám sát viên | UC-09, UC-10, UC-11 |
| T3 Quản lý | UC-12, UC-13, UC-14 |

**Không** nối trực tiếp T1/T2/T3 tới UC-01 và UC-15: quan hệ tổng quát hóa đã thể hiện cả ba tác nhân đều dùng hai use case này.

### 4.3. Quan hệ «extend» (4 đường, nét đứt, mũi tên chỉ về use case gốc)

| Use case mở rộng (đầu đuôi) | Use case gốc (đầu mũi tên) | Căn cứ trong `usecase_detail.md` |
| --- | --- | --- |
| UC-10 | UC-09 | UC-10: "bắt đầu sau khi UC-09 đã trả về kết quả" |
| UC-11 | UC-10 | UC-10 bước 9–10, A3, A4: chọn Tạo/Thêm Case thì "chuyển sang UC-11" |
| UC-13 | UC-12 | UC-12 bước 6–7, A1: chọn một Case gần đây thì "chuyển sang UC-13" |
| UC-14 | UC-13 | UC-13 A2: chọn một kết quả trong Case thì "chuyển sang UC-14" |

Mỗi đường ghi nhãn `«extend»` đặt giữa đường. Vì các use case này xếp dọc liền nhau, các đường «extend» là những đoạn ngắn nằm giữa hai elip kế tiếp.

**Không vẽ** `«include»` từ các use case tới UC-01 Đăng nhập. Đăng nhập là **tiền điều kiện**, không phải một bước bên trong use case; vẽ include tới đăng nhập là lỗi mô hình hóa hay gặp.

## 5. Chú giải

Sơ đồ UML chuẩn **không bắt buộc** chú giải. Nếu muốn, đặt ô nhỏ góc dưới phải gồm: đường liền (liên kết), tam giác rỗng (tổng quát hóa), nét đứt `«extend»`.

## 6. Điểm cần đối chiếu khi rà soát

- Đủ **15** use case, mã và tên khớp nguyên văn.
- Đúng **3 tác nhân cụ thể + 1 tác nhân trừu tượng**; không vẽ camera hay AI worker thành tác nhân (Mục 4.1 đã nêu lý do).
- Quản trị viên **không** nối tới UC-09…UC-14; Giám sát viên **không** nối tới UC-12…UC-14; Quản lý **không** nối tới UC-09…UC-11.
- Chiều mũi tên «extend»: từ use case **mở rộng** tới use case **gốc** (ví dụ UC-10 → UC-09), không ngược lại.
- Kích thước chữ trong elip đọc được khi hình rộng 16 cm (README mục 4); nếu chật, cho khung rộng hơn chiều cao (tỉ lệ khoảng 4:3).
