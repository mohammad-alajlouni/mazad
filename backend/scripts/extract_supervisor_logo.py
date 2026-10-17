"""Take the Infath logo out of the booklet artwork, keeping where it was.

The supervising body's logo is placed by the templates (see art.supervisor_logo)
so it can be replaced — a new Infath logo, or another body's — without editing
any design. This script, run once on the traced artwork:

- writes booklet-art/infath-logo.svg: the logo's 13 paths, as drawn on the
  pages, in a box of its own;
- writes booklet-art/logo-boxes.json: where the logo stood on each page
  artwork and each cover, in points (x, y, width, height);
- removes those paths from the page artworks and the six vector covers, and
  renders the covers' browser previews again from the cleaned files.

    python scripts/extract_supervisor_logo.py
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_cover import clean_cover

ASSETS = Path(__file__).resolve().parents[1] / "app/templates/infath/assets"
ART = ASSETS / "booklet-art"
W, H = 595.276, 841.89
LOGO = re.compile(r'<path d="([^"]*)" fill="#031445"/>')
PAGES = [
    "plain",
    "boundaries",
    "images-features",
    "information",
    "landscape",
    "landscape-close",
    "portrait",
    "portrait-close",
    "rentals",
    "summary",
]


def bounds(paths):
    nums = [[float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", p)] for p in paths]
    xs = [v for n in nums for v in n[0::2]]
    ys = [v for n in nums for v in n[1::2]]
    return min(xs), min(ys), max(xs), max(ys)


def box(x0, y0, x1, y1):
    return [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


boxes = {}
logo = None
for name in PAGES:
    path = ART / f"{name}.svg"
    svg = path.read_text()
    paths = LOGO.findall(svg)
    if len(paths) != 13:
        raise SystemExit(f"{name}: expected the logo's 13 paths, found {len(paths)}")
    x0, y0, x1, y1 = bounds(paths)
    boxes[name] = box(x0, y0, x1, y1)
    if logo is None:
        logo = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} '
            f'{x1 - x0:.2f} {y1 - y0:.2f}">'
            + "".join(f'<path d="{d}" fill="#031445"/>' for d in paths)
            + "</svg>"
        )
    path.write_text(LOGO.sub("", svg))
(ART / "infath-logo.svg").write_text(logo)

# The covers: white logo in the top corner. Its 13 drawings are the only
# paint wholly inside its box; backgrounds and photographs reach beyond it.
for n in range(1, 7):
    source = ART / f"vector/cover-{n}.pdf"
    page = pymupdf.open(source)[0]
    found = [
        d["rect"]
        for d in page.get_drawings()
        if d["rect"].x0 > 440 and d["rect"].y1 < 120 and d["rect"].width < 120
    ]
    if len(found) != 13:
        raise SystemExit(f"cover-{n}: expected the logo's 13 paths, found {len(found)}")
    area = found[0]
    for rect in found[1:]:
        area |= rect
    boxes[f"cover-{n}"] = box(*area)
    margin = area + (-1, -1, 1, 1)
    cleaned = clean_cover(str(source), [tuple(margin)])
    # The rewritten stream puts each operator on its own line; spaces, as in
    # the original, keep it readable for the photograph swap (art.py). Safe:
    # the covers carry no text strings or inline images.
    xref = cleaned[0].get_contents()[0]
    stream = cleaned.xref_stream(xref).decode("latin1")
    if re.search(r"\bBI\b|[()]", stream):
        raise SystemExit(f"cover-{n}: unexpected strings or inline images")
    cleaned.update_stream(xref, stream.replace("\n", " ").encode("latin1"))
    data = cleaned.tobytes(garbage=4, deflate=True)
    check = pymupdf.open(stream=data, filetype="pdf")[0]
    left = [d for d in check.get_drawings() if margin.contains(d["rect"])]
    if left:
        raise SystemExit(f"cover-{n}: {len(left)} drawings left in the logo box")
    source.write_bytes(data)
    # The browser preview of the cover, rendered from the cleaned vectors.
    preview = ASSETS / f"reference-cover-{n}.png"
    zoom = 1786 / W
    preview.write_bytes(
        check.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")
    )
    if n in (1, 6):
        # The frame laid over the author's photograph (see build_vector_art.py).
        frame = pymupdf.open(stream=data, filetype="pdf")
        target = frame[0].get_contents()[0]
        stream = frame.xref_stream(target).decode("latin1")
        own = re.search(
            r"q ?(?:/GS0 gs)? ?[-\d.]+ 0 0 [-\d.]+ [-\d.]+ [-\d.]+ cm /Im1 Do Q", stream
        )
        if not own:
            raise SystemExit(f"cover-{n}: photograph not found")
        beneath = re.sub(
            r"[-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ re f ", "", stream[: own.start()]
        )
        frame.update_stream(target, (beneath + stream[own.end() :]).encode("latin1"))
        scale = 1240 / W
        (ART / f"vector/cover-{n}-frame.png").write_bytes(
            frame[0]
            .get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
            .tobytes("png")
        )

# The introduction page (guide p.11): the logo at twice its footer size.
boxes["introduction"] = [400.1, 195.5, 63.3, 47.8]
(ART / "logo-boxes.json").write_text(json.dumps(boxes, indent=1) + "\n")


# The artwork manifests record every file's hash: only the changed lines move.
def rehash(manifest, extra=()):
    text = manifest.read_text()
    for name in [*re.findall(r'"([^"]+\.(?:svg|pdf|png))": "[0-9a-f]{64}"', text)]:
        target = manifest.parent / name
        if target.exists():
            text = re.sub(
                rf'("{re.escape(name)}": ")[0-9a-f]{{64}}',
                rf"\g<1>{hashlib.sha256(target.read_bytes()).hexdigest()}",
                text,
            )
    for name in extra:
        digest = hashlib.sha256((manifest.parent / name).read_bytes()).hexdigest()
        text = text.replace(
            '"files": {\n', f'"files": {{\n  "{name}": "{digest}",\n', 1
        )
    manifest.write_text(text)


rehash(ART / "manifest.json", ["infath-logo.svg", "logo-boxes.json"])
rehash(ART / "vector/manifest.json")
# The covers' record of what was taken out of their sources.
provenance = ASSETS / "provenance.json"
record = json.loads(provenance.read_text())
for n in range(1, 7):
    x, y, w, h = boxes[f"cover-{n}"]
    entry = record.get(f"cover-{n}")
    if entry is not None:
        entry["removed_supervisor_logo"] = [x, y, round(x + w, 2), round(y + h, 2)]
provenance.write_text(json.dumps(record, ensure_ascii=False, indent=2))
print("logo boxes:", json.dumps(boxes))
