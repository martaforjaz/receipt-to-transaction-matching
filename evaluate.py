"""Benchmark field accuracy, assignment accuracy and deliberate abstention."""
import argparse
import json
from dataclasses import asdict
from statistics import median
from time import perf_counter
from urllib.error import URLError

from matching import DATA, Fields, extract_ocr, extract_vision, load, match, normalize, parse_text

EXTRACTORS = {"ocr": extract_ocr, "vision": extract_vision}


def assess(extractor, case, ledger):
    start = perf_counter()
    error = None
    try:
        fields, raw = extractor(DATA / "receipts" / f"{case['id']}.png")
    except (URLError, TimeoutError) as exc:
        fields, raw = Fields(), ""
        error = str(exc)
    return score(case, ledger, fields, raw, error, (perf_counter() - start) * 1000)


def score(case, ledger, fields, raw, error, elapsed_ms):
    result = match(fields, ledger)
    return {
        "id": case["id"], "group": case["group"], "expected": case["expected"],
        "expected_status": case["expected_status"], "parsed": asdict(fields), "raw": raw,
        "result": result, "error": error, "ms": round(elapsed_ms, 1),
        "fields_correct": {
            "merchant": bool(fields.merchant and normalize(fields.merchant) == normalize(case["merchant"])),
            "date": fields.date == case["date"], "cents": fields.cents == case["cents"],
        },
    }


def summarize(rows):
    return {
        "cases": len(rows),
        "fields_correct": {field: sum(row["fields_correct"][field] for row in rows)
                           for field in ("merchant", "date", "cents")},
        "correct_matches": sum(row["expected"] is not None and row["result"]["transaction"] == row["expected"]
                               for row in rows),
        "wrong_matches": sum(row["result"]["transaction"] is not None
                             and row["result"]["transaction"] != row["expected"] for row in rows),
        "correct_abstentions": sum(row["expected"] is None and row["result"]["transaction"] is None
                                   and not row["error"] for row in rows),
        "correct_outcomes": sum(not row["error"] and row["expected_status"] == row["result"]["status"]
                                and row["expected"] == row["result"]["transaction"] for row in rows),
        "errors": sum(row["error"] is not None for row in rows),
        "median_ms": round(median(row["ms"] for row in rows if not row["error"]), 1)
        if any(not row["error"] for row in rows) else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=EXTRACTORS)
    parser.add_argument("--rescore", action="store_true", help="Reparse stored vision outputs without another model call")
    args = parser.parse_args()
    if args.rescore and args.method != "vision":
        parser.error("--rescore is supported for vision only")
    output_path = DATA / f"results-{args.method}.json"
    previous = {}
    if args.rescore:
        previous = {row["id"]: row for row in json.loads(output_path.read_text(encoding="utf-8"))["cases"]}
    cases, ledger = load("cases"), load("ledger")
    rows = []
    for case in cases:
        if args.rescore:
            saved = previous[case["id"]]
            row = score(case, ledger, parse_text(saved["raw"]), saved["raw"], saved["error"], saved["ms"])
        else:
            row = assess(EXTRACTORS[args.method], case, ledger)
        rows.append(row)
        print(case["id"], row["result"]["status"], row["ms"], flush=True)
    output = {"method": args.method, "summary": summarize(rows),
              "by_group": {group: summarize([row for row in rows if row["group"] == group])
                           for group in dict.fromkeys(case["group"] for case in cases)},
              "cases": rows}
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(output["summary"])
    raise SystemExit(bool(output["summary"]["errors"]))


if __name__ == "__main__":
    main()
