"""Sinh figures/H2-kien-truc-slide.drawio: bản NẰM NGANG của H2 cho slide 16:9 (slide 9).

Cùng khối và đường nối với H2 trong báo cáo (h2_architecture_drawio.py), sắp lại thành ba dải để vừa
vùng nội dung 1760 x 810 của slide với chữ lớn (22 px):
  dải trên  = nguồn camera (trái) | người dùng (phải)
  dải giữa  = tiến trình nền, pipeline hai hàng dạng rắn bò (trái) | máy chủ ứng dụng (phải)
2026-10-02: đủ mọi khối, nhãn và mũi tên như bản gốc (kể cả 'staged video file' và 5 nhãn đầu ra của pipeline).
  dải dưới  = tầng lưu trữ
Ký hiệu theo figures/README.md mục 3. Chạy: python report/tools-en/h2_architecture_slide_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/H2-kien-truc-slide.drawio'
FS = 22
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
# Xô vẽ ở 120 px (gấp 3 viewBox) nên nét 0,33 -> 1 px, bằng viền PostgreSQL; chỉ Milvus có viền đậm.
BUCKET = svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" fill="#FFE6CC" stroke="#D79B00" stroke-width="0.33">'
    '<path d="M5 9l4 27c.3 2 22 2 22.3 0L35 9z"/><ellipse cx="20" cy="9" rx="15" ry="4.5"/></svg>')


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def e(id, s, t, style, val='', pts=None, lx=None, off=None):
    g = '<mxGeometry relative="1" as="geometry"' + (f' x="{lx}"' if lx is not None else '') + '>'
    if off:
        g += f'<mxPoint x="{off[0]}" y="{off[1]}" as="offset"/>'
    if pts:
        g += '<Array as="points">' + ''.join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts) + '</Array>'
    g += '</mxGeometry>'
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} edge="1" parent="1" '
                 f'source="{s}" target="{t}">{g}</mxCell>')


FRAME = 'rounded=0;whiteSpace=wrap;html=1;dashed=1;fillColor=none;verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontStyle=1;'
PROC = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;'
DOC = 'shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFF2CC;strokeColor=#D6B656;'
MDOC = 'shape=mxgraph.flowchart.multi-document;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#D6B656;'
CONT = 'swimlane;whiteSpace=wrap;html=1;startSize=40;fillColor=#D5E8D4;strokeColor=#82B366;swimlaneFillColor=#F4FAF1;'
DB = 'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#FFE6CC;strokeColor=#D79B00;'
QUEUE = 'shape=mxgraph.flowchart.direct_data;whiteSpace=wrap;html=1;fillColor=#FFE6CC;strokeColor=#D79B00;'
COMP = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#D5E8D4;strokeColor=#82B366;'
ICON_L = 'shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=8;image='
ICON_B = 'shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image='
ICON_R = 'shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=8;image='
ACT = 'shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;'
DATA = 'endArrow=block;endFill=1;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;jumpStyle=arc;jumpSize=12;labelBackgroundColor=#ffffff;'
CTRL = DATA + 'dashed=1;'
RTSP = DATA + 'strokeWidth=3;'
SEARCH = 'strokeColor=#1F4E9A;fontColor=#1F4E9A;'

# ---------------- Dải trên ----------------
v('A', 'Camera data source', FRAME, 0, 0, 800, 210)
v('A1', '7 video files<br>(WILDTRACK)', MDOC, 20, 70, 190, 105)
v('A2', 'FFmpeg +<br>MediaMTX', PROC, 290, 80, 150, 84)
v('A3', '7 logical<br>cameras', ICON_R + CAMERA + ';', 620, 98, 64, 48)

v('D', 'Users', FRAME, 1120, 0, 650, 210)
v('D2a', 'Administrator', ACT, 1195, 44, 30, 56)
v('D2b', 'Operator', ACT, 1330, 44, 30, 56)
v('D2c', 'Viewer', ACT, 1455, 44, 30, 56)
v('D1', 'Web application (React)', COMP, 1150, 146, 300, 50)
v('A4', 'Uploaded<br>video file', DOC, 1580, 50, 160, 90)

# ---------------- Dải giữa: tiến trình nền ----------------
# Hàng 1 (trái -> phải): lấy mẫu -> phát hiện -> theo vết -> bộ đệm track.
# Hàng 2 (phải -> trái): hết phiên/tệp -> mã hóa ảnh -> ghi dữ liệu.
v('B', 'Background AI worker', FRAME, 0, 260, 1080, 560)
v('B1', 'RTSP session scheduler<br>(camera rotation)', PROC, 20, 300, 250, 64)
v('B2', 'Job queue<br>(in PostgreSQL)', QUEUE + 'spacingRight=28;', 320, 297, 220, 70)
v('B3', 'Frame sampling<br>(1/N)', PROC, 20, 455, 160, 84)
v('B4', 'Person detection<br>YOLO11n', ICON_B + BRAIN + ';', 333, 467, 60, 60)
v('B5', 'Tracking<br>ByteTrack /<br>BoT-SORT', ICON_B + BRAIN + ';', 546, 467, 60, 60)
v('BF', '<b>Track buffer</b><br>active tracks, representative<br>frame candidates', PROC, 760, 445, 300, 104)
v('B7', 'Image encoder<br>RaSa', ICON_B + BRAIN + ';', 880, 680, 60, 60)
v('B8', 'Write appearance data<br>(PENDING → READY)', PROC, 300, 670, 280, 80)

# ---------------- Dải giữa: máy chủ ứng dụng ----------------
v('C1', 'Application server (Flask API)', CONT, 1120, 260, 650, 560)
v('Q', 'Validate query', PROC, 1150, 360, 220, 64)
v('C3', 'Build a sentence<br>from attributes', PROC, 1150, 520, 220, 80)
v('C2', 'Query encoder<br>RaSa image / text', ICON_R + BRAIN + ';', 1480, 530, 60, 60)
v('C1t', '<i>authentication, access control,<br>search, cases, administration</i>', 'text;html=1;align=left;verticalAlign=middle;fontColor=#555555;', 1150, 680, 330, 56)

# ---------------- Dải dưới: lưu trữ ----------------
v('S', 'Storage layer', FRAME, 0, 900, 1770, 200)
v('S1', '<b>PostgreSQL</b><br>accounts, cameras, appearances,<br>cases, audit log, job queue', DB, 40, 945, 380, 135)
v('S3', '<b>MinIO</b><br>representative frames<br>(private bucket)', ICON_L + BUCKET + ';', 770, 955, 120, 120)
v('S2', '<b>Milvus</b> (vectors)<br>256-d vectors + area,<br>camera, time', DB + 'strokeWidth=3;', 1340, 945, 340, 135)

n = 0


def nid():
    global n
    n += 1
    return f'e{n}'


E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'
BOTH = 'startArrow=block;startFill=1;'

# Lập chỉ mục (đen)
e(nid(), 'A1', 'A2', DATA + E.format(1, .5, 0, .5))
e(nid(), 'A2', 'A3', RTSP + E.format(1, .5, 0, .5), 'RTSP', None, None, (0, -22))
# Ba đường vào bước lấy mẫu, mỗi đường một làn ngang riêng: hàng đợi (y 385), RTSP (y 405), tệp tạm (y 425).
e(nid(), 'A3', 'B3', RTSP + E.format(.5, 1, .5, 0), '', [(652, 405), (100, 405)])
e(nid(), 'B1', 'B2', CTRL + E.format(1, .5, 0, .5))
e(nid(), 'B2', 'B3', CTRL + E.format(.5, 1, .2, 0), 'next job', [(430, 385), (52, 385)], -0.6)
e(nid(), 'C1', 'B3', DATA + E.format(0, .295, .8, 0), 'staged video file', [(148, 425)], -0.35)
e(nid(), 'C1', 'B2', CTRL + E.format(0, .127, 1, .5), 'create job (uploaded file)', None, 0)
e(nid(), 'B3', 'B4', DATA + E.format(1, .5, 0, .5), 'each sampled<br>frame', None, None, (0, -34))
e(nid(), 'B4', 'B5', DATA + E.format(1, .5, 0, .5), 'person<br>boxes', None, None, (0, -34))
e(nid(), 'B5', 'BF', DATA + E.format(1, .5, 0, .5), 'update<br>tracks', None, None, (0, -34))
e(nid(), 'BF', 'B7', DATA + E.format(.5, 1, .5, 0), 'end of session or file:<br>person crop (temporary)', None, None, (-138, 0))
e(nid(), 'B7', 'B8', DATA + E.format(0, .5, 1, .5), 'feature vector', None, None, (0, -20))
e(nid(), 'B8', 'S1', DATA + E.format(.15, 1, .5, 0), '', [(342, 800), (230, 800)])
e(nid(), 'B8', 'S3', DATA + E.format(.5, 1, .5, 0), '', [(440, 830), (830, 830)])
e(nid(), 'B8', 'S2', DATA + E.format(.85, 1, .05, 0), '', [(538, 855), (1357, 855)])

# Tìm kiếm và truy cập dữ liệu (xanh)
e(nid(), 'A4', 'C1', DATA + SEARCH + E.format(.5, 1, .8308, 0), 'upload', None, 0.63, (42, 0))
e(nid(), 'D1', 'Q', DATA + SEARCH + E.format(.2, 1, .27, 0), 'query', None, -0.52, (38, 0))
e(nid(), 'C1', 'D1', DATA + SEARCH + E.format(.6, 0, .8, 1), 'results', [(1510, 235), (1390, 235)], -0.75, (46, 0))
e(nid(), 'Q', 'C3', DATA + SEARCH + E.format(.5, 1, .5, 0), 'attributes', None, None, (58, 0))
e(nid(), 'Q', 'C2', DATA + SEARCH + E.format(1, .5, .5, 0), 'image, sentence', [(1510, 392)], -0.3, (0, -20))
e(nid(), 'C3', 'C2', DATA + SEARCH + E.format(1, .5, 0, .5), 'English<br>sentence', None, None, (0, 38))
e(nid(), 'C2', 'S2', DATA + SEARCH + E.format(.5, 1, .5, 0), 'query vector<br>(pre-filtered)', None, 0.49, (-82, 0))
e(nid(), 'S2', 'C1', DATA + SEARCH + E.format(.65, 0, .6785, 1), 'nearest<br>results', None, 0.33, (62, 0))
e(nid(), 'S3', 'C1', DATA + SEARCH + E.format(1, .5, .28, 1), 'frames', [(1302, 1015)], 0.54, (-44, 0))
e(nid(), 'C1', 'S1', DATA + SEARCH + BOTH + E.format(.05, 1, .85, 0), 'scope, permissions, business data', [(1152, 880), (363, 880)], 0.34)

xml = ('<mxfile host="app.diagrams.net"><diagram name="H2 - Architecture (slide)" id="h2s"><mxGraphModel dx="1800" dy="1000" grid="1" '
       'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1790" '
       'pageHeight="1120" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
