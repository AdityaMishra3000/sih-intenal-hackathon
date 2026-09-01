"""FastAPI application: live SQLite-backed complaint command center."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .contracts import ComplaintIn
from .db import complaint_rows, connect, get_issue, init_db, issue_rows, now_iso, row_dict
from .dedup import find_issue
from .hotspot import analytics_stats, compute_hotspots
from .nlp import enrich
from .priority import score_issue

app = FastAPI(title="Grievance Intelligence API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    """Create SQLite tables on first local run."""
    init_db()
    _seed_demo_data_if_empty()


def _deadline(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _seed_demo_data_if_empty() -> None:
    """Populate the local demo only once, so a fresh clone has useful data."""
    if complaint_rows():
        return
    from .seed import SEED_COMPLAINTS

    for item in SEED_COMPLAINTS:
        create_complaint(
            ComplaintIn(text=item["text"], lat=item["lat"], lng=item["lng"], channel="seed"),
            backdate=int(item.get("minutes_ago", 0)),
        )


def _save_complaint(con: Any, data: ComplaintIn, enrichment: Any, issue_id: int, dedup: Any, created: str) -> int:
    cursor = con.execute("INSERT INTO complaints(text,lang,text_en,lat,lng,created_at,channel,citizen_phone,issue_id,dedup_score,dedup_reasons,state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (data.text,enrichment.lang,enrichment.text_en,data.lat,data.lng,created,data.channel,data.citizen_phone,issue_id,dedup.score,json.dumps(dedup.reasons),"LINKED" if dedup.decision=="LINK" else "OPEN"))
    return int(cursor.lastrowid)


def _issue_detail(issue_id: int) -> dict[str, Any]:
    issue = get_issue(issue_id)
    if not issue: raise HTTPException(404, "Issue not found")
    with connect() as con:
        reports = [dict(row) for row in con.execute("SELECT id,text,lang,dedup_reasons,created_at FROM complaints WHERE issue_id=? ORDER BY id",(issue_id,))]
    reasons: list[str] = []
    for report in reports:
        try: reasons.extend(json.loads(report.pop("dedup_reasons") or "[]"))
        except json.JSONDecodeError: pass
    issue["complaints"] = reports
    issue["dedup_reasons"] = list(dict.fromkeys(reasons))
    return issue


@app.get("/health")
def health() -> dict[str, str]:
    """Simple readiness endpoint."""
    return {"status":"ok"}


@app.post("/complaints")
def create_complaint(data: ComplaintIn, backdate: int = Query(0, ge=0, le=525600)) -> dict[str, Any]:
    """Create a ticket, link a real duplicate if appropriate, and re-score its issue."""
    enrichment = enrich(data.text)
    existing = issue_rows()
    created = now_iso(backdate)
    dedup = find_issue(enrichment, data.lat, data.lng, created, existing)
    with connect() as con:
        if dedup.decision == "LINK" and dedup.issue_id:
            issue = get_issue(dedup.issue_id)
            assert issue is not None
            issue["report_count"] = int(issue.get("report_count") or 0) + 1
            issue["severity"] = max(float(issue.get("severity") or 0), enrichment.severity)
            # Use the stored maximum severity when re-scoring a cluster; a later,
            # lower-severity duplicate must never downgrade an urgent issue.
            result = score_issue(issue)
            con.execute("UPDATE issues SET report_count=?,severity=?,priority_score=?,priority_label=?,priority_why=?,factors=?,department=?,ward=?,sla_due=? WHERE id=?",
                (issue["report_count"],issue["severity"],result.score,result.label,result.why,json.dumps(result.factors),result.department,result.ward,_deadline(result.sla_hours),dedup.issue_id))
            complaint_id = _save_complaint(con,data,enrichment,dedup.issue_id,dedup,created)
            issue_id = dedup.issue_id
        else:
            draft={"category_l1":enrichment.category_l1,"category_l2":enrichment.category_l2,"severity":enrichment.severity,"report_count":1,"lat":data.lat,"lng":data.lng,"summary":enrichment.summary,"created_at":created}
            result=score_issue(draft,enrichment)
            cursor=con.execute("INSERT INTO issues(category_l1,category_l2,lat,lng,summary,report_count,severity,priority_score,priority_label,priority_why,factors,department,ward,status,created_at,sla_due,needs_review) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (enrichment.category_l1,enrichment.category_l2,data.lat,data.lng,enrichment.summary,1,enrichment.severity,result.score,result.label,result.why,json.dumps(result.factors),result.department,result.ward,"OPEN",created,_deadline(result.sla_hours),0))
            issue_id=int(cursor.lastrowid)
            complaint_id=_save_complaint(con,data,enrichment,issue_id,dedup,created)
        con.execute("INSERT INTO events(issue_id,kind,note,at) VALUES(?,?,?,?)",(issue_id,"COMPLAINT_RECEIVED",f"Complaint #{complaint_id} {dedup.decision.lower()}",created))
    return {"ticket_id":complaint_id,"issue_id":issue_id,"dedup":dedup.model_dump(),"decision":dedup.decision,"priority":result.model_dump()}


@app.get("/complaints/{ticket_id}")
def complaint(ticket_id: int) -> dict[str, Any]:
    """Fetch one citizen ticket."""
    with connect() as con: row=con.execute("SELECT * FROM complaints WHERE id=?",(ticket_id,)).fetchone()
    result=row_dict(row)
    if not result: raise HTTPException(404,"Complaint not found")
    return result


@app.get("/issues")
def issues(
    priority: str | None = None,
    dept: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List live issue clusters, ordered for the officer queue."""
    records = issue_rows()
    if priority:
        records = [record for record in records if record["priority_label"] == priority.upper()]
    if dept:
        records = [record for record in records if record["department"] == dept]
    if status:
        records = [record for record in records if record["status"] == status.upper()]
    return records


