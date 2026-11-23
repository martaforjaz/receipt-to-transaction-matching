"""Extract receipt fields and match them conservatively to a synthetic ledger."""
import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


@dataclass(frozen=True)
class Fields:
    merchant: str | None = None
    date: str | None = None
    cents: int | None = None


def parse_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    first_line = re.sub(r"^\s*merchant\s*:\s*", "", first_line, flags=re.I)
    first_line = re.split(r"\b(?:date|total)\s*:", first_line, maxsplit=1, flags=re.I)[0]
    first_line = first_line.strip(" -:*;!`")
    merchant = first_line if re.fullmatch(r"[A-Za-z][A-Za-z &'-]{2,}", first_line) else None
    days = set(re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", text))
    day = next(iter(days)) if len(days) == 1 else None
    try:
        if day:
            date.fromisoformat(day)
    except ValueError:
        day = None
    amounts = {
        int(units) * 100 + int(fraction.ljust(2, "0"))
        for units, fraction in re.findall(r"\bTOTAL\s*(?:EUR\s*)?[:=]?\s*(\d+)[.,](\d{1,2})(?!\d)", text, re.I)
    }
    cents = next(iter(amounts)) if len(amounts) == 1 else None
    return Fields(None if merchant and merchant.upper() == "UNKNOWN" else merchant, day, cents)


@lru_cache(maxsize=1)
def ocr_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)


def extract_ocr(path):
    detections, _ = ocr_engine()(str(path))
    rows = []
    for box, text, confidence in sorted(detections or [], key=lambda item: (min(p[1] for p in item[0]), min(p[0] for p in item[0]))):
        y = sum(point[1] for point in box) / 4
        x = min(point[0] for point in box)
        if confidence < 0.35:
            continue
        if rows and abs(rows[-1][0] - y) < 12:
            rows[-1][1].append((x, text))
        else:
            rows.append((y, [(x, text)]))
    text = "\n".join(" ".join(value for _, value in sorted(parts)) for _, parts in rows)
    return parse_text(text), text


def extract_vision(path):
    base = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    payload = {
        "model": os.getenv("VISION_MODEL", "moondream"),
        "prompt": ("Read this receipt. Transcribe the merchant name on the first line, "
                   "the date in YYYY-MM-DD on the second, and TOTAL EUR followed by the "
                   "exact amount with two decimal digits on the third. No explanation. "
                   "Use UNKNOWN for unreadable fields."),
        "images": [base64.b64encode(path.read_bytes()).decode("ascii")],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 115},
    }
    request = Request(base.rstrip("/") + "/api/generate", json.dumps(payload).encode(),
                      {"Content-Type": "application/json"})
    with urlopen(request, timeout=120) as response:
        text = json.load(response)["response"]
    return parse_text(text), text


def normalize(name):
    return "".join(re.findall(r"[a-z0-9]+", name.lower()))


def match(fields, ledger):
    if not fields.date or fields.cents is None or not fields.merchant:
        return {"status": "needs_review", "transaction": None, "candidates": []}
    merchant = normalize(fields.merchant)
    candidates = sorted(
        ((SequenceMatcher(None, merchant, normalize(item["merchant"])).ratio(), item["id"])
         for item in ledger if item["date"] == fields.date and item["cents"] == fields.cents),
        reverse=True,
    )
    evidence = [{"id": identifier, "merchant_similarity": round(score, 3)} for score, identifier in candidates]
    if not candidates or candidates[0][0] < 0.85:
        return {"status": "no_match", "transaction": None, "candidates": evidence}
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.12:
        return {"status": "ambiguous", "transaction": None, "candidates": evidence}
    return {"status": "matched", "transaction": candidates[0][1], "candidates": evidence}


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
