"""
P2 — Language normalization + classification + extraction.

Public API (frozen contract with P1):
    enrich(text: str) -> Enrichment

Guarantees P1 can rely on:
  * NEVER raises. Worst case it returns a low-confidence keyword-rule guess.
  * category_l2 is ALWAYS one of L2_CATS.
  * category_l1 is DERIVED from category_l2 via L2_TO_L1 (the LLM is not
    trusted to keep the pair consistent — this kills a whole error class).
  * severity / confidence are always floats clamped to [0.0, 1.0].
  * Repeat calls with the same text are cached (instant + saves free quota).

Provider is swappable with one env var. Both Groq and Gemini speak the
OpenAI wire format, so there is no provider-specific code below.

    LLM_PROVIDER=groq    GROQ_API_KEY=gsk_...      # default, ~14400 req/day
    LLM_PROVIDER=gemini  GEMINI_API_KEY=AIza...    # better Indic, 250 req/day

Run it standalone:
    python -m app.nlp            # self-test on 8 multilingual complaints
    python -m app.nlp --models   # list model IDs your key can actually reach
"""

import os
import json
import re

try:
    from openai import OpenAI
except ImportError:  # The rule-based fallback must work without an LLM SDK.
    OpenAI = None  # type: ignore[assignment,misc]

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

_CFG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    },
}

if PROVIDER not in _CFG:
    raise SystemExit(f"LLM_PROVIDER must be one of {list(_CFG)}, got {PROVIDER!r}")

_C = _CFG[PROVIDER]
MODEL = _C["model"]
_KEY = os.getenv(_C["key_env"], "")

# No key -> client stays None -> every call goes straight to the keyword
# fallback. The pipeline still runs end to end, which is what matters at T+100.
_client = OpenAI(api_key=_KEY, base_url=_C["base_url"]) if _KEY and OpenAI else None


# ── Label space ───────────────────────────────────────────────────────────────
# L2 is what the model predicts. L1 is looked up, never predicted.

L2_TO_L1 = {
    "pothole":             "pwd",
    "road_damage":         "pwd",
    "tree_fallen":         "parks",
    "streetlight_out":     "power",
    "power_outage":        "power",
    "water_leak":          "water",
    "no_water_supply":     "water",
    "sewage_overflow":     "water",
    "garbage_uncollected": "swm",
    "mosquito_breeding":   "health",
    "stray_animals":       "health",
    "illegal_parking":     "traffic",
    "other":               "revenue",
}
L2_CATS = tuple(L2_TO_L1)

DEFAULT = {
    "lang": "unknown",
    "text_en": "",
    "category_l2": "other",
    "confidence": 0.25,
    "severity": 0.4,
    "landmarks": [],
    "summary": "",
}


# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM = """You process citizen grievance complaints for an Indian municipal body.

Input may be Hindi, Marathi, Tamil, Telugu, Bengali, English, or Roman-script
code-mixed (Hinglish, e.g. "road pe bada gaddha hai"). It may contain spelling
errors, SMS shorthand, and mixed scripts in one sentence.

Return ONLY a JSON object. No prose, no markdown fence.

