"""Sinh figures/S05-ke-hoach.drawio: biểu đồ Gantt kế hoạch thực hiện của cả nhóm (Part I + Part II) cho slide và Hình 12.1 (mục 12.1 Project Timeline) của bản tiếng Anh.

Mốc là kế hoạch ước lượng (bắt đầu 15/6/2026), không phải nhật ký chính xác. Font và bảng màu như các sơ đồ
khác (figures/README.md mục 3). Chạy: python report/tools-en/slide_plan_gantt_drawio.py
"""
from datetime import date, timedelta
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/S05-ke-hoach.drawio'
F = 'fontFamily=Times New Roman;'
cells = []
n = 0


def v(val, style, x, y, w, h):
    global n
    n += 1
    cells.append(f'<mxCell id="c{n}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


START = date(2026, 6, 15)          # thứ Hai
WEEKS = 17                          # tới hết tuần 5/10 - 11/10
NAME_W, RES_W, WEEK_W, ROW_H, HEAD_H = 400, 90, 72, 32, 60
X0 = NAME_W + RES_W


def x_of(d):
    return X0 + (d - START).days / 7 * WEEK_W


GROUPS = {
    'design': ('#DAE8FC', '#6C8EBF', 'Analysis & design'),
    'impl': ('#D5E8D4', '#82B366', 'Implementation'),
    'test': ('#FFE6CC', '#D79B00', 'Testing & deployment'),
    'report': ('#E1D5E7', '#9673A6', 'Report & defense'),
}
D = date
TASKS = [   # (nhóm, việc, người thực hiện, bắt đầu, kết thúc)
    ('design', 'Topic definition & scope', 'Both', D(2026, 6, 15), D(2026, 6, 28)),
    ('design', 'Survey of related systems & requirements', 'Huy', D(2026, 6, 22), D(2026, 7, 5)),
    ('design', 'Architecture, use cases, data design', 'Huy', D(2026, 6, 29), D(2026, 7, 19)),
    ('design', 'Model selection & trials (YOLO, RaSa)', 'Huy', D(2026, 7, 6), D(2026, 8, 2)),
    ('design', 'Literature review (TBPS, CLIP, ZARA)', 'Cuong', D(2026, 6, 22), D(2026, 7, 19)),
    ('design', 'Shared pipeline & search-block interface', 'Both', D(2026, 7, 6), D(2026, 7, 19)),
    ('impl', 'Storage layer (PostgreSQL, Milvus, MinIO)', 'Huy', D(2026, 7, 20), D(2026, 8, 9)),
    ('impl', 'Application server: API, auth, permissions', 'Huy', D(2026, 7, 27), D(2026, 8, 23)),
    ('impl', 'Background AI worker pipeline', 'Huy', D(2026, 8, 3), D(2026, 9, 6)),
    ('impl', 'Web application for three roles', 'Huy', D(2026, 8, 17), D(2026, 9, 13)),
    ('impl', 'RTSP simulation & integration', 'Huy', D(2026, 8, 31), D(2026, 9, 20)),
    ('impl', 'Attribute index with Qwen2.5-VL', 'Cuong', D(2026, 7, 20), D(2026, 8, 16)),
    ('impl', 'Multi-agent reasoning funnel & prompts', 'Cuong', D(2026, 8, 3), D(2026, 9, 13)),
    ('impl', 'Evaluation tooling & replay', 'Cuong', D(2026, 8, 24), D(2026, 9, 13)),
    ('test', 'Testing & search evaluation', 'Huy', D(2026, 9, 7), D(2026, 9, 27)),
    ('test', 'Demo data & deployment', 'Huy', D(2026, 9, 14), D(2026, 9, 27)),
    ('test', 'Experiments on Market-1501 & ablations', 'Cuong', D(2026, 9, 7), D(2026, 9, 27)),
    ('report', 'Report outline, introduction & conclusion', 'Both', D(2026, 8, 24), D(2026, 9, 27)),
    ('report', 'Report Part I (application)', 'Huy', D(2026, 8, 24), D(2026, 9, 30)),
    ('report', 'Report Part II (research)', 'Cuong', D(2026, 9, 7), D(2026, 9, 30)),
    ('report', 'Report review, slides & rehearsal', 'Both', D(2026, 9, 28), D(2026, 10, 11)),
]
MILESTONES = [('Mid-term review', D(2026, 8, 10)), ('Report submitted', D(2026, 9, 30))]

rows = len(TASKS) + 1               # +1 hàng mốc
W = X0 + WEEKS * WEEK_W
H = HEAD_H + rows * ROW_H

HEAD = 'rounded=0;whiteSpace=wrap;html=1;fillColor=#F4F5FA;strokeColor=#D0D3E0;fontStyle=1;fontSize=17;'
CELL = 'rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#E3E5EF;'
TXT = 'text;html=1;align=left;verticalAlign=middle;spacingLeft=10;fontSize=16;'

# Tiêu đề cột tên công việc
v('Task', HEAD + 'align=left;spacingLeft=10;', 0, 0, NAME_W, HEAD_H)
v('Member', HEAD, NAME_W, 0, RES_W, HEAD_H)
# Hàng tháng
months = []
d = START
for i in range(WEEKS):
    wk = START + timedelta(weeks=i)
    key = wk.strftime('%b %Y')
    if not months or months[-1][0] != key:
        months.append([key, i, 1])
    else:
        months[-1][2] += 1
for key, i, cnt in months:
    v(key, HEAD, X0 + i * WEEK_W, 0, cnt * WEEK_W, HEAD_H / 2)
# Hàng ngày đầu tuần
for i in range(WEEKS):
    wk = START + timedelta(weeks=i)
    v(f'{wk.day}/{wk.month}', HEAD + 'fontStyle=0;fontSize=16;', X0 + i * WEEK_W, HEAD_H / 2, WEEK_W, HEAD_H / 2)

# Lưới và tên công việc
for r in range(rows):
    y = HEAD_H + r * ROW_H
    v('', CELL + ('fillColor=#FAFAFC;' if r % 2 else ''), 0, y, W, ROW_H)
for i in range(1, WEEKS):
    v('', 'line;strokeColor=#E3E5EF;direction=south;html=1;', X0 + i * WEEK_W - 1, HEAD_H, 2, rows * ROW_H)
v('', 'line;strokeColor=#C9CCD8;direction=south;html=1;', X0 - 1, 0, 2, H)
v('', 'line;strokeColor=#E3E5EF;direction=south;html=1;', NAME_W - 1, 0, 2, H)

for r, (g, name, who, a, b) in enumerate(TASKS):
    y = HEAD_H + r * ROW_H
    fill, stroke, _ = GROUPS[g]
    v(name, TXT, 0, y, NAME_W, ROW_H)
    v(who, 'text;html=1;align=center;verticalAlign=middle;fontSize=16;' + ('fontStyle=1;' if who == 'Both' else ''),
      NAME_W, y, RES_W, ROW_H)
    x1, x2 = x_of(a), x_of(b + timedelta(days=1))
    v('', f'rounded=1;arcSize=30;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;',
      x1, y + 6, x2 - x1, ROW_H - 12)

# Hàng mốc
y = HEAD_H + len(TASKS) * ROW_H
v('<b>Milestones</b>', TXT, 0, y, NAME_W, ROW_H)
for label, d in MILESTONES:
    cx = x_of(d) + WEEK_W / 14
    v('', 'rhombus;html=1;fillColor=#D9822B;strokeColor=#B5651D;', cx - 10, y + 6, 20, 20)
    left = cx > W - 260              # mốc gần mép phải: đặt nhãn bên trái hình thoi
    v(label, 'text;html=1;align=%s;verticalAlign=middle;fontSize=16;fontColor=#B5651D;fontStyle=1;'
      % ('right' if left else 'left'), cx - 214 if left else cx + 14, y + 1, 200, 30)

# Chú giải
lx = 0
ly = H + 18
for g in ('design', 'impl', 'test', 'report'):
    fill, stroke, label = GROUPS[g]
    v('', f'rounded=1;arcSize=30;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;', lx, ly + 6, 40, 20)
    v(label, 'text;html=1;align=left;verticalAlign=middle;fontSize=17;', lx + 48, ly, 230, 32)
    lx += 290

xml = ('<mxfile host="app.diagrams.net"><diagram name="S05 - Plan (slide)" id="s05"><mxGraphModel dx="1800" dy="800" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       f'pageWidth="{int(W) + 20}" pageHeight="{int(ly) + 50}" math="0" shadow="0"><root><mxCell id="0"/>'
       '<mxCell id="1" parent="0"/>' + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
