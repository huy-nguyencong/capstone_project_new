"""Sinh figures/H12-luong-man-hinh.drawio: sơ đồ luồng màn hình theo vai trò.

Khớp frontend/src/constants/navigation.js (menu, trang chủ theo vai trò), routes/AppRoutes.jsx (route + RequireRole),
features/results/ResultViewer.jsx (hộp thoại chi tiết -> CreateCaseDialog / AddToCaseDialog), features/cases/CaseDetail.jsx
(mở ResultViewer), pages/viewer/OverviewPage.jsx (chọn vụ việc gần đây -> /case-files?case=id), CaseBrowserPage (nút Tìm kiếm).
Chạy: python report/tools/h12_screen_flow_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/H12-luong-man-hinh.drawio'
FS = 20
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


n = 0


def e(s, t, style, val='', pts=None, lx=None, off=None):
    global n
    n += 1
    g = '<mxGeometry relative="1" as="geometry"' + (f' x="{lx}"' if lx is not None else '') + '>'
    if off:
        g += f'<mxPoint x="{off[0]}" y="{off[1]}" as="offset"/>'
    if pts:
        g += '<Array as="points">' + ''.join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts) + '</Array>'
    g += '</mxGeometry>'
    cells.append(f'<mxCell id="e{n}" value={quoteattr(val)} style={quoteattr(style + F)} edge="1" parent="1" '
                 f'source="{s}" target="{t}">{g}</mxCell>')


SCREEN = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#D5E8D4;strokeColor=#82B366;'
DIALOG = 'rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#FFFFFF;strokeColor=#666666;'
LANE = 'rounded=0;whiteSpace=wrap;html=1;dashed=1;fillColor=none;verticalAlign=top;align=left;spacingLeft=10;fontStyle=1;spacingTop=4;'
SEC = 'text;html=1;align=left;verticalAlign=middle;fontStyle=2;'
A = 'endArrow=block;endFill=1;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;labelBackgroundColor=#ffffff;'
HOME = A + 'strokeWidth=2.5;'
E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'

v('login', 'Login', SCREEN, 390, 0, 220, 56)
# Làn Quản trị viên
v('LA', 'Administrator', LANE, 0, 120, 310, 690)
v('sa1', 'Administration', SEC, 25, 165, 150, 30)
for i, name in enumerate(['Accounts', 'Cameras', 'AI processing', 'AI models', 'Video processing']):
    v(f'a{i}', name, SCREEN, 30, 200 + i * 62, 250, 48)
v('sa2', 'Monitoring', SEC, 25, 515, 150, 30)
for i, name in enumerate(['System status', 'AI check', 'Audit log']):
    v(f'm{i}', name, SCREEN, 30, 550 + i * 62, 250, 48)
# Làn Giám sát viên
v('LO', 'Operator', LANE, 345, 120, 310, 690)
v('o1', 'Person search', SCREEN, 375, 180, 250, 60)
v('o2', 'Result details<br>(full frame)', DIALOG, 375, 330, 250, 70)
v('o3', 'Create new case /<br>Add to existing case', DIALOG, 375, 480, 250, 70)
v('o4', 'My cases<br>(list + details)', SCREEN, 375, 660, 250, 70)
# Làn Quản lý
v('LV', 'Viewer', LANE, 690, 120, 310, 690)
v('v1', 'Overview', SCREEN, 720, 180, 250, 60)
v('v2', 'Case files<br>(list + details)', SCREEN, 720, 330, 250, 70)
v('v3', 'Result details<br>(full frame)', DIALOG, 720, 480, 250, 70)

# Trang chủ theo vai trò sau đăng nhập
e('login', 'a0', HOME + E.format(0, .5, .8, 0), '', [(230, 28)])
e('login', 'o1', HOME + E.format(.5, 1, .5, 0))
e('login', 'v1', HOME + E.format(1, .5, .6, 0), '', [(870, 28)])
# Giám sát viên
e('o1', 'o2', A + E.format(.5, 1, .5, 0), 'select result')
e('o2', 'o3', A + E.format(.5, 1, .5, 0), 'save result')
e('o4', 'o2', A + E.format(1, .5, 1, .5), 'select saved<br>result', [(640, 695), (640, 365)], -0.35)
e('o4', 'o1', A + E.format(0, .3, 0, .5), 'search', [(360, 681), (360, 210)], -0.5)
# Quản lý
e('v1', 'v2', A + E.format(.5, 1, .5, 0), 'select a recent case')
e('v2', 'v3', A + E.format(.5, 1, .5, 0), 'select result')

# Không vẽ chú giải (SV quyết định 2026-09-29: nhãn trên hình đã đủ rõ).

xml = ('<mxfile host="app.diagrams.net"><diagram name="H12 - Screen flow" id="h12"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
