"""Shared data contracts — OWNER: P1. FROZEN at T+15, nobody edits after.

Created by P3 only because the file did not exist yet and dedup.py must import
DedupResult. P1: take this over, verify against the plan, then freeze.
"""

from pydantic import BaseModel
from typing import Optional, Literal


# ── P2 output ────────────────────────────────────────────────
class Enrichment(BaseModel):
    lang: str                    # "hi" | "mr" | "en" | "hi-Latn"
    text_en: str                 # English pivot — everything downstream uses this
    category_l1: str             # dept key: "pwd"|"water"|"power"|"swm"|"health"|"traffic"
    category_l2: str             # "pothole"|"streetlight_out"|"garbage_uncollected"|...
    confidence: float            # 0-1;  < 0.55 => needs_triage
    severity: float              # 0-1;  injury/live-wire/collapse => ~1.0
    landmarks: list[str]         # ["MG Road", "Modern School"]
    summary: str                 # one line for the officer queue


# ── P3 output ────────────────────────────────────────────────
class DedupResult(BaseModel):
    decision: Literal["NEW", "LINK", "REVIEW"]
    issue_id: Optional[int]
    score: float
    reasons: list[str]           # ["semantic 0.91", "82m apart", "same day"]


# ── P4 output ────────────────────────────────────────────────
class PriorityResult(BaseModel):
    score: int                   # 0-100
    label: Literal["P0", "P1", "P2", "P3"]
    factors: dict[str, float]    # {"severity": 25.5, "poi_proximity": 20.0, ...}
    why: str                     # "injury reported · school 80m · 3 citizens"
    department: str
    ward: str
    sla_hours: int


# ── API in ───────────────────────────────────────────────────
class ComplaintIn(BaseModel):
    text: str
    lat: float
    lng: float
    channel: str = "web"
    citizen_phone: str = "9999900000"
