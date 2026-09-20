"""Fail closed on dimensions, page clipping and bounded text overflow."""

from fastapi import HTTPException
import pymupdf
import logging


def check_layout(document, content):
    for page in document.pages:

        def walk(box, region=None):
            element = getattr(box, "element", None)
            if (
                element is not None
                and element.get("data-fit")
                and box.__class__.__name__ in ("BlockBox", "AbsolutePlaceholder")
            ):
                region = (
                    box.content_box_x(),
                    box.content_box_y(),
                    box.width,
                    float(element.get("data-max-height", box.height)),
                    element.get("data-fit"),
                )
            if region and box.__class__.__name__ == "TextBox":
                x, y, w, h, name = region
                if (
                    box.position_x < x - 1
                    or box.position_x + box.width > x + w + 1
                    or box.position_y < y - 1
                    or box.position_y + box.height > y + h + 1
                ):
                    logging.getLogger(__name__).warning(
                        "Text overflow in %s: region=%s text_box=%s",
                        name,
                        region[:4],
                        (box.position_x, box.position_y, box.width, box.height),
                    )
                    raise HTTPException(422, "Generated layout failed preflight")
            for child in getattr(box, "children", ()):
                walk(child, region)

        walk(page._page_box)


def inspect_pdf(pdf, content):
    expected = None
    count = None
    kind = "booklet"
    if content.get("social"):
        s = content["social"]
        expected = (s["width_px"] * 0.75, s["height_px"] * 0.75)
        count = len(content["items"]) if s["post_kind"] == "property" else 1
        kind = "social"
    elif content.get("banner"):
        b = content["banner"]
        expected = (b["width_mm"] * 72 / 25.4, b["height_mm"] * 72 / 25.4)
        count = len(content["items"])
        kind = "banner"
    elif content.get("booklet"):
        expected = (210 * 72 / 25.4, 297 * 72 / 25.4)
        count = len(content["booklet"]["pages"])
    else:
        return None
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        if not len(doc) or (count is not None and len(doc) != count):
            raise HTTPException(422, "Generated layout failed preflight")
        for page in doc:
            if any(
                abs(actual - target) > 0.15
                for actual, target in zip((page.rect.width, page.rect.height), expected)
            ):
                raise HTTPException(422, "Generated layout failed preflight")
            for b in page.get_text("blocks"):
                if (
                    b[0] < -1
                    or b[1] < -1
                    or b[2] > page.rect.width + 1
                    or b[3] > page.rect.height + 1
                ):
                    logging.getLogger(__name__).warning(
                        "PDF text outside page %s: %s", page.number + 1, b[:4]
                    )
                    raise HTTPException(422, "Generated layout failed preflight")
        return {
            "passed": True,
            "version": 1,
            "kind": kind,
            "page_count": len(doc),
            "width_pt": round(expected[0], 2),
            "height_pt": round(expected[1], 2),
            "checks": ["dimensions", "page_count", "text_bounds", "fixed_text_regions"],
        }
