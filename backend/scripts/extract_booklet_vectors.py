"""Extract original reference artwork; measured coordinates are PDF points.
Run with the three user-supplied sources in --source (defaults to Downloads).
Dynamic text/photos are rendered separately; no sample auction data is retained.
"""

import argparse
import hashlib
import json
from pathlib import Path
import pymupdf
from PIL import Image
from clean_cover import clean_cover

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=Path.home() / "Downloads")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1] / "app/templates/infath/assets"
book_path = args.source / "كتيب-حضوري-الكتروني-مفتوح.pdf"
guide_path = args.source / "دليل-التسويق-والهوية-البصرية-للمزادات-V2.pdf"
book = pymupdf.open(book_path)
guide = pymupdf.open(guide_path)
manifest = {"sources": {}, "assets": {}, "page_pt": [595.276, 841.89], "version": 2}
for path in [book_path, guide_path]:
    manifest["sources"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()


def background(name, index, clips):
    canvas = Image.new("RGBA", (2382, 3368), (255, 255, 255, 0))
    for box in clips:
        pix = book[index].get_pixmap(
            matrix=pymupdf.Matrix(4, 4), clip=pymupdf.Rect(box), alpha=True
        )
        image = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        canvas.paste(image, (round(box[0] * 4), round(box[1] * 4)))
    target = name.replace(".svg", ".png")
    canvas.save(root / target)
    manifest["assets"][target] = {
        "page": index + 1,
        "clips_pt": clips,
        "dpi": 288,
        "sha256": hashlib.sha256((root / target).read_bytes()).hexdigest(),
    }


background(
    "reference-footer.svg", 5, [(520, 770, 595.276, 826), (0, 826, 595.276, 841.89)]
)
background("reference-agent.svg", 2, [(0, 670, 595.276, 841.89)])
# Original icons at 288 dpi and their measured size.
for name, box in {
    "time": (461, 404, 493, 435),
    "calendar": (461, 444, 493, 477),
    "location": (461, 485, 493, 516),
    "platform": (461, 527, 493, 560),
}.items():
    target = "reference-" + name + ".png"
    book[3].get_pixmap(
        matrix=pymupdf.Matrix(4, 4), clip=pymupdf.Rect(box), alpha=True
    ).save(root / target)
    manifest["assets"][target] = {
        "page": 4,
        "clip_pt": box,
        "dpi": 288,
        "sha256": hashlib.sha256((root / target).read_bytes()).hexdigest(),
    }
# Participation artwork keeps the source's icons, numerals and heading decoration.
for name, box in {
    "participation-title": (125, 80, 492, 214),
    "step-1": (430, 305, 495, 383),
    "step-2": (300, 305, 375, 383),
    "step-3": (145, 303, 220, 383),
    "step-4": (340, 475, 415, 550),
    "step-5": (202, 475, 272, 550),
}.items():
    target = "reference-" + name + ".png"
    book[19].get_pixmap(
        matrix=pymupdf.Matrix(4, 4), clip=pymupdf.Rect(box), alpha=True
    ).save(root / target)
    manifest["assets"][target] = {
        "page": 20,
        "clip_pt": box,
        "dpi": 288,
        "sha256": hashlib.sha256((root / target).read_bytes()).hexdigest(),
    }
# Preserve original cover transparency while removing dynamic title/footer ink.
for n in range(1, 7):
    path = args.source / f"اغلفة-الكتيف/Ai/{n}.ai"
    title = (
        (175, 350, 390, 453)
        if n in (2, 3)
        else (290, 350, 500, 453)
        if n in (4, 5)
        else (360, 730, 570, 819)
    )
    source = clean_cover(path, [title, (18, 775, 577, 823)])
    p = source[0]
    # Render the original PDF transparency groups; SVG export changes Illustrator masks.
    target = f"reference-cover-{n}.png"
    p.get_pixmap(matrix=pymupdf.Matrix(3, 3)).save(root / target)
    data = (root / target).read_bytes()
    manifest["assets"][target] = {
        "source": path.name,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "erase_pt": [title, (18, 775, 577, 823)],
        "sha256": hashlib.sha256(data).hexdigest(),
    }
(root / "reference-layout.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2)
)
# Native PDF forms preserve the source vectors/fonts and avoid SVG mask conversion.
intro = pymupdf.open()
intro.insert_pdf(book, from_page=1, to_page=1)
intro.save(root / "reference-introduction.pdf", garbage=4, deflate=True)
manifest["assets"]["reference-introduction.pdf"] = {
    "page": 2,
    "sha256": hashlib.sha256(
        (root / "reference-introduction.pdf").read_bytes()
    ).hexdigest(),
}
for kind, box in [
    ("physical", (111, 222, 251, 390)),
    ("hybrid", (331, 214, 464, 411)),
    ("electronic", (525, 234, 670, 400)),
]:
    doc = pymupdf.open()
    p = doc.new_page(width=box[2] - box[0], height=box[3] - box[1])
    p.show_pdf_page(p.rect, guide, 23, clip=pymupdf.Rect(box))
    name = f"reference-terms-{kind}.pdf"
    doc.save(root / name, garbage=4, deflate=True)
    manifest["assets"][name] = {
        "page": 24,
        "clip_pt": box,
        "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
    }
(root / "reference-layout.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2)
)
