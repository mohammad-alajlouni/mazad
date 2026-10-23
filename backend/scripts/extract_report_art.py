"""Take the Real Estate General Authority's two report templates apart.

    python scripts/extract_report_art.py CLOSING.pdf REPORT.pdf

CLOSING.pdf is «نموذج إقفال المزاد العقاري» (the blank form) and REPORT.pdf an
outputs report made on the authority's template («تقرير مخرجات»). Writes, in
templates/infath/assets/reports (see app/generation/reports/spec.py):

- closing.pdf / closing.png: the form's page as it is, placed under the values;
- report.pdf: the report's pages (one per kind), without the auction's own
  content; report-<kind>.png for the live preview;
- frames.pdf / frame-<n>.png: the phone and tablet frames the screenshots
  stand in, placed only where a screenshot is;
- layout.json: every value's place, font, size and colour, and the tables'
  grids, measured from the templates; manifest.json: the files' hashes.
"""

import hashlib
import json
import sys
from itertools import pairwise
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from extract_marketing_art import font_of, hex_colour, norm, spans_of

from app.generation.reports.spec import CLOSING, FOOTER, LOGO, PAGES

OUT = ROOT / "app/templates/infath/assets/reports"


def find(spans, sample, region=None):
    """The span holding sample (exactly, else containing it); words in either
    order (the PDF keeps some lines' words reversed)."""
    keys = {norm(sample), norm(" ".join(reversed(sample.split())))}
    found = [
        s
        for s in spans
        if (region is None or pymupdf.Rect(region).intersects(s["bbox"]))
        and any(s["norm"] == k or (len(k) >= 3 and k in s["norm"]) for k in keys)
    ]
    if not found:
        raise SystemExit(f"sample not found: {sample!r}")
    exact = [s for s in found if s["norm"] in keys]
    return (exact or found)[0]


def glyphs(span):
    chars = [c for c in span["chars"] if c["c"].strip()]
    return min(c["bbox"][0] for c in chars), max(c["bbox"][2] for c in chars)


def style(span):
    family, weight = font_of(span)
    return {
        "font": span["font"].split("+")[-1],
        "family": family,
        "weight": weight,
        "size": round(span["size"], 3),
        "color": hex_colour(span["color"]),
    }


def baseline_cut(span):
    """The span's own glyphs: its line's middle, clear of the lines around."""
    b, base, size = pymupdf.Rect(span["bbox"]), span["origin"][1], span["size"]
    return pymupdf.Rect(b.x0 + 0.1, base - size * 0.6, b.x1 - 0.1, base + size * 0.1)


def blank(doc, xref):
    """An image emptied in place: a transparent pixel (its mask written
    plainly: a 1-bit fax mask reads opaque)."""
    pixel = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1, 1), 1)
    pixel.clear_with(0)
    page = next(p for p in doc if any(i[0] == xref for i in p.get_images()))
    page.replace_image(xref, pixmap=pixel)
    mask = doc.xref_get_key(xref, "SMask")
    if mask[0] == "xref":
        number = int(mask[1].split()[0])
        doc.update_object(
            number,
            "<< /Type /XObject /Subtype /Image /Width 1 /Height 1"
            " /BitsPerComponent 8 /ColorSpace /DeviceGray >>",
        )
        doc.update_stream(number, b"\x00")


def photos(page, region):
    """The photographs inside region (images of their own), in reading order,
    each with the box it shows in (the template crops them)."""
    area = pymupdf.Rect(region)
    shown = {
        b["number"]: b["bbox"]
        for b in page.get_text("dict")["blocks"]
        if b["type"] == 1
    }
    found = []
    for info in page.get_image_info(xrefs=True):
        box = pymupdf.Rect(shown.get(info["number"], info["bbox"])) & pymupdf.Rect(
            info["bbox"]
        )
        if info["xref"] and box in area and box.width > 20:
            found.append({**info, "bbox": tuple(box)})
    # Right to left along each row, rows top to bottom.
    found.sort(key=lambda i: (round(i["bbox"][1] / 40), -i["bbox"][2]))
    return found


def grid(page, region):
    """The table's lines: column edges, row edges, stroke."""
    area = pymupdf.Rect(region)
    table = next(
        d
        for d in page.get_drawings()
        if d["type"] == "s" and d["rect"] in area and d["rect"].width > 300
    )
    xs = sorted(
        {
            round(a.x, 2)
            for k, a, b, *_ in table["items"]
            if k == "l" and abs(a.x - b.x) < 0.2
        }
    )
    ys = sorted(
        {
            round(a.y, 2)
            for k, a, b, *_ in table["items"]
            if k == "l" and abs(a.y - b.y) < 0.2
        }
    )
    return table, xs, ys


