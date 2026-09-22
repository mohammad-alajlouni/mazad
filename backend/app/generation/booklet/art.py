"""Reference photo windows and page artwork, in PDF points."""

import base64
import json
import re
from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import quoteattr

from .assets import ASSETS

PAGE_W, PAGE_H = 595.276, 841.89


@lru_cache(maxsize=1)
def shapes():
    return json.loads((ASSETS / "booklet-art/shapes.json").read_text())


def path_box(d):
    values = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = [], []
    for command, args in re.findall(r"([MLHVCZ])([^MLHVCZ]*)", d):
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", args)]
        if command == "H":
            xs += nums
        elif command == "V":
            ys += nums
        else:
            xs += nums[0::2]
            ys += nums[1::2]
    return (min(xs), min(ys), max(xs), max(ys)) if values else (0, 0, 0, 0)


_photo_ids = iter(range(1, 10**12))


def photo(src, window, fit="cover", backdrop=None):
    """Inline SVG showing a photograph through one reference window.

    The photograph keeps its aspect ratio: "cover" fills the window and trims
    the overflow, "contain" shows it whole on the window's backdrop colour.
    Inline markup (not an image) so browsers also load linked photographs in
    the live preview; each clip path gets its own id within the document.
    """
    from markupsafe import Markup

    d = shapes().get(window, window)
    x0, y0, x1, y1 = path_box(d)
    scaling = "meet" if fit == "contain" else "slice"
    clip = f"photo-window-{next(_photo_ids)}"
    fill = f'<path d="{d}" fill="{backdrop}"/>' if backdrop and fit == "contain" else ""
    return Markup(
        f'<svg class="art" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_W} {PAGE_H}">'
        f'<defs><clipPath id="{clip}"><path d="{d}"/></clipPath></defs>'
        f'<g clip-path="url(#{clip})">{fill}'
        f'<image href={quoteattr(src)} x="{x0}" y="{y0}" width="{x1 - x0}" '
        f'height="{y1 - y0}" preserveAspectRatio="xMidYMid {scaling}"/></g></svg>'
    )


def page_shape(d, fill, stroke=None, width=0.25):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_W} {PAGE_H}" '
        f'width="{PAGE_W}pt" height="{PAGE_H}pt">'
        + "".join(
            f'<path d="{p}" fill="{fill}"/>'
            if not stroke
            else f'<path d="{p}" fill="none" stroke="{stroke}" stroke-width="{width}"/>'
            for p in ([d] if isinstance(d, str) else d)
        )
        + "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def table_lines(
    columns, top, bottom, rows, left, right, colour, column_width, row_width
):
    """Inner column rules and a rule under every row, ending at the last row."""
    paths = [
        f'<path d="M{x} {top}V{bottom}" stroke="{colour}" stroke-width="{column_width}"/>'
        for x in columns
    ] + [
        f'<path d="M{left} {y}H{right}" stroke="{colour}" stroke-width="{row_width}"/>'
        for y in rows
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_W} {PAGE_H}" '
        f'width="{PAGE_W}pt" height="{PAGE_H}pt" fill="none">{"".join(paths)}</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def shape_in(d, fill):
    """A reference shape drawn in its own box, to be placed and sized in CSS."""
    x0, y0, x1, y1 = path_box(d)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1 - x0} {y1 - y0}" '
        f'preserveAspectRatio="none" width="{x1 - x0}pt" height="{y1 - y0}pt">'
        f'<path d="{d}" fill="{fill}"/></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def summary_column(bottom):
    """The numbered side column of a table, closed at its last row (page 5)."""
    return (
        f"M559.47 293.62V{bottom - 10.11:.2f}C555.52 {bottom - 6.16:.2f} 553.31 "
        f"{bottom - 3.95:.2f} 549.36 {bottom:.2f}H521.1V303.73C525.05 299.78 527.26 "
        "297.57 531.21 293.62Z"
    )


