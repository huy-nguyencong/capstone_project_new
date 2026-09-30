"""Sinh figures/H8-erd.drawio: ERD (ký hiệu chân quạ) của cơ sở dữ liệu quan hệ PostgreSQL.

Nguồn: backend/src/person_search/storage/postgres/models/*.py (khớp 13 migration). 11 bảng có khóa ngoại;
worker_heartbeats không có khóa ngoại nên không vẽ. Bản số lấy từ nullable của khóa ngoại:
NOT NULL -> phía cha "một và chỉ một" (ERmandOne); NULL được -> "không hoặc một" (ERzeroToOne); phía con "không hoặc nhiều".
Mỗi bảng chỉ thể hiện PK, FK và thuộc tính chính (đầy đủ ở từ điển dữ liệu Mục 5.3.1).
Hình đặt trên trang ngang (rộng 24 cm). Chạy: python report/tools/h8_erd_drawio.py
"""
from xml.sax.saxutils import quoteattr

OUT = r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H8-erd.drawio'
FS = 18
F = f'fontFamily=Times New Roman;fontSize={FS};'
cells = []
LINE = 24
HEADER = 34
W = 270

ENTITY = ('swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;startSize=' + str(HEADER)
          + ';horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=0;marginBottom=0;'
          'html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;swimlaneFillColor=#FFFFFF;')
BODY = 'text;html=1;align=left;verticalAlign=top;spacingLeft=8;spacingTop=2;whiteSpace=wrap;'


def entity(id, name, rows, x, y):
    h = HEADER + LINE * len(rows) + 8
    cells.append(f'<mxCell id="{id}" value={quoteattr(name)} style={quoteattr(ENTITY + F)} vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{W}" height="{h}" as="geometry"/></mxCell>')
    body = '<br>'.join(rows)
    cells.append(f'<mxCell id="{id}b" value={quoteattr(body)} style={quoteattr(BODY + F)} vertex="1" parent="{id}">'
                 f'<mxGeometry y="{HEADER}" width="{W}" height="{h - HEADER}" as="geometry"/></mxCell>')


def pk(c):
    return f'<b>PK</b>&nbsp;&nbsp;<u>{c}</u>'


def fk(c):
    return f'<i>FK</i>&nbsp;&nbsp;&nbsp;{c}'


def at(c):
    return f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{c}'


n = 0


def rel(parent, child, parent_end, style_extra='', pts=None):
    """parent_end: 'one' (FK NOT NULL) hoặc 'zeroone' (FK NULL được). Phía con luôn là không hoặc nhiều."""
    global n
    n += 1
    start = 'ERmandOne' if parent_end == 'one' else 'ERzeroToOne'
    style = (f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;startArrow={start};startFill=0;endArrow=ERzeroToMany;'
             'endFill=0;startSize=14;endSize=14;jumpStyle=arc;' + style_extra)
    g = '<mxGeometry relative="1" as="geometry">'
    if pts:
        g += '<Array as="points">' + ''.join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts) + '</Array>'
    g += '</mxGeometry>'
    cells.append(f'<mxCell id="r{n}" value="" style={quoteattr(style + F)} edge="1" parent="1" source="{parent}" '
                 f'target="{child}">{g}</mxCell>')


E = 'exitX={};exitY={};exitDx=0;exitDy=0;entryX={};entryY={};entryDx=0;entryDy=0;'
X0, X1, X2, X3 = 0, 340, 680, 1020
Y0, Y1, Y2 = 0, 250, 525

entity('areas', 'areas', [pk('id'), at('code (UQ)'), at('name')], X0, Y0)
entity('users', 'users', [pk('id'), fk('assigned_area_id'), at('username (UQ)'), at('role, status'), at('version')], X1, Y0)
entity('sessions', 'auth_sessions', [pk('id'), fk('user_id'), at('token_hash (UQ)'), at('expires_at, revoked_at')], X2, Y0)
entity('audit', 'audit_logs', [pk('id'), fk('actor_user_id'), at('event_type, result'), at('target_type, target_id'), at('occurred_at')], X3, Y0)
entity('cameras', 'cameras', [pk('id'), fk('area_id'), at('code (UQ), name'), at('rtsp_url, rtsp_credentials'), at('status, rtsp_status'), at('ai_enabled, version')], X0, Y1)
entity('jobs', 'processing_jobs', [pk('id'), fk('camera_id'), fk('ai_config_version_id'), fk('requested_by'), at('source_type, source_ref'), at('status, sampling_interval'), at('lease_expires_at, attempts')], X1, Y1)
entity('aicfg', 'ai_config_versions', [pk('id'), at('version (UQ)'), at('detector_name, _version'), at('tracker_name, _version'), at('encoder_version, _dimension'), at('status')], X2, Y1)
entity('cases', 'cases', [pk('id'), fk('owner_user_id'), at('title, note'), at('status, closed_at'), at('version')], X3, Y1)
entity('outbox', 'storage_outbox_events', [pk('id'), fk('track_id'), at('event_type'), at('status, attempts'), at('available_at')], X0, Y2)
entity('tracks', 'person_tracks', [pk('id'), fk('camera_id'), fk('processing_job_id'), fk('ai_config_version_id'), at('appeared_at_utc'), at('bbox_x, _y, _width, _height'), at('minio_object_key'), at('encoder_version'), at('index_status')], X1, Y2)
entity('results', 'case_results', [pk('id'), fk('case_id'), fk('track_id'), at('camera_name_snapshot'), at('area_name_snapshot'), at('appeared_at_snapshot'), at('saved_at')], X2 + 60, Y2)

# Quan hệ (cha -> con)
rel('areas', 'users', 'zeroone', E.format(1, .5, 0, 0.352))
rel('areas', 'cameras', 'one', E.format(.5, 1, .5, 0))
rel('users', 'sessions', 'one', E.format(1, 0.383, 0, .45))
rel('users', 'audit', 'zeroone', E.format(.5, 0, .5, 0), [(475, -40), (1155, -40)])
rel('users', 'cases', 'one', E.format(.85, 1, .5, 0), [(570, 205), (1155, 205)])
rel('users', 'jobs', 'zeroone', E.format(.35, 1, .35, 0))
rel('cameras', 'jobs', 'one', E.format(1, .3, 0, 0.266))
rel('cameras', 'tracks', 'one', E.format(.5, 1, .15, 0), [(135, 482), (380, 482)])
rel('aicfg', 'jobs', 'one', E.format(0, .55, 1, 0.487))
rel('aicfg', 'tracks', 'one', E.format(.25, 1, .85, 0), [(747, 482), (570, 482)])
rel('jobs', 'tracks', 'one', E.format(.4, 1, .4, 0))
rel('tracks', 'results', 'one', E.format(1, 0.448, 0, .55))
rel('cases', 'results', 'one', E.format(.5, 1, 1, .4))
rel('tracks', 'outbox', 'one', E.format(0, 0.345, 1, .55))

xml = ('<mxfile host="app.diagrams.net"><diagram name="H8 - ERD" id="h8"><mxGraphModel dx="1400" dy="1100" grid="1" '
       'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1654" '
       'pageHeight="1169" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + ''.join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(OUT, 'w', encoding='utf-8').write(xml)
import xml.dom.minidom as M  # noqa: E402
M.parseString(xml.encode())
print('ok', len(cells))