{
  "lang": "<BCP-47; append -Latn if an Indian language is written in Roman
            script, e.g. hi-Latn, mr-Latn>",
  "text_en": "<faithful English translation. Keep proper nouns (road names,
               landmarks) as-is. If input is already English, copy verbatim.>",
  "category_l2": "<EXACTLY one of: pothole | road_damage | streetlight_out |
      water_leak | no_water_supply | power_outage | garbage_uncollected |
      sewage_overflow | stray_animals | mosquito_breeding | illegal_parking |
      tree_fallen | other>",
  "confidence": <0.0-1.0 — your honest confidence in category_l2>,
  "severity": <choose EXACTLY one of 0.1, 0.4, 0.7, 1.0 — never any other value:
      1.0  someone is ALREADY hurt, or a fall/accident/death is described;
           live or fallen electric wire; open manhole or uncovered drain;
           wall, building or tree collapse; sewage inside homes; gas leak
      0.7  a real hazard that has not injured anyone YET: deep pothole or
           open pit on a used road, flooding or burst pipe on a road, no
           water for more than a day, an area unsafe after dark, blocked
           road or traffic jam, garbage rotting 3+ days or breeding
           disease, dengue risk, or anything near a school or hospital
      0.4  persistent inconvenience with no path to injury: garbage missed
           for 1-2 days, one streetlight out on an otherwise lit street,
           low water pressure, illegal parking, potholes on a quiet lane
      0.1  cosmetic only: faded road paint, minor litter, bent signboard>,
  "landmarks": ["<road names, areas, and nearby places named in the text.
                  Transliterate to English. Empty list if none.>"],
  "summary": "<max 12 English words, imperative, for an officer's work queue>"
}

Rules:
- Be conservative with confidence. If the complaint is vague, or plausibly
  belongs to two different departments, output confidence below 0.55 so a
  human triages it. A wrong confident answer is worse than an honest
  low-confidence one.
- Severity is about what the TEXT DESCRIBES, not how the writer feels. Angry
  tone is not severity. A calm sentence reporting that someone already fell
  is still 1.0.
- Two complaints describing the same incident in different languages must get
  the same severity. Judge the event, not the wording.
- A physical hazard always belongs to the department that owns the asset. Map
  these to the closest listed category instead of "other":
    open, missing or broken manhole / drain cover  -> sewage_overflow
    live, fallen, sagging or sparking electric wire -> power_outage
    broken, leaning or damaged electric pole        -> power_outage
    damaged footpath, divider, guardrail or kerb    -> road_damage
    overflowing, choked or blocked storm drain      -> sewage_overflow
    waterlogging or flooding on a road              -> sewage_overflow
