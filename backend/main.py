import json, math, re
from datetime import datetime, timezone
from typing import Annotated
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from .contracts import *
from . import db

app=FastAPI(title="CivicLens — Citizen Grievance API", version="1.0.0")
db.init_db()

KEYWORDS={'pothole':('pwd','pothole'),'gaddha':('pwd','pothole'),'streetlight':('power','streetlight_out'),'garbage':('swm','garbage_uncollected'),'water leak':('water','water_leak'),'sewage':('water','sewage_overflow'),'power cut':('power','power_outage')}
def enrich_stub(text):
    t=text.lower(); l1,l2=next((v for k,v in KEYWORDS.items() if k in t),('revenue','other'))
    return Enrichment(text_en=text,category_l1=l1,category_l2=l2,severity=0.7 if any(w in t for w in ('injury','danger','bada')) else .4,summary=text[:80])
def distance(a,b): return 6371000*2*math.asin(math.sqrt(math.sin(math.radians(a[0]-b[0])/2)**2+math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(math.radians(a[1]-b[1])/2)**2))
def process(cid,x,e):
    with db.connect() as c: issues=[dict(r) for r in c.execute("SELECT * FROM issues WHERE status!='RESOLVED'")]
    hit=next((i for i in issues if i['category_l2']==e.category_l2 and distance((x.lat,x.lng),(i['lat'],i['lng']))<200),None)
    d=DedupResult(decision='LINK' if hit else 'NEW',issue_id=hit['id'] if hit else None,score=.9 if hit else 0,reasons=['same category', 'within 200m'] if hit else ['no matching open issue'])
    p=PriorityResult(score=55 if e.severity>=.7 else 30,label='P1' if e.severity>=.7 else 'P2',factors={'severity':30*e.severity,'category_base':20},why='high severity' if e.severity>=.7 else 'standard priority')
    iid=hit['id'] if hit else db.create_issue(e,x,p); db.link_complaint(cid,iid,d); db.add_event(iid,'LINK' if hit else 'CREATED','Complaint processed')
    return iid,d,p

@app.post('/complaints',status_code=202)
def submit(x:ComplaintIn, tasks:BackgroundTasks):
    e=enrich_stub(x.text); cid=db.insert_complaint(x,e); tasks.add_task(process,cid,x,e)
    return {'ticket_id':cid,'message':'Complaint received and processing started'}
@app.get('/complaints/{ticket_id}')
def complaint(ticket_id:int):
    with db.connect() as c:r=c.execute('SELECT * FROM complaints WHERE id=?',(ticket_id,)).fetchone()
    if not r:raise HTTPException(404,'Ticket not found')
    return db.row(r)
@app.get('/issues')
def issues(priority:str|None=None,dept:str|None=None,status:str|None=None):
    q='SELECT * FROM issues WHERE 1=1'; a=[]
    if priority:q+=' AND priority_label=?';a.append(priority)
    if dept:q+=' AND department=?';a.append(dept)
    if status:q+=' AND status=?';a.append(status)
    with db.connect() as c:return [db.row(r) for r in c.execute(q+' ORDER BY priority_score DESC,created_at DESC',a)]
@app.get('/issues/{issue_id}')
def issue(issue_id:int):
    with db.connect() as c:
        r=c.execute('SELECT * FROM issues WHERE id=?',(issue_id,)).fetchone(); cs=c.execute('SELECT * FROM complaints WHERE issue_id=?',(issue_id,)).fetchall(); ev=c.execute('SELECT * FROM events WHERE issue_id=? ORDER BY at',(issue_id,)).fetchall()
    if not r:raise HTTPException(404,'Issue not found')
    d=db.row(r); d['complaints']=[db.row(x) for x in cs]; d['timeline']=[dict(x) for x in ev]; return d
@app.post('/issues/{issue_id}/status')
def status(issue_id:int,x:StatusIn):
    with db.connect() as c:c.execute('UPDATE issues SET status=? WHERE id=?',(x.status,issue_id))
    db.add_event(issue_id,'STATUS',x.status); return {'issue_id':issue_id,'status':x.status}
