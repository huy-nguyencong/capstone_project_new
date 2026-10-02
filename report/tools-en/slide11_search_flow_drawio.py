"""Sinh figures/S11-luong-tim-kiem.drawio: sơ đồ luồng tìm kiếm cho slide 11 (không dùng trong báo cáo).

Bám theo code: api/v1/searches.py (kiểm tra), services/searches.py (tạo câu, mã hóa),
services/track_search.py (_authorize -> phạm vi, Milvus có lọc, _hydrate -> kiểm tra lại).
Ký hiệu theo figures/README.md mục 3: bước xử lý = chữ nhật bo góc, mô hình AI = bộ não,
CSDL = hình trụ (CSDL vector viền đậm), thành phần phần mềm = khối xanh lá, dữ liệu vào/ra = hình bình hành.
Chạy: python report/tools-en/slide11_search_flow_drawio.py
"""
import base64
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/S11-luong-tim-kiem.drawio'
F = 'fontFamily=Times New Roman;fontSize=20;'
cells = []

BRAIN = 'data:image/svg+xml,' + base64.b64encode((
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#E1D5E7" stroke="#9673A6" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 5a3 3 0 0 0-5.6-1.5A3 3 0 0 0 3.5 7a3 3 0 0 0-.9 5.2A3.5 3.5 0 0 0 5 18a3 3 0 0 0 5.5 1.5A2 2 0 0 0 12 20z"/>'
    '<path d="M12 5a3 3 0 0 1 5.6-1.5A3 3 0 0 1 20.5 7a3 3 0 0 1 .9 5.2A3.5 3.5 0 0 1 19 18a3 3 0 0 1-5.5 1.5A2 2 0 0 1 12 20z"/>'
    '<path d="M12 5v15M8 8.5c1 0 2 .7 2 2M16 8.5c-1 0-2 .7-2 2M7.5 14c1.2 0 2.2-.6 2.5-1.5M16.5 14c-1.2 0-2.2-.6-2.5-1.5" fill="none"/>'
    '</svg>').encode()).decode()

# Máy chủ ứng dụng (README: thành phần phần mềm lớn = biểu tượng máy chủ, xanh lá)
SERVER = 'data:image/svg+xml,' + base64.b64encode((
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#D5E8D4" stroke="#82B366" stroke-width="1.3">'
    '<rect x="4" y="2.5" width="16" height="5.5" rx="1"/><rect x="4" y="9.25" width="16" height="5.5" rx="1"/>'
    '<rect x="4" y="16" width="16" height="5.5" rx="1"/>'
    '<g fill="#82B366" stroke="none"><circle cx="7" cy="5.25" r=".9"/><circle cx="7" cy="12" r=".9"/><circle cx="7" cy="18.75" r=".9"/></g>'
    '</svg>').encode()).decode()


def v(id, val, style, x, y, w, h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def e(id, s, t):
    cells.append(f'<mxCell id="{id}" value="" style={quoteattr(ARROW + F)} edge="1" parent="1" source="{s}" target="{t}">'
                 '<mxGeometry relative="1" as="geometry"/></mxCell>')


PROC = 'rounded=1;whiteSpace=wrap;html=1;spacingLeft=14;spacingRight=14;fillColor=#DAE8FC;strokeColor=#6C8EBF;'
HOT = 'rounded=1;whiteSpace=wrap;html=1;spacingLeft=14;spacingRight=14;fillColor=#DAE8FC;strokeColor=#D9822B;strokeWidth=3;'
DATA = 'shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;size=18;fillColor=#FFF2CC;strokeColor=#D6B656;'
COMP = 'rounded=1;whiteSpace=wrap;html=1;fillColor=#D5E8D4;strokeColor=#82B366;'
DB = 'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=8;fillColor=#FFE6CC;strokeColor=#D79B00;verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;'
ICON = 'shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image='
ARROW = 'endArrow=block;endFill=1;html=1;rounded=0;exitX=1;exitY=0.5;entryX=0;entryY=0.5;exitDx=0;exitDy=0;entryDx=0;entryDy=0;'
TXT = 'text;html=1;align=center;verticalAlign=middle;'

BW, BH, BY, GAP = 210, 130, 120, 50
X0 = 230  # x của hộp 1; đầu vào nằm trước, rộng 180


def bx(i):
    return X0 + i * (BW + GAP)


# Đầu vào / đầu ra
v('IN', 'Query<br><span style="font-size:18px">image, text<br>or attributes</span>', DATA, 0, BY + 10, 180, 110)
v('OUT', 'Top-k results<br><span style="font-size:18px">+ Matching<br>Score</span>', DATA, bx(5), BY + 10, 190, 110)

steps = [
    ('1 Validate', 'top-k, English text, image type', PROC),
    ('2 Encode', 'RaSa → 256-d vector', PROC),
    ('3 Resolve scope', "cameras of the Operator's area", HOT),
    ('4 Vector search', 'Milvus, inner product', HOT),
    ('5 Re-check', 'READY and still in scope', PROC),
]
for i, (title, desc, style) in enumerate(steps):
    v(f'S{i}', f'<b style="font-size:22px">{title}</b><br><span style="color:#444444">{desc}</span>', style,
      bx(i), BY, BW, BH)

# Thành phần thực hiện mỗi bước, đặt phía trên hộp
cx = [bx(i) + BW / 2 for i in range(5)]
# Cùng đỉnh y 14 và cùng cao 56 để năm nhãn thẳng hàng.
v('C0', 'Flask API', ICON + SERVER + ';', cx[0] - 28, 14, 56, 56)
v('C1', 'RaSa', ICON + BRAIN + ';', cx[1] - 28, 14, 56, 56)
v('C2', 'PostgreSQL', DB, cx[2] - 32, 14, 64, 56)
v('C3', 'Milvus', DB + 'strokeWidth=3;', cx[3] - 32, 14, 64, 56)
v('C4', 'PostgreSQL', DB, cx[4] - 32, 14, 64, 56)

# Mũi tên giữa các bước
chain = ['IN', 'S0', 'S1', 'S2', 'S3', 'S4', 'OUT']
for k in range(len(chain) - 1):
    e(f'e{k}', chain[k], chain[k + 1])

# Ngoặc cam dưới bước 3 và 4: phép lọc nằm ngay trong truy vấn vector
v('BR', '', 'shape=partialRectangle;whiteSpace=wrap;html=1;top=0;fillColor=none;strokeColor=#D9822B;strokeWidth=3;',
  bx(2), BY + BH + 14, bx(3) + BW - bx(2), 22)
v('BRT', '<b>filtered inside the search, before top-k</b>', TXT + 'fontColor=#C0661A;',
  bx(2), BY + BH + 40, bx(3) + BW - bx(2), 34)

xml = ('<mxfile host="app.diagrams.net"><diagram name="S11 - Search flow (slide)" id="s11"><mxGraphModel dx="1800" dy="500" '
       'grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
       'pageWidth="1760" pageHeight="340" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
