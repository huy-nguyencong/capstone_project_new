from xml.sax.saxutils import quoteattr
FS=24
F=f"fontFamily=Times New Roman;fontSize={FS};"
cells=[]
def v(id,val,style,x,y,w,h):
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style+F)} vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
def e(id,s,t,style,val="",pts=None):
    g='<mxGeometry relative="1" as="geometry">'
    if pts: g+='<Array as="points">'+''.join(f'<mxPoint x="{a}" y="{b}"/>' for a,b in pts)+'</Array>'
    g+='</mxGeometry>'
    cells.append(f'<mxCell id="{id}" value={quoteattr(val)} style={quoteattr(style+F)} edge="1" parent="1" source="{s}" target="{t}">{g}</mxCell>')
ACT="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
UC="ellipse;whiteSpace=wrap;html=1;"
W,H=290,110
v("sys","Hệ thống PRISM","rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;align=center;fontStyle=1;fillColor=none;spacingTop=6;",150,90,740,1180)
v("t0","<i>Người dùng</i>",ACT+"verticalLabelPosition=top;verticalAlign=bottom;",500,-100,40,80)
v("t1","Quản trị viên<br>(Admin)",ACT+"labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=10;",60,720,40,80)
v("t2","Giám sát viên<br>(Operator)",ACT,970,560,40,80)
v("t3","Quản lý<br>(Viewer)",ACT,970,1100,40,80)
v("uc01","UC-01<br>Đăng nhập hệ thống",UC,235,130,260,96)
v("uc15","UC-15<br>Đăng xuất hệ thống",UC,545,130,260,96)
admin=[("uc02","UC-02<br>Quản lý tài khoản<br>người dùng"),("uc03","UC-03<br>Quản lý camera"),("uc04","UC-04<br>Quản lý xử lý AI<br>trên camera"),("uc05","UC-05<br>Cấu hình mô hình AI"),("uc06","UC-06<br>Theo dõi trạng thái<br>hệ thống"),("uc07","UC-07<br>Kiểm tra hoạt động<br>của AI"),("uc08","UC-08<br>Xem nhật ký hệ thống")]
for i,(id,val) in enumerate(admin): v(id,val,UC,175,280+i*140,W,H)
op=[("uc09","UC-09<br>Tìm kiếm người<br>bằng AI",280),("uc10","UC-10<br>Xem và đánh giá<br>kết quả tìm kiếm",450),("uc11","UC-11<br>Quản lý hồ sơ<br>vụ việc",620)]
vi=[("uc12","UC-12<br>Xem thông tin<br>tổng quan",800),("uc13","UC-13<br>Xem hồ sơ vụ việc",970),("uc14","UC-14<br>Xem thông tin kết quả<br>tìm kiếm đã lưu",1140)]
for id,val,y in op+vi: v(id,val,UC,575,y,W,H)
ASSOC="endArrow=none;html=1;rounded=0;"
GEN="endArrow=block;endFill=0;endSize=16;html=1;rounded=0;edgeStyle=orthogonalEdgeStyle;"
EXT="endArrow=open;endSize=12;dashed=1;html=1;rounded=0;labelBackgroundColor=#ffffff;"
n=0
def nid():
    global n; n+=1; return f"e{n}"
e(nid(),"t0","uc01",ASSOC+"exitX=0;exitY=0.35;exitDx=0;exitDy=0;")
e(nid(),"t0","uc15",ASSOC+"exitX=1;exitY=0.35;exitDx=0;exitDy=0;")
for id,_ in admin: e(nid(),"t1",id,ASSOC+"exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;")
for id,_,_ in op: e(nid(),"t2",id,ASSOC+"exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;")
for id,_,_ in vi: e(nid(),"t3",id,ASSOC+"exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;")
e(nid(),"t1","t0",GEN+"exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;","",[(80,-60)])
e(nid(),"t2","t0",GEN+"exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;","",[(990,-60)])
e(nid(),"t3","t0",GEN+"exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;","",[(1070,1140),(1070,-60)])
for s,t in [("uc10","uc09"),("uc11","uc10"),("uc13","uc12"),("uc14","uc13")]:
    e(nid(),s,t,EXT+"exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;","«extend»")
xml=('<mxfile host="app.diagrams.net"><diagram name="H1 - Use case" id="h1"><mxGraphModel dx="1400" dy="1100" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1654" pageHeight="1169" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
     +''.join(cells)+'</root></mxGraphModel></diagram></mxfile>')
open(r'D:/uni-studies/semester-253/capstone_project_new/report/thesis/figures/H1-use-case.drawio','w',encoding='utf-8').write(xml)
import xml.dom.minidom as M; M.parseString(xml.encode()); print('ok',len(cells))
