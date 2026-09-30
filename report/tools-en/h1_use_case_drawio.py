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
v("sys","Person search system","rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;align=center;fontStyle=1;fillColor=none;spacingTop=6;",150,90,740,1180)
v("t0","<i>User</i>",ACT+"verticalLabelPosition=top;verticalAlign=bottom;",500,-100,40,80)
v("t1","Administrator<br>(Admin)",ACT+"labelPosition=left;verticalLabelPosition=middle;align=right;verticalAlign=middle;spacingRight=10;",60,720,40,80)
v("t2","Operator",ACT,970,560,40,80)
v("t3","Viewer",ACT,970,1100,40,80)
v("uc01","UC-01<br>Log in",UC,235,130,260,96)
v("uc15","UC-15<br>Log out",UC,545,130,260,96)
admin=[("uc02","UC-02<br>Manage user<br>accounts"),("uc03","UC-03<br>Manage cameras"),("uc04","UC-04<br>Manage AI processing<br>of cameras"),("uc05","UC-05<br>Configure AI models"),("uc06","UC-06<br>Monitor system<br>status"),("uc07","UC-07<br>Check AI<br>operation"),("uc08","UC-08<br>View the audit log")]
for i,(id,val) in enumerate(admin): v(id,val,UC,175,280+i*140,W,H)
op=[("uc09","UC-09<br>Search for people<br>with AI",280),("uc10","UC-10<br>View and assess<br>search results",450),("uc11","UC-11<br>Manage case<br>files",620)]
vi=[("uc12","UC-12<br>View the<br>overview",800),("uc13","UC-13<br>View case files",970),("uc14","UC-14<br>View saved<br>search results",1140)]
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
open(r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en/figures/H1-use-case.drawio','w',encoding='utf-8').write(xml)
import xml.dom.minidom as M; M.parseString(xml.encode()); print('ok',len(cells))
