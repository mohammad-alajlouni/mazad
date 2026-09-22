"""Reference photo windows, in PDF points, without deforming photographs."""

import base64
from xml.sax.saxutils import quoteattr


def booklet_photo(src, portrait=False, fit="cover"):
    w, h = (320, 548) if portrait else (500, 293)
    cut = 40
    path = (
        f"M {cut} 0 H {w} V {h - cut} L {w - cut} {h} H 0 V {cut} Z"
        if portrait
        else f"M 0 0 H {w - cut} L {w} {cut} V {h} H {cut} L 0 {h - cut} Z"
    )
    inset = 9 if portrait else 0
    scaling = "meet" if fit == "contain" else "slice"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs><clipPath id="window"><path d="{path}"/></clipPath></defs><g clip-path="url(#window)"><path d="{path}" fill="#19a1a1"/><image href={quoteattr(src)} x="{inset}" y="{inset}" width="{w - 2 * inset}" height="{h - 2 * inset}" preserveAspectRatio="xMidYMid {scaling}"/></g></svg>'''
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def original_pdf_artwork(pdf, content):
    """Overlay immutable original forms on their reserved pages in both preview/export."""
    import pymupdf

    from .assets import ASSETS

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
                name = f"reference-terms-{page['auction_type']}.pdf"
                box = pymupdf.Rect(114, 115, 499, 689)
            else:
                continue
            with pymupdf.open(ASSETS / name) as artwork:
                document[n].show_pdf_page(box, artwork, 0, keep_proportion=True)
        return document.tobytes(garbage=3, deflate=True)
