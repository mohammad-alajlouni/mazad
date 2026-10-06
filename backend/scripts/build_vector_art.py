"""Vector copies of the booklet's fixed artwork, for the exported PDF.

Icons, tiles, the footer bar, the six covers and the Infath page keep their
original vector paths and gradients: each is re-emitted by MuPDF from its
source into a small PDF holding only what lies in its box (no sample text),
and export places that PDF where the template reserved a box. The browser
preview shows a high-resolution PNG of the same artwork.

    python scripts/build_vector_art.py [--source ~/Downloads]

Output: app/templates/infath/assets/booklet-art/vector/.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pymupdf
from pymupdf import mupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_cover import clean_cover  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=Path.home() / "Downloads")
args = parser.parse_args()
OUT = (
    Path(__file__).resolve().parents[1]
    / "app/templates/infath/assets/booklet-art/vector"
)
OUT.mkdir(parents=True, exist_ok=True)
BOOK = args.source / "كتيب-حضوري-الكتروني-مفتوح.pdf"
GUIDE = args.source / "دليل-التسويق-والهوية-البصرية-للمزادات-V2.pdf"
book, guide = pymupdf.open(BOOK), pymupdf.open(GUIDE)
W, H = 595.276, 841.89
manifest = {
    "sources": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (BOOK, GUIDE)
    },
    "files": {},
}


def flat(page, clip):
    """The part of a page inside clip as a flat one-page PDF (objects outside
    the box are not copied; nested forms are expanded). Returns its bytes."""
    clip = pymupdf.Rect(clip)
    path = OUT / "_flat.pdf"
    writer = pymupdf.DocumentWriter(str(path))
    area = pymupdf.Rect(0, 0, clip.width, clip.height)
    device = writer.begin_page(area)
    mupdf.fz_run_display_list(
        page.get_displaylist().this,
        device.this,
        pymupdf.JM_matrix_from_py(pymupdf.Matrix(1, 0, 0, 1, -clip.x0, -clip.y0)),
        pymupdf.JM_rect_from_py(area),
        mupdf.FzCookie(),
    )
    writer.end_page()
    writer.close()
    data = path.read_bytes()
    path.unlink()
    return data


def save(name, data, zoom=8, text=False, compact=True, preview=True, target=None):
    """Store the vector PDF and its preview PNG. The PDF is compacted straight
    from its bytes, once: MuPDF loses shading and pattern resources if the
    page is drawn first or collected twice."""
    if compact:
        data = pymupdf.open(stream=data, filetype="pdf").tobytes(
            garbage=3, deflate=True
        )
    (target or OUT / f"{name}.pdf").write_bytes(data)
    manifest["files"][f"{name}.pdf"] = hashlib.sha256(data).hexdigest()
    page = pymupdf.open(stream=data, filetype="pdf")[0]
    if preview:
        scale = min(zoom, 2400 / max(page.rect.width, page.rect.height))
        png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True).tobytes(
            "png"
        )
        (OUT / f"{name}.png").write_bytes(png)
        manifest["files"][f"{name}.png"] = hashlib.sha256(png).hexdigest()
    left = page.get_text().strip()
    if left and not text:
        raise SystemExit(f"{name}: sample text would be copied: {left[:40]!r}")
    print(
        f"{name:26} {page.rect.width:7.1f} x {page.rect.height:6.1f} pt"
        f"  {len(data) // 1024:5} KB"
    )


_textless = {}


def textless(document, number):
    """A copy of a source page (1-based) with every text object removed."""
    key = (id(document), number)
    if key not in _textless:
        copy = pymupdf.open()
        copy.insert_pdf(document, from_page=number - 1, to_page=number - 1)
        copy[0].add_redact_annot(copy[0].rect, fill=False)
        copy[0].apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
        _textless[key] = pymupdf.open(stream=copy.tobytes(), filetype="pdf")
    return _textless[key][0]


def emit(name, document, number, clip):
    save(name, flat(textless(document, number), clip))


def visible_box(page, clip, zoom=12):
    """Tight box of what is drawn inside clip (transparent render)."""
    clip = pymupdf.Rect(clip)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=True)
    from PIL import Image

    alpha = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples).getchannel(
        "A"
    )
    x0, y0, x1, y1 = alpha.point(lambda a: 255 if a > 5 else 0).getbbox()
    return pymupdf.Rect(
        clip.x0 + x0 / zoom,
        clip.y0 + y0 / zoom,
        clip.x0 + x1 / zoom,
        clip.y0 + y1 / zoom,
    )


# Reference booklet (1-based pages), the boxes the templates already use.
emit("footer-bar", book, 6, (0, 822, W, H))
emit("footer-bar-reverse", book, 21, (0, 822, W, H))
emit("participation-title", book, 20, (400, 95, 474, 202))
# The fixed rentals note is outlined artwork in the reference, not text.
emit("rentals-note", book, 18, (44, 696, 568, 739))
for key, box in {
    "time": (461, 404, 493, 435),
    "calendar": (461, 444, 493, 477),
    "location": (461, 485, 493, 516),
    "platform": (461, 527, 493, 560),
}.items():
    emit("auction-" + key, book, 4, box)
for key, box in {
    "platform": (498, 348, 525, 375),
    "location": (388, 348, 412, 375),
    "calendar": (254, 348, 281, 375),
    "time": (120, 348, 147, 375),
    "phone": (265, 516, 283, 535),
    "whatsapp": (420, 514, 438, 533),
}.items():
    emit("contact-" + key, book, 21, box)
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
    emit(f"step-{n}", book, 20, box)
emit(
    "auction-icon-gradient",
    book,
    4,
    visible_box(textless(book, 4), (438, 204, 495, 274)),
)

# The silver auction icon (guide p.5) is drawn on a flat colour square: copy
# its box and drop that square, the first fill in the flat stream.
import re  # noqa: E402

leaf = pymupdf.open(
    stream=flat(textless(guide, 5), (478.862, 188.445, 503.555, 219.486)),
    filetype="pdf",
)
target = leaf[0].get_contents()[0]  # the flat page draws directly in its stream
stream = leaf.xref_stream(target).decode("latin1")
square = re.search(r"[-\d. ]+ re\nf\n", stream)
if not square or square.start() > 200:
    raise SystemExit("silver icon: background square not found")
leaf.update_stream(
    target, (stream[: square.start()] + stream[square.end() :]).encode("latin1")
)
save("auction-icon-silver", leaf.tobytes(garbage=3, deflate=True), compact=False)

# Guide V2: the Infath page (p.11) and the contact tiles of the agent page
# (p.12) in the guide's own shape. Thumbnails are exact 1:2.0126 A4 pages.
frame = pymupdf.Rect(301.148, 57.937, 596.928, 476.254)
# Its text stays real text (fonts and reading order from the guide): the page
# is copied as a form, with everything outside the thumbnail removed first.
source = pymupdf.open()
source.insert_pdf(guide, from_page=10, to_page=10)
inner = frame + (0.5, 0.5, -0.5, -0.5)
for outside in (
    (0, 0, 1000, inner.y0),
    (0, inner.y1, 1000, 562.5),
    (0, 0, inner.x0, 562.5),
    (inner.x1, 0, 1000, 562.5),
):
    source[0].add_redact_annot(pymupdf.Rect(outside), fill=False)
source[0].apply_redactions(
    images=pymupdf.PDF_REDACT_IMAGE_NONE,
    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
)
intro = pymupdf.open()
intro.new_page(width=W, height=H).show_pdf_page(
    pymupdf.Rect(0, 0, W, H), source, 0, clip=inner
)
# The preview and the export both read this file (the whole Infath page).
save(
    "reference-introduction",
    intro.tobytes(),
    text=True,
    preview=False,
    target=OUT.parents[1] / "reference-introduction.pdf",
)
for key, box in {
    "web": (252.33, 358.75, 262.58, 369.05),
    "phone": (296.83, 358.75, 307.13, 369.05),
    "x": (341.28, 358.75, 351.53, 369.05),
}.items():
    emit("agent-" + key, guide, 12, pymupdf.Rect(box) + (-0.05, -0.05, 0.05, 0.05))

# The six covers from their Illustrator sources, sample title and footer removed.
for n in range(1, 7):
    title = (
        (175, 350, 390, 453)
        if n in (2, 3)
        else (290, 350, 500, 453)
        if n in (4, 5)
        else (360, 730, 570, 819)
    )
    cover = clean_cover(
        args.source / f"اغلفة-الكتيف/Ai/{n}.ai", [title, (18, 775, 577, 823)]
    )
    # Drop Illustrator's private editing data and thumbnail (most of the file)
    # and store the photograph as a high-quality JPEG; the artwork is untouched.
    slim = pymupdf.open(stream=cover.tobytes(), filetype="pdf")
    for key in ("PieceInfo", "Thumb"):
        slim.xref_set_key(slim[0].xref, key, "null")
    if n in (
        1,
        6,
    ):  # photographic covers (re-encoding breaks pattern fills in the others)
        slim.rewrite_images(dpi_threshold=1000, dpi_target=999, quality=92)
    # The browser preview keeps the existing reference-cover-N.png.
    save(
        f"cover-{n}",
        slim.tobytes(garbage=4, deflate=True),
        compact=False,
        preview=False,
    )

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
print(f"wrote {len(manifest['files'])} files to {OUT}")
