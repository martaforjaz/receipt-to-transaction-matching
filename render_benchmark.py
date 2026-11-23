"""Render manuscript-style benchmark panels directly from the result files."""
from html import escape
from pathlib import Path

from matching import ROOT, load

LABELS = ("Clean", "Blurred", "Same total", "Ambiguous", "No match")


def render():
    methods = [load("results-ocr"), load("results-vision")]
    colors = ("#25598a", "#39877b")
    groups = list(methods[0]["by_group"])
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="335" viewBox="0 0 960 335" role="img" aria-labelledby="title">',
             '<title id="title">Correct end-to-end outcomes by receipt scenario and correct extracted fields</title>',
             '<rect width="960" height="335" fill="#fff"/>',
             '<g font-family="system-ui,sans-serif" fill="#172d44">']
    for left, letter, title, labels, values, maximum in [
        (28, "A", "Correct outcomes", LABELS,
         [[method["by_group"][group]["correct_outcomes"] for group in groups] for method in methods], 4),
        (506, "B", "Correct fields", ("Merchant", "Date", "Total"),
         [[method["summary"]["fields_correct"][key] for key in ("merchant", "date", "cents")]
          for method in methods], 20),
    ]:
        parts.append(f'<text x="{left}" y="30" font-size="18" font-weight="700">{letter}</text>')
        parts.append(f'<text x="{left + 32}" y="30" font-size="18" font-weight="600">{title}</text>')
        for tick in range(5):
            x = left + 110 + tick * 60
            parts.append(f'<path d="M{x} 52v213" stroke="#dce4ea"/>')
            parts.append(f'<text x="{x}" y="284" text-anchor="middle" font-size="13">{tick * maximum // 4}</text>')
        for position, name in enumerate(labels):
            y = 70 + position * 41
            parts.append(f'<text x="{left}" y="{y + 12}" font-size="14">{escape(name)}</text>')
            for method_index, color in enumerate(colors):
                value = values[method_index][position]
                width = 240 * value / maximum
                top = y + method_index * 12
                if value:
                    parts.append(f'<rect x="{left + 110}" y="{top}" width="{width}" height="9" fill="{color}"/>')
                parts.append(f'<text x="{left + 114 + width}" y="{top + 9}" font-size="11">{value}</text>')
    for x, color, label in zip((327, 515), colors, ("RapidOCR + rules", "Moondream + rules")):
        parts.append(f'<rect x="{x}" y="308" width="15" height="9" fill="{color}"/>')
        parts.append(f'<text x="{x + 22}" y="317" font-size="14">{label}</text>')
    parts.append("</g></svg>")
    path = ROOT / "figures" / "benchmark.svg"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    render()
