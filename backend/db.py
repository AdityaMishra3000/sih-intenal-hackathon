"""SQLite persistence helpers for the local CivicResolve demo.

The application deliberately uses a file-backed SQLite database so it works
without a separate database server.  ``GRIEVANCE_DB`` can override the path
when deployment needs a different location.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _PROJECT_ROOT / "grievance.db"
DB_PATH = Path(os.getenv("GRIEVANCE_DB", str(_DEFAULT_DB))).expanduser()


def connect() -> sqlite3.Connection:
    """Open a connection with dictionary-like rows and FK support."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create the complete local schema when the database is new or empty."""
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                category_l1 TEXT NOT NULL,
                category_l2 TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                summary TEXT NOT NULL,
                report_count INTEGER NOT NULL DEFAULT 1,
                severity REAL NOT NULL DEFAULT 0,
                priority_score INTEGER NOT NULL DEFAULT 0,
                priority_label TEXT NOT NULL DEFAULT 'P3',
                priority_why TEXT NOT NULL DEFAULT '',
                factors TEXT NOT NULL DEFAULT '{}',
                department TEXT NOT NULL DEFAULT 'Unassigned',
                ward TEXT NOT NULL DEFAULT 'Unassigned',
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL,
                sla_due TEXT,
                needs_review INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                lang TEXT,
                text_en TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                created_at TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'web',
                citizen_phone TEXT,
                issue_id INTEGER REFERENCES issues(id),
                dedup_score REAL,
                dedup_reasons TEXT NOT NULL DEFAULT '[]',
                state TEXT NOT NULL DEFAULT 'OPEN'
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                issue_id INTEGER NOT NULL REFERENCES issues(id),
                kind TEXT NOT NULL,
                note TEXT,
                at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY,
                complaint_id INTEGER REFERENCES complaints(id),
                field TEXT NOT NULL,
                predicted TEXT,
                corrected TEXT,
                at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_complaints_issue_id ON complaints(issue_id);
            CREATE INDEX IF NOT EXISTS idx_issues_queue ON issues(status, priority_score DESC);
            """
        )


def now_iso(backdate_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=backdate_minutes)).isoformat()


def _decode(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Return a JSON-ready record, decoding columns stored as JSON text."""
    if row is None:
        return None
    result = dict(row)
    if "factors" in result:
        result["factors"] = _decode(result["factors"], {})
    if "dedup_reasons" in result:
        result["dedup_reasons"] = _decode(result["dedup_reasons"], [])
    return result


def complaint_rows() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    return [row_dict(row) for row in rows if row is not None]


def issue_rows() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM issues ORDER BY priority_score DESC, created_at DESC, id DESC"
        ).fetchall()
    return [row_dict(row) for row in rows if row is not None]


def get_issue(issue_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    return row_dict(row)
