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
LAYOUT_VERSION = 10
# Rows that the reference tables hold before continuing on another page.
# Summary table (guide p.14). Column edges (right to left) come from the open
# reference booklet; the title and table sit where the guide places them, and
# the table fills its area down to the footer: rows share the height evenly.
SUMMARY_COLS = (509.2, 455.1, 413.1, 350.6, 308.6, 265.9, 225.9, 152.6, 37.6)
SUMMARY_SHIFT = -103.5  # from the open booklet's position up to the guide's
SUMMARY_TOP = 297.7 + SUMMARY_SHIFT
SUMMARY_LIMIT = 740.0  # the table ends above the footer
SUMMARY_MIN_ROW = 26.0  # the reference row
SUMMARY_ROWS = 20  # properties on a summary page; the next ones open a new page
# With few properties a row grows no taller than in a full eight-row table
# (the guide's), so a short list does not turn into oversized rows.
SUMMARY_MAX_ROW = (SUMMARY_LIMIT - SUMMARY_TOP) / 8
SUMMARY_LINE = 10.5  # line height of a value wrapped inside its cell
RENTAL_ROWS = 19
# Rentals table (reference page 18): column edges right to left, the reference
# row, and the lowest row bottom that still leaves room for the note under it.
RENTAL_COLS = (516.5, 462.3, 430.4, 382.9, 327.4, 271.2, 215.0, 159.0, 95.5, 44.0)
RENTAL_TOP = 152.8
RENTAL_ROW = 26.3
RENTAL_LIMIT = 690.0
RENTAL_NOTE_GAP = 12.0  # the fixed note follows the last row
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
# Guide p.12 (selling agent): Ruaq Medium 16.02 pt on 28.5 pt lines, ten lines
# in a 317 pt column whose right edge (466) is shared by the logo and the name.
AGENT_TEXT = (16.02, 317.0, 10)
AGENT_LINE = 28.5
AGENT_BOX = 285  # points of height for the agent's description (10 lines)
# The agent's extra contact text sits under the numbers on the contact page.
CONTACT_EXTRA = (10, 360, 2)
AGENT_MIN = 11.0  # smallest size the description is set at before it must be shortened
# The announcement and court decision (guide p.13): three 29 pt lines at 19 pt,
# right-aligned. A longer text keeps that setting and grows to six lines (the
# schedule under it moves down); longer still, it is set smaller in that space.
ANNOUNCEMENT = (19, 373, 3)
ANNOUNCEMENT_LINE = 29.0
ANNOUNCEMENT_LINES = 6
ANNOUNCEMENT_MIN = 13.0
BOUNDARY_PAGE = (15, 444, 4)  # the fifth line carries the length
# Width in points beside each direction label on the property page.
BOUNDARY_WIDTH = {"landscape": 100, "portrait": 130}
# Boundaries beside their labels: one line each at 9.6 pt, set smaller down to
# 8 pt; longer ones take two lines at 7.5 pt inside the same row.
BOUNDARY_SIZE, BOUNDARY_ONE_LINE, BOUNDARY_TWO_LINES = 9.6, 8.0, 7.5
LENGTH_SIZE, LENGTH_MIN = 10.06, 7.5
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


def fit_length(text, size, width, max_lines, name="RuaqArabic-Light", margin=0.98):
    """Characters of text that fit in max_lines of width, broken as the page breaks them.

    Returns (length, lines used). Justified regions keep a 2% width margin.
    """
    width *= margin
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


def split_text(text, size, width, max_lines, margin=0.98):
    """First part that fits the region, the remainder continuing elsewhere."""
    length, _ = fit_length(text, size, width, max_lines, margin=margin)
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


