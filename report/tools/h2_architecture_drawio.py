"""Sinh figures/H2-kien-truc.drawio (kiến trúc tổng thể) theo figures/specs/H2-kien-truc.md.

Bố cục 2 cột dọc để chữ in ra ~9pt ở khổ 16 cm: trái = lập chỉ mục (nguồn camera -> xử lý nền),
phải = tìm kiếm (người dùng -> máy chủ ứng dụng); tầng lưu trữ trải ngang phía dưới.
Ký hiệu theo figures/README.md mục 3. Chạy: python report/tools/h2_architecture_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H2-kien-truc.drawio'
FS = 20
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []


def svg_uri(svg):
    return 'data:image/svg+xml,' + base64.b64encode(svg.encode()).decode()


BRAIN = svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#E1D5E7" stroke="#9673A6" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 5a3 3 0 0 0-5.6-1.5A3 3 0 0 0 3.5 7a3 3 0 0 0-.9 5.2A3.5 3.5 0 0 0 5 18a3 3 0 0 0 5.5 1.5A2 2 0 0 0 12 20z"/>'
    '<path d="M12 5a3 3 0 0 1 5.6-1.5A3 3 0 0 1 20.5 7a3 3 0 0 1 .9 5.2A3.5 3.5 0 0 1 19 18a3 3 0 0 1-5.5 1.5A2 2 0 0 1 12 20z"/>'
    '<path d="M12 5v15M8 8.5c1 0 2 .7 2 2M16 8.5c-1 0-2 .7-2 2M7.5 14c1.2 0 2.2-.6 2.5-1.5M16.5 14c-1.2 0-2.2-.6-2.5-1.5" fill="none"/>'
    '</svg>')
CAMERA = svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 24" fill="#ffffff" stroke="#333333" '
    'stroke-width="1.4" stroke-linejoin="round">'
    '<path d="M3 5l20 3v7L3 12z"/><path d="M23 9.5l6-2v7l-6-2"/>'
    '<path d="M9 13.5v4H4v3" fill="none"/><circle cx="7" cy="8.6" r="1.6"/></svg>')
BUCKET = svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" fill="#FFE6CC" stroke="#D79B00" stroke-width="1.5">'
    '<path d="M5 9l4 27c.3 2 22 2 22.3 0L35 9z"/><ellipse cx="20" cy="9" rx="15" ry="4.5"/></svg>')


def v(id, val, style, x, y, w, h, parent='1'):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="{parent}">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def e(id, s, t, style, val='', pts=None, lx=None):
    g = '<mxGeometry relative="1" as="geometry"' + (f' x="{lx}"' if lx is not None else '') + '>'
    if pts:
        g += '<Array as="points">' + ''.join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts) + '</Array>'
    g += '</mxGeometry>'
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} edge="1" parent="1" '
                 f'source="{s}" target="{t}">{g}</mxCell>')


FRAME = 'rounded=0;whiteSpace=wrap;html=1;dashed=1;fillColor=none;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;'
PROC = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;'
DOC = 'shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFF2CC;strokeColor=#D6B656;'
MDOC = 'shape=mxgraph.flowchart.multi-document;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#D6B656;'
CONT = 'swimlane;whiteSpace=wrap;html=1;startSize=34;fillColor=#D5E8D4;strokeColor=#82B366;swimlaneFillColor=#F4FAF1;'
DB = 'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#FFE6CC;strokeColor=#D79B00;'
QUEUE = 'shape=mxgraph.flowchart.direct_data;whiteSpace=wrap;html=1;fillColor=#FFE6CC;strokeColor=#D79B00;'
COMP = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#D5E8D4;strokeColor=#82B366;'
ICON_L = 'shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=6;image='
ICON_T = 'shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=top;verticalAlign=bottom;image='
ICON_R = 'shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;image='
ICON_B = 'shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image='
ACT = 'shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;'
DATA = 'endArrow=block;endFill=1;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;jumpStyle=arc;jumpSize=10;labelBackgroundColor=#ffffff;'
CTRL = DATA + 'dashed=1;'
RTSP = DATA + 'strokeWidth=3;'
SEARCH = 'strokeColor=#1F4E9A;fontColor=#1F4E9A;'

# --- Cột trái: nguồn camera ---
v('A', 'Nguồn dữ liệu camera', FRAME, 0, 0, 470, 230)
v('A1', '7 tệp video<br>WILDTRACK', MDOC, 15, 75, 135, 90)
v('A2', 'FFmpeg +<br>MediaMTX', PROC, 185, 80, 135, 80)
v('A3', '7 camera logic', ICON_T + CAMERA + ';', 395, 90, 70, 53)
# --- Cột trái: xử lý nền ---
v('B', 'Tiến trình xử lý nền (AI worker)', FRAME, 0, 270, 470, 690)
v('B1', 'Bộ lập lịch phiên RTSP<br>(xoay vòng camera)', PROC, 15, 320, 185, 76)
v('B2', 'Hàng đợi công việc<br>(trong PostgreSQL)', QUEUE, 210, 320, 205, 76)
v('B3', 'Lấy mẫu khung hình (1/N)', PROC, 110, 445, 250, 56)
v('B4', 'Phát hiện người<br>YOLO11n', ICON_R + BRAIN + ';', 205, 535, 60, 60)
v('B5', 'Theo vết<br>ByteTrack / BoT-SORT', ICON_R + BRAIN + ';', 205, 630, 60, 60)
v('B6', 'Chọn khung hình đại diện', PROC, 110, 725, 250, 56)
v('B7', 'Mã hóa ảnh<br>RaSa', ICON_R + BRAIN + ';', 205, 815, 60, 60)
v('B8', 'Ghi dữ liệu lần xuất hiện<br>(PENDING → READY)', PROC, 110, 895, 250, 56)
# --- Cột phải: người dùng ---
v('D', 'Người dùng', FRAME, 530, 0, 470, 230)
v('D2a', 'Quản trị viên', ACT, 575, 40, 30, 56)
v('D2b', 'Giám sát viên', ACT, 700, 40, 30, 56)
v('D2c', 'Quản lý', ACT, 820, 40, 30, 56)
v('D1', 'Ứng dụng web (React)', COMP, 560, 150, 250, 56)
v('A4', 'Tệp video tải lên', DOC, 840, 140, 140, 70)
# --- Cột phải: máy chủ ứng dụng (container = ranh giới tiến trình) ---
v('C1', 'Máy chủ ứng dụng (Flask API)', CONT, 530, 300, 470, 600)
v('C1t', '<i>xác thực, phân quyền, tìm kiếm,<br>vụ việc, quản trị</i>', 'text;html=1;align=center;verticalAlign=middle;', 545, 345, 440, 60)
v('C3', 'Tạo câu mô tả<br>từ thuộc tính', PROC, 560, 470, 190, 76)
v('C2', 'Mã hóa truy vấn<br>RaSa ảnh / văn bản', ICON_L + BRAIN + ';', 845, 620, 60, 60)
# --- Tầng lưu trữ ---
v('S', 'Tầng lưu trữ', FRAME, 0, 1030, 1000, 200)
v('S1', '<b>PostgreSQL</b><br>tài khoản, camera, lần xuất hiện,<br>vụ việc, nhật ký, hàng đợi', DB, 20, 1075, 290, 135)
v('S2', '<b>Milvus</b> (vector)<br>vector 256 chiều + khu vực,<br>camera, thời gian', DB, 350, 1075, 290, 135)
v('S3', '<b>MinIO</b><br>khung hình đại diện<br>(bucket riêng tư)', ICON_R + BUCKET + ';', 700, 1100, 80, 80)

n = 0


def nid():
    global n
    n += 1
    return f'e{n}'


E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'
BOTH = 'startArrow=block;startFill=1;'
# Lập chỉ mục (đen)
e(nid(), 'A1', 'A2', DATA + E.format(1, .5, 0, .5))
e(nid(), 'A2', 'A3', RTSP + E.format(1, .5, 0, .5), 'RTSP')
e(nid(), 'A3', 'B3', RTSP + E.format(.5, 1, 1, .5), '', [(430, 473)])
e(nid(), 'B1', 'B2', CTRL + E.format(1, .5, 0, .5))
e(nid(), 'B2', 'B3', CTRL + E.format(.5, 1, .5, 0), 'công việc kế tiếp', [(320, 425), (235, 425)])
e(nid(), 'B3', 'B4', DATA + E.format(.5, 1, .5, 0), 'khung hình đã lấy mẫu')
e(nid(), 'B4', 'B5', DATA + E.format(.5, 1, .5, 0), 'khung bao người')
e(nid(), 'B5', 'B6', DATA + E.format(.5, 1, .5, 0), 'lần xuất hiện đã kết thúc')
e(nid(), 'B6', 'B7', DATA + E.format(.5, 1, .5, 0), 'ảnh người (cắt tạm)')
e(nid(), 'B7', 'B8', DATA + E.format(.5, 1, .5, 0), 'vector đặc trưng')
e(nid(), 'B8', 'S1', DATA + E.format(.2, 1, .5, 0), '', [(160, 1000)])
e(nid(), 'B8', 'S2', DATA + E.format(.5, 1, .3, 0), '', [(235, 990), (437, 990)])
e(nid(), 'B8', 'S3', DATA + E.format(.8, 1, .5, 0), '', [(310, 980), (740, 980)])
# Công việc từ tệp tải lên
e(nid(), 'C1', 'B2', CTRL + E.format(0, .3, 1, .5), 'tạo công việc<br>(tệp tải lên)', [(495, 480), (495, 358)])
# Tìm kiếm và truy cập dữ liệu (xanh)
e(nid(), 'D1', 'C1', DATA + SEARCH + E.format(.3, 1, .22, 0), 'truy vấn')
e(nid(), 'C1', 'D1', DATA + SEARCH + E.format(.5, 0, .82, 1), 'kết quả')
e(nid(), 'A4', 'C1', DATA + SEARCH + E.format(.5, 1, .81, 0), 'tải lên')
e(nid(), 'C3', 'C2', DATA + SEARCH + E.format(1, .5, .5, 0), 'câu tiếng Anh', [(875, 508)])
e(nid(), 'C1', 'S1', DATA + SEARCH + BOTH + E.format(.06, 1, .85, 0), 'quyền, thông tin mô tả', [(558, 1010), (266, 1010)])
e(nid(), 'C2', 'S2', DATA + SEARCH + BOTH + E.format(.5, 1, .8, 0), 'tìm vector gần nhất<br>(lọc trước)', [(875, 1018), (582, 1018)], -0.55)
e(nid(), 'S3', 'C1', DATA + SEARCH + E.format(.75, 0, .49, 1), 'khung hình', [(760, 960)], 0.6)

# Chú giải (chỉ các ký hiệu có trong hình)
LG = 'text;html=1;align=left;verticalAlign=middle;whiteSpace=wrap;'
v('L', 'Chú giải', FRAME, 0, 1250, 1000, 185)
v('L1', 'Tệp dữ liệu', DOC, 20, 1292, 120, 50)
v('L2', 'Xử lý', PROC, 160, 1295, 80, 45)
v('L3', 'Thành phần phần mềm', COMP, 260, 1295, 210, 45)
v('L4', 'Mô hình AI', ICON_R + BRAIN + ';', 495, 1295, 45, 45)
v('L5', '', DB, 20, 1365, 36, 50)
v('L5t', 'CSDL', LG, 62, 1375, 60, 30)
v('L6', 'Hàng đợi', QUEUE, 140, 1370, 100, 40)
v('L7', 'Kho đối tượng', ICON_R + BUCKET + ';', 262, 1368, 45, 45)
v('L8', 'Camera', ICON_R + CAMERA + ';', 495, 1373, 50, 38)
v('L9', '<b>━</b> luồng RTSP<br>- - - điều khiển<br><font color="#1F4E9A">──</font> tìm kiếm, truy cập dữ liệu', LG, 720, 1300, 275, 110)

xml = ('<mxfile host="app.diagrams.net"><diagram name="H2 - Kiến trúc" id="h2"><mxGraphModel dx="1400" dy="1100" grid="1" '
       'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" '
       'pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
