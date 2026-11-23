"""Generate synthetic receipt images and a separate candidate ledger."""
import json
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MERCHANTS = ("LUMEN MARKET", "ATLAS COFFEE", "NORTH BOOKS", "TEJO BAKERY",
             "VISTA GROCERY", "PORTO STUDIO", "OLIVE CORNER", "RIVER CAFE")
GROUPS = ("clean", "blurred", "same_amount", "indistinguishable", "no_match")


def generate():
    images = DATA / "receipts"
    images.mkdir(parents=True, exist_ok=True)
    ledger, cases = [], []
    for group_index, group in enumerate(GROUPS):
        for offset in range(4):
            index = group_index * 4 + offset
            day = (date(2026, 3, 1) + timedelta(days=index * 3)).isoformat()
            merchant = MERCHANTS[index % len(MERCHANTS)]
            amount = 725 + index * 137
            key = f"r{index + 1:02}"
            base = {"merchant": merchant, "date": day, "cents": amount}
            other = dict(base, merchant=MERCHANTS[(index + 2) % len(MERCHANTS)])
            # Only present ledger evidence can disambiguate identical candidates.
            if group != "no_match":
                ledger.append(dict(base, id=f"T{index + 1:02}A"))
            if group == "indistinguishable":
                other = base
            if group in {"clean", "blurred"}:
                other = dict(other, cents=amount + 231)
            ledger.append(dict(other, id=f"T{index + 1:02}B"))
            expected = (f"T{index + 1:02}A" if group in GROUPS[:3] else None)
            cases.append(dict(base, id=key, group=group, expected=expected,
                              expected_status={"indistinguishable": "ambiguous",
                                               "no_match": "no_match"}.get(group, "matched")))
            image = Image.new("RGB", (460, 370), "#f4f1e8")
            draw = ImageDraw.Draw(image)
            for y, text, size in [
                (28, merchant, 31), (94, f"DATE  {day}", 23),
                (147, "ITEMS                         EUR", 20),
                (190, f"Purchase                 {amount / 100:.2f}", 20),
                (245, f"TOTAL EUR {amount / 100:.2f}", 34),
                (320, "THANK YOU", 18),
            ]:
                draw.text((36, y), text, fill="#181918", font=ImageFont.load_default(size=size))
            draw.line((35, 230, 423, 230), fill="#6d706d")
            if group == "blurred":
                image = image.filter(ImageFilter.GaussianBlur((0.9, 1.6, 2.3, 3.1)[offset]))
            image.save(images / f"{key}.png", optimize=True)
    for name, rows in (("ledger", ledger), ("cases", cases)):
        (DATA / f"{name}.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
