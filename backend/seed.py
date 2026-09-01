"""Offline, deterministic Pune demo data and a small API seed runner."""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "http://127.0.0.1:8000/complaints"
SEED_COMPLAINTS: list[dict[str, Any]] = []


def _add_group(group: str, category: str, lat: float, lng: float, minutes: int, texts: list[str], hint: str | None = None) -> None:
    """Add one physical issue with fixed small coordinate offsets (about 30–120m)."""
    offsets = [(0, 0), (.00035, .00028), (-.00045, .0005), (.0007, -.00022), (-.0002, -.0007)]
    for index, text in enumerate(texts):
        dlat, dlng = offsets[index]
        SEED_COMPLAINTS.append({"text": text, "lat": round(lat + dlat, 6), "lng": round(lng + dlng, 6),
                                "minutes_ago": minutes + index * 11, "true_group_id": group,
                                "expected_category": category, "expected_priority_hint": hint})


# 12 duplicate groups (English, Hindi, Marathi, Hinglish/romanized Marathi).
_add_group("g01_school_manhole", "sewage_overflow", 18.5204, 73.8415, 35, [
    "Open manhole beside Fergusson College gate; cyclist injured.", "कॉलेज गेट के पास खुला मैनहोल है, साइकिल सवार घायल हुआ।",
    "फर्ग्युसन कॉलेजजवळ उघडे मॅनहोल आहे, सायकलस्वार जखमी झाला.", "FC gate ke paas open manhole, cyclist hurt hai.",
    "College gate jawal ughda manhole aahe, khup dhokadayak."], "P0")
_add_group("g02_pothole_mg", "pothole", 18.5230, 73.8422, 120, [
    "Large pothole on MG Road near Deccan.", "एमजी रोड पर बड़ा गड्ढा है।", "एमजी रोडवर मोठा खड्डा आहे."])
_add_group("g03_water_leak", "water_leak", 18.5123, 73.8574, 300, [
    "Water pipe leaking continuously near Mandai.", "मंडईजवळ पाण्याची पाइपलाइन गळत आहे.", "Mandai ke paas water pipe leak ho raha hai."])
_add_group("g04_garbage", "garbage_uncollected", 18.5315, 73.8615, 840, [
    "Garbage has not been collected near Koregaon Park lane.", "कोरेगाव पार्क लेन में कचरा नहीं उठाया गया।", "कोरेगाव पार्क लेनमध्ये कचरा उचललेला नाही."])
_add_group("g05_streetlight", "streetlight_out", 18.5080, 73.8080, 1560, [
    "Streetlight is off near Kothrud Fire Station.", "कोथरूड फायर स्टेशनजवळ स्ट्रीट लाईट बंद आहे.", "Kothrud fire station ke paas light band hai."])
_add_group("g06_power", "power_outage", 18.5440, 73.8850, 2500, [
    "Power outage in Yerawada; entire lane is dark.", "यरवडा में बिजली गई है, पूरी गली अंधेरी है।", "यरवड्यात वीज गेली आहे, संपूर्ण गल्ली अंधारात आहे."])
_add_group("g07_sewage", "sewage_overflow", 18.5058, 73.8640, 3600, [
    "Sewage overflowing on the road near Swargate.", "स्वारगेटजवळ रस्त्यावर सांडपाणी वाहत आहे.", "Swargate road var sewage overflow hot ahe."])
_add_group("g08_water_shortage", "no_water_supply", 18.5500, 73.8030, 5100, [
    "No water supply in Aundh since morning.", "औंध में सुबह से पानी नहीं आ रहा है।", "औंधमध्ये सकाळपासून पाणी आलेले नाही."])
_add_group("g09_parking", "illegal_parking", 18.5290, 73.8758, 6900, [
    "Cars are blocking the ambulance lane near Sassoon Hospital.", "ससून अस्पताल के पास एंबुलेंस लेन में गाड़ियां खड़ी हैं।", "ससून हॉस्पिटलजवळ अॅम्ब्युलन्स लेनमध्ये गाड्या उभ्या आहेत."])
_add_group("g10_tree", "tree_fallen", 18.5180, 73.8330, 8200, [
    "Fallen tree blocking the road near Deccan Police Station.", "डेक्कन पोलीस स्टेशनजवळ पडलेले झाड रस्ता अडवत आहे.", "Deccan police station ke paas gira hua ped road block kar raha hai."])
_add_group("g11_mosquito", "mosquito_breeding", 18.5035, 73.9180, 9800, [
    "Stagnant water is causing mosquito breeding in Hadapsar.", "हडपसर में जमा पानी से मच्छर पैदा हो रहे हैं।", "हडपसरमध्ये साचलेल्या पाण्यात डासांची पैदास होत आहे."])
_add_group("g12_strays", "stray_animals", 18.5385, 73.8935, 11300, [
    "Aggressive stray dogs near Kalyani Nagar school.", "कल्याणी नगर स्कूल के पास आवारा कुत्ते हैं।", "कल्याणी नगर शाळेजवळ भटके कुत्रे आहेत."])