def rentals_column(bottom):
    return (
        f"M566.91 146.15V{bottom - 10.11:.2f}C562.96 {bottom - 6.16:.2f} 560.74 "
        f"{bottom - 3.95:.2f} 556.79 {bottom:.2f}H528.47V156.25C532.42 152.31 534.64 "
        "150.1 538.59 146.15Z"
    )


@lru_cache(maxsize=32)
def prepared_logo(src, white=False):
    """A logo ready for placement: background removed, margins trimmed.

    Uploaded logos arrive in any shape: with transparency or on a flat
    background, with wide empty margins, at any resolution. A flat background
    (uniform border) becomes transparent, the artwork is trimmed to its visible
    extent and large files are reduced. With white=True the artwork becomes a
    white silhouette for dark covers. Returns (data URI, width / height).
    """
    from PIL import Image, ImageChops

    try:
        _, data = src.split(",", 1)
        image = Image.open(BytesIO(base64.b64decode(data)))
        image.load()
    except (ValueError, OSError):
        return src, 1.0
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] == 255:
        # Opaque: treat a uniform border colour as background.
        w, h = image.size
        rgb = image.convert("RGB")
        border = [
            rgb.getpixel((x, y))
            for x in range(0, w, max(1, w // 40))
            for y in (0, h - 1)
        ]
        border += [
            rgb.getpixel((x, y))
            for y in range(0, h, max(1, h // 40))
            for x in (0, w - 1)
        ]
        base = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))
        if sum(
            max(abs(c[i] - base[i]) for i in range(3)) <= 24 for c in border
        ) >= 0.9 * len(border):
            distance = ImageChops.difference(
                rgb, Image.new("RGB", rgb.size, base)
            ).convert("L")
            # Soft edge: distance 12 or less is background, 48 or more is artwork.
            cleared = distance.point(
                lambda d: 0 if d <= 12 else 255 if d >= 48 else (d - 12) * 7
            )
            # A logo that is one solid block has no background to remove.
            visible = sum(cleared.histogram()[9:]) / (w * h)
            if visible >= 0.02:
                alpha = cleared
                image.putalpha(alpha)
    # Decided before trimming, which removes the transparent margin itself.
    transparent = alpha.getextrema()[0] < 255
    box = alpha.point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        image = image.crop(box)
    if max(image.size) > 1600:
        image.thumbnail((1600, 1600))
    # A white silhouette needs real transparency; an opaque logo (a photograph,
    # or artwork on a busy background) would become a white block, so it keeps
    # its own colours.
    if white and transparent:
        silhouette = Image.new("RGBA", image.size, (255, 255, 255, 0))
        silhouette.putalpha(image.getchannel("A"))
        image = silhouette
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
    return uri, image.width / max(1, image.height)


def logo_fit(src, max_width, max_height, white=False):
    """Prepared logo and its size in points inside a reference box."""
    uri, ratio = prepared_logo(src, white)
    width = min(max_width, max_height * ratio)
    return {"src": uri, "width": round(width, 2), "height": round(width / ratio, 2)}


def white_logo(src):
    return prepared_logo(src, True)[0]


def original_pdf_artwork(pdf, content):
    """Overlay immutable original forms on their reserved pages in both preview/export."""
    import pymupdf

    if not content.get("booklet"):
        return pdf
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        for n, page in enumerate(content["booklet"]["pages"]):
            if n >= len(document):
                break  # The normal page-count preflight rejects an invalid composition.
            if page["kind"] == "introduction":
                name = "reference-introduction.pdf"
                box = document[n].rect
            elif page["kind"] == "terms":
                # Reference page 19, clipped to the terms block; footer is the template's.
                name = "booklet-art/terms.pdf"
                box = pymupdf.Rect(110, 110, 505, 692)
            else:
                continue
            with pymupdf.open(ASSETS / name) as artwork:
                clip = box if page["kind"] == "terms" else None
                document[n].show_pdf_page(box, artwork, 0, clip=clip)
        return document.tobytes(garbage=3, deflate=True)