@app.get("/issues/{issue_id}")
def issue(issue_id: int) -> dict[str, Any]:
    """Fetch an issue with citizen reports and duplicate evidence."""
    return _issue_detail(issue_id)


class StatusIn(BaseModel): status: str

@app.post("/issues/{issue_id}/status")
def change_status(issue_id: int, data: StatusIn) -> dict[str, Any]:
    """Record a safe officer workflow status change."""
    status=data.status.upper()
    if status not in {"OPEN","ACK","IN_PROGRESS","RESOLVED"}: raise HTTPException(422,"Unsupported status")
    with connect() as con:
        if not con.execute("SELECT 1 FROM issues WHERE id=?",(issue_id,)).fetchone(): raise HTTPException(404,"Issue not found")
        con.execute("UPDATE issues SET status=? WHERE id=?",(status,issue_id))
        con.execute("INSERT INTO events(issue_id,kind,note,at) VALUES(?,?,?,?)",(issue_id,"STATUS",status,now_iso()))
    return _issue_detail(issue_id)


class ReassignIn(BaseModel):
    department: str


@app.post("/issues/{issue_id}/reassign")
def reassign_issue(issue_id: int, data: ReassignIn) -> dict[str, Any]:
    """Move an issue to another department and keep an audit event."""
    department = data.department.strip()
    if not department:
        raise HTTPException(422, "Department is required")
    with connect() as con:
        if not con.execute("SELECT 1 FROM issues WHERE id=?", (issue_id,)).fetchone():
            raise HTTPException(404, "Issue not found")
        con.execute("UPDATE issues SET department=? WHERE id=?", (department, issue_id))
        con.execute(
            "INSERT INTO events(issue_id,kind,note,at) VALUES(?,?,?,?)",
            (issue_id, "REASSIGNED", department, now_iso()),
        )
    return _issue_detail(issue_id)


@app.post("/complaints/{ticket_id}/unmerge")
def unmerge_complaint(ticket_id: int) -> dict[str, Any]:
    """Detach a report from its cluster for manual officer review."""
    with connect() as con:
        complaint = con.execute("SELECT issue_id FROM complaints WHERE id=?", (ticket_id,)).fetchone()
        if not complaint:
            raise HTTPException(404, "Complaint not found")
        issue_id = complaint["issue_id"]
        con.execute("UPDATE complaints SET issue_id=NULL,state='UNMERGED' WHERE id=?", (ticket_id,))
        if issue_id:
            con.execute(
                "UPDATE issues SET report_count=MAX(0, report_count - 1) WHERE id=?", (issue_id,)
            )
            con.execute(
                "INSERT INTO events(issue_id,kind,note,at) VALUES(?,?,?,?)",
                (issue_id, "UNMERGED", f"Complaint #{ticket_id}", now_iso()),
            )
    return {"ticket_id": ticket_id, "state": "UNMERGED"}


@app.get("/analytics/stats")
def stats() -> dict[str, Any]:
    """Return calculated, never hard-coded, command-center metrics."""
    return analytics_stats(complaint_rows(), issue_rows())


@app.get("/analytics/hotspots")
def hotspots() -> list[dict[str, Any]]:
    """Return statistically explainable current issue hotspots."""
    return compute_hotspots(issue_rows())


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="dashboard")