def logo_box(page):
    area = pymupdf.Rect(LOGO)
    box = None
    for d in page.get_drawings():
        if d["rect"] in area and d.get("fill") == (1.0, 1.0, 1.0):
            box = d["rect"] if box is None else box | d["rect"]
    return [round(v, 2) for v in box] if box else None


def report_page(source, kind, spec, number):
    """One report page without its variable content, and its slots."""
    doc = pymupdf.open(source)
    page = doc[spec["page"] - 1]
    spans = spans_of(page)
    text_cuts, art_cuts, region_cuts, slots, stamps = [], [], [], [], []
    logo = logo_box(page)
    if logo:
        art_cuts.append(pymupdf.Rect(LOGO))
        slots.append({"key": "agent_logo", "kind": "logo", "box": logo})
    if spec.get("footer", True):
        span = find(spans, FOOTER["sample"], [1100, 650, 1300, 740])
        x0, x1 = glyphs(span)
        text_cuts.append(baseline_cut(span))
        slots.append(
            {
                "key": "footer_name",
                "kind": "text",
                "align": "right",
                "x": round(x1, 2),
                "base": round(span["origin"][1], 2),
                **style(span),
            }
        )
    for slot in spec["slots"]:
        kind_ = slot["kind"]
        if kind_ == "text":
            span = find(spans, slot["sample"])
            x0, x1 = glyphs(span)
            out = {
                "key": slot["key"],
                "kind": "text",
                "align": slot["align"],
                "x": round(
                    {"right": x1, "left": x0, "center": (x0 + x1) / 2}[slot["align"]], 2
                ),
                "base": round(span["origin"][1], 2),
                "width": round(x1 - x0, 2),
                **style(span),
            }
            if slot["align"] == "left":
                # The contact pills: everything on the sample's line, in its pill.
                line = [
                    s
                    for s in spans
                    if abs(s["origin"][1] - span["origin"][1]) < 1
                    and x0 - 2 <= s["bbox"][0] < x0 + 220
                ]
                for s in line:
                    text_cuts.append(baseline_cut(s))
                latin = next(
                    (s for s in line if s["font"].endswith("NotoSans-Regular")), None
                )
                if latin:
                    out["latin_font"] = "NotoSans-Regular"
            else:
                text_cuts.append(baseline_cut(span))
            slots.append(out)
        elif kind_ == "para":
            found = [find(spans, s) for s in slot["samples"]]
            for s in found:
                text_cuts.append(baseline_cut(s))
            edges = [glyphs(s) for s in found]
            slots.append(
                {
                    "key": slot["key"],
                    "kind": "para",
                    "x0": round(min(e[0] for e in edges), 2),
                    "x1": round(max(e[1] for e in edges), 2),
                    "base": round(min(s["origin"][1] for s in found), 2),
                    "pitch": slot["pitch"],
                    **style(found[0]),
                }
            )
        elif kind_ == "table":
            table, xs, ys = grid(page, slot["region"])
            sample = find(spans, slot["sample"], slot["body"])
            region_cuts.append(pymupdf.Rect(slot["body"]))
            out = {
                "key": slot["key"],
                "kind": "table",
                "columns": xs,
                "rows": ys,
                "stroke": hex_colour(table["color"]),
                "stroke_width": round(table["width"], 3),
                "merged": slot["merged"],
                "keep": bool(slot.get("keep")),
                # Each row's text stands this far below the row's top.
                "base_offset": round(
                    sample["origin"][1]
                    - max(y for y in ys if y <= sample["origin"][1]),
                    2,
                ),
                **style(sample),
            }
            if not slot.get("keep"):
                art_cuts.append(pymupdf.Rect(table["rect"]) + (-1, -1, 1, 1))
            slots.append(out)
        elif kind_ == "images":
            found = photos(page, slot["region"])
            for info in found:
                blank(doc, info["xref"])
            slots.append(
                {
                    "key": slot["key"],
                    "kind": "images",
                    "boxes": [[round(v, 2) for v in i["bbox"]] for i in found],
                }
            )
        elif kind_ == "frames":
            screens = []
            for frame in slot["frames"]:
                inside = photos(page, frame)
                for info in inside:
                    blank(doc, info["xref"])
                screens.append([round(v, 2) for v in inside[0]["bbox"]])
                stamps.append(frame)
                art_cuts.append(pymupdf.Rect(frame) + (-0.5, -0.5, 0.5, 0.5))
            slots.append(
                {
                    "key": slot["key"],
                    "kind": "frames",
                    "frames": [list(f) for f in slot["frames"]],
                    "screens": screens,
                }
            )
    # The frames as stamps of their own, before they leave the page.
    frames = []
    for n, frame in enumerate(stamps):
        copy = pymupdf.open()
        copy.insert_pdf(doc, from_page=spec["page"] - 1, to_page=spec["page"] - 1)
        p = copy[0]
        r, full = pymupdf.Rect(frame), p.rect
        # Clear of the frame by a point, so its own edges stay.
        g = pymupdf.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1)
        for cut in (
            pymupdf.Rect(full.x0, full.y0, full.x1, g.y0),
            pymupdf.Rect(full.x0, g.y1, full.x1, full.y1),
            pymupdf.Rect(full.x0, g.y0, g.x0, g.y1),
            pymupdf.Rect(g.x1, g.y0, full.x1, g.y1),
        ):
            p.add_redact_annot(cut, fill=False)
        p.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
        # The page's flat navy (drawn across it) stays under the frame: the
        # same colour as the page it is placed on, where nothing else is.
        p.set_cropbox(r)
        frames.append((f"{kind}-{n + 1}", copy))
    for r in text_cuts + region_cuts:
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    for r in art_cuts:
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
        text=pymupdf.PDF_REDACT_TEXT_NONE,
    )
    single = pymupdf.open()
    single.insert_pdf(doc, from_page=spec["page"] - 1, to_page=spec["page"] - 1)
    return (
        single,
        {
            "page": number,
            "size": [round(page.rect.width, 3), round(page.rect.height, 3)],
            "slots": slots,
        },
        frames,
    )


