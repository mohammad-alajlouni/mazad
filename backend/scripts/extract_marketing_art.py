"""Take the guide's boards and social posts out of the guide, as vectors.

    python scripts/extract_marketing_art.py GUIDE.pdf

GUIDE.pdf is «دليل التسويق والهوية البصرية للمزادات» (V2). For each design in
app/generation/marketing/spec.py it writes, in templates/infath/assets/marketing:

- <name>.pdf: the design ("مثال") cut from its page, its sample values,
  placeholders and photograph removed; placed under the values on export;
- <name>.png: the same for the live preview;
- layout.json: each slot measured from the guide's own sample (font, size,
  colour, baseline, alignment), relative to the design's top left corner;
- manifest.json: the guide's and every file's hash.
"""

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.generation.marketing.spec import TEMPLATES

ASSETS = ROOT / "app/templates/infath/assets"
OUT = ASSETS / "marketing"
FONTS = {
    ("r", 400): ASSETS / "identity/RuaqArabic-Light.ttf",
    ("r", 500): ASSETS / "identity/RuaqArabic-Medium.ttf",
    ("r", 700): ASSETS / "identity/RuaqArabic-Bold.ttf",
    ("l", 400): ASSETS / "identity/LamaSans-Light.ttf",
    ("l", 500): ASSETS / "identity/LamaSans-Medium.ttf",
    ("l", 700): ASSETS / "LamaSans-Bold.otf",
    ("l", 900): ASSETS / "identity/LamaSans-Black.ttf",
}
WEIGHTS = {
    "Light": 400,
    "Regular": 500,
    "Medium": 500,
    "SemiBold": 500,
    "Bold": 700,
    "ExtraBold": 900,
    "Black": 900,
}


def norm(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ـً-ْ()\s]", "", text)
    return text


def font_of(span):
    name = span["font"].split("+")[-1]
    family = "l" if name.startswith("Lama") else "r"
    weight = WEIGHTS.get(name.split("-")[-1], 500)
    if family == "r":
        weight = min(max(weight, 400), 700)
    return family, weight


def hex_colour(value):
    if isinstance(value, int):
        return f"#{value:06x}"
    return "#{:02x}{:02x}{:02x}".format(*tuple(round(c * 255) for c in value))


def edge(align, x, sample, family, weight, size, figures=None):
    """An outlined sample's anchor moved from its ink to its glyphs' edge
    (where the page aligns text): the side bearing of the glyph at that end."""
    from app.generation.marketing.compose import FONT_FILES, runs

    slot = {"family": family, "weight": weight, "size": 1, "digits": figures}
    parts = [r for r in runs(sample, slot) if r[0].strip()]

    def bearings(part, name):
        font = ImageFont.truetype(str(ASSETS / FONT_FILES[name]), 1000)
        box = drawn(part.strip(), font)
        advance = font.getlength(part.strip(), direction="rtl")
        return box[0] / 1000, (advance - box[2]) / 1000

    # Right to left: the first run stands at the right, the last at the left.
    right = bearings(parts[0][0], parts[0][1])[1]
    left = bearings(parts[-1][0], parts[-1][1])[0]
    if align == "right":
        return x + right * size
    if align == "left":
        return x - left * size
    return x + (right - left) / 2 * size


def run_ink(sample, family, weight):
    """Top and bottom of a sample's ink at 1 pt (y down from the baseline),
    each run in its font: figures in Lama, as the page sets them."""
    from app.generation.marketing.compose import FONT_FILES, runs

    slot = {"family": family, "weight": weight, "size": 1}
    tops, bottoms = [], []
    for part, name, _, _ in runs(sample, slot):
        if not part.strip():
            continue
        font = ImageFont.truetype(str(ASSETS / FONT_FILES[name]), 1000)
        box = font.getbbox(part.strip(), anchor="ls", direction="rtl")
        tops.append(box[1] / 1000)
        bottoms.append(box[3] / 1000)
    return min(tops), max(bottoms)