def agent_size(text):
    """Largest size (guide: 16.02 pt on 28.5 pt lines) that sets the description
    on page 3.

    The guide has exactly one agent page; a longer description is set smaller,
    and below AGENT_MIN it has to be shortened (reported in the workflow).
    """
    size = AGENT_TEXT[0]
    while True:
        lines = int(AGENT_BOX // (AGENT_LINE * size / AGENT_TEXT[0]))
        fitted = fit_length(text, size, AGENT_TEXT[1], lines, "RuaqArabic-Medium")
        if fitted[0] >= len(text.rstrip()):
            return size, True
        if size <= AGENT_MIN:
            return AGENT_MIN, False
        size = max(AGENT_MIN, round(size - 0.25, 2))


# Letters that join the next one: a kashida (tatweel) may follow them.
JOINING = set("بتثجحخسشصضطظعغفقكلمنهيئـ")
TATWEEL = "ـ"


def wrap_lines(text, size, width, name):
    """Text broken into lines as the page breaks it; each is (line, ends_paragraph)."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for token in TOKENS.findall(paragraph):
            candidate = (current + token).rstrip()
            if current.strip() and text_width(candidate, size, name) > width:
                lines.append((current.rstrip(), False))
                current = token.lstrip()
            else:
                current += token
        lines.append((current.rstrip(), True))
    return lines


def kashida(line, size, width, name, per_word=4):
    """A line lengthened towards width with kashidas, as the guide sets its
    justified Arabic text; the small remainder is left to word spacing."""
    unit = text_width(TATWEEL, size, name)
    room = int((width - text_width(line, size, name)) // unit) if unit else 0
    words = line.split(" ")
    spots = []
    for word in words:
        # The join into the word's last letters reads best; never inside lam-alef.
        found = [
            i
            for i in range(len(word) - 1)
            if word[i] in JOINING
            and "\u0621" <= word[i + 1] <= "\u064a"
            and not (word[i] == "ل" and word[i + 1] in "اأإآ")
        ]
        spots.append(found[-1] if found and len(word) > 2 else None)
    added = [0] * len(words)
    while room > 0:
        progressed = False
        for n, spot in enumerate(spots):
            if spot is not None and added[n] < per_word and room > 0:
                added[n] += 1
                room -= 1
                progressed = True
        if not progressed:
            break
    return " ".join(
        word if spot is None else word[: spot + 1] + TATWEEL * extra + word[spot + 1 :]
        for word, spot, extra in zip(words, spots, added)
    )


def justified(text, size, width, name="RuaqArabic-Medium"):
    """Lines for a justified block: every line but a paragraph's last is filled."""
    return [
        {
            "text": line if last else kashida(line, size, width * 0.985, name),
            "last": last,
        }
        for line, last in wrap_lines(text, size, width * 0.98, name)
    ]


def summary_value(item, key, language="ar"):
    """A property's value as the summary table prints it."""
    from .formatting import number

    value = item["property_data"].get(key)
    if key in ("area", "participation_amount"):
        value = number(value, language, key == "participation_amount")
    if key == "deed_number":
        # Every deed of the property, each on its own line in the cell.
        value = " ".join(deeds(item["property_data"]))
    return str(value or "-")


# Table values: words in Ruaq, figures in Lama (the wider of the two counts).
CELL_FONTS = (("RuaqArabic-Medium", 8.13), ("LamaSans-Medium", 8))


def cell_width(text):
    return max(text_width(text, size, name) for name, size in CELL_FONTS)


def cell_text(text, width):
    """A value as the lines it takes in a table cell, none wider than the cell.

    Words wrap. A single run wider than the cell cannot wrap: it breaks after
    its separators (1433/234/17), and a part still too wide (a long deed
    number) is split into equal pieces. The page prints exactly these lines,
    in the browser preview and in the export alike.
    """
    limit = width * 0.94  # measured widths differ slightly between renderers

    def pieces(word):
        """An over-wide run as parts that each fit on a line."""
        found = []
        for part in re.findall(r"[^/\\\-–٫،,.:]+[/\\\-–٫،,.:]*|[/\\\-–٫،,.:]+", word):
            count = 1
            while True:
                size = -(-len(part) // count)
                cut = [part[i : i + size] for i in range(0, len(part), size)]
                if size == 1 or all(cell_width(c) <= limit for c in cut):
                    break
                count += 1
            found += cut
        return found

    lines, line = [], ""
    for word in str(text).split():
        if cell_width(word) > limit:
            if line:
                lines.append(line)
            line = ""
            for piece in pieces(word):
                if line and cell_width(line + piece) > limit:
                    lines.append(line)
                    line = piece
                else:
                    line += piece
        elif line and cell_width(f"{line} {word}") > limit:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return lines or ["-"]


def spread(needs, space, cap):
    """Row heights sharing a table's space evenly: every row is at least as tall
    as its content needs, no row taller than cap, the total within space."""
    low, high = min(needs), max(cap, min(needs))
    for _ in range(40):
        level = (low + high) / 2
        if sum(max(n, level) for n in needs) <= space:
            low = level
        else:
            high = level
    return [max(n, low) for n in needs]


def summary_pages(items, language="ar"):
    """Summary tables with every value shown whole, at the reference size.

    A value too long for its column wraps inside its cell and its row grows.
    A page takes at most SUMMARY_ROWS properties (fewer when wrapped rows fill
    it down to the footer first), and its rows share the table's height evenly.
    """
    space = SUMMARY_LIMIT - SUMMARY_TOP
    pages, rows, needs, lines = [], [], [], []

    def close():
        heights = spread(needs, space, SUMMARY_MAX_ROW)
        bottoms, y = [], SUMMARY_TOP
        for height in heights:
            y += height
            bottoms.append(round(y, 2))
        pages.append(
            {"kind": "summary", "rows": rows, "bottoms": bottoms, "lines": lines}
        )

    for item in items:
        texts = {
            key: cell_text(
                summary_value(item, key, language),
                SUMMARY_COLS[i] - SUMMARY_COLS[i + 1] - 4,
            )
            for i, key in enumerate(SUMMARY_FIELDS)
        }
        longest = max(len(text) for text in texts.values())
        need = max(SUMMARY_MIN_ROW, longest * SUMMARY_LINE + 6)
        if rows and (len(rows) == SUMMARY_ROWS or sum(needs) + need > space + 0.01):
            close()
            rows, needs, lines = [], [], []
        rows.append(item)
        needs.append(need)
        lines.append(texts)
    if rows:
        close()
    return pages


def rental_pages(item, rentals, language="ar"):
    """Rental tables whose values stay inside their cells: a long value wraps
    and its row grows; the page ends when the table and its note are full."""
    from .formatting import number

    pages, rows, bottoms, lines = [], [], [], []

    def close():
        pages.append(
            {
                "kind": "rentals",
                "item": item,
                "rows": rows,
                "bottoms": bottoms,
                "lines": lines,
            }
        )

    for row in rentals:
        texts = {}
        for i, key in enumerate(RENTAL_FIELDS):
            value = row.get(key)
            if key == "annual_rent_value":
                value = number(value, language or "ar", True)
            texts[key] = cell_text(
                str(value or "-"), RENTAL_COLS[i] - RENTAL_COLS[i + 1] - 4
            )
        longest = max(len(text) for text in texts.values())
        height = max(RENTAL_ROW, longest * SUMMARY_LINE + 6)
        top = bottoms[-1] if bottoms else RENTAL_TOP
        if rows and (len(rows) == RENTAL_ROWS or top + height > RENTAL_LIMIT):
            close()
            rows, bottoms, lines = [], [], []
            top = RENTAL_TOP
        rows.append(row)
        bottoms.append(round(top + height, 2))
        lines.append(texts)
    if rows:
        close()
    return pages


SIDES = ("north", "south", "east", "west")


def boundary_fit(boundaries, layout="landscape"):
    """How the boundaries are set beside their labels on the property page.

    All four descriptions share one setting: a line each at the reference
    size or a little smaller, or two lines each at 7.5 pt in the same rows.
    Returns {"size", "lines": {side: [..]}, "length_size"}, or None when they
    do not fit even so and continue on a page of their own.
    """
    width = BOUNDARY_WIDTH[layout] * 0.97
    texts = {s: (boundaries.get(s + "_description") or "").strip() for s in SIDES}
    lengths = [(boundaries.get(s + "_length") or "").strip() for s in SIDES]
    if any("\n" in value for value in lengths):
        return None
    longest = max(text_width(value, LENGTH_SIZE) for value in lengths)
    length_size = (
        LENGTH_SIZE if longest <= width else round(LENGTH_SIZE * width / longest, 2)
    )
    if length_size < LENGTH_MIN:
        return None
    widest = max(text_width(value, BOUNDARY_SIZE) for value in texts.values())
    plain = not any("\n" in value for value in texts.values())
    if plain and widest * BOUNDARY_ONE_LINE / BOUNDARY_SIZE <= width:
        size = (
            BOUNDARY_SIZE
            if widest <= width
            else round(BOUNDARY_SIZE * width / widest, 2)
        )
        lines = {side: [value or "-"] for side, value in texts.items()}
        return {"size": size, "lines": lines, "length_size": length_size}
    lines = {}
    for side, value in texts.items():
        rows = [
            row
            for row, _ in wrap_lines(
                value, BOUNDARY_TWO_LINES, width, "LamaSans-Medium"
            )
            if row
        ]
        if len(rows) > 2 or any(
            text_width(row, BOUNDARY_TWO_LINES) > width for row in rows
        ):
            return None
        lines[side] = rows or ["-"]
    return {"size": BOUNDARY_TWO_LINES, "lines": lines, "length_size": length_size}


def boundaries_need_page(boundaries, layout="landscape"):
    return boundary_fit(boundaries, layout) is None


def announcement_fit(text):
    """The announcement as the lines it prints on the auction page.

    Returns (size, line height, lines, rest): the reference setting while the
    text fits six lines, smaller (down to 13 pt) to keep a longer one in the
    same space, and whatever still does not fit as the rest for a later page.
    """
    size, width, _ = ANNOUNCEMENT
    space = ANNOUNCEMENT_LINES * ANNOUNCEMENT_LINE
    while True:
        height = round(ANNOUNCEMENT_LINE * size / ANNOUNCEMENT[0], 2)
        rows = wrap_lines(text, size, width, "RuaqArabic-Light") if text else []
        if len(rows) * height <= space + 0.01 or size <= ANNOUNCEMENT_MIN:
            break
        size = max(ANNOUNCEMENT_MIN, round(size - 0.5, 2))
    count = int((space + 0.01) // height)
    rest = "".join(row + ("\n" if last else " ") for row, last in rows[count:])
    return size, height, [row for row, _ in rows[:count]], rest.strip()


def deeds(prop):
    """A property's deed numbers: the first and up to three more."""
    return [
        str(value).strip()
        for value in [prop.get("deed_number"), *(prop.get("extra_deed_numbers") or [])]
        if str(value or "").strip()
    ]


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


INFO_MIN = 6.5  # smallest size of the additional-information box


def fit_box(entries, size, width, capacity):
    """The whole content in its box, set smaller when there is more of it.

    Returns (shown, rest, size): the reference size while everything fits, then
    smaller down to INFO_MIN (lines tighten in proportion); only content that
    does not fit even then continues on an additional page.
    """
    height = capacity * 1.4 * size
    current = size
    while True:
        shown, rest = fill_box(
            entries, current, width, int(height // (1.4 * current) + 1e-6)
        )
        if not rest or current <= INFO_MIN:
            return shown, rest, current
        current = max(INFO_MIN, round(current - 0.5, 2))


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
    # Guide order: cover, Infath, the selling agent (one page), the auction.
    agent = project.get("selling_agent", {})
    description = (agent.get("description") or "").strip()
    size, _ = agent_size(description)
    pages.append(
        {
            "kind": "agent",
            "text": description,
            "size": size,
            "line_height": round(AGENT_LINE * size / AGENT_TEXT[0], 2),
            "lines": justified(description, size, AGENT_TEXT[1]),
        }
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
    size, height, lines, rest = announcement_fit(announcement)
    auction_page.update(
        announcement="\n".join(lines),
        announcement_lines=lines,
        announcement_size=size,
        announcement_line=height,
        # The schedule below keeps its distance from a block taller than the
        # reference's three lines.
        shift=round(
            max(0.0, len(lines) * height - ANNOUNCEMENT[2] * ANNOUNCEMENT_LINE), 2
        ),
    )
    for text in measured_chunks(rest, *INFO_PAGE):
        pages.append(
            {"kind": "information", "heading": "legal_announcement_text", "text": text}
        )
    pages += summary_pages(items, auction.get("document_language") or "ar")
    for index, item in enumerate(items, 1):
        item["number"] = index
        prop = item["property_data"]
        layout = property_layout(item)
        boundaries = prop.get("boundaries", {})
        beside = boundary_fit(boundaries, layout)
        separate_boundaries = beside is None
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
        shown, rest, info_size = fit_box(
            info_entries(item, include_info), *INFO_BOX[layout]
        )
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
                "boundaries": beside,
                "description": description[0] if description else "",
                "info": shown,
                "info_size": info_size,
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
        if prop.get("include_rentals_page", True):
            pages += rental_pages(item, rentals, auction.get("document_language"))
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