# Eight geographically far near-misses: similar language/category, deliberately new issues.
NEAR_MISS_CASES = [
    ("Big pothole on Nagar Road near Viman Nagar.", 18.5660, 73.9140), ("एमजी रोड जैसा बड़ा गड्ढा मगर शिवाजीनगर में है।", 18.5320, 73.8470),
    ("Water pipeline leak near Kothrud depot.", 18.5100, 73.8000), ("कोथरूड में पानी की सप्लाई बंद है।", 18.5000, 73.8080),
    ("Garbage is uncollected at Hadapsar market.", 18.4950, 73.9300), ("Street light बंद है near Aundh market.", 18.5580, 73.8070),
    ("Sewage overflow near Camp area road.", 18.5200, 73.8800), ("Illegal parking blocking lane in Baner.", 18.5640, 73.7800),
]
for i, (text, lat, lng) in enumerate(NEAR_MISS_CASES, 1):
    SEED_COMPLAINTS.append({"text": text, "lat": lat, "lng": lng, "minutes_ago": 300 + i * 130,
                            "true_group_id": None, "expected_category": "pothole" if i <= 2 else "other"})

# Ten distinct road defects concentrated around one local Deccan grid area: hotspot signal.
for i, (text, lat, lng) in enumerate([
    ("Deep pothole outside JM Road bus stop.", 18.5221, 73.84175), ("Road surface broken near Deccan Gymkhana crossing.", 18.5237, 73.84175),
    ("Crater on lane behind FC Road cafe.", 18.5229, 73.84345), ("Broken road edge at Apte Road junction.", 18.5242, 73.8450),
    ("Pothole filled with rainwater near Deccan signal.", 18.5260, 73.8450), ("Damaged asphalt on JM Road service lane.", 18.5242, 73.8471),
    ("Uneven road causing bike skids near FC Road.", 18.5260, 73.8471), ("Road crack widening near Deccan metro approach.", 18.5242, 73.8492),
    ("Pothole near college bus pickup point.", 18.5260, 73.8492), ("Broken road drain cover near JM Road.", 18.5278, 73.8508),
]):
    SEED_COMPLAINTS.append({"text": text, "lat": lat, "lng": lng, "minutes_ago": 50 + i * 40,
                            "true_group_id": None, "expected_category": "pothole"})

# Four unrelated singletons complete the exactly-60 dataset.
SEED_COMPLAINTS.extend([
    {"text": "Broken footpath tile near Pune station entrance.", "lat": 18.5289, "lng": 73.8750, "minutes_ago": 1800, "true_group_id": None, "expected_category": "road_damage"},
    {"text": "नाली जाम है और बदबू आ रही है।", "lat": 18.5140, "lng": 73.8560, "minutes_ago": 2400, "true_group_id": None, "expected_category": "sewage_overflow"},
    {"text": "Public tap leaking near Yerawada community point.", "lat": 18.5525, "lng": 73.8800, "minutes_ago": 4200, "true_group_id": None, "expected_category": "water_leak"},
    {"text": "रस्त्यावर कचरा टाकलेला आहे, कृपया साफ करा.", "lat": 18.5060, "lng": 73.8150, "minutes_ago": 6000, "true_group_id": None, "expected_category": "garbage_uncollected"},
])


def validate_seed(records: list[dict[str, Any]] = SEED_COMPLAINTS) -> None:
    """Assert the deterministic data constraints required for the hackathon demo."""
    assert len(records) == 60, f"expected 60 records, found {len(records)}"
    assert any(any("अ" <= char <= "ह" for char in record["text"]) for record in records), "Hindi/Marathi text missing"
    assert any(all(ord(char) < 128 for char in record["text"]) for record in records), "Latin-script text missing"
    groups = Counter(record["true_group_id"] for record in records if record["true_group_id"])
    assert len(groups) == 12 and all(3 <= size <= 5 for size in groups.values()), "duplicate groups invalid"
    assert len(NEAR_MISS_CASES) == 8, "near-miss cases missing"
    assert all(18.45 <= float(record["lat"]) <= 18.60 and 73.75 <= float(record["lng"]) <= 73.95 for record in records), "coordinates not Pune-like"


def validate_seed_data(records: list[dict[str, Any]] = SEED_COMPLAINTS) -> None:
    """Compatibility name for validating the deterministic 60-record seed set."""
    validate_seed(records)


def submit_seed(api_url: str = API_URL) -> int:
    """Submit records sequentially; return a process-style success status."""
    validate_seed()
    successes = failures = 0
    for index, record in enumerate(SEED_COMPLAINTS, 1):
        payload = {key: record[key] for key in ("text", "lat", "lng")}
        payload.update({"channel": "seed", "citizen_phone": "9999900000"})
        url = f"{api_url}?{urlencode({'backdate': record['minutes_ago']})}"
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=5) as response:
                response.read()
            successes += 1
            print(f"[{index:02d}/60] submitted")
        except (URLError, HTTPError, TimeoutError) as exc:
            failures += 1
            print(f"[{index:02d}/60] failed: {getattr(exc, 'reason', exc)}")
            if index == 1:
                print("FastAPI is unavailable. Start the API at http://127.0.0.1:8000 before seeding.")
                break
    print(f"Submitted: {successes + failures}; success: {successes}; failures: {failures}; expected duplicate groups: 12")
    print("Evaluation skipped — required API data unavailable.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    validate_seed()
    sys.exit(submit_seed())