def tracking(span):
    """The span's tracking, in em between characters: its width in the guide
    against the font's own (Lama only: spacing breaks Ruaq's joins)."""
    family, weight = font_of(span)
    if family != "l":
        return 0
    text = unicodedata.normalize("NFKC", span["text"]).strip()
    font = ImageFont.truetype(str(FONTS[(family, weight)]), 1000)
    natural = font.getlength(text) / 1000 * span["size"]
    chars = [c for c in span["chars"] if c["c"].strip()]
    wide = max(c["bbox"][2] for c in chars) - min(c["bbox"][0] for c in chars)
    em = (wide - natural) / max(1, len(text) - 1) / span["size"]
    return round(em, 4) if abs(em) > 0.002 else 0


def drawn(text, font):
    """Ink box of text at 1000 px, relative to its baseline start (x0, top,
    x1, bottom; y down), from the drawn glyphs: Pillow's own box runs from
    advance to advance across."""
    from PIL import Image, ImageDraw

    width = int(font.getlength(text, direction="rtl")) + 2000
    canvas = Image.new("L", (width, 3000), 0)
    ImageDraw.Draw(canvas).text(
        (1000, 2000), text, font=font, fill=255, anchor="ls", direction="rtl"
    )
    x0, y0, x1, y1 = canvas.getbbox()
    return x0 - 1000, y0 - 2000, x1 - 1000, y1 - 2000


def ink(text, family, weight):
    """Ink box of text at 1 pt, relative to its baseline start (x0, top,
    x1, bottom; y down)."""
    font = ImageFont.truetype(str(FONTS[(family, weight)]), 1000)
    return tuple(v / 1000 for v in drawn(text, font))


def spans_of(page):
    found = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = "".join(c["c"] for c in span["chars"])
                if text.strip():
                    found.append({**span, "text": text, "norm": norm(text)})
    return found


def match(spans, board, sample, at):
    key = norm(sample)
    candidates = [
        s
        for s in spans
        if board.intersects(pymupdf.Rect(s["bbox"]))
        and (s["norm"] == key or (len(key) >= 3 and key in s["norm"]))
    ]
    if not candidates:
        raise SystemExit(f"sample not found: {sample!r}")
    exact = [s for s in candidates if s["norm"] == key]
    candidates = exact or candidates
    if at:
        candidates.sort(
            key=lambda s: (
                abs((s["bbox"][0] + s["bbox"][2]) / 2 - at[0])
                + abs(s["origin"][1] - at[1])
            )
        )
    elif len(candidates) > 1:
        raise SystemExit(f"sample {sample!r} is not unique: give at")
    return candidates[0]


def anchor(align, x0, x1):
    return {"right": x1, "left": x0, "center": (x0 + x1) / 2}[align]


def line_width(page, spans, region):
    """Width of a sample line drawn partly as outlines, partly as text."""
    area, region = None, pymupdf.Rect(region)
    for drawing in page.get_drawings():
        if region.contains(drawing["rect"]):
            area = drawing["rect"] if area is None else area | drawing["rect"]
    for span in spans:
        b = pymupdf.Rect(span["bbox"])
        if (b & region).get_area() > b.get_area() * 0.5:
            area = b if area is None else area | b
    return area.width


def ink_box(page, region, colour=None):
    """Union of the drawings inside region (of one fill colour if given)."""
    area = None
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if not pymupdf.Rect(region).contains(r):
            continue
        fill = drawing.get("fill")
        if colour and (
            not fill
            or max(
                abs(round(c * 255) - int(colour[i : i + 2], 16))
                for c, i in zip(fill, (1, 3, 5))
            )
            > 3
        ):
            continue
        area = r if area is None else area | r
    if area is None:
        raise SystemExit(f"no drawings in {region}")
    return area


def svg_path(items, ox, oy):
    d, at = [], None
    for item in items:
        kind, *points = item
        if kind == "re":
            r = points[0]
            d.append(
                f"M{r.x0 - ox:.2f} {r.y0 - oy:.2f}H{r.x1 - ox:.2f}"
                f"V{r.y1 - oy:.2f}H{r.x0 - ox:.2f}Z"
            )
            at = None
            continue
        start = points[0]
        if at is None or abs(at.x - start.x) > 0.01 or abs(at.y - start.y) > 0.01:
            d.append(f"M{start.x - ox:.2f} {start.y - oy:.2f}")
        if kind == "l":
            d.append(f"L{points[1].x - ox:.2f} {points[1].y - oy:.2f}")
        elif kind == "c":
            d.append(
                "C" + " ".join(f"{p.x - ox:.2f} {p.y - oy:.2f}" for p in points[1:4])
            )
        at = points[-1]
    return "".join(d) + "Z"


