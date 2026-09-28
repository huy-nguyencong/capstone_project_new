"""Sinh figures/H6-trang-thai-lan-xuat-hien.drawio: sơ đồ trạng thái UML của một lần xuất hiện (person_tracks.index_status).

Khớp storage/postgres/models/person_track.py (ALLOWED_TRACK_TRANSITIONS: PENDING->PENDING/READY/FAILED, FAILED->FAILED/PENDING,
READY->READY/FAILED), services/track_ingestion.py (RetryPolicy 5 lần, 2 s nhân đôi, tối đa 300 s) và
services/storage_maintenance.py (đối soát cách ly READY -> FAILED; requeue FAILED -> PENDING).
Chạy: python report/tools/h6_track_state_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H6-trang-thai-lan-xuat-hien.drawio'
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
INIT = 'ellipse;html=1;fillColor=#000000;strokeColor=#000000;'
T = 'endArrow=open;endSize=12;html=1;rounded=0;labelBackgroundColor=#ffffff;'
ORTHO = T + 'edgeStyle=orthogonalEdgeStyle;'
E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'

v('init', '', INIT, 135, 20, 30, 30)
v('P', '<b>Chờ</b><br>(PENDING)', STATE, 50, 150, 200, 80)
v('R', '<b>Sẵn sàng</b><br>(READY)', STATE, 650, 150, 200, 80)
v('F', '<b>Thất bại</b><br>(FAILED)', STATE, 350, 470, 200, 80)

e('t0', 'init', 'P', T + E.format(.5, 1, .5, 0), 'ghi bản ghi + sự kiện<br>outbox (một giao dịch)', None, 0, (130, 0))
e('t1', 'P', 'R', T + E.format(1, .5, 0, .5), 'đã ghi khung hình (MinIO)<br>và vector (Milvus)')
e('t2', 'P', 'P', ORTHO + E.format(0, .3, 0, .7), 'lỗi tạm thời /<br>hẹn thử lại', [(15, 174), (15, 206)], None, (-80, 0))
e('t3', 'P', 'F', ORTHO + E.format(.5, 1, 0, .5), 'lỗi không phục hồi<br>hoặc hết 5 lần thử', [(150, 510)])
e('t4', 'F', 'P', ORTHO + E.format(0, .25, .8, 1), 'đưa lại hàng chờ<br>(requeue-track)', [(290, 490), (290, 330), (210, 330)], 0.35)
e('t5', 'R', 'F', ORTHO + E.format(.5, 1, 1, .5), 'đối soát phát hiện thiếu<br>khung hình, vector<br>hoặc sai mã băm', [(750, 510)])

xml = ('<mxfile host="app.diagrams.net"><diagram name="H6 - Trạng thái lần xuất hiện" id="h6"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="827" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
