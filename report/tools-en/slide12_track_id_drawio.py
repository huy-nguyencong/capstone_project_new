"""Sinh figures/S12-track-id.drawio: ba kho lưu trữ liên kết qua track_id, cho slide 12 (không dùng trong báo cáo).

2026-10-02: bố cục CỘT HẸP (ô track_id ở góc trên, đường trục dọc bên trái rẽ vào ba kho xếp chồng) để đặt
cạnh H6 trên cùng một slide mà H6 vẫn đủ lớn.

Ký hiệu giống H2 (figures/README.md mục 3): PostgreSQL = hình trụ viền mảnh, Milvus = hình trụ viền đậm
(CSDL vector), MinIO = hình xô viền mảnh 1 px. Nội dung mỗi kho lấy từ báo cáo Mục 5.3 và slide_guide_en.md.
Chạy: python report/tools-en/slide12_track_id_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/S12-track-id.drawio'
F = 'fontFamily=Times New Roman;fontSize=20;'
cells = []

BUCKET_W = 90
BUCKET = 'data:image/svg+xml,' + base64.b64encode((
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" fill="#FFE6CC" stroke="#D79B00" '
    f'stroke-width="{round(40 / BUCKET_W, 2)}">'  # nét 1 px khi vẽ ở bề rộng BUCKET_W
    '<path d="M5 9l4 27c.3 2 22 2 22.3 0L35 9z"/><ellipse cx="20" cy="9" rx="15" ry="4.5"/></svg>').encode()).decode()


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def e(id, s, t, ex, ey, pts):
    g = '<mxGeometry relative="1" as="geometry"><Array as="points">' + ''.join(
        f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts) + '</Array></mxGeometry>'
    cells.append(f'<mxCell id="{id}" value="" style={quoteattr(LINK + f"entryX={ex};entryY={ey};entryPerimeter=0;" + F)} edge="1" '
                 f'parent="1" source="{s}" target="{t}">{g}</mxCell>')


DB = 'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#FFE6CC;strokeColor=#D79B00;'
ICON_R = ('shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=right;verticalLabelPosition=middle;'
          'align=left;verticalAlign=middle;spacingLeft=14;image=')
KEY = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#ECE9FB;strokeColor=#6D5BD0;strokeWidth=2;fontColor=#3E2F9E;'
LINK = ('endArrow=none;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;strokeColor=#6D5BD0;strokeWidth=2;'
        'exitX=0.25;exitY=1;exitDx=0;exitDy=0;entryDx=0;entryDy=0;')

# Ô track_id ở góc trên trái; trục dọc tại x 40 (= 1/4 bề rộng ô) rẽ ngang vào giữa cạnh trái mỗi kho.
v('K', '<b>track_id</b><br><span style="font-size:16px">one appearance</span>', KEY, 0, 0, 160, 64)
v('PG', '<b>PostgreSQL</b><br>accounts, areas, cameras,<br>appearances, cases,<br>audit log, job queue',
  DB, 90, 100, 330, 150)
v('MI', '<b>MinIO</b><br>one representative<br>frame per appearance<br>(~358 KB)',
  ICON_R + BUCKET + ';', 84, 285, BUCKET_W, BUCKET_W)
v('MV', '<b>Milvus</b> (vectors)<br>one 256-d RaSa vector<br>+ area, camera, time',
  DB + 'strokeWidth=3;', 90, 420, 330, 140)

# Đường liên kết (không mũi tên): cùng một track_id ở cả ba kho.
# Thành trái của xô ở giữa chiều cao nằm tại x = 7/40 bề rộng ảnh (ảnh có lề trong suốt).
e('l1', 'K', 'PG', 0, .5, [(40, 175)])
e('l2', 'K', 'MI', .175, .5, [(40, 330)])
e('l3', 'K', 'MV', 0, .5, [(40, 490)])

xml = ('<mxfile host="app.diagrams.net"><diagram name="S12 - track_id (slide)" id="s12"><mxGraphModel dx="900" dy="700" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="440" pageHeight="580" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
