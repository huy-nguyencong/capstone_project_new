"""Sinh figures/H3-luu-do-xu-ly-camera.drawio: lưu đồ xử lý một công việc (vòng lặp theo khung hình).

Chi tiết hơn Hình 5.1: vòng lặp đọc khung, các điểm rẽ nhánh (kết thúc nguồn/hủy, lấy mẫu i mod N, lần xuất hiện kết thúc),
dữ liệu trung gian. Khớp workers/pipeline.py, workers/sampling.py, ai/selectors/representative.py, services/track_ingestion.py.
Ký hiệu theo figures/README.md mục 3. Chạy: python report/tools/h3_pipeline_flow_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/H3-luu-do-xu-ly-camera.drawio'
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
BUCKET = svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" fill="#FFE6CC" stroke="#D79B00" stroke-width="1.5">'
    '<path d="M5 9l4 27c.3 2 22 2 22.3 0L35 9z"/><ellipse cx="20" cy="9" rx="15" ry="4.5"/></svg>')


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


PROC = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;'
DATA = 'shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;size=18;fillColor=#FFF2CC;strokeColor=#D6B656;'
DEC = 'rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;'
TERM = 'rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=#666666;'
DB = 'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=10;fillColor=#FFE6CC;strokeColor=#D79B00;'
ICON_R = 'shape=image;html=1;imageAspect=0;aspect=fixed;labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;image='
ICON_B = 'shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image='
A = 'endArrow=block;endFill=1;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;labelBackgroundColor=#ffffff;jumpStyle=arc;'
E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'

# --- Cột trái: vòng lặp theo khung hình (khớp workers/production.py ProductionPipeline.run) ---
# Sửa 2026-09-29: mã hóa và ghi dữ liệu diễn ra SAU vòng lặp (selector.flush -> encode -> publish ở workers/durable.py),
# không phải ngay khi từng lần xuất hiện kết thúc. Hủy/quá hạn giữa chừng -> không ghi lần xuất hiện nào (mô tả trong văn bản 5.2.1).
v('L0', 'Processing job<br>(camera, source, N)', DATA, 50, 0, 330, 70)
v('L1', 'Read and decode the next frame', PROC, 50, 110, 330, 64)
v('L2', 'End of source or<br>session limit?', DEC, 45, 215, 340, 130)
v('L3', 'i mod N = 0 ?', DEC, 80, 385, 270, 100)
v('L4', 'Person detection<br>(YOLO11n)', ICON_R + BRAIN + ';', 185, 525, 60, 60)
v('L5', 'Person boxes', DATA, 85, 620, 260, 56)
v('L6', 'Tracking<br>(ByteTrack /<br>BoT-SORT)', ICON_R + BRAIN + ';', 185, 715, 60, 60)
v('L8', 'Update representative frame<br>candidates (at most 3);<br>appearance ended:<br>choose and keep its frame', PROC, 20, 830, 390, 130)
# --- Cột phải: sau khi đọc hết nguồn ---
v('R0', 'End the appearances<br>still being tracked', PROC, 470, 240, 330, 80)
v('R1', 'For each appearance: crop the<br>person temporarily (widen 5%)', PROC, 470, 370, 330, 80)
v('R2b', 'Image encoder<br>(RaSa)', ICON_R + BRAIN + ';', 605, 490, 60, 60)
v('R3', '256-d vector, frame,<br>bounding box', DATA, 470, 590, 330, 70)
v('R4', 'Write to the three stores<br>(PENDING → READY, retries)', PROC, 470, 700, 330, 76)
v('END', 'End of job', TERM, 525, 830, 220, 60)
# --- Kho dữ liệu ---
v('S1', '<b>PostgreSQL</b><br>descriptions', DB, 930, 560, 190, 90)
v('S3', '<b>MinIO</b><br>frames', ICON_R + BUCKET + ';', 935, 700, 60, 60)
v('S2', '<b>Milvus</b><br>vector', DB, 930, 800, 190, 90)

e('L0', 'L1', A + E.format(.5, 1, .5, 0))
e('L1', 'L2', A + E.format(.5, 1, .5, 0))
e('L2', 'R0', A + E.format(1, .5, 0, .5), 'Yes')
e('L2', 'L3', A + E.format(.5, 1, .5, 0), 'No')
e('L3', 'L1', A + E.format(0, .5, 0, .5), 'No', [(0, 435), (0, 142)], -0.85)
e('L3', 'L4', A + E.format(.5, 1, .5, 0), 'Yes')
e('L4', 'L5', A + E.format(.5, 1, .5, 0))
e('L5', 'L6', A + E.format(.5, 1, .5, 0))
e('L6', 'L8', A + E.format(.5, 1, .5, 0))
e('L8', 'L1', A + E.format(0, .5, 0, .5), '', [(0, 895), (0, 142)])
e('R0', 'R1', A + E.format(.5, 1, .5, 0))
e('R1', 'R2b', A + E.format(.5, 1, .5, 0))
e('R2b', 'R3', A + E.format(.5, 1, .5, 0))
e('R3', 'R4', A + E.format(.5, 1, .5, 0))
e('R4', 'END', A + E.format(.5, 1, .5, 0))
e('R4', 'S1', A + E.format(1, .5, 0, .5), '', [(870, 738), (870, 605)])
e('R4', 'S3', A + E.format(1, .5, 0, .5), '', [(870, 738), (870, 730)])
e('R4', 'S2', A + E.format(1, .5, 0, .5), '', [(870, 738), (870, 845)])

# Không vẽ chú giải (SV quyết định 2026-09-29: nhãn trên hình đã đủ rõ).

xml = ('<mxfile host="app.diagrams.net"><diagram name="H3 - Job flowchart" id="h3"><mxGraphModel dx="1400" dy="1100" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1169" pageHeight="1654" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