@app.post('/issues/{issue_id}/reassign')
def reassign(issue_id:int,x:ReassignIn):
    with db.connect() as c:
        old=c.execute('SELECT department FROM issues WHERE id=?',(issue_id,)).fetchone()
        if not old: raise HTTPException(404,'Issue not found')
        c.execute('UPDATE issues SET department=? WHERE id=?',(x.department,issue_id))
        c.execute('INSERT INTO labels(field,predicted,corrected,at) VALUES(?,?,?,?)',('department',old['department'],x.department,db.now()))
    db.add_event(issue_id,'REASSIGNED',x.department); return {'issue_id':issue_id,'department':x.department}
@app.post('/issues/{issue_id}/override_priority')
def override_priority(issue_id:int,x:PriorityOverrideIn):
    with db.connect() as c:
        r=c.execute('SELECT priority_label FROM issues WHERE id=?',(issue_id,)).fetchone()
        if not r: raise HTTPException(404,'Issue not found')
        c.execute('UPDATE issues SET priority_score=?,priority_label=? WHERE id=?',(x.score,x.label,issue_id))
        c.execute('INSERT INTO labels(field,predicted,corrected,at) VALUES(?,?,?,?)',('priority',r['priority_label'],x.label,db.now()))
    db.add_event(issue_id,'PRIORITY_OVERRIDE',f'{x.label} ({x.score})'); return {'issue_id':issue_id,'score':x.score,'label':x.label}
@app.post('/complaints/{complaint_id}/unmerge')
def unmerge(complaint_id:int):
    with db.connect() as c:
        r=c.execute('SELECT * FROM complaints WHERE id=?',(complaint_id,)).fetchone()
        if not r: raise HTTPException(404,'Complaint not found')
        c.execute('UPDATE complaints SET issue_id=NULL,state=\'UNMERGED\' WHERE id=?',(complaint_id,))
    return {'complaint_id':complaint_id,'status':'UNMERGED','message':'Complaint detached; submit for reprocessing'}
@app.get('/analytics/stats')
def stats():
    with db.connect() as c:
        complaints=c.execute('SELECT count(*) n FROM complaints').fetchone()['n']; issues=c.execute('SELECT count(*) n FROM issues').fetchone()['n']
    return {'total_complaints':complaints,'unique_issues':issues,'duplicates_collapsed':round((complaints-issues)/complaints*100,1) if complaints else 0}

@app.get('/analytics/hotspots')
def hotspots(category:str|None=None,priority:str|None=None,min_reports:Annotated[int,Query(ge=1)]=1,limit:Annotated[int,Query(ge=1,le=50)]=10):
    q='SELECT * FROM issues WHERE status!=? AND lat IS NOT NULL AND lng IS NOT NULL AND report_count>=?'
    a=['RESOLVED',min_reports]
    if category:
        q+=' AND category_l2=?'
        a.append(category)
    if priority:
        q+=' AND priority_label=?'
        a.append(priority)
    with db.connect() as c:
        rows=[db.row(r) for r in c.execute(q,a)]

    buckets={}
    for r in rows:
        key=(round(r['lat'],3),round(r['lng'],3),r['category_l2'])
        h=buckets.setdefault(key,{
            'lat':key[0],
            'lng':key[1],
            'category_l2':r['category_l2'],
            'department':r['department'],
            'open_issues':0,
            'report_count':0,
            'max_priority_score':0,
            'top_priority':'P3',
            'issue_ids':[]
        })
        h['open_issues']+=1
        h['report_count']+=r['report_count'] or 0
        h['issue_ids'].append(r['id'])
        if (r['priority_score'] or 0)>h['max_priority_score']:
            h['max_priority_score']=r['priority_score'] or 0
            h['top_priority']=r['priority_label']

    ranked=sorted(
        buckets.values(),
        key=lambda h:(h['report_count'],h['max_priority_score'],h['open_issues']),
        reverse=True
    )
    return {'hotspots':ranked[:limit]}
