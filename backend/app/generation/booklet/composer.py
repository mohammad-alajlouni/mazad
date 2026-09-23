"""Pure page composition from the same normalized snapshot used by all outputs."""

import copy
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .codes import qr
from .registry import COVERS

FIELDS = (
    "property_type",
    "area",
    "deed_number",
    "usage",
    "plan_number",
    "district",
    "plot_number",
    "participation_amount",
    "execution_request_number",
)
SUMMARY_FIELDS = (
    "property_type",
    "city",
    "district",
    "area",
    "plan_number",
    "plot_number",
    "deed_number",
    "participation_amount",
)
RENTAL_FIELDS = (
    "property_type",
    "unit_number",
    "contract_status",
    "contract_start_date",
    "contract_end_date",
    "annual_rent_value",
    "contract_duration",
    "paid_period",
    "next_due_date",
)
# Version of the stored page plan; raise it whenever compose() output changes shape.
LAYOUT_VERSION = 4
# Rows that the reference tables hold before continuing on another page.
SUMMARY_ROWS = 10
RENTAL_ROWS = 19
# Links shown on the property page; the rest continue on a links page.
PAGE_LINKS = 4
LINK_ORDER = (
    "survey_link",
    "rental_information_link",
    "additional_images_link",
    "other_document_link",
    "location_link",
)
# Reference text regions: (font size, width in points, lines).
DESCRIPTION = {"landscape": (10, 497.3, 3), "portrait": (12, 198, 5)}
INFO_BOX = {"landscape": (10, 268, 11), "portrait": (10, 262, 8)}
INFO_PAGE = (11, 500, 33)
NUMBER_INDENT = 11
# Other text regions: (font size, width, lines), measured on the reference.
AGENT_TEXT = (17.02, 387.6, 8)
ANNOUNCEMENT = (19, 373, 3)
BOUNDARY_PAGE = (15, 444, 4)  # the fifth line carries the length
# Width in points beside each direction label on the property page.
BOUNDARY_WIDTH = {"landscape": 100, "portrait": 130}
IDENTITY = Path(__file__).resolve().parents[2] / "templates/infath/assets/identity"


def chunks(rows, count):
    return [rows[i : i + count] for i in range(0, len(rows), count)]


