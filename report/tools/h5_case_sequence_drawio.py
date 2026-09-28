"""Sinh figures/H5-tuan-tu-vu-viec.drawio: sơ đồ tuần tự UML của luồng lưu kết quả vào vụ việc.

Khớp api/v1/cases.py (POST /cases, POST /cases/{id}/results, PATCH /cases/{id}) và services/cases.py
(người phụ trách lấy từ phiên; _save_track: READY + camera ACTIVE thuộc khu vực hiện tại; bản chụp; vụ việc CLOSED bị khóa;
PATCH so số phiên bản). "Đánh dấu hoàn thành khi lưu" = yêu cầu thứ hai do giao diện gửi.
Chạy: python report/tools/h5_case_sequence_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H5-tuan-tu-vu-viec.drawio'
FS = 20
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []
X = {'GS': 60, 'WEB': 250, 'API': 480, 'PG': 790}
NAMES = {'GS': 'Giám sát viên', 'WEB': 'Ứng dụng web', 'API': 'Máy chủ ứng dụng', 'PG': 'PostgreSQL'}
TOP, BOTTOM, HEAD = 0, 1145, 60


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


n = 0


def msg(a, b, y, text, ret=False):
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


def frame(id, kind, x, y, w, h, guard, gx):
    v(id, kind, 'shape=umlFrame;whiteSpace=wrap;html=1;width=60;height=32;boundedLbl=1;verticalAlign=middle;align=left;'
      'spacingLeft=6;fillColor=none;', x, y, w, h)
    v(id + 'g', guard, 'text;html=1;align=left;verticalAlign=top;', gx, y + 3, 330, 32)


def divider(y, x, w, guard, gx):
    global n
    n += 1
    cells.append(f'<mxCell id="d{n}" value="" style={quoteattr("endArrow=none;dashed=1;html=1;rounded=0;" + F)} edge="1" parent="1">'
                 f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x}" y="{y}" as="sourcePoint"/>'
                 f'<mxPoint x="{x + w}" y="{y}" as="targetPoint"/></mxGeometry></mxCell>')
    v(f'dg{n}', guard, 'text;html=1;align=left;verticalAlign=top;', gx, y + 3, 330, 32)


for key, x in X.items():
    if key == 'GS':
        v('ll' + key, NAMES[key], 'shape=umlLifeline;participant=umlActor;perimeter=lifelinePerimeter;html=1;container=0;'
          'collapsible=0;recursiveResize=0;verticalAlign=top;spacingTop=62;outlineConnect=0;whiteSpace=nowrap;size=' + str(HEAD) + ';',
          x - 20, TOP, 40, BOTTOM)
    else:
        v('ll' + key, NAMES[key], 'shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=0;'
          'collapsible=0;recursiveResize=0;outlineConnect=0;fillColor=#DAE8FC;strokeColor=#6C8EBF;size=' + str(HEAD) + ';',
          x - 90, TOP, 180, BOTTOM)
ACTV = 'html=1;points=[];perimeter=orthogonalPerimeter;fillColor=#ffffff;'
v('act1', '', ACTV, X['API'] - 6, 240, 12, 510)
v('act2', '', ACTV, X['API'] - 6, 870, 12, 150)

msg('GS', 'WEB', 130, 'chọn kết quả để lưu')
frame('alt', 'alt', 150, 165, 800, 410, '[tạo vụ việc mới]', 225)
msg('WEB', 'API', 265, 'tạo vụ việc (tiêu đề, ghi chú,<br>mã lần xuất hiện)')
msg('API', 'PG', 325, 'tạo vụ việc, người phụ trách<br>lấy từ phiên đăng nhập')
divider(360, 150, 800, '[thêm vào vụ việc đã có]', 160)
msg('WEB', 'API', 460, 'thêm kết quả (mã vụ việc,<br>mã lần xuất hiện)')
msg('API', 'PG', 525, 'kiểm tra vụ việc của mình,<br>đang xử lý')
msg('API', 'PG', 640, 'kiểm tra lần xuất hiện: sẵn sàng,<br>camera vận hành, đúng khu vực')
msg('API', 'PG', 705, 'tạo mục kết quả + bản chụp,<br>ghi nhật ký')
msg('API', 'WEB', 755, 'vụ việc, số phiên bản', ret=True)
frame('opt', 'opt', 150, 790, 800, 250, '[đánh dấu hoàn thành khi lưu]', 225)
msg('WEB', 'API', 880, 'đổi trạng thái Hoàn thành<br>(kèm số phiên bản)')
msg('API', 'PG', 950, 'so số phiên bản, cập nhật,<br>ghi nhật ký')
msg('API', 'WEB', 1015, 'thành công / lỗi', ret=True)
msg('WEB', 'GS', 1095, 'thông báo kết quả', ret=True)

xml = ('<mxfile host="app.diagrams.net"><diagram name="H5 - Tuần tự vụ việc" id="h5"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