- Reserve "other" for complaints that are not a physical civic defect at all
  (staff behaviour, documents, billing, requests for information). Never put a
  dangerous physical hazard in "other"."""


# ── Keyword fallback (layer 3) ────────────────────────────────────────────────
# Runs when there is no API key, the call fails twice, or JSON is unparseable.
# Devanagari + romanized forms, because Hinglish is what people actually type.

KEYWORDS = {
    "pothole": ["pothole", "gaddha", "gadda", "khadda", "khadde", "गड्ढा", "गढ्ढा", "खड्डा"],
    "road_damage": ["road broken", "road damage", "sadak", "सड़क", "रस्ता", "tuti", "टूटी"],
    "streetlight_out": ["streetlight", "street light", "lamp post", "batti", "बत्ती",
                        "दिवा", "khamba", "खंभा", "स्ट्रीट लाइट"],
    "power_outage": ["power cut", "no electricity", "outage", "bijli", "बिजली",
                     "veej", "वीज", "light gayi", "load shedding", "transformer"],
    "water_leak": ["leak", "leakage", "pipe burst", "galti", "गळती", "पाइप",
                   "paani beh", "पानी बह"],
    "no_water_supply": ["no water", "water supply", "paani nahi", "पानी नहीं",
                        "पाणी नाही", "tanker", "टँकर", "nal", "नल"],
    "sewage_overflow": ["sewage", "drain", "drainage", "gutter", "nali", "नाली",
                        "गटार", "गंदा पानी", "manhole", "मैनहोल", "sandas"],
    "garbage_uncollected": ["garbage", "trash", "waste", "kachra", "कचरा",
                            "kooda", "कूड़ा", "ghanta gadi", "घंटा गाडी", "dump"],
    "mosquito_breeding": ["mosquito", "machchar", "मच्छर", "das", "डास", "dengue", "डेंगू"],
    "stray_animals": ["stray dog", "kutta", "कुत्ता", "कुत्रा", "cattle",
                      "गाय", "bhains", "भैंस", "monkey", "बंदर", "pig", "डुक्कर"],
    "illegal_parking": ["illegal parking", "parking", "पार्किंग", "encroach",
                        "अतिक्रमण", "no parking"],
    "tree_fallen": ["tree fallen", "tree fell", "ped gir", "पेड़ गिर", "झाड पड",
                    "branch", "डाली"],
}

SEVERE = ["injur", "injured", "गिर गया", "गिर गई", "gir gaya", "pad gaya", "जखमी",
          "wound", "khoon", "खून", "live wire", "current", "करंट", "बिजली का तार",
          "shock", "झटका", "open manhole", "खुला", "collapse", "ढह", "कोसळ",
          "death", "मौत", "accident", "एक्सीडेंट", "अपघात", "hospital", "ambulance"]

MODERATE = ["traffic", "jam", "जाम", "school", "स्कूल", "शाळा", "hospital",
            "अस्पताल", "smell", "बदबू", "दुर्गंध", "disease", "बीमारी",
            "children", "बच्चे", "मुले", "blocked", "बंद"]


def _keyword_guess(text: str) -> dict:
    """Layer-3 fallback. Never fails, never calls the network."""
    low = text.lower()
    hits = {c: sum(1 for k in kws if k.lower() in low) for c, kws in KEYWORDS.items()}
    best = max(hits, key=hits.get)
    n = hits[best]

    if n == 0:
        cat, conf = "other", 0.2
    else:
        cat, conf = best, min(0.30 + 0.12 * n, 0.54)   # capped below the 0.55
                                                       # triage line on purpose
    if any(s in low for s in SEVERE):
        sev = 0.9
    elif any(m in low for m in MODERATE):
        sev = 0.65
    else:
        sev = 0.4

    return {
        "lang": "unknown",
        "text_en": text,                # unchanged; dedup still works on it
        "category_l2": cat,
        "confidence": conf,
        "severity": sev,
        "landmarks": [],
        "summary": text[:60],
        "_source": "keyword",
    }


# ── Coercion (layer 2) ────────────────────────────────────────────────────────

def _clamp(v, lo=0.0, hi=1.0, default=0.4) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _extract_json(raw: str) -> dict:
    """Models sometimes wrap JSON in a fence or add a sentence. Dig it out."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)      # first {...} block
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError("no JSON object in model output")


def _coerce(d: dict, text: str) -> dict:
    """Force whatever the model returned into the frozen contract shape."""
    cat = str(d.get("category_l2", "other")).strip().lower()
    if cat not in L2_TO_L1:
        cat = "other"

    lm = d.get("landmarks") or []
    if isinstance(lm, str):
        lm = [lm]
    lm = [str(x).strip() for x in lm if str(x).strip()][:5]

    text_en = str(d.get("text_en") or "").strip() or text
    summary = str(d.get("summary") or "").strip() or text_en[:60]

    return {
        "lang": str(d.get("lang") or "unknown").strip()[:12],
        "text_en": text_en,
        "category_l2": cat,
        "confidence": _clamp(d.get("confidence"), default=0.5),
        "severity": _clamp(d.get("severity"), default=0.4),
        "landmarks": lm,
        "summary": summary[:120],
        "_source": PROVIDER,
    }


# ── LLM call (layer 1) ────────────────────────────────────────────────────────

def _call_llm(text: str) -> dict:
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": text}],
        response_format={"type": "json_object"},   # honoured by Groq + Gemini
        temperature=0.0,                           # classification: be boring
        # Headroom matters: newer models (Gemini 3.x) spend tokens on internal
        # reasoning before the JSON. At 500 they run out and return nothing.
        max_tokens=2000,
        timeout=30,
    )
    return _extract_json(resp.choices[0].message.content)


# ── Public entry point ────────────────────────────────────────────────────────

_CACHE: dict[str, dict] = {}


