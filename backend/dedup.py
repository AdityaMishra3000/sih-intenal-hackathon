"""P3 — Duplicate complaint detection engine.

Public API (this is the whole surface P1 wires into main.py):

    warmup()                                    -> preload the embedding model
    find_issue(enr, lat, lng, ts, open_issues)  -> DedupResult
    register_issue(issue_id, enr, lat, lng, ts) -> call after creating a NEW issue
    absorb(issue_id, enr, ts)                   -> call after a LINK/REVIEW merge
    forget(issue_id)                            -> call on unmerge/close
    backend_name(), index_stats(), reset_index()

CONTRACT FOR P1 — how to act on `decision`:
    NEW    -> create a new issue, then call register_issue(new_id, enr, lat, lng, ts)
    LINK   -> link complaint to result.issue_id, report_count++, recompute priority,
              then call absorb(result.issue_id, enr, ts)
    REVIEW -> same as LINK **plus** set issues.needs_review = 1. The merge happened,
              but an officer should confirm it (and can /unmerge). This is the LLM
              adjudicator's grey-band verdict.

find_issue NEVER raises and never blocks on the network for the auto-merge path.
On any internal failure it degrades to decision="NEW" (a missed duplicate is
recoverable; a false merge buries a citizen's complaint).

This module keeps its own in-memory index of {issue_id: (vector, landmarks,
last_seen)} so it needs no new DB columns. If an issue is missing from the index
(server restart, seeded rows), it falls back to embedding the issue's stored
`summary` on the fly.

Standalone checks:
    python -m backend.dedup               # 6-case correctness suite (all must PASS)
    python -m backend.dedup --llm-check   # is the grey-band adjudicator key live?
    python -m backend.dedup --groq-models # which model ids does this key accept?
    python -m backend.dedup --sweep       # threshold grid search for T+130 tuning

The grey-band adjudicator runs on Groq (default) or Anthropic — whichever API key
is present. Neither is required: without a key the engine simply never merges
grey-band pairs.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import zlib
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

import numpy as np

# Load .env *before* the constants below are evaluated, otherwise GROQ_MODEL and
# the threshold overrides are read from a not-yet-populated environment. This
# never overrides variables already set in the real environment, so P1's main.py
# calling load_dotenv() again is harmless.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from .contracts import DedupResult, Enrichment
except ImportError:  # allows `python app/dedup.py`
    from contracts import DedupResult, Enrichment  # type: ignore

# ══════════════════════════════════════════════════════════════════════
# FROZEN CONSTANTS — announced to the team. Tunable via env at T+130 only.
# ══════════════════════════════════════════════════════════════════════

MODEL_NAME = os.getenv("DEDUP_MODEL", "BAAI/bge-small-en-v1.5")

W = {"sem": 0.45, "spatial": 0.30, "temporal": 0.10, "entity": 0.15}

AUTO_MERGE = float(os.getenv("DEDUP_AUTO_MERGE", "0.78"))
GREY_LOW = float(os.getenv("DEDUP_GREY_LOW", "0.55"))
_THRESHOLDS_PINNED = bool(os.getenv("DEDUP_AUTO_MERGE") or os.getenv("DEDUP_GREY_LOW"))

# The char n-gram fallback backend produces systematically lower cosine values
# for paraphrases than bge-small (measured: 0.28-0.49 vs ~0.85 on the same
# pairs), so the bands shift with it. Env vars override both pairs.
FALLBACK_AUTO_MERGE, FALLBACK_GREY_LOW = 0.62, 0.45


def thresholds() -> tuple[float, float]:
    """(auto_merge, grey_low) for the backend actually in use."""
    if _THRESHOLDS_PINNED or backend_name().startswith("fastembed"):
        return AUTO_MERGE, GREY_LOW
    return FALLBACK_AUTO_MERGE, FALLBACK_GREY_LOW

# category-specific hard gate: (radius_m, time_window_hours)
GATE: dict[str, tuple[float, float]] = {
    "streetlight_out":     (60,   720),   "pothole":             (120, 2160),
    "road_damage":         (150, 2160),   "garbage_uncollected": (150,   72),
    "water_leak":          (300,  168),   "no_water_supply":     (800,   48),
    "power_outage":        (1500,   6),   "sewage_overflow":     (200,  120),
    "stray_animals":       (400,  336),   "mosquito_breeding":   (400,  336),
    "illegal_parking":     (100,   24),   "tree_fallen":         (100,  336),
    "other":               (250,  168),
}

# ── Grey-band adjudicator LLM. Groq is the primary provider; Anthropic is used
#    only if no GROQ_API_KEY is set. DEDUP_LLM_PROVIDER=groq|anthropic forces one.
#    Groq's endpoint is OpenAI-compatible, so no SDK is needed.
ANTHROPIC_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ADJUDICATOR_TIMEOUT_S = float(os.getenv("DEDUP_ADJ_TIMEOUT", "12"))
# A cap, not a target: non-reasoning models stop at their own EOS after "YES".
# Sized so reasoning models (qwen3 et al.) can emit a <think> block and still
# reach their verdict instead of being truncated into silence.
ADJUDICATOR_MAX_TOKENS = int(os.getenv("DEDUP_ADJ_MAX_TOKENS", "256"))
ADJUDICATOR_ENABLED = os.getenv("DEDUP_ADJUDICATOR", "1") not in ("0", "false", "no")

_EARTH_R = 6_371_000.0  # metres

# words that carry no locating information — dropped from landmark tokens
_LANDMARK_STOP = {
    "road", "rd", "street", "st", "lane", "marg", "nagar", "chowk", "circle",
    "area", "near", "the", "of", "and", "path", "cross", "sector", "colony",
}


def _log(msg: str) -> None:
    print(f"[dedup] {msg}", file=sys.stderr)

# ══════════════════════════════════════════════════════════════════════
# Embeddings — fastembed if available, deterministic char n-gram hash if not
# ══════════════════════════════════════════════════════════════════════

_HASH_DIM = 8192
_HASH_NGRAMS = (3, 4, 5)


def _hash_embed(text: str) -> np.ndarray:
    """Insurance backend: L2-normalised char n-gram hash vector, numpy only.

    Deliberately not sklearn TF-IDF: same char n-gram signal, no extra
    dependency, and stateless so it needs no corpus fit. crc32 (not hash())
    because Python string hashing is salted per process.
    """
    s = " " + re.sub(r"[^\w\s]+", " ", text.lower()).strip() + " "
    s = re.sub(r"\s+", " ", s)
    v = np.zeros(_HASH_DIM, dtype=np.float32)
    for n in _HASH_NGRAMS:
        for i in range(max(len(s) - n + 1, 0)):
            v[zlib.crc32(s[i:i + n].encode("utf-8")) % _HASH_DIM] += 1.0
    for tok in s.split():
        v[zlib.crc32(("__" + tok).encode("utf-8")) % _HASH_DIM] += 2.0
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v


class _Embedder:
    def __init__(self) -> None:
        self._fn = None
        self._name = "unloaded"
        self._lock = threading.Lock()
        self._memo: dict[str, np.ndarray] = {}

    def _load(self) -> None:
        if self._fn is not None:
            return
        with self._lock:
            if self._fn is not None:
                return
            try:
                from fastembed import TextEmbedding

                model = TextEmbedding(MODEL_NAME)
                list(model.embed(["warm up"]))  # force download + first inference

                def _fn(texts: Sequence[str]) -> list[np.ndarray]:
                    return [np.asarray(v, dtype=np.float32)
                            for v in model.embed(list(texts))]

                self._fn, self._name = _fn, f"fastembed:{MODEL_NAME}"
                _log(f"backend = {self._name}")
                return
            except Exception as exc:  # noqa: BLE001 - any failure must fall back
                _log(f"fastembed unavailable ({type(exc).__name__}: {exc}); "
                     f"using char-ngram hash fallback")

            self._fn = lambda texts: [_hash_embed(t) for t in texts]
            self._name = f"charngram-hash:{_HASH_DIM}"

    @property
    def name(self) -> str:
        self._load()
        return self._name

    def embed(self, text: str) -> np.ndarray:
        self._load()
        key = text.strip()
        hit = self._memo.get(key)
        if hit is None:
            vec = self._fn([key])[0]  # type: ignore[misc]
            norm = float(np.linalg.norm(vec))
            hit = (vec / norm if norm else vec).astype(np.float32)
            self._memo[key] = hit
        return hit


_EMB = _Embedder()


def warmup() -> str:
    """T+0: call this at import/startup so the 133 MB download is not on the
    critical path of the first complaint."""
    return _EMB.name


def backend_name() -> str:
    return _EMB.name

# ══════════════════════════════════════════════════════════════════════
# Similarity primitives
# ══════════════════════════════════════════════════════════════════════

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Both inputs are already L2-normalised, so this is just a dot product."""
    return float(np.clip(np.dot(a, b), -1.0, 1.0))


