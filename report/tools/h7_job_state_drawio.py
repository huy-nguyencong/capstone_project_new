"""Sinh figures/H7-trang-thai-cong-viec.drawio: sơ đồ trạng thái UML của công việc xử lý (processing job).

Khớp services/jobs.py (claim: PENDING hoặc RUNNING hết hạn giữ chỗ -> RUNNING, giữ chỗ 60 s; cancel: PENDING -> CANCELLED ngay,
RUNNING -> CANCELLED khi tiến trình kiểm tra; defer_retry) và workers/durable.py (tối đa 3 lần thử).
Chạy: python report/tools/h7_job_state_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H7-trang-thai-cong-viec.drawio'
FS = 21
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []


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


STATE = 'rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;'
END_STATE = 'rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=#666666;'
INIT = 'ellipse;html=1;fillColor=#000000;strokeColor=#000000;'
FINAL = 'ellipse;html=1;shape=endState;fillColor=#000000;strokeColor=#000000;'
T = 'endArrow=open;endSize=12;html=1;rounded=0;labelBackgroundColor=#ffffff;'
ORTHO = T + 'edgeStyle=orthogonalEdgeStyle;'
E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'

v('init', '', INIT, 235, 30, 30, 30)
v('P', '<b>Chờ xử lý</b><br>(PENDING)', STATE, 150, 150, 200, 80)
v('R', '<b>Đang xử lý</b><br>(RUNNING)', STATE, 620, 150, 200, 80)
v('C', '<b>Đã hủy</b><br>(CANCELLED)', END_STATE, 150, 560, 200, 80)
v('F', '<b>Thất bại</b><br>(FAILED)', END_STATE, 450, 560, 200, 80)
v('S', '<b>Hoàn thành</b><br>(SUCCEEDED)', END_STATE, 750, 560, 200, 80)
v('fin', '', FINAL, 535, 740, 30, 30)

e('t0', 'init', 'P', T + E.format(.5, 1, .5, 0), 'Quản trị viên tải tệp lên /<br>bộ lập lịch tạo phiên RTSP', None, 0, (-150, 0))
e('t1', 'P', 'R', T + E.format(1, .5, 0, .5), 'tiến trình xử lý nền<br>nhận việc (giữ chỗ 60 s)')
e('t2', 'R', 'R', ORTHO + E.format(.3, 0, .7, 0), 'báo hiệu định kỳ / gia hạn giữ chỗ;<br>lỗi tạm thời, còn lượt thử / chờ rồi thử lại;<br>hết hạn giữ chỗ / nhận lại', [(680, 60), (760, 60)])
e('t4', 'R', 'S', ORTHO + E.format(.8, 1, .5, 0), 'xử lý xong', [(780, 400), (850, 400)])
e('t5', 'R', 'F', ORTHO + E.format(.5, 1, .5, 0), 'lỗi không phục hồi<br>hoặc hết số lần thử', [(720, 440), (550, 440)])
e('t6', 'R', 'C', ORTHO + E.format(.2, 1, .8, 0), 'yêu cầu hủy, camera ngừng<br>vận hành hoặc tắt AI', [(660, 330), (310, 330)])
e('t7', 'P', 'C', T + E.format(.3, 1, .3, 0), 'yêu cầu hủy')
e('t8', 'C', 'fin', ORTHO + E.format(.5, 1, 0, .5), '', [(250, 755)])
e('t9', 'F', 'fin', T + E.format(.5, 1, .5, 0))
e('t10', 'S', 'fin', ORTHO + E.format(.5, 1, 1, .5), '', [(850, 755)])

xml = ('<mxfile host="app.diagrams.net"><diagram name="H7 - Trạng thái công việc" id="h7"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="827" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