def closing(source):
    doc = pymupdf.open(source)
    page = doc[0]
    xs, ys = set(), set()
    for d in page.get_drawings():
        if d["type"] != "s" or not d.get("width") or d["width"] < 0.5:
            continue
        for k, a, b, *_ in d["items"]:
            if k == "l" and abs(a.x - b.x) < 0.3 and abs(a.y - b.y) > 5:
                xs.add(round(a.x, 2))
            if k == "l" and abs(a.y - b.y) < 0.3 and abs(a.x - b.x) > 5:
                ys.add(round(a.y, 2))
    xs, ys = sorted(xs), sorted(ys)
    # The row text: the authority's own table text, set on a row's middle.
    header = next(s for s in spans_of(page) if norm(s["text"]) == norm("حالة الترسية"))
    data = {
        "size": [round(page.rect.width, 3), round(page.rect.height, 3)],
        # Right to left: #, deed, type, usage, status, reason, winner, value.
        "columns": list(zip(xs[1:], xs[:-1], strict=True))[::-1],
        "header": [ys[0], ys[1]],
        "rows": list(pairwise(ys[1:])),
        "names": CLOSING["columns"],
        **{k: CLOSING[k] for k in ("date", "approval", "signature", "stamp")},
        "header_color": hex_colour(header["color"]),
    }
    data["columns"] = [[round(a, 2), round(b, 2)] for b, a in data["columns"]]
    single = pymupdf.open()
    single.insert_pdf(doc, from_page=0, to_page=0)
    return single, data


def main():
    closing_source, report_source = Path(sys.argv[1]), Path(sys.argv[2])
    OUT.mkdir(exist_ok=True)
    form, closing_layout = closing(closing_source)
    (OUT / "closing.pdf").write_bytes(form.tobytes(garbage=4, deflate=True, clean=True))
    form[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
        OUT / "closing.png"
    )
    pages, report_layout, frame_docs = pymupdf.open(), {}, []
    for n, (kind, spec) in enumerate(PAGES.items()):
        single, layout, frames = report_page(report_source, kind, spec, n)
        pages.insert_pdf(single)
        report_layout[kind] = layout
        frame_docs += frames
    data = pages.tobytes(garbage=4, deflate=True, clean=True)
    (OUT / "report.pdf").write_bytes(data)
    check = pymupdf.open("pdf", data)
    for n, kind in enumerate(PAGES):
        check[n].get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25), alpha=False).save(
            OUT / f"report-{kind}.png"
        )
    stamps = pymupdf.open()
    frame_layout = {}
    for n, (name, doc) in enumerate(frame_docs):
        stamps.insert_pdf(doc)
        frame_layout[name] = n
    data = stamps.tobytes(garbage=4, deflate=True, clean=True)
    (OUT / "frames.pdf").write_bytes(data)
    check = pymupdf.open("pdf", data)
    for name, n in frame_layout.items():
        check[n].get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=True).save(
            OUT / f"frame-{name}.png"
        )
    layout = {
        "closing": closing_layout,
        "report": report_layout,
        "frames": frame_layout,
    }
    (OUT / "layout.json").write_text(
        json.dumps(layout, ensure_ascii=False, indent=1) + "\n"
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "source": {
                    "نموذج-اقفال-المزاد-العقاري.pdf": hashlib.sha256(
                        closing_source.read_bytes()
                    ).hexdigest(),
                    "تقرير-مخرجات (قالب الهيئة)": hashlib.sha256(
                        report_source.read_bytes()
                    ).hexdigest(),
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
    print(len(report_layout), "report pages,", len(frame_layout), "frames written")


if __name__ == "__main__":
    main()