def enrich_raw(text: str) -> dict:
    """Returns a plain dict matching the Enrichment contract. Never raises.

    Kept dict-shaped so P2 can develop and test before P1's contracts.py
    exists. `enrich()` below is the wrapper P1 actually calls.
    """
    text = (text or "").strip()
    if not text:
        return {**DEFAULT, "category_l1": "revenue", "_source": "empty"}

    key = " ".join(text.lower().split())
    if key in _CACHE:
        return _CACHE[key]

    out = None
    if _client:
        for attempt in (1, 2):                     # one retry, then give up
            try:
                out = _coerce(_call_llm(text), text)
                break
            except Exception as e:                 # noqa: BLE001 — must not raise
                msg = str(e)
                print(f"[nlp] {PROVIDER} attempt {attempt} failed: "
                      f"{type(e).__name__}: {msg}")
                if type(e).__name__ == "NotFoundError" or "model" in msg.lower() and (
                        "not_found" in msg or "no longer available" in msg
                        or "does not exist" in msg):
                    print(f"[nlp] HINT: model {MODEL!r} is not available on this "
                          f"key. Run `python -m app.nlp --models` and put a real "
                          f"id in .env as {'GROQ_MODEL' if PROVIDER == 'groq' else 'GEMINI_MODEL'}.")
                    break                          # retrying a bad id is pointless
    if out is None:
        out = _keyword_guess(text)

    out["category_l1"] = L2_TO_L1[out["category_l2"]]   # derived, never trusted
    _CACHE[key] = out
    return out


def enrich(text: str):
    """Contract entry point. Returns an Enrichment if P1's contracts.py is
    importable, else the raw dict — so this module is never blocked on P1."""
    d = enrich_raw(text)
    try:
        from backend.contracts import Enrichment
    except Exception:                              # noqa: BLE001
        return d
    return Enrichment(**{k: v for k, v in d.items() if not k.startswith("_")})


def needs_triage(d) -> bool:
    """P1: route to the human triage queue instead of a department."""
    c = d["confidence"] if isinstance(d, dict) else d.confidence
    return c < 0.55


# ── Self-test ─────────────────────────────────────────────────────────────────

SAMPLES = [
    "MG road pe bahut bada gaddha hai, kal scooter gir gaya, school ke samne",
    "एमजी रोड पर बड़ा गड्ढा है, कोई गिर सकता है",
    "Large pothole in front of Modern School on MG Road, someone fell yesterday",
    "आमच्या भागात ३ दिवसांपासून कचरा उचलला नाही, खूप दुर्गंध येते",
    "Street light number 42 near Shivaji Chowk band hai 1 week se, raat ko dar lagta hai",
    "पाइप फूट गया है, सारा पानी सड़क पर बह रहा है, Kothrud area",
    "There is a live electric wire hanging low near the bus stop, very dangerous",
    "kal se paani nahi aaya, tanker bhejo please",
]

if __name__ == "__main__":
    import sys

    # Windows consoles default to cp1252 and crash on Devanagari. Force UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if "--models" in sys.argv:
        if not _client:
            raise SystemExit(f"set {_C['key_env']} in .env first")
        for m in _client.models.list().data:
            print(m.id)
        raise SystemExit(0)

    print(f"provider={PROVIDER}  model={MODEL}  key={'set' if _KEY else 'MISSING'}\n")

    # Any free text passed on the command line classifies just that one input:
    #   python -m app.nlp "MG road pe gaddha hai"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    todo = args if args else SAMPLES

    for s in todo:
        d = enrich_raw(s)
        flag = "  <<< TRIAGE" if needs_triage(d) else ""
        print(f"  in   : {s[:70]}")
        print(f"  lang : {d['lang']:<8} src={d['_source']}")
        print(f"  cat  : {d['category_l1']}/{d['category_l2']}  "
              f"conf={d['confidence']:.2f}  sev={d['severity']:.2f}{flag}")
        print(f"  en   : {d['text_en'][:70]}")
        print(f"  marks: {d['landmarks']}")
        print(f"  sum  : {d['summary']}\n")





