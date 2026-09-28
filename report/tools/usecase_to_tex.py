import re
B = chr(92)
src = open(r'D:/uni-studies/semester-253/capstone_project_new/files/usecase_detail.md', encoding='utf-8').read()
blocks = re.split(r'\n## (UC-\d\d) – ', src)[1:]
ucs = []
for i in range(0, len(blocks), 2):
    code = blocks[i]
    body = blocks[i + 1]
    name = body.split('\n', 1)[0].strip()
    rows = {}
    for m in re.finditer(r'^\| \*\*(.+?)\*\* \| (.*) \|\s*$', body, re.M):
        rows[m.group(1)] = m.group(2)
    ucs.append((code, name, rows))

R = [
    (r'\*\*Điểm phù hợp \(Matching Score\)\*\*', 'điểm phù hợp'),
    (r'Điểm phù hợp \(Matching Score\)', 'điểm phù hợp'),
    (r'Matching Score', 'điểm phù hợp'),
    (r'Điểm phù hợp', 'điểm phù hợp'),
    (r'\(`top_k`\)', '(top-$k$)'),
    (r'`top_k` không thuộc tập `\{4, 8, 12, 16\}`', 'số lượng kết quả không thuộc tập $' + B + '{4, 8, 12, 16' + B + '}$'),
    (r'tối đa `top_k` kết quả', 'tối đa số lượng kết quả đã chọn'),
    (r'`top_k`', 'số lượng kết quả'),
    (r'`RTSP → Detector → Tracker → Image Encoder`', 'RTSP $' + B + 'rightarrow$ Detector $' + B + 'rightarrow$ Tracker $' + B + 'rightarrow$ bộ mã hóa ảnh'),
    (r'\*\*Camera Processing Pipeline\*\*', '**nhóm xử lý camera**'),
    (r'\*\*Search Components\*\*', '**nhóm tìm kiếm**'),
    (r'Camera Processing Pipeline', 'nhóm xử lý camera'),
    (r'Search Components', 'nhóm tìm kiếm'),
    (r'`Image Encoder` và `Text Encoder`', 'bộ mã hóa ảnh và bộ mã hóa văn bản'),
    (r'Image Encoder', 'bộ mã hóa ảnh'),
    (r'Text Encoder', 'bộ mã hóa văn bản'),
    (r'Person Embedding', 'vector đặc trưng'),
    (r'từng encoder', 'từng bộ mã hóa'),
    (r'hồ sơ vụ việc \(Case\)', 'hồ sơ vụ việc'),
    (r'biểu mẫu hoặc request', 'biểu mẫu hoặc yêu cầu gửi tới máy chủ'),
    (r'ảnh đã crop chứa người cần tìm', 'ảnh chứa người cần tìm'),
    (r'ảnh crop chứa người do Operator tải lên', 'ảnh chứa người do Giám sát viên cung cấp'),
    (r'crop động', 'cắt động'),
    (r'crop ', 'cắt '),
    (r'full frame', 'khung hình toàn cảnh'),
    (r'frame toàn cảnh', 'khung hình toàn cảnh'),
    (r'bounding box', 'khung bao'),
    (r'frame', 'khung hình'),
    (r'pipeline AI', 'quy trình xử lý AI'),
    (r'pipeline', 'quy trình xử lý'),
    (r'audit log', 'nhật ký hệ thống'),
    (r'backend', 'máy chủ'),
    (r'request trực tiếp', 'yêu cầu gửi trực tiếp'),
    (r'request', 'yêu cầu'),
    (r'worker', 'tiến trình xử lý nền'),
    (r'metadata', 'thông tin mô tả'),
    (r'Viewer \(Manager/Director\)', 'Quản lý'),
    (r', với vai trò là Manager hoặc Director,', ''),
    (r'Manager hoặc Director', 'cán bộ quản lý'),
    (r'Operator', 'Giám sát viên'),
    (r'Admin', 'Quản trị viên'),
    (r'Viewer', 'Quản lý'),
    (r'\bCase\b', 'vụ việc'),
    (r'use-case', 'use case'),
    (r'Offline/Chưa xác minh', B + 'emph{Offline/Chưa xác minh}'),
    (r'hard-delete', 'xóa vĩnh viễn'),
    (r'UX helper/prompt builder', 'công cụ hỗ trợ tạo câu mô tả'),
]


def conv(t):
    for a, b in R:
        t = re.sub(a, lambda m, b=b: b, t)
    parts = t.split('**')
    out = ''
    for k, pp in enumerate(parts):
        out += pp if k % 2 == 0 else B + 'textbf{' + pp + '}'
    t = out
    t = re.sub(r'`([^`]+)`', lambda m: B + 'texttt{' + m.group(1) + '}', t)
    t = t.replace(' – ', ' -- ').replace('%', B + '%').replace('&', B + '&')
    t = re.sub(r'(^|\.\s+|<br>|\d\.\s|-- |\{)(vụ việc|điểm phù hợp|bộ mã hóa|khung hình|nhóm)',
               lambda m: m.group(1) + m.group(2)[0].upper() + m.group(2)[1:], t)
    return t