def text_chunks(value, size=900, max_lines=24):
    # Preserve all characters, including whitespace/newlines and long unbroken tokens.
    result = []
    while value:
        end = min(size, len(value))
        breaks = [i + 1 for i, char in enumerate(value[:end]) if char == "\n"]
        if len(breaks) >= max_lines:
            end = breaks[max_lines - 1]
        if end < len(value):
            boundary = value.rfind(" ", end // 2, end)
            if boundary > 0:
                end = boundary + 1
        result.append(value[:end])
        value = value[end:]
    return result


def property_layout(item):
    prop = item["property_data"]
    selected = prop.get("booklet_layout", "auto")
    if selected != "auto":
        return selected
    kind = unicodedata.normalize("NFKC", prop.get("property_type", "")).lower()
    if any(
        word in kind
        for word in ("برج", "أبراج", "ابراج", "عمارة", "عمائر", "tower", "building")
    ):
        return "portrait"
    if any(
        word in kind
        for word in ("فيلا", "فيللا", "مزرعة", "أرض", "ارض", "villa", "farm", "land")
    ):
        return "landscape"
    assets = item.get("image_assets", [])
    return (
        "portrait"
        if assets and assets[0].get("orientation") == "portrait"
        else "landscape"
    )


@lru_cache(maxsize=4)
def face(name):
    from PIL import ImageFont

    return ImageFont.truetype(str(IDENTITY / f"{name}.ttf"), 100)


def text_width(text, size=9.6, name="LamaSans-Medium"):
    """Shaped width in points, measured with the booklet's own font."""
    try:
        return face(name).getlength(text) / 100 * size
    except OSError:  # font unavailable: assume wide Latin figures
        return len(text) * size * 0.6


TOKENS = re.compile(r"\n|[^\s]+[ \t]*|[ \t]+")


def fit_length(text, size, width, max_lines, name="RuaqArabic-Light"):
    """Characters of text that fit in max_lines of width, broken as the page breaks them.

    Returns (length, lines used). Width keeps a 2% margin for justification.
    """
    width *= 0.98
    lines, used, consumed = 1, 0.0, 0
    for token in TOKENS.findall(text):
        if token == "\n":
            if lines == max_lines:
                return consumed, lines
            lines, used = lines + 1, 0.0
            consumed += 1
            continue
        word = text_width(token.rstrip(), size, name)
        if used and used + word > width:
            if lines == max_lines:
                return consumed, lines
            lines, used = lines + 1, 0.0
        used += text_width(token, size, name)
        consumed += len(token)
    return consumed, lines


def split_text(text, size, width, max_lines):
    """First part that fits the region, the remainder continuing elsewhere."""
    length, _ = fit_length(text, size, width, max_lines)
    return text[:length], text[length:]


def measured_chunks(text, size, width, max_lines):
    """Text split into region-sized parts by measured line breaks, losing nothing."""
    parts = []
    while text:
        first, text = split_text(text, size, width, max_lines)
        if not first:  # a leading line break alone: move it on with the next part
            first, text = text[:1], text[1:]
        parts.append(first)
    return parts


def lines_used(text, size, width):
    return fit_length(text, size, width, 10**6)[1]


def boundaries_need_page(boundaries, layout="landscape"):
    # Each direction has one line beside its label on the property page.
    return any(
        "\n" in boundaries.get(side + key, "")
        or text_width(boundaries.get(side + key, "")) > BOUNDARY_WIDTH[layout]
        for side in ("north", "south", "east", "west")
        for key in ("_description", "_length")
    )


def info_entries(item, include_lists):
    """Box content in reference order: features, notes, then free text."""
    prop = item["property_data"]
    entries = []
    if include_lists:
        features = [f.strip() for f in prop.get("features", []) if f.strip()]
        if features:
            entries.append({"heading": "features"})
            entries += [{"number": n, "text": f} for n, f in enumerate(features, 1)]
        notes = [n.strip() for n in (item.get("notes") or "").split("\n") if n.strip()]
        if notes:
            entries.append({"heading": "notes"})
            entries += [{"number": n, "text": t} for n, t in enumerate(notes, 1)]
    if prop.get("additional_information", "").strip():
        entries.append({"text": prop["additional_information"].strip()})
    return entries


def fill_box(entries, size, width, capacity):
    """Entries that fit a text region, and the entries that continue after it."""
    shown, used = [], 0
    for index, entry in enumerate(entries):
        text = entry.get("text", "")
        indent = NUMBER_INDENT if "number" in entry else 0
        need = 1 if "heading" in entry else lines_used(text, size, width - indent)
        if used + need <= capacity:
            shown.append(entry)
            used += need
            continue
        free = capacity - used
        rest = entries[index:]
        if set(entry) == {"text"} and free > 0:
            # Free text is split at a line break; nothing is repeated or lost.
            first, remainder = split_text(text, size, width, free)
            if first.strip():
                shown.append({"text": first})
                rest = [{"text": remainder}] + entries[index + 1 :]
        elif shown and "heading" in shown[-1]:
            rest = [shown.pop()] + rest  # never leave a heading without its items
        if not shown:  # a single entry larger than the region still has to move on
            shown, rest = [entry], entries[index + 1 :]
        return shown, rest
    return shown, []


def paginate(entries, size, width, capacity):
    pages = []
    while entries:
        page, entries = fill_box(entries, size, width, capacity)
        pages.append(page)
    return pages


def compose(project, items):
    auction = project["auction"]
    cover = COVERS[auction["selected_cover_template_id"]]
    electronic = auction["auction_type"] in ("electronic", "hybrid")
    edition = auction.get("booklet_edition") or "print"
    pages = [
        {"kind": "cover", "cover_number": cover.display_order},
        {"kind": "introduction"},
    ]
    agent = project.get("selling_agent", {})
    for text in measured_chunks(agent.get("description", ""), *AGENT_TEXT) or [""]:
        pages.append({"kind": "agent", "text": text})
    for text in measured_chunks(agent.get("contact_information", ""), *INFO_PAGE):
        pages.append(
            {"kind": "information", "heading": "contact_information", "text": text}
        )
    auction_page = {"kind": "auction"}
    pages.append(auction_page)
    announcement = "\n".join(
        t.strip()
        for t in (
            auction.get("legal_announcement_text", ""),
            auction.get("court_decision_text", ""),
        )
        if t and t.strip()
    )
    first, rest = split_text(announcement, *ANNOUNCEMENT)
    auction_page["announcement"] = first
    for text in measured_chunks(rest, *INFO_PAGE):
        pages.append(
            {"kind": "information", "heading": "legal_announcement_text", "text": text}
        )
    for rows in chunks(items, SUMMARY_ROWS):
        pages.append({"kind": "summary", "rows": rows})
    for index, item in enumerate(items, 1):
        item["number"] = index
        prop = item["property_data"]
        layout = property_layout(item)
        boundaries = prop.get("boundaries", {})
        separate_boundaries = boundaries_need_page(boundaries, layout)
        include_info = prop.get("include_information_page", True)
        links = [k for k in LINK_ORDER if prop.get(k)] + sorted(
            k for k in prop if k.endswith("_link") and prop[k] and k not in LINK_ORDER
        )
        item["qr_links"] = [
            {"label": k, "url": prop[k], "image": qr(prop[k], "#3cbebb", 0)}
            for k in links
        ]
        first, remainder = split_text(item.get("description", ""), *DESCRIPTION[layout])
        description = (
            [first] + measured_chunks(remainder, *INFO_PAGE)
            if first or remainder
            else []
        )
        shown, rest = fill_box(info_entries(item, include_info), *INFO_BOX[layout])
        close = electronic and bool(
            prop.get("auction_close_date") or prop.get("auction_close_time")
        )
        pages.append(
            {
                "kind": "property",
                "item": item,
                "layout": layout,
                "variant": layout + ("-close" if close else ""),
                "edition": edition,
                "separate_boundaries": separate_boundaries,
                "description": description[0] if description else "",
                "info": shown,
                "additional_information": "".join(
                    e["text"] for e in shown if set(e) == {"text"}
                ),
            }
        )
        if separate_boundaries:
            rows = []
            for side in ("north", "south", "east", "west"):
                for text in measured_chunks(
                    boundaries.get(side + "_description", ""), *BOUNDARY_PAGE
                ) or ["-"]:
                    rows.append(
                        {
                            "side": side,
                            "text": text,
                            "length": boundaries.get(side + "_length", "") or "-",
                        }
                    )
            for group in chunks(rows, 4):
                pages.append({"kind": "boundaries", "item": item, "rows": group})
        for group in chunks(item["qr_links"][PAGE_LINKS:], 4):
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "property_links",
                    "links": group,
                    "text": "",
                }
            )
        for text in description[1:]:
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "description",
                    "text": text,
                }
            )
        if include_info:
            for field in ("specifications", "technical_information"):
                for text in measured_chunks(item.get(field, ""), *INFO_PAGE):
                    pages.append(
                        {
                            "kind": "information",
                            "item": item,
                            "heading": field,
                            "text": text,
                        }
                    )
        for group in paginate(rest, *INFO_PAGE):
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "additional_information",
                    "entries": group,
                    "text": "".join(e["text"] for e in group if set(e) == {"text"}),
                }
            )
        for images in (
            chunks(item.get("image_assets", [])[1:], 3)
            if prop.get("include_images_page", True)
            else []
        ):
            pages.append({"kind": "images", "item": item, "images": images})
        rentals = [
            r
            for r in prop.get("rental_contracts", [])
            if any(v not in (None, "") for v in r.values())
        ]
        for rows in (
            chunks(rentals, RENTAL_ROWS)
            if prop.get("include_rentals_page", True)
            else []
        ):
            pages.append({"kind": "rentals", "item": item, "rows": rows})
    pages.append({"kind": "terms", "auction_type": auction["auction_type"]})
    if electronic:
        pages.append({"kind": "participation"})
    pages.append({"kind": "contact"})
    return {
        "layout_version": LAYOUT_VERSION,
        "theme": "navy" if cover.display_order in (2, 4) else "teal",
        "pages": pages,
        "cover_id": cover.id,
        "auction_qrs": [
            {"label": k, "url": v, "image": qr(v, "#12375c", 0)}
            for k, v in auction.items()
            if k.endswith("_url") and v
        ],
    }


def current_booklet(content):
    """Stored output content with its booklet page plan in the current layout.

    Outputs keep the data snapshot they were generated from. A plan written by
    an older composer is rebuilt from that same snapshot, so re-rendering an
    old draft (approve, edit) uses today's templates with the original data.
    Returns (content, upgraded).
    """
    booklet = content.get("booklet")
    if not booklet or booklet.get("layout_version") == LAYOUT_VERSION:
        return content, False
    project = copy.deepcopy(content.get("project") or {})
    if not project.get("auction"):
        return content, False
    items = copy.deepcopy(content.get("items") or [])
    return {**content, "booklet": compose(project, items)}, True