def near(r, target, tolerance=0.6):
    return all(abs(a - b) <= tolerance for a, b in zip(r, target))


def extract(name, spec, guide):
    doc = pymupdf.open(guide)
    page = doc[spec["page"] - 1]
    board = pymupdf.Rect(spec["board"])
    inset = spec.get("stroke", 0) / 2 + (0.05 if spec.get("stroke") else 0)
    cut = pymupdf.Rect(
        board.x0 + inset, board.y0 + inset, board.x1 - inset, board.y1 - inset
    )
    ox, oy = cut.x0, cut.y0
    spans = spans_of(page)
    text_cuts, art_cuts, slots = [], [], []

    def rel(r):
        return [
            round(r[0] - ox, 3),
            round(r[1] - oy, 3),
            round(r[2] - ox, 3),
            round(r[3] - oy, 3),
        ]

    for slot in spec["slots"]:
        kind, key = slot["kind"], slot["key"]
        if kind == "text":
            found = [
                match(spans, board, sample, slot["at"]) for sample in slot["spans"]
            ]
            for span in found:
                # Only its own glyphs: the line's middle, clear of a line above.
                b, base, size = (
                    pymupdf.Rect(span["bbox"]),
                    span["origin"][1],
                    span["size"],
                )
                text_cuts.append(
                    pymupdf.Rect(
                        b.x0 + 0.1, base - size * 0.45, b.x1 - 0.1, base - size * 0.05
                    )
                )
            ruaq = [s for s in found if font_of(s)[0] == "r"]
            lama = [s for s in found if font_of(s)[0] == "l"]
            primary = (ruaq or lama)[0]
            fam, weight = font_of(primary)
            # The glyphs' extent (a span may carry a space at either end).
            glyphs = [c["bbox"] for s in found for c in s["chars"] if c["c"].strip()]
            x0 = min(b[0] for b in glyphs)
            x1 = max(b[2] for b in glyphs)
            lines = sorted({round(s["origin"][1], 2) for s in found})
            if slot["lines"] == 1:
                lines = [round(primary["origin"][1], 2)]
            out = {
                "key": key,
                "kind": "text",
                "align": slot["align"],
                "x": round(anchor(slot["align"], x0, x1) - ox, 3),
                "bases": [round(b - oy, 3) for b in lines],
                "family": fam,
                "weight": weight,
                "size": round(primary["size"], 3),
                "color": hex_colour(primary["color"]),
                # Never narrower than the guide's own sample.
                "maxw": round(
                    max(slot["maxw"] or (x1 - x0) * 1.5, (x1 - x0) * 1.05), 2
                ),
                "sample": " ".join(
                    # Right to left along each line; the PDF keeps
                    # parentheses as drawn (mirrored).
                    unicodedata.normalize("NFKC", s["text"])
                    .strip()
                    .translate(str.maketrans("()", ")("))
                    for s in sorted(
                        found, key=lambda s: (int(s["origin"][1] / 3), -s["bbox"][2])
                    )
                ),
            }
            out["font"] = primary["font"].split("+")[-1]
            if not lama and any(c.isdigit() for s in found for c in s["text"]):
                out["digits"] = "r"  # the guide's figures here are Ruaq's
            if tracking(primary):
                out["tracking"] = tracking(primary)
            if lama:
                out["lama_size"] = round(lama[0]["size"], 3)
                out["lama_weight"] = font_of(lama[0])[1]
                out["lama_font"] = lama[0]["font"].split("+")[-1]
                if tracking(lama[0]):
                    out["lama_tracking"] = tracking(lama[0])
            out["measured"] = x1 - x0
            if key == "license":
                # The guide's sample is spaced by hand: the number keeps its width.
                digits = norm(primary["text"])
                face = ImageFont.truetype(str(FONTS[(fam, weight)]), 1000)
                width = face.getlength(digits) / 1000 * primary["size"]
                out["spacing"] = round((x1 - x0 - width) / max(1, len(digits) - 1), 3)
            slots.append(out)
        elif kind in ("line", "phone"):
            erase = slot["erase"]
            if erase:
                art_cuts.append(pymupdf.Rect(erase))
            if kind == "phone":
                box = ink_box(page, erase, "#121a44")
                sample = slot["sample"]
                k = ink(sample, "r", 500)
                size = box.height / (k[3] - k[1])
                spacing = (box.width - (k[2] - k[0]) * size) / (len(sample) - 1)
                slots.append(
                    {
                        "key": key,
                        "kind": "text",
                        "align": slot["align"],
                        "x": round(
                            edge(
                                slot["align"],
                                anchor(slot["align"], box.x0, box.x1),
                                sample,
                                "r",
                                500,
                                size,
                                "r",
                            )
                            - ox,
                            3,
                        ),
                        "bases": [round(box.y1 - k[3] * size - oy, 3)],
                        "family": "r",
                        "weight": 500,
                        "size": round(size, 3),
                        "color": "#121a45",
                        "spacing": round(spacing, 3),
                        "lama_size": round(size, 3),
                        "digits": "r",
                        "maxw": round(max(slot["maxw"], box.width * 1.05), 2),
                    }
                )
                continue
            if "fit" in slot:
                x0, x1, sample, fam, weight, *flags = slot["fit"]
                box = ink_box(page, erase)
                k = ink(sample.replace(" ", "") if flags else sample, fam, weight)
                if flags:  # spaced digits
                    top, bottom = k[1], k[3]
                    size = box.height / (bottom - top)
                    spacing = (box.width - (k[2] - k[0]) * size) / (len(sample) - 1)
                else:
                    # The height decides (the guide widens its spaces): the
                    # ink of each run in its own font, figures in Lama.
                    top, bottom = run_ink(sample, fam, weight)
                    size = box.height / (bottom - top)
                    spacing = 0
                base = box.y1 - bottom * size
                out = {
                    "key": key,
                    "kind": "text",
                    "align": slot["align"],
                    "x": round(
                        edge(
                            slot["align"],
                            slot["x"],
                            sample.replace(" ", "") if flags else sample,
                            fam,
                            weight,
                            size,
                            "r" if flags else None,
                        )
                        - ox,
                        3,
                    ),
                    "bases": [round(base - oy, 3)],
                    "family": fam,
                    "weight": weight,
                    "size": round(size, 3),
                    "color": slot["color"],
                    "maxw": slot["maxw"],
                }
                if spacing:
                    out["spacing"] = round(spacing, 3)
                    out["digits"] = "r"
                else:
                    out["sample"], out["measured"] = sample, box.width
                    out["maxw"] = round(max(slot["maxw"], box.width * 1.05), 2)
                    if " " not in sample and fam == "l":
                        # Figures alone: the guide's tracking, from its width.
                        k = ink(sample, fam, weight)
                        extra = box.width - (k[2] - k[0]) * size
                        out["tracking"] = round(extra / (len(sample) - 1) / size, 4)
                slots.append(out)
                continue
            slots.append(
                {
                    "key": key,
                    "kind": "text",
                    "align": slot["align"],
                    "x": round(
                        (
                            edge(
                                slot["align"],
                                slot["x"],
                                slot["sample"],
                                "r",
                                slot["weight"],
                                slot["size"],
                            )
                            if slot.get("sample")
                            else slot["x"]
                        )
                        - ox,
                        3,
                    ),
                    "bases": [round(slot["base"] - oy, 3)],
                    "family": "r",
                    "weight": slot["weight"],
                    "size": slot["size"],
                    "color": slot["color"],
                    "maxw": round(
                        max(slot["maxw"], line_width(page, spans, erase) * 1.05)
                        if slot.get("sample") and erase
                        else slot["maxw"],
                        2,
                    ),
                    **(
                        {
                            "sample": slot["sample"],
                            "measured": line_width(page, spans, erase),
                        }
                        if slot.get("sample")
                        else {}
                    ),
                }
            )
        elif kind in ("qr", "image", "icon"):
            if slot["erase"] and kind != "icon":
                art_cuts.append(pymupdf.Rect(slot["erase"]))
            slots.append({"key": key, "kind": kind, "box": rel(slot["box"])})
        elif kind == "erase":
            art_cuts.append(pymupdf.Rect(slot["erase"]))
        elif kind == "photo":
            clip = None
            for drawing in page.get_drawings(extended=True):
                if drawing["type"] == "clip" and near(drawing["scissor"], slot["clip"]):
                    clip = drawing
                    break
            if clip is None:
                raise SystemExit(f"{name}: photo clip not found")
            frame = pymupdf.Rect(slot["clip"])
            # The photograph (an image of its own) is emptied in place.
            for info in page.get_image_info(xrefs=True):
                r = pymupdf.Rect(info["bbox"])
                if (
                    info["xref"]
                    and r.intersects(frame)
                    and r.get_area() > frame.get_area() * 0.6
                ):
                    blank = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1, 1), 1)
                    blank.clear_with(0)
                    page.replace_image(info["xref"], pixmap=blank)
                    # Its mask, written plainly: a 1-bit fax mask reads opaque.
                    mask = doc.xref_get_key(info["xref"], "SMask")[1].split()[0]
                    doc.update_object(
                        int(mask),
                        "<< /Type /XObject /Subtype /Image /Width 1 /Height 1"
                        " /BitsPerComponent 8 /ColorSpace /DeviceGray >>",
                    )
                    doc.update_stream(int(mask), b"\x00")
            slots.append(
                {
                    "key": key,
                    "kind": "photo",
                    "box": rel(frame),
                    "path": svg_path(clip["items"], ox, oy),
                }
            )
        elif kind == "accent":
            target = pymupdf.Rect(slot["rect"])
            found = [
                d
                for d in page.get_drawings()
                if d.get("fill") and near(d["rect"], target, 0.8)
            ]
            if not found:
                raise SystemExit(f"{name}: accent not found")
            accent = found[0]
            art_cuts.append(
                pymupdf.Rect(
                    target.x0 - 0.5, target.y0 - 0.5, target.x1 + 0.5, target.y1 + 0.5
                )
            )
            slots.append(
                {
                    "key": key,
                    "kind": "accent",
                    "box": rel(accent["rect"]),
                    "path": svg_path(accent["items"], ox, oy),
                    "color": hex_colour(accent["fill"]),
                }
            )
    # The guide widens the spaces of some lines (its word spacing): measured
    # as the guide's width against the font's own, spread over the spaces.
    from app.generation.marketing.compose import width

    for s in slots:
        measured = s.pop("measured", None)
        sample = s.get("sample") or ""
        if (
            measured
            and " " in sample
            and len(s["bases"]) == 1
            and s["key"] not in ("supervision", "license", "phone")
        ):
            extra = (measured - width(sample, s) / 1.03) / sample.count(" ") / s["size"]
            if abs(extra) > 0.01:
                s["word_spacing"] = round(extra, 4)
    # The accent follows the headline: its place relative to the headline's
    # right edge and baseline.
    head = next((s for s in slots if s["key"] == "headline"), None)
    for s in slots:
        if s["kind"] == "accent" and head:
            s["dx"] = round(s["box"][0] - head["x"], 3)
            s["dy"] = round(s["box"][1] - head["bases"][0], 3)
    # The text inside an erased region goes with it, the text around it
    # (a label over a box) stays.
    for span in spans:
        b = pymupdf.Rect(span["bbox"])
        if any((b & r).get_area() > b.get_area() * 0.5 for r in art_cuts):
            base, size = span["origin"][1], span["size"]
            text_cuts.append(
                pymupdf.Rect(
                    b.x0 + 0.1, base - size * 0.45, b.x1 - 0.1, base - size * 0.05
                )
            )
    for r in text_cuts:
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    # A stroked outline counts as covered only with room for its mitre: the
    # guide's outlined samples (white fill, grey stroke) otherwise keep their
    # strokes.
    stroked = [d["rect"] for d in page.get_drawings() if "s" in d["type"]]
    for r in art_cuts:
        pad = 3 if any(d in r for d in stroked) else 0
        page.add_redact_annot(
            pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad), fill=False
        )
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
        text=pymupdf.PDF_REDACT_TEXT_NONE,
    )
    left = [
        d["rect"] for d in page.get_drawings() if any(d["rect"] in r for r in art_cuts)
    ]
    if left:
        raise SystemExit(f"{name}: {len(left)} sample shapes left, e.g. {left[0]}")
    # Everything around the design goes (the other designs on the page).
    full, gap = page.rect, 3
    around = [
        pymupdf.Rect(full.x0, full.y0, full.x1, board.y0 - gap),
        pymupdf.Rect(full.x0, board.y1 + gap, full.x1, full.y1),
        pymupdf.Rect(full.x0, board.y0 - gap, board.x0 - gap, board.y1 + gap),
        pymupdf.Rect(board.x1 + gap, board.y0 - gap, full.x1, board.y1 + gap),
    ]
    for r in around:
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    single = pymupdf.open()
    single.insert_pdf(doc, from_page=spec["page"] - 1, to_page=spec["page"] - 1)
    single[0].set_cropbox(cut)
    data = single.tobytes(garbage=4, deflate=True, clean=True)
    (OUT / f"{name}.pdf").write_bytes(data)
    check = pymupdf.open("pdf", data)[0]
    width = 2400 if name.startswith("board") else 1080
    zoom = width / cut.width
    check.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(
        OUT / f"{name}.png"
    )
    free_room(OUT / f"{name}.png", slots, zoom)
    return {"size": [round(cut.width, 3), round(cut.height, 3)], "slots": slots}


