"""Sinh figures/H2-kien-truc.drawio (kiến trúc tổng thể) theo figures/specs/H2-kien-truc.md.

Bố cục 2 cột dọc để chữ in ra ~9pt ở khổ 16 cm: trái = lập chỉ mục (nguồn camera -> xử lý nền),
phải = tìm kiếm (người dùng -> máy chủ ứng dụng); tầng lưu trữ trải ngang phía dưới.
Ký hiệu theo figures/README.md mục 3. Chạy: python report/tools/h2_architecture_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/H2-kien-truc.drawio'
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
# 2026-09-29: cột phải dời sang phải 70 px (khe giữa hai cột 130 px) để nhãn của các đường nối
# giữa máy chủ và tiến trình nền không đè lên khung; nhãn vòng lặp viết dọc.
v('A', 'Camera data source', FRAME, 0, 0, 530, 230)
v('A1', '7 video files<br>(WILDTRACK)', MDOC, 8, 70, 180, 100)
v('A2', 'FFmpeg +<br>MediaMTX', PROC, 214, 80, 124, 80)
v('A3', '7 logical<br>cameras', ICON_T + CAMERA + ';', 425, 110, 70, 53)
# --- Cột trái: xử lý nền ---
# 2026-09-29 (góp ý GVHD): khung hình không đi thẳng xuống bước ghi; mỗi khung hình được lấy mẫu,
# phát hiện, theo vết rồi cập nhật BỘ ĐỆM TRACK (SV bỏ mũi tên vòng lặp, thay bằng nhãn 'từng khung hình'). Chỉ khi hết phiên
# RTSP (1.800 khung hình nguồn) hoặc hết tệp, các track mới được cắt ảnh, mã hóa và ghi (production.py).
v('B', 'Background AI worker', FRAME, 0, 270, 530, 815)
v('B1', 'RTSP session scheduler<br>(camera rotation)', PROC, 12, 320, 172, 76)
v('B2', 'Job queue<br>(in PostgreSQL)', QUEUE + 'spacingRight=30;', 224, 320, 218, 76)
v('B3', 'Frame sampling (1/N)', PROC, 45, 440, 230, 56)
v('B4', 'Person detection<br>YOLO11n', ICON_R + BRAIN + ';', 130, 545, 60, 60)
v('B5', 'Tracking<br>ByteTrack / BoT-SORT', ICON_R + BRAIN + ';', 130, 645, 60, 60)
v('BF', '<b>Track buffer</b><br>active tracks, representative<br>frame candidates', PROC, 35, 758, 250, 96)
v('B7', 'Image encoder<br>RaSa', ICON_R + BRAIN + ';', 130, 925, 60, 60)
v('B8', 'Write appearance data<br>(PENDING → READY)', PROC, 45, 1015, 230, 56)
# --- Cột phải: người dùng ---
v('D', 'Users', FRAME, 660, 0, 470, 230)
v('D2a', 'Administrator', ACT, 705, 40, 30, 56)
v('D2b', 'Operator', ACT, 830, 40, 30, 56)
v('D2c', 'Viewer', ACT, 950, 40, 30, 56)
v('D1', 'Web application (React)', COMP, 690, 150, 250, 56)
v('A4', 'Uploaded<br>video file', DOC, 970, 135, 140, 80)
# --- Cột phải: máy chủ ứng dụng (container = ranh giới tiến trình) ---
v('C1', 'Application server (Flask API)', CONT, 660, 300, 470, 700)
v('C1t', '<i>authentication, access control,<br>search, cases, administration</i>', 'text;html=1;align=center;verticalAlign=middle;', 790, 345, 330, 60)
# 2026-09-30: phạm vi được xác định sau khi mã hóa (track_search.py), nên ô chỉ còn 'Kiểm tra truy vấn'; phạm vi
# nằm ở nhãn mũi tên tới PostgreSQL. Kho xếp PostgreSQL | MinIO | Milvus: 3 chỗ cắt (tối thiểu) thay vì 6.
# 2026-09-29: truy vấn đi qua bước kiểm tra (5.2.3), rồi tách: thuộc tính -> tạo câu, ảnh/câu mô tả -> bộ mã hóa.
v('Q', 'Validate query', PROC, 690, 425, 240, 70)
v('C3', 'Build a sentence<br>from attributes', PROC, 690, 560, 190, 76)
v('C2', 'Query encoder<br>RaSa image / text', ICON_L + BRAIN + ';', 975, 740, 60, 60)
# --- Tầng lưu trữ ---
v('S', 'Storage layer', FRAME, 0, 1215, 1130, 200)
v('S1', '<b>PostgreSQL</b><br>accounts, cameras, appearances,<br>cases, audit log, job queue', DB, 20, 1260, 290, 135)
v('S2', '<b>Milvus</b> (vectors)<br>256-d vectors + area,<br>camera, time', DB, 780, 1260, 290, 135)
v('S3', '<b>MinIO</b><br>representative frames<br>(private bucket)', ICON_L + BUCKET + ';', 560, 1290, 70, 70)

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
e(nid(), 'A3', 'B3', RTSP + E.format(.5, 1, 1, .3), '', [(460, 457)])
e(nid(), 'B1', 'B2', CTRL + E.format(1, .5, 0, .5))
e(nid(), 'B2', 'B3', CTRL + E.format(.5, 1, .5, 0), 'next job', [(333, 420), (160, 420)])
e(nid(), 'B3', 'B4', DATA + E.format(.5, 1, .5, 0), 'each sampled frame')
e(nid(), 'B4', 'B5', DATA + E.format(.5, 1, .5, 0), 'person boxes')
e(nid(), 'B5', 'BF', DATA + E.format(.5, 1, .5, 0), 'update tracks')
e(nid(), 'BF', 'B7', DATA + E.format(.5, 1, .5, 0), 'end of session or file:<br>person crop (temporary)')
e(nid(), 'B7', 'B8', DATA + E.format(.5, 1, .5, 0), 'feature vector')
e(nid(), 'B8', 'S1', DATA + E.format(.2, 1, .62, 0), '', [(91, 1140), (200, 1140)])
e(nid(), 'B8', 'S2', DATA + E.format(.8, 1, .2, 0), '', [(229, 1097), (838, 1097)])
e(nid(), 'B8', 'S3', DATA + E.format(.5, 1, .5, 0), '', [(160, 1115), (595, 1115)])
# Tệp tải lên: máy chủ lưu tạm trên ổ đĩa (video_staging.py), tiến trình nền đọc tệp đó
e(nid(), 'C1', 'B2', CTRL + E.format(0, .257, 1, .5), 'create job<br>(uploaded file)', [(595, 480), (595, 358)])
e(nid(), 'C1', 'B3', DATA + E.format(0, .369, 1, .75), 'staged<br>video file', [(490, 558), (490, 482)], -0.72)
# Tìm kiếm và truy cập dữ liệu (xanh)
e(nid(), 'D1', 'Q', DATA + SEARCH + E.format(.25, 1, .258, 0), 'query', None, -0.5)
e(nid(), 'Q', 'C3', DATA + SEARCH + E.format(.4, 1, .5, 0), 'attributes')
e(nid(), 'Q', 'C2', DATA + SEARCH + E.format(1, .5, 1, .5), 'image, sentence', [(1080, 460), (1080, 770)], -0.69)
e(nid(), 'C1', 'D1', DATA + SEARCH + E.format(.5, 0, .82, 1), 'results')
e(nid(), 'A4', 'C1', DATA + SEARCH + E.format(.5, 1, .81, 0), 'upload')
e(nid(), 'C3', 'C2', DATA + SEARCH + E.format(1, .5, .5, 0), 'English sentence', [(1005, 598)])
e(nid(), 'C1', 'S1', DATA + SEARCH + BOTH + E.format(.02, 1, .85, 0), 'scope, permissions,<br>business data', [(669, 1175), (266, 1175)], 0.47)
# Bộ mã hóa chỉ tạo vector; Milvus trả kết quả về máy chủ (không về bộ mã hóa).
e(nid(), 'C2', 'S2', DATA + SEARCH + E.format(.5, 1, .776, 0), 'query vector<br>(pre-filtered)', None, -0.45)
e(nid(), 'S2', 'C1', DATA + SEARCH + E.format(.517, 0, .574, 1), 'nearest<br>results', None, 0.65)
e(nid(), 'S3', 'C1', DATA + SEARCH + E.format(1, .5, .213, 1), 'frames', [(760, 1325)], 0.8)

# Không vẽ chú giải (SV quyết định 2026-09-29: nhãn trên hình đã đủ rõ).

xml = ('<mxfile host="app.diagrams.net"><diagram name="H2 - Architecture" id="h2"><mxGraphModel dx="1400" dy="1100" grid="1" '
       'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" '
       'pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
