import json, os, sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("GRIEVANCE_DB", "grievances.db")

def connect():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def init_db():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS complaints (id INTEGER PRIMARY KEY, text TEXT NOT NULL, lang TEXT, text_en TEXT, lat REAL, lng REAL, created_at TEXT, channel TEXT, citizen_phone TEXT, issue_id INTEGER, dedup_score REAL, dedup_reasons TEXT, state TEXT DEFAULT 'RECEIVED');
        CREATE TABLE IF NOT EXISTS issues (id INTEGER PRIMARY KEY, category_l1 TEXT, category_l2 TEXT, lat REAL, lng REAL, summary TEXT, report_count INTEGER DEFAULT 1, severity REAL, priority_score INTEGER, priority_label TEXT, priority_why TEXT, factors TEXT, department TEXT, ward TEXT, status TEXT DEFAULT 'OPEN', created_at TEXT, sla_due TEXT, needs_review INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, issue_id INTEGER, kind TEXT, note TEXT, at TEXT);
        CREATE TABLE IF NOT EXISTS labels (id INTEGER PRIMARY KEY, complaint_id INTEGER, field TEXT, predicted TEXT, corrected TEXT, at TEXT);
        ''')

def now(): return datetime.now(timezone.utc).isoformat()
def insert_complaint(x, e):
    with connect() as c:
        cur=c.execute("INSERT INTO complaints(text,lang,text_en,lat,lng,created_at,channel,citizen_phone) VALUES(?,?,?,?,?,?,?,?)", (x.text,e.lang,e.text_en,x.lat,x.lng,now(),x.channel,x.citizen_phone)); return cur.lastrowid
def create_issue(e, x, p):
    with connect() as c:
        cur=c.execute("INSERT INTO issues(category_l1,category_l2,lat,lng,summary,severity,priority_score,priority_label,priority_why,factors,department,ward,created_at,sla_due) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now', '+' || ? || ' hours'))", (e.category_l1,e.category_l2,x.lat,x.lng,e.summary,e.severity,p.score,p.label,p.why,json.dumps(p.factors),p.department,p.ward,now(),p.sla_hours)); return cur.lastrowid
def link_complaint(cid, iid, d):
    with connect() as c:
        c.execute("UPDATE complaints SET issue_id=?,dedup_score=?,dedup_reasons=?,state='PROCESSED' WHERE id=?",(d.issue_id or iid,d.score,json.dumps(d.reasons),cid)); c.execute("UPDATE issues SET report_count=report_count+? WHERE id=?",(1 if d.decision=='LINK' else 0,iid))
def add_event(iid, kind, note):
    with connect() as c: c.execute("INSERT INTO events(issue_id,kind,note,at) VALUES(?,?,?,?)",(iid,kind,note,now()))
def row(r):
    if not r:return None
    d=dict(r)
    for k in ('factors','dedup_reasons'): d[k]=json.loads(d[k] or '[]' if k=='dedup_reasons' else d[k] or '{}')
    return d
