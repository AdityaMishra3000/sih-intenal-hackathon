from typing import Literal, Optional

from pydantic import BaseModel, Field


class Enrichment(BaseModel):
    lang: str = "en"
    text_en: str
    category_l1: str = "revenue"
    category_l2: str = "other"
    confidence: float = Field(0.3, ge=0, le=1)
    severity: float = Field(0.4, ge=0, le=1)
    landmarks: list[str] = []
    summary: str = "Municipal complaint requiring review"


class DedupResult(BaseModel):
    decision: Literal["NEW", "LINK", "REVIEW"]
    issue_id: Optional[int] = None
    score: float = 0
    reasons: list[str] = []


class PriorityResult(BaseModel):
    score: int = 30
    label: Literal["P0", "P1", "P2", "P3"] = "P2"
    factors: dict[str, float] = {}
    why: str = "Standard priority"
    department: str = "Municipal Corporation"
    ward: str = "Ward 12"
    sla_hours: int = 72


class ComplaintIn(BaseModel):
    text: str = Field(..., min_length=3, max_length=5000)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    channel: str = "web"
    citizen_phone: str = "9999900000"


class StatusIn(BaseModel):
    status: Literal["OPEN", "ACK", "IN_PROGRESS", "RESOLVED"]


class ReassignIn(BaseModel):
    department: str


class PriorityOverrideIn(BaseModel):
    score: int = Field(..., ge=0, le=100)
    label: Literal["P0", "P1", "P2", "P3"]