REQ = {'UC-01': 'FR-C01', 'UC-02': 'FR-A01, FR-A02', 'UC-03': 'FR-A03, FR-A04, FR-A05',
       'UC-04': 'FR-A06, FR-A07, FR-S01, FR-S02', 'UC-05': 'FR-A08, FR-S02, FR-S04', 'UC-06': 'FR-A09',
       'UC-07': 'FR-A10', 'UC-08': 'FR-A11', 'UC-09': 'FR-O01 đến FR-O06, FR-S03',
       'UC-10': 'FR-O06, FR-O07, FR-O08', 'UC-11': 'FR-O09 đến FR-O14', 'UC-12': 'FR-V01',
       'UC-13': 'FR-V02, FR-V03', 'UC-14': 'FR-V04', 'UC-15': 'FR-C02'}


def steps(t):
    items = [s for s in t.split('<br>') if s.strip()]
    items = [re.sub(r'^\d+\.\s*', '', s) for s in items]
    # Tự đánh số với thụt lề treo: enumerate trong ô p{} để lại một dòng trống ở đầu ô.
    # Trả về danh sách: mỗi bước là một hàng riêng để longtable ngắt trang được giữa các bước.
    return [B + 'hangindent=1.6em' + B + 'hangafter=1' + B + 'noindent' + B + 'makebox[1.6em][l]{' + str(k + 1) + '.}' + s
            for k, s in enumerate(items)]


def labeled(t):
    if t.strip().rstrip('.') == 'Không có':
        return ['Không có.']
    return [s for s in t.split('<br><br>') if s.strip()]


out = []
out.append('% !TEX root = ../../main.tex\n'
           '% C4.5 — Đặc tả use case. Sinh từ files/usecase_detail.md bằng report/tools/usecase_to_tex.py, thuật ngữ theo tên giao diện, rồi rà soát tay.\n'
           '% Không có dòng mã FR (SV bỏ 2026-09-28: hội đồng khó tra); liên kết FR→UC nằm ở cuối mỗi yêu cầu trong 4.2. Phần "Ghi chú" của nguồn đã được đưa vào 4.2 và 4.3 (không có mục quy tắc nghiệp vụ riêng, SV duyệt bỏ 4.7).\n'
           '% Nếu sửa usecase_detail.md: chạy lại script rồi rà soát lại các chỗ đã sửa tay (xem nhật ký report_plan.md).\n')
out.append(B + 'section{Đặc tả use case}\n' + B + 'label{sec:4.5}\n\n')
out.append('Mục này đặc tả chi tiết 15 use case đã liệt kê ở Bảng~' + B + 'ref{tab:usecases}. Mỗi đặc tả gồm tác nhân, mục đích, '
           'tiền điều kiện, hậu điều kiện, luồng chính, các ngoại lệ (ký hiệu E) và các luồng thay thế (ký hiệu A). '
           'Các ràng buộc dùng chung giữa nhiều use case đã được nêu trong các yêu cầu ở Mục~' + B + 'ref{sec:4.2} và Mục~'
           + B + 'ref{sec:4.3}; phạm vi dữ liệu mà mỗi vai trò được truy cập được tổng hợp trong ma trận phân quyền ở Mục~'
           + B + 'ref{sec:4.6}.\n\n')
for code, name, rows in ucs:
    lab = 'tab:' + code.lower().replace('-', '')
    # Cỡ chữ và giãn dòng của bảng do \tablestyle trong main.tex quy định chung.
    out.append(B + 'begin{longtable}{|>{' + B + 'raggedright' + B + 'arraybackslash}p{2.9cm}|p{12.3cm}|}\n')
    out.append(B + 'caption{Đặc tả use case ' + code + ': ' + conv(name) + '}' + B + 'label{' + lab + '}' + B + B + '\n'
               + B + 'hline\n' + B + 'endfirsthead\n'
               + B + 'multicolumn{2}{l}{' + B + 'textit{(tiếp theo Bảng~' + B + 'ref{' + lab + '})}}' + B + B + '\n'
               + B + 'hline\n' + B + 'endhead\n')

    def row(k, v):
        out.append(B + 'textbf{' + k + '} & ' + v + ' ' + B + B + ' ' + B + 'hline\n')

    row('Tác nhân', conv(rows['Actors']))
    row('Mục đích', conv(rows['Mục đích']))
    row('Tiền điều kiện', conv(rows['Tiền điều kiện']))
    row('Hậu điều kiện', conv(rows['Hậu điều kiện']))
    main = steps(conv(rows['Luồng chính']))
    for j, txt in enumerate(main):
        first = (B + 'textbf{Luồng chính}') if j == 0 else ''
        end = (B + 'hline') if j == len(main) - 1 else ''  # không kẻ giữa các bước
        out.append(first + ' & ' + txt + ' ' + B + B + ' ' + end + '\n')
    for key in ['Ngoại lệ', 'Luồng thay thế']:
        items = labeled(conv(rows[key]))
        for j, txt in enumerate(items):
            first = (B + 'textbf{' + key + '}') if j == 0 else ''
            end = (B + 'hline') if j == len(items) - 1 else (B + 'cline{2-2}')
            out.append(first + ' & ' + txt + ' ' + B + B + ' ' + end + '\n')
    out.append(B + 'end{longtable}\n\n')
open(r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/sections/chapter4/4.5.tex', 'w', encoding='utf-8').write(''.join(out))
print(len(ucs))
