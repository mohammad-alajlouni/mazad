"""Build the booklet page artwork from the supplied open reference booklet.

Every fixed shape (frames, tabs, table bands, icons, footer) is copied from the
reference PDF as vector paths, selected by drawing sequence number. Text, photos,
QR codes and the seller's logo are left out; the templates render them at the
reference coordinates. Output: app/templates/infath/assets/booklet-art/.

    python scripts/build_booklet_art.py [--source ~/Downloads]
"""

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=Path.home() / "Downloads")
args = parser.parse_args()
SOURCE = args.source / "كتيب-حضوري-الكتروني-مفتوح.pdf"
OUT = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/booklet-art"
OUT.mkdir(parents=True, exist_ok=True)
book = pymupdf.open(SOURCE)
W, H = 595.276, 841.89


def num(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def colour(c):
    r, g, b = (round(v * 255) for v in c[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def path_d(items, close=False):
    parts, cursor = [], None
    for item in items:
        kind = item[0]
        if kind == "re":
            r = item[1]
            parts.append(
                f"M{num(r.x0)} {num(r.y0)}H{num(r.x1)}V{num(r.y1)}H{num(r.x0)}Z"
            )
            cursor = None
            continue
        if kind == "qu":
            q = item[1]
            parts.append(
                "M"
                + "L".join(f"{num(p.x)} {num(p.y)}" for p in (q.ul, q.ur, q.lr, q.ll))
                + "Z"
            )
            cursor = None
            continue
        start = item[1]
        if (
            cursor is None
            or abs(cursor.x - start.x) > 0.01
            or abs(cursor.y - start.y) > 0.01
        ):
            parts.append(f"M{num(start.x)} {num(start.y)}")
        if kind == "l":
            cursor = item[2]
            parts.append(f"L{num(cursor.x)} {num(cursor.y)}")
        elif kind == "c":
            cursor = item[4]
            parts.append("C" + " ".join(f"{num(p.x)} {num(p.y)}" for p in item[2:5]))
    return "".join(parts) + ("Z" if close else "")


def element(g, evenodd=False):
    attrs = [f'd="{path_d(g["items"], g.get("closePath"))}"']
    fill, stroke = g.get("fill"), g.get("color")
    if fill is not None and g["type"] in ("f", "fs"):
        attrs.append(f'fill="{colour(fill)}"')
        if (g.get("fill_opacity") or 1) < 1:
            attrs.append(f'fill-opacity="{num(g["fill_opacity"])}"')
        if evenodd or g.get("even_odd"):
            attrs.append('fill-rule="evenodd"')
    else:
        attrs.append('fill="none"')
    if stroke is not None and g["type"] in ("s", "fs"):
        attrs.append(
            f'stroke="{colour(stroke)}" stroke-width="{num(g.get("width") or 1)}"'
        )
        if (g.get("stroke_opacity") or 1) < 1:
            attrs.append(f'stroke-opacity="{num(g["stroke_opacity"])}"')
        caps = g.get("lineCap") or (0,)
        attrs.append(
            {1: 'stroke-linecap="round"', 2: 'stroke-linecap="square"'}.get(
                max(caps), ""
            )
        )
        attrs.append(
            {1: 'stroke-linejoin="round"', 2: 'stroke-linejoin="bevel"'}.get(
                g.get("lineJoin"), ""
            )
        )
    return "<path " + " ".join(a for a in attrs if a) + "/>"


def drawings(page, seqs=(), regions=(), skip=()):
    """Drawings chosen by sequence number, or wholly inside a region (points)."""
    boxes = [pymupdf.Rect(r) for r in regions]
    for g in book[page - 1].get_drawings():
        if g["seqno"] in skip or len(g["items"]) > 200:
            continue
        if g["seqno"] in seqs or any(g["rect"] in box for box in boxes):
            yield g


def svg(body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(W)} {num(H)}" '
        f'width="{num(W)}pt" height="{num(H)}pt">{body}</svg>'
    )


manifest = {
    "source": {SOURCE.name: hashlib.sha256(SOURCE.read_bytes()).hexdigest()},
    "files": {},
}


def write(name, data):
    path = OUT / name
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()


def layer(name, parts):
    body = "".join(
        element(g, g["seqno"] in parts.get("evenodd", ()))
        for p, sel in parts["draw"]
        for g in drawings(p, **sel)
    )
    write(name + ".svg", svg(body))


def crop(name, page, box, zoom=4, redact_text=True):
    """Raster copy of gradient artwork that PDF shadings carry (no text)."""
    doc = pymupdf.open()
    doc.insert_pdf(book, from_page=page - 1, to_page=page - 1)
    if redact_text:
        doc[0].add_redact_annot(doc[0].rect, fill=False)
        doc[0].apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
    pix = doc[0].get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(box), alpha=True
    )
    write(name + ".png", pix.tobytes("png"))


def trimmed(pix):
    """PNG of a transparent render, cropped to its visible pixels."""
    from io import BytesIO

    from PIL import Image

    image = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    image = image.crop(
        image.getchannel("A").point(lambda a: 255 if a > 5 else 0).getbbox()
    )
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def cut_from_flat(pix):
    """An opaque shape rendered on a flat colour, as a transparent PNG.

    Distance from the background colour gives coverage at the anti-aliased
    edge; the edge colour is un-mixed from the background.
    """
    from io import BytesIO

    import numpy as np
    from PIL import Image

    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    rgb = rgb.astype(float)
    background = rgb[2, 2].copy()
    alpha = np.clip((np.abs(rgb - background).max(axis=2) - 6) / 48, 0, 1)[..., None]
    colour = np.where(
        alpha > 0, (rgb - (1 - alpha) * background) / np.maximum(alpha, 1e-3), 0
    ).clip(0, 255)
    image = Image.fromarray(np.dstack([colour, alpha * 255]).astype(np.uint8), "RGBA")
    image = image.crop(
        image.getchannel("A").point(lambda a: 255 if a > 5 else 0).getbbox()
    )
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


FOOTER_LOGO = (525, 775, 582, 818)  # Infath mark in the page footer
Q = {"regions": [FOOTER_LOGO]}

# Property page, landscape photograph (reference page 6) and its electronic
# variant with the "bidding closes" badge on the photograph (page 10).
layer(
    "landscape",
    {"draw": [(6, {"seqs": {57, 61, 62, 63, 122}}), (6, Q)], "evenodd": {61}},
)
layer(
    "landscape-close",
    {
        "draw": [
            (10, {"seqs": {3, 7, 8, 9, 68}, "regions": [(39, 314, 284, 357)]}),
            (10, Q),
        ],
        "evenodd": {7},
    },
)
# Portrait photograph (page 7) and its electronic variant (page 12). The frame
# is drawn beneath the photograph, everything else above it.
layer("portrait-under", {"draw": [(7, {"seqs": {129}})]})
layer("portrait", {"draw": [(7, {"seqs": {130, 131, 163, 170, 184}}), (7, Q)]})
layer("portrait-close-under", {"draw": [(12, {"seqs": {120}})]})
layer(
    "portrait-close",
    {
        "draw": [
            (12, {"seqs": {121, 122, 154, 161, 175}, "regions": [(36, 549, 281, 592)]}),
            (12, Q),
        ]
    },
)
layer("images-features", {"draw": [(14, {"seqs": {40, 42}}), (14, Q)]})
layer("information", {"draw": [(15, {"seqs": {2, 3}}), (15, Q)]})
layer("boundaries", {"draw": [(16, {"seqs": set(range(15, 23))}), (16, Q)]})
layer("plain", {"draw": [(17, Q)]})
layer("summary", {"draw": [(5, {"seqs": {64, 65, 66, 67}}), (5, Q)]})
layer("rentals", {"draw": [(18, {"seqs": {2, 3, 4, 5, 34, 62}}), (18, Q)]})
layer("agent", {"draw": [(3, {"seqs": {8, 9}})]})
layer(
    "participation",
    {"draw": [(20, {"regions": [(90, 290, 520, 620)]})]},
)
layer("contact", {"draw": [(21, {"seqs": {2, 3}})]})

crop("footer-bar", 6, (0, 822, W, H), redact_text=False)
crop("footer-bar-reverse", 21, (0, 822, W, H), redact_text=False)
crop("link-label", 6, (144, 633, 225, 648))
crop("participation-title", 20, (400, 95, 474, 202))
# The fixed rentals note is outlined artwork in the reference, not text.
crop("rentals-note", 18, (44, 696, 568, 739), redact_text=False)
for key, box in {
    "x": (471, 581, 496, 606),
    "phone": (369, 581, 393, 606),
    "web": (266, 581, 290, 606),
}.items():
    crop("agent-" + key, 3, box, redact_text=False)
for key, box in {
    "platform": (498, 348, 525, 375),
    "location": (388, 348, 412, 375),
    "calendar": (254, 348, 281, 375),
    "time": (120, 348, 147, 375),
    "phone": (265, 516, 283, 535),
    "whatsapp": (420, 514, 438, 533),
}.items():
    crop("contact-" + key, 21, box, redact_text=False)

for n, box in enumerate(
    [
        (472, 309, 490, 334),
        (354, 309, 372, 334),
        (200, 307, 218, 332),
        (388, 481, 404, 504),
        (244, 481, 261, 504),
    ],
    1,
):
    crop(f"step-{n}", 20, box)
# The terms page is fixed; keep the original vector page, placed clipped to its block.
terms = pymupdf.open()
terms.insert_pdf(book, from_page=18, to_page=18)
write("terms.pdf", terms.tobytes(garbage=3, deflate=True))

# The auction icon is fixed (guide V2, pages 3-6): gradient on white backgrounds,
# silver on dark, coloured and photographic ones. Only the auction name changes.
leaf = book[3].get_pixmap(
    matrix=pymupdf.Matrix(12, 12), clip=pymupdf.Rect(438, 204, 495, 274), alpha=True
)
write("auction-icon-gradient.png", trimmed(leaf))
guide = pymupdf.open(args.source / "دليل-التسويق-والهوية-البصرية-للمزادات-V2.pdf")
# The silver icon is opaque: cut it from a flat square by its outline (page 5).
navy = guide[4].get_pixmap(
    matrix=pymupdf.Matrix(24, 24), clip=pymupdf.Rect(478.3, 184.9, 509.3, 222.9)
)
write("auction-icon-silver.png", cut_from_flat(navy))

# Clip windows and variable-length shapes, in points.
shapes = {
    "photo_landscape": "M48.8 48.3H506.8L549 90.5V341H87.8L48.8 302Z",
    "photo_portrait": "M77 48.25H334.5V519.5L290.75 563.25H33.75V92Z",
    "images": [path_d(g["items"]) for g in drawings(17, seqs={2, 3, 4})],
    "images_features": [path_d(g["items"]) for g in drawings(14, seqs={39, 44, 45})],
    "summary_band": next(path_d(g["items"]) for g in drawings(5, seqs={107})),
    "rentals_band": next(path_d(g["items"]) for g in drawings(18, seqs={34})),
    "link_arrow": "M235 637.1L230.9 639.55L235 642Z",
    "button": next(path_d(g["items"]) for g in drawings(9, seqs={40})),
}
write("shapes.json", json.dumps(shapes, ensure_ascii=False, indent=1))
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
print(f"wrote {len(manifest['files'])} files to {OUT}")
