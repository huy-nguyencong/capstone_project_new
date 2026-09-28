"""Sinh figures/H4-tuan-tu-tim-kiem.drawio: sơ đồ tuần tự UML của luồng tìm kiếm.

Khớp services/searches.py (tạo câu từ thuộc tính, mã hóa trong tiến trình API), services/track_search.py
(khu vực/camera từ phiên, lọc trước trong Milvus, đối chiếu PostgreSQL, tìm lại gấp đôi tối đa 3 lượt)
và API ảnh cắt (kiểm tra quyền rồi đọc khung hình từ MinIO). Chạy: python report/tools/h4_search_sequence_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H4-tuan-tu-tim-kiem.drawio'
FS = 20
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []
X = {'GS': 60, 'WEB': 220, 'API': 400, 'PG': 640, 'MV': 805, 'MN': 955}
NAMES = {'GS': 'Giám sát viên', 'WEB': 'Ứng dụng web', 'API': 'Máy chủ<br>ứng dụng', 'PG': 'PostgreSQL',
         'MV': 'Milvus', 'MN': 'MinIO'}
TOP, BOTTOM, HEAD = 0, 1210, 60


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


n = 0


def msg(a, b, y, text, ret=False):
    """Thông điệp ngang từ lifeline a tới b tại tung độ y (ret=True: thông điệp trả về, nét đứt)."""
    global n
    n += 1
    xa, xb = X[a], X[b]
    xa += 6 if xb > xa else -6
    xb += -6 if xb > xa else 6
    style = ('html=1;verticalAlign=bottom;labelBackgroundColor=none;rounded=0;'
             + ('dashed=1;endArrow=open;endSize=10;' if ret else 'endArrow=block;endFill=1;endSize=10;'))
    cells.append(f'<mxCell id="m{n}" value={quoteattr(text)} style={quoteattr(style + F)} edge="1" parent="1">'
                 f'<mxGeometry relative="1" as="geometry"><mxPoint x="{xa}" y="{y}" as="sourcePoint"/>'
                 f'<mxPoint x="{xb}" y="{y}" as="targetPoint"/></mxGeometry></mxCell>')


def self_msg(a, y, text, h=34):
    global n
    n += 1
    x = X[a] + 6
    style = 'html=1;align=left;spacingLeft=8;verticalAlign=middle;labelBackgroundColor=#ffffff;rounded=0;endArrow=block;endFill=1;endSize=10;'
    cells.append(f'<mxCell id="m{n}" value={quoteattr(text)} style={quoteattr(style + F)} edge="1" parent="1">'
                 f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x}" y="{y}" as="sourcePoint"/>'
                 f'<mxPoint x="{x}" y="{y + h}" as="targetPoint"/><Array as="points"><mxPoint x="{x + 40}" y="{y}"/>'
                 f'<mxPoint x="{x + 40}" y="{y + h}"/></Array><mxPoint x="36" y="0" as="offset"/></mxGeometry></mxCell>')


# Lifeline
for key, x in X.items():
    if key == 'GS':
        v('ll' + key, NAMES[key], 'shape=umlLifeline;participant=umlActor;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;'
          'container=0;collapsible=0;recursiveResize=0;verticalAlign=top;spacingTop=62;outlineConnect=0;size=' + str(HEAD) + ';whiteSpace=nowrap;',
          x - 20, TOP, 40, BOTTOM)
    else:
        v('ll' + key, NAMES[key], 'shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=0;'
          'collapsible=0;recursiveResize=0;outlineConnect=0;fillColor=#DAE8FC;strokeColor=#6C8EBF;size=' + str(HEAD) + ';',
          x - 62, TOP, 124, BOTTOM)
# Thanh kích hoạt của máy chủ ứng dụng
ACTV = 'html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#ffffff;'
v('act1', '', ACTV, X['API'] - 6, 175, 12, 625)
v('act2', '', ACTV, X['API'] - 6, 880, 12, 240)

msg('GS', 'WEB', 130, 'nhập truy vấn')
msg('WEB', 'API', 175, 'gửi truy vấn, bộ lọc, k')
msg('API', 'PG', 225, 'kiểm tra phiên, khu vực')
msg('PG', 'API', 270, 'camera đang vận hành', ret=True)
self_msg('API', 300, 'tạo câu tiếng Anh<br>(nếu theo thuộc tính)')
self_msg('API', 375, 'mã hóa truy vấn')
v('loop', 'loop', 'shape=umlFrame;whiteSpace=wrap;html=1;width=70;height=32;boundedLbl=1;verticalAlign=middle;align=left;'
  'spacingLeft=6;fillColor=none;', 150, 440, 740, 320)
v('guard', '[thiếu kết quả hợp lệ;<br>k nhân đôi, tối đa 3 lượt]', 'text;html=1;align=left;verticalAlign=top;', 420, 445, 250, 60)
msg('API', 'MV', 545, 'tìm k vector gần nhất (lọc trước)')
msg('MV', 'API', 590, 'mã lần xuất hiện + điểm', ret=True)
msg('API', 'PG', 655, 'đối chiếu, kiểm tra')
msg('PG', 'API', 700, 'camera, thời điểm, bbox', ret=True)
msg('API', 'WEB', 795, 'tối đa k kết quả', ret=True)
v('loop2', 'loop', 'shape=umlFrame;whiteSpace=wrap;html=1;width=70;height=32;boundedLbl=1;verticalAlign=middle;align=left;'
  'spacingLeft=6;fillColor=none;', 110, 825, 900, 320)
v('guard2', '[mỗi kết quả]', 'text;html=1;align=left;verticalAlign=top;', 185, 828, 160, 30)
msg('WEB', 'API', 880, 'yêu cầu ảnh người')
msg('API', 'PG', 930, 'kiểm tra quyền')
msg('API', 'MN', 985, 'đọc khung hình đại diện')
msg('MN', 'API', 1030, 'khung hình toàn cảnh', ret=True)
self_msg('API', 1055, 'cắt, nới khung,<br>làm tối xung quanh')
msg('API', 'WEB', 1125, 'ảnh người', ret=True)
msg('WEB', 'GS', 1175, 'hiển thị', ret=True)

xml = ('<mxfile host="app.diagrams.net"><diagram name="H4 - Tuần tự tìm kiếm" id="h4"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
