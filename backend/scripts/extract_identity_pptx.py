"""Copy the supplied DrawingML icon geometry into SVG; no redraw or recoloring.
Usage: python backend/scripts/extract_identity_pptx.py /path/to/source.pptx /path/to/decoded-fonts
"""

import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
ROOT = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/identity"
ROOT.mkdir(exist_ok=True)


def dimensions(x):
    return tuple(
        float(x.find(tag, NS).get(key))
        for tag, key in [
            ("a:off", "x"),
            ("a:off", "y"),
            ("a:ext", "cx"),
            ("a:ext", "cy"),
        ]
    )


def transform(x, group=False):
    ox, oy, w, h = dimensions(x)
    t = f"translate({ox + w / 2} {oy + h / 2}) rotate({float(x.get('rot', 0)) / 60000}) scale({-1 if x.get('flipH') == '1' else 1} {-1 if x.get('flipV') == '1' else 1}) translate({-w / 2} {-h / 2})"
    if group:
        off = x.find("a:chOff", NS)
        ext = x.find("a:chExt", NS)
        t += f" scale({w / float(ext.get('cx'))} {h / float(ext.get('cy'))}) translate({-float(off.get('x'))} {-float(off.get('y'))})"
    return t


def color(node):
    if node is None:
        return "none"
    c = node.find("a:solidFill/a:srgbClr", NS)
    return "#" + c.get("val") if c is not None else "none"


def render(shape):
    if shape.tag.endswith("grpSp"):
        x = shape.find("p:grpSpPr/a:xfrm", NS)
        return (
            '<g transform="'
            + transform(x, True)
            + '">'
            + "".join(render(c) for c in shape if c.tag.endswith(("}sp", "}grpSp")))
            + "</g>"
        )
    pr = shape.find("p:spPr", NS)
    x = pr.find("a:xfrm", NS)
    if pr.find("a:custGeom", NS) is None:
        raise ValueError("Unsupported non-native icon geometry")
    _, _, w, h = dimensions(x)
    line = pr.find("a:ln", NS)
    stroke = color(line)
    width = line.get("w", "0")
    paths = []
    for path in pr.findall("a:custGeom/a:pathLst/a:path", NS):
        d = []
        for command in path:
            name = command.tag.split("}")[-1]
            code = {"moveTo": "M", "lnTo": "L", "cubicBezTo": "C", "close": "Z"}[name]
            d.append(code + " ".join(p.get("x") + " " + p.get("y") for p in command))
        paths.append(
            f'<path transform="scale({w / float(path.get("w"))} {h / float(path.get("h"))})" d="{" ".join(d)}" fill="{color(pr) if path.get("fill") != "none" else "none"}" stroke="{stroke if path.get("stroke") != "0" else "none"}" stroke-width="{width}" stroke-linecap="butt" stroke-linejoin="miter"/>'
        )
    return '<g transform="' + transform(x) + '">' + "".join(paths) + "</g>"


source = Path(sys.argv[1])
with ZipFile(source) as archive:
    slide = ET.fromstring(archive.read("ppt/slides/slide5.xml"))
    icons = []
    for shape in slide.find("p:cSld/p:spTree", NS):
        if shape.find(".//a:custGeom", NS) is None:
            continue
        x = (
            shape.find("p:grpSpPr/a:xfrm", NS)
            if shape.tag.endswith("grpSp")
            else shape.find("p:spPr/a:xfrm", NS)
        )
        ox, oy, w, h = dimensions(x)
        id = shape.find(".//p:cNvPr", NS).get("id")
        # Constant transparent padding preserves thin strokes at the edge.
        pad = max(w, h) * 0.04
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{(w + 2 * pad) / 12700}" height="{(h + 2 * pad) / 12700}" viewBox="{ox - pad} {oy - pad} {w + 2 * pad} {h + 2 * pad}">{render(shape)}</svg>'
        name = f"icon-{id}.svg"
        (ROOT / name).write_text(svg)
        icons.append(
            {
                "id": id,
                "file": name,
                "bounds_pt": [v / 12700 for v in (ox, oy, w, h)],
                "sha256": hashlib.sha256(svg.encode()).hexdigest(),
            }
        )
    manifest = {
        "source": source.name,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "slide": 5,
        "icons": icons,
    }
    # The selected semantics are verified against the rendered source sheet.
    centers = {
        "time": (166, 206),
        "calendar": (200, 206),
        "location": (376, 151),
        "platform": (755, 299),
        "phone": (374, 330),
    }
    manifest["selected"] = {
        name: min(
            icons,
            key=lambda i: (
                (i["bounds_pt"][0] + i["bounds_pt"][2] / 2 - xy[0]) ** 2
                + (i["bounds_pt"][1] + i["bounds_pt"][3] / 2 - xy[1]) ** 2
            ),
        )["file"]
        for name, xy in centers.items()
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(len(icons), "original icons extracted", manifest["selected"])

# EMF records contain the original vector PDF, rather than a bitmap preview.
# Keep only its painted paths: the full-page clipping wrapper emitted by MuPDF
# is redundant and can leak into later SVG painting in the HTML renderer.
import pymupdf

for number, name in [(9, "navy"), (10, "teal"), (11, "white")]:
    with ZipFile(source) as archive:
        raw = archive.read(f"ppt/media/image{number}.emf")
    start = raw.index(b"%PDF")
    end = raw.index(b"%%EOF", start) + 5
    with pymupdf.open(stream=raw[start:end], filetype="pdf") as doc:
        svg = ET.fromstring(doc[0].get_svg_image())
        paths = list(
            svg.findall(
                ".//{http://www.w3.org/2000/svg}g//{http://www.w3.org/2000/svg}path"
            )
        )
        attrs = dict(svg.attrib)
        clean = ET.Element("{http://www.w3.org/2000/svg}svg", attrs)
        clean.extend(paths)
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        data = ET.tostring(clean, encoding="utf-8")
    filename = f"infath-{name}.svg"
    (ROOT / filename).write_bytes(data)
    manifest.setdefault("logos", {})[name] = {
        "file": filename,
        "source_part": f"ppt/media/image{number}.emf",
        "sha256": hashlib.sha256(data).hexdigest(),
    }

# Full embedded EOT/MTX faces decompressed by the companion Node script.
font_dir = Path(sys.argv[2])
for number, name in [
    (5, "LamaSans-Black"),
    (6, "LamaSans-Light"),
    (7, "LamaSans-Medium"),
    (8, "RuaqArabic-Medium"),
    (9, "RuaqArabic-Bold"),
    (10, "RuaqArabic-Light"),
]:
    data = (font_dir / f"font{number}.ttf").read_bytes()
    (ROOT / (name + ".ttf")).write_bytes(data)
    manifest.setdefault("fonts", {})[name] = {
        "file": name + ".ttf",
        "source_part": f"ppt/fonts/font{number}.fntdata",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
manifest["palette"] = {
    "ink": "#001447",
    "navy": "#00365D",
    "teal": "#04A6A4",
    "white": "#FFFFFF",
    "mint": "#37C2BF",
    "green": "#78CAAB",
    "pale": "#D1EDF3",
    "gray": "#D1D3D4",
}
manifest["palette_basis"] = (
    "Slide 2 actual shape fills; printed hex labels conflict with those fills."
)
(ROOT / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
)
