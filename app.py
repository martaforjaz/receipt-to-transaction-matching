"""Local demo of OCR and ledger matching on the benchmark receipts."""
import json
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from matching import DATA, ROOT, extract_ocr, load, match

LEDGER = load("ledger")
BENCHMARK = {case["id"]: case["group"] for case in load("cases")}


class Handler(BaseHTTPRequestHandler):
    def send(self, content, mime="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, value, status=200):
        self.send(json.dumps(value).encode(), status=status)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            return self.send((ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/cases":
            return self.send_json(BENCHMARK)
        request = re.fullmatch(r"/(receipt|match|vision)/(r\d{2})", path)
        if not request or request[2] not in BENCHMARK:
            return self.send_json({"error": "Unknown receipt"}, 404)
        image = DATA / "receipts" / f"{request[2]}.png"
        if request[1] == "receipt":
            return self.send(image.read_bytes(), "image/png")
        if request[1] == "vision":
            results = DATA / "results-vision.json"
            if not results.exists():
                return self.send_json({"error": "Vision benchmark has not been run"}, 503)
            row = next(item for item in json.loads(results.read_text(encoding="utf-8"))["cases"]
                       if item["id"] == request[2])
            return self.send_json(row)
        fields, raw = extract_ocr(image)
        return self.send_json({"parsed": asdict(fields), "result": match(fields, LEDGER), "raw": raw})


if __name__ == "__main__":
    print("Receipt matcher at http://127.0.0.1:8766")
    HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