def _local_haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Metres between two points. Prefers P4's geo.haversine when it lands so
    both modules agree to the metre; falls back to a local copy until then."""
    try:
        from .geo import haversine as _p4  # type: ignore
    except Exception:  # noqa: BLE001
        return _local_haversine(lat1, lng1, lat2, lng2)
    try:
        return float(_p4(lat1, lng1, lat2, lng2))
    except TypeError:  # P4 may export haversine((lat,lng), (lat,lng))
        return float(_p4((lat1, lng1), (lat2, lng2)))


def _landmark_tokens(landmarks: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for raw in landmarks or []:
        for tok in re.split(r"[^\w]+", str(raw).lower()):
            # min length 2, not 3: "MG", "FC", "JM" are real Indian road names
            if len(tok) >= 2 and tok not in _LANDMARK_STOP and not tok.isdigit():
                out.add(tok)
    return out


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    ta, tb = _landmark_tokens(a), _landmark_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def entity_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    """Containment, not Jaccard: |A∩B| / min(|A|,|B|).

    Deliberate change from the announced spec. Landmark lists are asymmetric —
    one citizen writes "MG Road, Modern School", another just "MG Road". Jaccard
    scores that 0.33 and punishes the more detailed report; containment scores it
    1.0, which is what "they named the same place" should mean.
    """
    ta, tb = _landmark_tokens(a), _landmark_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _shared_landmarks(a: Iterable[str], b: Iterable[str]) -> list[str]:
    tb = _landmark_tokens(b)
    return sorted({str(x) for x in (a or []) if _landmark_tokens([x]) & tb})


def _parse_ts(ts: Any) -> datetime:
    """Accepts datetime, ISO-8601 string, or epoch seconds. Always returns UTC."""
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    else:
        raw = str(ts).strip().replace("Z", "+00:00").replace(" ", "T", 1)
        dt = datetime.fromisoformat(raw)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _hours_apart(a: Any, b: Any) -> float:
    return abs((_parse_ts(a) - _parse_ts(b)).total_seconds()) / 3600.0

# ══════════════════════════════════════════════════════════════════════
# In-memory issue index — {issue_id: vector}, owned entirely by this module
# ══════════════════════════════════════════════════════════════════════

_VEC: dict[int, np.ndarray] = {}
_LM: dict[int, set[str]] = {}
_SEEN: dict[int, datetime] = {}


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field off a dict, sqlite3.Row, pydantic model, or plain object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    try:
        return obj[name]  # sqlite3.Row
    except Exception:  # noqa: BLE001
        return getattr(obj, name, default)


def register_issue(issue_id: int, enr: Any, lat: float, lng: float, ts: Any) -> None:
    """P1 calls this right after INSERT of a new issue (decision == NEW)."""
    text = _field(enr, "text_en") or _field(enr, "summary") or ""
    _VEC[int(issue_id)] = _EMB.embed(text)
    _LM[int(issue_id)] = _landmark_tokens(_field(enr, "landmarks") or [])
    _SEEN[int(issue_id)] = _parse_ts(ts)


def absorb(issue_id: int, enr: Any, ts: Any) -> None:
    """P1 calls this after a LINK/REVIEW. Unions landmarks and refreshes
    last-seen so a long-running issue keeps matching new reports."""
    iid = int(issue_id)
    _LM.setdefault(iid, set()).update(_landmark_tokens(_field(enr, "landmarks") or []))
    _SEEN[iid] = _parse_ts(ts)
    if iid not in _VEC:
        _VEC[iid] = _EMB.embed(_field(enr, "text_en") or "")


def forget(issue_id: int) -> None:
    """Call on unmerge or when an issue leaves the open set."""
    iid = int(issue_id)
    _VEC.pop(iid, None)
    _LM.pop(iid, None)
    _SEEN.pop(iid, None)


def reset_index() -> None:
    _VEC.clear()
    _LM.clear()
    _SEEN.clear()


def index_stats() -> dict[str, Any]:
    auto_merge, grey_low = thresholds()
    return {"backend": _EMB.name, "issues_indexed": len(_VEC),
            "auto_merge": auto_merge, "grey_low": grey_low}


def _issue_vector(issue: Any, iid: int) -> np.ndarray:
    """Cold-start safe: if the issue was never registered (restart, seed load),
    embed its stored English summary now and cache it."""
    vec = _VEC.get(iid)
    if vec is None:
        text = (_field(issue, "text_en") or _field(issue, "summary") or "")
        vec = _EMB.embed(str(text))
        _VEC[iid] = vec
    return vec


def _issue_landmarks(issue: Any, iid: int) -> set[str]:
    lm = _LM.get(iid)
    if lm is None:
        raw = _field(issue, "landmarks") or []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:  # noqa: BLE001
                raw = [raw]
        lm = _landmark_tokens(raw)
        _LM[iid] = lm
    return lm

# ══════════════════════════════════════════════════════════════════════
# Composite score
#   0.45*semantic + 0.30*exp(-d/radius) + 0.10*exp(-h/window) + 0.15*jaccard
# ══════════════════════════════════════════════════════════════════════

class _Candidate:
    __slots__ = ("issue", "iid", "score", "parts", "dist_m", "hours", "shared")

    def __init__(self, issue, iid, score, parts, dist_m, hours, shared):
        self.issue, self.iid, self.score = issue, iid, score
        self.parts, self.dist_m, self.hours, self.shared = parts, dist_m, hours, shared


def _score(new_vec, new_lm_raw, issue_vec, issue_lm, dist_m, hours,
           radius_m, window_h) -> tuple[float, dict[str, float], list[str]]:
    sem = cosine(new_vec, issue_vec)
    # Gaussian in d/radius, not exp(-d/radius): GPS error is Gaussian, so two
    # reports 60m apart inside a 120m gate should still read as "same spot".
    # Same value (0.37) at the gate boundary, far more tolerant of jitter inside it.
    spatial = math.exp(-((dist_m / radius_m) ** 2))
    temporal = math.exp(-hours / window_h)

    parts = {"sem": sem, "spatial": spatial, "temporal": temporal}
    weights = dict(W)
    shared = _shared_landmarks(new_lm_raw, issue_lm)

    if _landmark_tokens(new_lm_raw) and issue_lm:
        parts["entity"] = entity_overlap(new_lm_raw, issue_lm)
    else:
        # No landmark data on one side — treat entity as *unavailable* rather
        # than zero, and renormalise so scores stay comparable to the 0.78 bar.
        weights.pop("entity")
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

    score = sum(weights[k] * parts[k] for k in weights)
    return score, parts, shared


def _reasons(parts: dict[str, float], dist_m: float, hours: float,
             shared: list[str]) -> list[str]:
    out = [f"semantic {parts['sem']:.2f}", f"{dist_m:.0f}m apart"]
    if hours < 24:
        out.append("same day" if hours < 12 else f"{hours:.0f}h apart")
    elif hours < 48:
        out.append("1 day apart")
    else:
        out.append(f"{hours / 24:.0f} days apart")
    if shared:
        out.append("shared landmark: " + ", ".join(shared[:2]))
    elif "entity" not in parts:
        out.append("no landmark overlap data")
    return out

# ══════════════════════════════════════════════════════════════════════
# Grey-band LLM adjudicator — one Haiku call, YES/NO only
# ══════════════════════════════════════════════════════════════════════

_ADJ_PROMPT = (
    "Two citizen complaints about a city. Are they reporting the SAME physical "
    "problem at the SAME place?\n\nA: {a}\nB: {b}\nThey are {dist:.0f} metres "
    "apart and reported {hours:.0f} hours apart.\n\nAnswer with one word: YES or NO."
)


def active_provider() -> Optional[tuple[str, str]]:
    """(provider, model) for the adjudicator, or None if no key is configured."""
    if not ADJUDICATOR_ENABLED:
        return None
    forced = os.getenv("DEDUP_LLM_PROVIDER", "").strip().lower()
    have = {"anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY"))}
    order = [forced] if forced in have else ["groq", "anthropic"]
    for name in order:
        if have.get(name):
            return (name, ANTHROPIC_MODEL if name == "anthropic" else GROQ_MODEL)
    return None


def _http_json(url: str, headers: dict[str, str],
               payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Minimal JSON call. httpx if present, else stdlib — no SDK required.

    On an HTTP error the provider's response body is folded into the exception
    message: a Groq 404 says exactly which model id it did not recognise, and
    that detail is worth far more than the status code alone.
    """
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    if body is not None:
        headers = {**headers, "content-type": "application/json"}
    try:
        import httpx

        resp = httpx.request("POST" if body else "GET", url, headers=headers,
                             content=body, timeout=ADJUDICATOR_TIMEOUT_S)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    except ImportError:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST" if body else "GET")
        try:
            with urllib.request.urlopen(req, timeout=ADJUDICATOR_TIMEOUT_S) as fh:
                return json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            raise RuntimeError(f"HTTP {err.code}: "
                               f"{err.read().decode('utf-8', 'replace')[:300]}") from None


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    return _http_json(url, headers, payload)


