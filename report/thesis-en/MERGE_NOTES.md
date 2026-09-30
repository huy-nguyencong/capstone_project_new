# Ghi chú bản gộp tiếng Anh (thesis-en), 2026-09-30

Bản này gộp báo cáo ứng dụng (Nguyễn Công Huy) và báo cáo nghiên cứu (Nguyễn Hữu Cường) thành một báo cáo
tiếng Anh cho đồ án hai sinh viên. **Bản tiếng Việt gốc `report/thesis/` không bị sửa**; các script sơ đồ gốc
`report/tools/` cũng giữ nguyên.

Build: trong thư mục này chạy `latexmk` (XeLaTeX + Biber, cấu hình ở `.latexmkrc`). Kết quả: `build/main.pdf`,
197 trang; thân bài trang 1–136, tài liệu tham khảo từ trang 137, phụ lục prompt từ trang 143 (giới hạn khoa: 150 trang
cho đồ án 2 sinh viên).

## 1. Cấu trúc và ai viết phần nào

| Phần | Chương | Nguồn | Tệp |
| --- | --- | --- | --- |
| Mở đầu (chung) | bìa, cam đoan, cảm ơn, **Work Contribution (mới)**, tóm tắt, tóm tắt chương, viết tắt | viết mới / dịch | `sections/front/` |
| Chung | 1 Introduction | dịch chương 1 + đoạn `[MERGE]` cho Part II | `sections/chapter1/` |
| **Part I** – Huy | 2–8 | dịch chương 2–8 | `sections/chapter2..8/` |
| **Part II** – Cường | 9 Motivation and Overview, 10 Attribute Index and Multi-Agent Reasoning, 11 Experiments and Results | chép nguyên văn từ `D:\downloads\report_latex_v3\report.tex` (§1–3, §4–5, §6–9) | `sections/research/chapter9..11.tex` |
| Chung | 12 Conclusion and Future Work | dịch chương 9 cũ; mỗi mục chia Part I / Part II; Part II lấy nguyên văn §10–11 | `sections/chapter12/`, `sections/research/_limits.tex`, `_conclusion.tex` |
| Phụ lục A (Part II) | System Prompts | nguyên văn, đọc các tệp trong `prompts/` | `sections/research/appendix-prompts.tex` |

Script gộp Part II: `report/tools-en/merge_research.py` (tách theo tiêu đề mục, thêm tiền tố `r-` cho mọi nhãn của Part II
để không trùng Part I, đổi khóa trích dẫn sang `ref.bib`, đổi "this report" → "this part"). Nếu bạn Cường sửa lại
`report.tex`, có thể chạy lại script đó thay vì chép tay.

## 2. Việc cần hai bạn xem và quyết định

1. **Trang Work Contribution** (`front/contribution.tex`): danh sách việc của từng người do tôi soạn từ cách chia
   Part I / Part II; dòng chữ đỏ đã xóa (2026-09-30), nhưng nội dung bảng vẫn cần hai bạn xác nhận. Nếu khoa yêu cầu % đóng góp,
   thêm cột vào bảng.
2. **Lời cam đoan**: đoạn khai báo AI viết chung "we used ... Claude (Anthropic)". Bạn Cường cần xác nhận các công cụ
   AI mình đã dùng (README cũ của bạn ấy cho thấy có dùng công cụ AI khi biên dịch báo cáo) và sửa tên công cụ nếu khác.
   Ngày ký: chỉ ghi tháng và năm (SV quyết định 2026-09-30).
3. **Các đoạn đánh dấu `% [MERGE]`** là nội dung tôi viết thêm để nối hai phần, chưa có trong bản nào trước đó:
   - 1.2 mục tiêu 6 (nghiên cứu), 1.3 đoạn "Research on the search block", 1.4 hạn chế cuối;
   - 12.3.2 "Bringing the Two Parts Together" (hướng gắn lớp suy luận vào ứng dụng).
