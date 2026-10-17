"""Take the terms page's fixed design out of its original artwork.

The terms of entry (guide p.19) were placed as one original PDF block, their
text drawn as outlines, so they could not be edited. Each auction may now
change them (some terms differ: the commission, VAT...), and the page sets
them as text. This script, run once on booklet-art/terms.pdf:

- writes booklet-art/terms-title.svg: the title "شروط الدخول بالمزاد" as
  drawn on the page (its outlines, on a page-sized canvas);
- adds the frame (stroked) and the bar beneath the terms (filled) to
  booklet-art/shapes.json as "terms_frame" and "terms_bar".

    python scripts/extract_terms_frame.py
"""

import hashlib
import json
import re
from pathlib import Path

import pymupdf

ART = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/booklet-art"
W, H = 595.28, 841.89
TEAL = (0.086, 0.631, 0.631)


def path_of(drawing):
    d, at = [], None
    for item in drawing["items"]:
        kind, points = item[0], item[1:]
        if kind == "re":
            r = points[0]
            d.append(f"M{r.x0:.2f} {r.y0:.2f}H{r.x1:.2f}V{r.y1:.2f}H{r.x0:.2f}Z")
            at = None
            continue
        if kind == "qu":
            q = points[0]
            d.append(
                f"M{q.ul.x:.2f} {q.ul.y:.2f}L{q.ur.x:.2f} {q.ur.y:.2f}"
                f"L{q.lr.x:.2f} {q.lr.y:.2f}L{q.ll.x:.2f} {q.ll.y:.2f}Z"
            )
            at = None
            continue
        start = points[0]
        if at is None or abs(at.x - start.x) > 0.01 or abs(at.y - start.y) > 0.01:
            d.append(f"M{start.x:.2f} {start.y:.2f}")
        if kind == "l":
            d.append(f"L{points[1].x:.2f} {points[1].y:.2f}")
        elif kind == "c":
            d.append("C" + " ".join(f"{p.x:.2f} {p.y:.2f}" for p in points[1:4]))
        at = points[-1]
    if drawing.get("closePath"):
        d.append("Z")
    return "".join(d)


page = pymupdf.open(ART / "terms.pdf")[0]
drawings = page.get_drawings()
title = [
    x
    for x in drawings
    if x.get("fill")
    and all(abs(a - b) < 0.01 for a, b in zip(x["fill"], TEAL))
    and x["rect"].y1 < 140
]
frame = [x for x in drawings if x.get("color") and x["rect"].height > 500]
bar = [
    x
    for x in drawings
    if x.get("fill") and x["rect"].width > 300 and x["rect"].y0 > 600
]
if len(title) != 1 or len(frame) != 1 or len(bar) != 1:
    raise SystemExit(f"unexpected artwork: {len(title)} {len(frame)} {len(bar)}")
(ART / "terms-title.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
    f'width="{W}pt" height="{H}pt"><path d="{path_of(title[0])}" '
    'fill="#16a1a1" fill-rule="evenodd"/></svg>'
)
shapes_file = ART / "shapes.json"
shapes = json.loads(shapes_file.read_text())
shapes["terms_frame"] = path_of(frame[0])
shapes["terms_bar"] = path_of(bar[0])
shapes_file.write_text(json.dumps(shapes, indent=1) + "\n")

# The artwork manifest records every file's hash.
manifest = ART / "manifest.json"
text = manifest.read_text()
for name in ("terms-title.svg", "shapes.json"):
    digest = hashlib.sha256((ART / name).read_bytes()).hexdigest()
    if f'"{name}"' in text:
        text = re.sub(
            rf'("{re.escape(name)}": ")[0-9a-f]{{64}}', rf"\g<1>{digest}", text
        )
    else:
        text = text.replace(
            '"files": {\n', f'"files": {{\n  "{name}": "{digest}",\n', 1
        )
manifest.write_text(text)
print("title, frame and bar written")