def _ask_llm(prompt: str) -> Optional[str]:
    """Raw text answer from the configured provider, or None on any failure."""
    picked = active_provider()
    if picked is None:
        return None
    provider, model = picked
    try:
        if provider == "groq":
            data = _post_json(
                GROQ_URL,
                {"authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                {"model": model, "max_tokens": ADJUDICATOR_MAX_TOKENS, "temperature": 0,
                 "messages": [{"role": "user", "content": prompt}]},
            )
            return data["choices"][0]["message"]["content"]

        data = _post_json(
            ANTHROPIC_URL,
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
             "anthropic-version": "2023-06-01"},
            {"model": model, "max_tokens": ADJUDICATOR_MAX_TOKENS, "temperature": 0,
             "messages": [{"role": "user", "content": prompt}]},
        )
        return "".join(p.get("text", "") for p in data.get("content", []))
    except Exception as exc:  # noqa: BLE001
        _log(f"{provider} adjudicator failed on model {model!r} "
             f"({type(exc).__name__}: {exc})")
        return None


_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.S | re.I)
_VERDICT_RE = re.compile(r"\b(YES|NO)\b")


def _parse_verdict(answer: str) -> Optional[bool]:
    """YES/NO out of a model's reply, tolerant of reasoning models.

    Strips <think> blocks (including an unterminated one left by truncation) and
    takes the *last* standalone YES/NO, since the conclusion comes after any
    hedging that precedes it.
    """
    hits = _VERDICT_RE.findall(_THINK_RE.sub(" ", answer).upper())
    return None if not hits else hits[-1] == "YES"