def free_room(png, slots, zoom):
    """A value's room: the empty space the design leaves from its edge to the
    next drawing or value (at least the guide's own sample)."""
    import numpy as np
    from PIL import Image

    from app.generation.marketing.compose import width

    art = np.asarray(Image.open(png).convert("L")).astype(int)
    texts = [s for s in slots if s["kind"] == "text"]

    def extent(s):
        w = width(s.get("sample") or "", s) if s.get("sample") else s["maxw"]
        x0 = {"right": s["x"] - w, "left": s["x"], "center": s["x"] - w / 2}
        return x0[s["align"]], x0[s["align"]] + w

    for s in texts:
        # Values in the guide's boxes keep the box (its border is faint).
        if s["align"] == "center" or s.get("spacing") or not s.get("sample"):
            continue
        rows = sorted(
            {
                y
                for base in s["bases"]
                for y in range(
                    int((base - s["size"] * 0.75) * zoom),
                    int((base + s["size"] * 0.25) * zoom),
                )
                if 0 <= y < art.shape[0]
            }
        )
        # Other values on these lines stop it as a drawing does.
        stops = [
            extent(o)
            for o in texts
            if o is not s
            and any(
                abs(a - b) < max(o["size"], s["size"])
                for a in o["bases"]
                for b in s["bases"]
            )
        ]
        # So do the photograph, the logo, the QR code and the icon.
        top, bottom = rows[0] / zoom, rows[-1] / zoom
        stops += [
            (o["box"][0], o["box"][2])
            for o in slots
            if "box" in o and o["box"][1] < bottom and o["box"][3] > top
        ]
        step = -1 if s["align"] == "right" else 1
        start = int(s["x"] * zoom) + step * 2
        x = start
        while 0 < x < art.shape[1] - 1:
            here = x / zoom
            if any(a <= here <= b for a, b in stops):
                break
            if np.abs(art[rows, x] - art[rows, x - step]).max() > 40:
                break
            x += step
        room = abs(x - start) / zoom - 2
        s["maxw"] = round(max(s["maxw"], room), 2)


def main():
    guide = Path(sys.argv[1])
    OUT.mkdir(exist_ok=True)
    layout = {name: extract(name, spec, guide) for name, spec in TEMPLATES.items()}
    (OUT / "layout.json").write_text(
        json.dumps(layout, ensure_ascii=False, indent=1) + "\n"
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "source": {
                    "دليل-التسويق-والهوية-البصرية-للمزادات-V2.pdf": hashlib.sha256(
                        guide.read_bytes()
                    ).hexdigest()
                },
                "files": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(OUT.iterdir())
                    if p.name != "manifest.json"
                },
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    print(len(layout), "designs written")


if __name__ == "__main__":
    main()