4. **Trang bìa**: tên đề tài tiếng Anh dùng bản dịch của bạn Cường ("Developing a Person Search System from Multimodal
   Descriptions"); "CAPSTONE PROJECT", "SEMESTER 253, ACADEMIC YEAR 2025–2026", hội đồng 1CC giữ như bản Việt.
5. ~~Gạch dài trong Part II~~: đã rà soát văn phong 2026-09-30 (xem §8).

## 3. Nội dung trùng giữa hai phần (để nguyên, cân nhắc rút gọn sau)

| Part II | Trùng với Part I | Gợi ý |
| --- | --- | --- |
| 9.1.1–9.1.2 bài toán TBPS, giới hạn của CLIP | 3.1 (TBPS), 3.5 (CLIP, ALBEF) | giữ luận điểm "một điểm số không giải thích được", dẫn chiếu 3.1/3.5 thay cho phần định nghĩa |
| 9.2.1 và Hình 9.1 (pipeline dạng khối) | 3.1.6, Hình 5.1 | có thể bỏ hình, dẫn chiếu Hình 5.1 |
| 9.3.1 bảng chọn mô hình (YOLO11n, ByteTrack, Milvus) | 3.2, 3.3, 3.6, 6.1 | giữ bảng, bỏ câu giải thích lại detector/tracker |
| 11.1.5 định nghĩa R@k | 8.2 (Recall@k, MRR) | dẫn chiếu 8.2 |

## 4. Lỗi trong báo cáo của bạn Cường chưa sửa (đã nêu trước, nằm ngoài yêu cầu gộp)

- Hình `pruning_work` (Hình 10.x, "The same two stages at work"): khối bằng chứng ghi "short 8/10, long 2/10",
  linkage 0.57, together 0.73, nhưng ghi chú viết "skirt 2/10", 0.65, 0.60; phần xếp hạng nói "yellow and white".
  Chú thích hình lại khẳng định "every figure in the note appears in the block".
- Hình `selector_work`: "Gender: Male 60 %, Female 60%" (tổng 120%).
- Ca minh họa (Hình 11.x): truy vấn "A teenage man…" trong khi ảnh đúng trông là nữ.
- Tên phiên bản Gemini ("Flash-Lite 3.5", "Flash 3.8") nên kiểm tra lại.

## 5. Quy ước dịch Part I

- Vai trò: Quản trị viên → **Administrator**, Giám sát viên → **Operator**, Quản lý → **Viewer** (khớp spec và code).
- Vụ việc → **case** (trạng thái Open/Closed); lần xuất hiện → **appearance** (track); khu vực → **area**;
  camera logic → **logical camera**; bộ đệm track → **track buffer**; nhật ký hệ thống → **audit log**.
- Trạng thái công việc: Queued / Running / Succeeded / Failed / Cancelled; lần xuất hiện: Pending / Ready / Failed.
- Số liệu viết theo kiểu tiếng Anh (1,488; 0.833). Mọi số liệu giữ nguyên như bản Việt (nguồn `files/report-data-guide.md`).
- Ảnh chụp màn hình vẫn là giao diện tiếng Việt (NFR-19); văn bản gọi tên màn hình bằng nghĩa tiếng Anh và có câu nói rõ
  điều này ở 6.3.4.

## 6. Hình

- Sơ đồ H1–H7, H12 đã dịch sang tiếng Anh: script ở `report/tools-en/` (nhãn được thay bằng
  `tools-en/translate_labels.py`), xuất 200% vào `thesis-en/figures/` **cùng tên tệp** với bản Việt (tên tệp không hiện
  trong báo cáo). H8 (ERD) vốn chỉ có tên bảng/cột nên dùng lại. Nếu sửa sơ đồ gốc tiếng Việt, cần sửa cả bản trong
  `tools-en/`.
- Hình của Part II: `figures/research/` (chép từ `figs/` của bạn Cường).

## 7. Tài liệu tham khảo

- `ref.bib` dùng chung; thêm 7 mục của Part II theo danh sách bạn Cường gửi (ZARA, CLIP ViT-H/14, Milvus docs,
  Qwen2.5-VL-3B, Gemini Flash-Lite, Market-1501, Market-1501 Attribute). ByteTrack và YOLO11 trùng với mục đã có nên dùng chung.
- Ghi chú tiếng Việt trong `ref.bib` đã dịch; tên bài VnExpress giữ nguyên tiếng Việt, ghi chú "In Vietnamese".

## 8. Rà soát văn phong (2026-09-30)

- Part II (chương 9–11, `_limits`, `_conclusion`, phần mở đầu phụ lục A) **không còn là bản chép nguyên văn** của
  `report_latex_v3`: đã bỏ gạch dài (em dash), câu tu từ ("CLIP proposes, the funnel disposes", "the heart of the system",
  "The cost is honest and small"...) và các câu mở đầu in đậm; tiêu đề "Stage N --- ..." thành "Stage N: ...";
  khoảng số "4--10" thành "4 to 10"; ô "---" trong Bảng tab:r-lostwhy/tab:r-rerun thành "n/a". Số liệu, nhãn, trích dẫn,
  hình, bảng giữ nguyên. Bạn Cường cần đọc lại để xác nhận ý không đổi.
- Đã xóa ghi chú đỏ ở trang Work Contribution (2026-09-30, SV yêu cầu); nội dung bảng vẫn cần hai SV xác nhận.
- **Không chạy lại** `tools-en/merge_research.py`: script sẽ ghi đè các tệp trên bằng bản gốc chưa rà soát.
- `prompts/*.txt` không sửa (là dữ liệu gửi cho mô hình).