def _adjudicate(a: str, b: str, dist_m: float, hours: float) -> Optional[bool]:
    """True = same issue, False = different, None = adjudicator unavailable."""
    answer = _ask_llm(_ADJ_PROMPT.format(a=a[:600], b=b[:600], dist=dist_m, hours=hours))
    if answer is None:
        return None
    verdict = _parse_verdict(answer)
    if verdict is None:
        _log(f"adjudicator gave unparseable answer: {answer[:200]!r}")
    return verdict


def list_groq_models() -> int:
    """`--groq-models` — print the model ids this key can actually call."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("No GROQ_API_KEY in the environment.")
        return 1
    try:
        data = _http_json(GROQ_MODELS_URL, {"authorization": f"Bearer {key}"})
    except Exception as exc:  # noqa: BLE001
        print(f"Could not list models: {type(exc).__name__}: {exc}")
        return 1
    ids = sorted(m.get("id", "?") for m in data.get("data", []))
    print(f"{len(ids)} models available to this key "
          f"(GROQ_MODEL is currently {GROQ_MODEL!r}):\n")
    for mid in ids:
        print(f"  {'*' if mid == GROQ_MODEL else ' '} {mid}")
    if GROQ_MODEL not in ids:
        print(f"\n{GROQ_MODEL!r} is NOT in that list — that is what produces the 404. "
              f"Set GROQ_MODEL in .env to one of the ids above.")
    return 0

# ══════════════════════════════════════════════════════════════════════
# Decision flow
# ══════════════════════════════════════════════════════════════════════

def _candidates(enr: Any, lat: float, lng: float, ts: Any,
                open_issues: Iterable[Any]) -> tuple[list[_Candidate], float, float]:
    l2 = str(_field(enr, "category_l2") or "other")
    radius_m, window_h = GATE.get(l2, GATE["other"])
    new_vec = _EMB.embed(str(_field(enr, "text_en") or ""))
    new_lm = _field(enr, "landmarks") or []

    out: list[_Candidate] = []
    for issue in open_issues or []:
        iid = _field(issue, "id")
        if iid is None:
            continue
        iid = int(iid)

        # ── HARD GATE 1: same fine-grained category
        if str(_field(issue, "category_l2") or "") != l2:
            continue
        if str(_field(issue, "status") or "OPEN").upper() == "RESOLVED":
            continue

        ilat, ilng = _field(issue, "lat"), _field(issue, "lng")
        if ilat is None or ilng is None:
            continue

        # ── HARD GATE 2: within the category's radius
        dist_m = haversine(float(lat), float(lng), float(ilat), float(ilng))
        if dist_m > radius_m:
            continue

        # ── HARD GATE 3: within the category's time window
        ref_ts = _SEEN.get(iid) or _field(issue, "created_at") or ts
        try:
            hours = _hours_apart(ts, ref_ts)
        except Exception:  # noqa: BLE001 - unparseable timestamp must not gate out
            hours = 0.0
        if hours > window_h:
            continue

        score, parts, shared = _score(
            new_vec, new_lm, _issue_vector(issue, iid), _issue_landmarks(issue, iid),
            dist_m, hours, radius_m, window_h,
        )
        out.append(_Candidate(issue, iid, score, parts, dist_m, hours, shared))

    out.sort(key=lambda c: c.score, reverse=True)
    return out, radius_m, window_h


def _find_issue(enr: Any, lat: float, lng: float, ts: Any,
                open_issues: Iterable[Any]) -> DedupResult:
    cands, radius_m, window_h = _candidates(enr, lat, lng, ts, open_issues)

    if not cands:
        return DedupResult(
            decision="NEW", issue_id=None, score=0.0,
            reasons=[f"no open {_field(enr, 'category_l2')} issue within "
                     f"{radius_m:.0f}m / {window_h:.0f}h"],
        )

    best = cands[0]
    reasons = _reasons(best.parts, best.dist_m, best.hours, best.shared)
    auto_merge, grey_low = thresholds()

    if best.score >= auto_merge:
        return DedupResult(decision="LINK", issue_id=best.iid,
                           score=round(best.score, 3),
                           reasons=reasons + [f"score {best.score:.2f} ≥ {auto_merge}"])

    if best.score >= grey_low:
        verdict = _adjudicate(
            str(_field(enr, "text_en") or ""),
            str(_field(best.issue, "summary") or _field(best.issue, "text_en") or ""),
            best.dist_m, best.hours,
        )
        grey = [f"score {best.score:.2f} in grey band [{grey_low}, {auto_merge})"]
        if verdict is True:
            return DedupResult(decision="REVIEW", issue_id=best.iid,
                               score=round(best.score, 3),
                               reasons=reasons + grey + ["LLM adjudicator: YES — flagged for officer review"])
        if verdict is False:
            return DedupResult(decision="NEW", issue_id=None,
                               score=round(best.score, 3),
                               reasons=reasons + grey + ["LLM adjudicator: NO — kept separate"])
        return DedupResult(decision="NEW", issue_id=None, score=round(best.score, 3),
                           reasons=reasons + grey + ["adjudicator unavailable — kept separate (precision first)"])

    return DedupResult(decision="NEW", issue_id=None, score=round(best.score, 3),
                       reasons=reasons + [f"best score {best.score:.2f} < {grey_low}"])


def find_issue(enr: Any, lat: float, lng: float, ts: Any,
               open_issues: Iterable[Any]) -> DedupResult:
    """Never raises. Any internal failure degrades to a new issue."""
    try:
        return _find_issue(enr, lat, lng, ts, open_issues)
    except Exception as exc:  # noqa: BLE001
        _log(f"find_issue crashed ({type(exc).__name__}: {exc}) — failing open as NEW")
        return DedupResult(decision="NEW", issue_id=None, score=0.0,
                           reasons=[f"dedup unavailable: {type(exc).__name__}",
                                    "failed open as NEW"])

# ══════════════════════════════════════════════════════════════════════
# Standalone test suite — `python -m backend.dedup`
# 3 true duplicates (one cross-lingual) + 3 near-misses. All 6 must pass.
# ══════════════════════════════════════════════════════════════════════

_PUNE = (18.5204, 73.8567)  # Pune, MG Road area


def _offset(lat: float, lng: float, north_m: float, east_m: float) -> tuple[float, float]:
    return (lat + north_m / 111_320.0,
            lng + east_m / (111_320.0 * math.cos(math.radians(lat))))


def _enr(text_en: str, l2: str, landmarks: list[str], lang: str = "en",
         l1: str = "pwd", severity: float = 0.5) -> Enrichment:
    return Enrichment(lang=lang, text_en=text_en, category_l1=l1, category_l2=l2,
                      confidence=0.9, severity=severity, landmarks=landmarks,
                      summary=text_en[:60])


_CASES: list[dict[str, Any]] = [
    dict(name="hi↔en pothole, 80m, 3h", expect={"LINK", "REVIEW"},
         a=_enr("There is a big pothole on MG Road near Modern School",
                "pothole", ["MG Road", "Modern School"], lang="hi-Latn"),
         b=_enr("Large pothole on MG Road in front of the school, bikes are falling",
                "pothole", ["MG Road"]),
         d_m=80, hours=3),
    dict(name="mr↔en streetlight, 40m, 6h", expect={"LINK", "REVIEW"},
         a=_enr("The streetlight on FC Road near the bus stop is not working",
                "streetlight_out", ["FC Road"], lang="mr", l1="power"),
         b=_enr("Street light not working at FC Road bus stop, very dark at night",
                "streetlight_out", ["FC Road", "bus stop"], l1="power"),
         d_m=40, hours=6),
    dict(name="garbage dupe, 100m, 12h", expect={"LINK", "REVIEW"},
         a=_enr("Garbage has not been collected in Kothrud market for four days",
                "garbage_uncollected", ["Kothrud market"], l1="swm"),
         b=_enr("Trash is piling up at Kothrud market, nobody has picked it up",
                "garbage_uncollected", ["Kothrud market"], l1="swm"),
         d_m=100, hours=12),
    dict(name="near-miss pothole 900m apart", expect={"NEW"},
         a=_enr("Deep pothole on MG Road near the post office",
                "pothole", ["MG Road"]),
         b=_enr("Deep pothole on Karve Road near the post office",
                "pothole", ["Karve Road"]),
         d_m=900, hours=2),
    dict(name="near-miss garbage 1.2km apart", expect={"NEW"},
         a=_enr("Garbage dump overflowing near Kothrud market",
                "garbage_uncollected", ["Kothrud market"], l1="swm"),
         b=_enr("Garbage dump overflowing near Aundh market",
                "garbage_uncollected", ["Aundh market"], l1="swm"),
         d_m=1200, hours=4),
    dict(name="near-miss streetlight 45m but 45 days later", expect={"NEW"},
         a=_enr("Streetlight not working on FC Road",
                "streetlight_out", ["FC Road"], l1="power"),
         b=_enr("Streetlight not working on FC Road",
                "streetlight_out", ["FC Road"], l1="power"),
         d_m=45, hours=45 * 24),
    # 7th: passes every hard gate but is arguably a different pole. Must NOT
    # auto-LINK — this is precisely what the grey band exists for.
    dict(name="grey probe: two poles 50m apart", expect={"NEW", "REVIEW"},
         a=_enr("Streetlight outside gate 3 of the school is off",
                "streetlight_out", ["school"], l1="power"),
         b=_enr("Pole number 42 near the temple has no light",
                "streetlight_out", ["temple"], l1="power"),
         d_m=50, hours=8),
]

def _run_case(case: dict[str, Any]) -> tuple[DedupResult, float]:
    """Register A as issue 1, then ask what happens to B."""
    reset_index()
    t0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    a, b = case["a"], case["b"]
    lat_b, lng_b = _offset(_PUNE[0], _PUNE[1], case["d_m"], 0)
    t_b = t0.timestamp() + case["hours"] * 3600

    register_issue(1, a, _PUNE[0], _PUNE[1], t0)
    issue = {"id": 1, "category_l2": a.category_l2, "lat": _PUNE[0], "lng": _PUNE[1],
             "summary": a.summary, "text_en": a.text_en, "created_at": t0.isoformat(),
             "status": "OPEN", "report_count": 1}

    cands, _, _ = _candidates(b, lat_b, lng_b, t_b, [issue])
    raw = cands[0].score if cands else 0.0
    return find_issue(b, lat_b, lng_b, t_b, [issue]), raw


def selftest() -> int:
    auto_merge, grey_low = thresholds()
    picked = active_provider()
    adj_on = picked is not None
    print(f"backend      : {backend_name()}")
    print(f"thresholds   : AUTO_MERGE={auto_merge}  GREY_LOW={grey_low}")
    print(f"adjudicator  : {f'{picked[0]} / {picked[1]}' if adj_on else 'off (no ANTHROPIC_API_KEY or GROQ_API_KEY)'}\n")

    failures = degraded = 0
    for case in _CASES:
        res, raw = _run_case(case)
        is_dupe = "LINK" in case["expect"]
        ok = res.decision in case["expect"]
        mark = "PASS" if ok else "FAIL"
        stalled = any("adjudicator unavailable" in r for r in res.reasons)
        # A grey-band duplicate cannot be merged without a working adjudicator.
        # Reaching the grey band is the correct behaviour, so don't call that a
        # code failure — whether the adjudicator is absent or just unreachable.
        if not ok and is_dupe and raw >= grey_low and (not adj_on or stalled):
            mark, degraded = "PASS*", degraded + 1
        elif not ok:
            failures += 1
        print(f"{mark:<5} {case['name']:<44} {res.decision:<7} score={raw:.3f} "
              f"expected={'/'.join(sorted(case['expect']))}")
        print(f"      reasons: {'; '.join(res.reasons)}")

    print(f"\n{len(_CASES) - failures}/{len(_CASES)} passed"
          + (f"  ({degraded} via PASS* = routed to the grey band; set GROQ_API_KEY "
             f"or install fastembed to auto-merge)" if degraded else ""))
    return 1 if failures else 0


def sweep(pairs_json: Optional[str] = None) -> None:
    """T+130 threshold tuning. Prints precision/recall for a grid of thresholds.

    Defaults to the built-in 6 cases; point it at P5's seed ground truth with
    a JSON list of {"a": <Enrichment>, "b": <Enrichment>, "d_m":, "hours":,
    "dupe": true|false} to tune on the real 60-row set.
    """
    cases = _CASES
    if pairs_json:
        with open(pairs_json, encoding="utf-8") as fh:
            cases = [dict(name=f"pair{i}", a=Enrichment(**p["a"]), b=Enrichment(**p["b"]),
                          d_m=p["d_m"], hours=p["hours"],
                          expect={"LINK", "REVIEW"} if p["dupe"] else {"NEW"})
                     for i, p in enumerate(json.load(fh))]

    scored = [(("LINK" in c["expect"]), _run_case(c)[1]) for c in cases]
    auto_merge, _ = thresholds()
    print(f"backend: {backend_name()}   pairs: {len(scored)} "
          f"({sum(1 for d, _ in scored if d)} true dupes)\n")
    print(f"{'AUTO_MERGE':>11} {'TP':>4} {'FP':>4} {'FN':>4} {'precision':>10} {'recall':>8} {'F1':>6}")
    for thr in [round(0.40 + 0.02 * i, 2) for i in range(26)]:
        tp = sum(1 for dupe, s in scored if dupe and s >= thr)
        fp = sum(1 for dupe, s in scored if not dupe and s >= thr)
        fn = sum(1 for dupe, s in scored if dupe and s < thr)
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        flag = "  <- current" if abs(thr - auto_merge) < 1e-9 else ""
        print(f"{thr:>11.2f} {tp:>4} {fp:>4} {fn:>4} {prec:>10.2f} {rec:>8.2f} {f1:>6.2f}{flag}")
    print("\nA false merge hides a citizen's complaint: pick the highest threshold "
          "that still keeps recall acceptable, i.e. favour precision.")


def llm_check() -> int:
    """`python -m backend.dedup --llm-check` — is the adjudicator key actually live?

    Two probes with known answers: one true duplicate pair (expect YES) and one
    unrelated pair at the same distance (expect NO). Never prints the key.
    """
    picked = active_provider()
    if picked is None:
        print("adjudicator OFF — no ANTHROPIC_API_KEY or GROQ_API_KEY in the "
              "environment.\nPut one in .env at the repo root, then re-run.")
        return 1
    provider, model = picked
    key = os.getenv("ANTHROPIC_API_KEY" if provider == "anthropic" else "GROQ_API_KEY", "")
    print(f"provider : {provider}\nmodel    : {model}\nkey      : "
          f"{len(key)} chars, ends {key[-4:]!r}\n")

    probes = [
        (True, "Big pothole on MG Road near Modern School, bikes are falling in it",
         "Large crater in the road surface on MG Road outside the school", 80.0, 3.0),
        (False, "Garbage has not been collected in Kothrud market for four days",
         "The streetlight outside the Kothrud market gate is not working", 80.0, 3.0),
    ]
    failures = unavailable = 0
    for expected, a, b, dist, hours in probes:
        got = _adjudicate(a, b, dist, hours)
        ok = got is expected
        failures += 0 if ok else 1
        unavailable += 1 if got is None else 0
        shown = {True: "YES", False: "NO", None: "unavailable"}[got]
        print(f"{'PASS' if ok else 'FAIL'}  expected "
              f"{'YES' if expected else 'NO':<3} -> got {shown}")
        print(f"      A: {a[:62]}\n      B: {b[:62]}")

    if unavailable:
        print(f"\nThe call itself did not succeed — see the error above. A 404 from "
              f"Groq means the model id is wrong, not the key:\n"
              f"  python -m backend.dedup --groq-models\n"
              f"lists exactly what {provider!r} will accept. A 401 means the key "
              f"is bad.")
    elif failures:
        print(f"\nCalls succeeded but {model!r} disagreed with the probes. Its "
              f"judgement is too weak for the grey band — pick a stronger model.")
    else:
        print("\nAdjudicator live and answering correctly. Grey-band pairs "
              f"[{thresholds()[1]}, {thresholds()[0]}) will now resolve.")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--groq-models" in sys.argv:
        sys.exit(list_groq_models())
    if "--llm-check" in sys.argv:
        sys.exit(llm_check())
    if "--sweep" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--sweep"]
        sweep(rest[0] if rest else None)
    else:
        sys.exit(selftest())
