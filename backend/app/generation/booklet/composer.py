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
LAYOUT_VERSION = 12
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
# The property description (guide p.15 and p.19): its first line's baseline,
# right edge and width, the reference size and line height, and the lowest
# point it may reach (above the property's facts). A longer description is
# set smaller, a quarter point at a time, down to DESCRIPTION_MIN, using the
# whole region; only what does not fit even then continues on another page.
DESCRIPTION = {
    "landscape": {
        "base": 390.6,
        "right": 550.1,
        "width": 497.3,
        "size": 10,
        "line": 14,
        "bottom": 441.0,
    },
    "portrait": {
        "base": 93.9,
        "right": 563.8,
        "width": 198.0,
        "size": 12,
        "line": 14.4,
        "bottom": 176.0,
    },
}
DESCRIPTION_MIN = 8.0
DESCRIPTION_FONT = "RuaqArabic-Light"
# The additional-information box (guide p.15 and p.19-20): its edges in
# points. In portrait the digital edition's box is wider (its links are
# buttons in a narrow column) than the print edition's (two columns of QR
# codes beside it). The text keeps the same margin from the top and both
# sides of the box, and uses all of its width.
INFO_REGION = {
    "portrait": {
        "top": 627.56,
        "bottom": 757.68,
        "right": 564.9,
        "left": {"digital": 160.7, "print": 266.3},
    },
    "landscape": {
        "top": 577.59,
        "bottom": 750.62,
        "right": 563.04,
        "left": {"digital": 258.71, "print": 258.71},
    },
}
# When the boundaries continue on a page of their own, the box takes their
# place: in portrait it moves up beside the photograph (its tab where the
# boundaries tab stood), in landscape it runs across to the page margin (the
# links move up into the column the boundaries left).
INFO_SEPARATE = {
    "portrait": {
        "top": 398.76,
        "bottom": 757.68,
        "right": 564.9,
        "left": 350.0,
        "tab": -228.8,
    },
    "landscape": {
        "top": 577.59,
        "bottom": 750.62,
        "right": 563.04,
        "left": 34.3,
        "tab": 0.0,
    },
}
INFO_PAD = 8.0
INFO_SIZE, INFO_LINE = 10.0, 1.4


def info_region(layout, edition, separate=False):
    """The box, and the text region inside it: right edge, width, top of its
    first line box, the lines it holds at the reference size, and how far its
    tab moved (when the boundaries continue on their own page)."""
    box = INFO_SEPARATE[layout] if separate else INFO_REGION[layout]
    left = box["left"] if separate else box["left"].get(edition, box["left"]["print"])
    line = INFO_SIZE * INFO_LINE
    top = box["top"] + INFO_PAD - (line - INFO_SIZE) / 2
    return {
        "box": [left, box["top"], box["right"], box["bottom"]],
        "right": round(box["right"] - INFO_PAD, 2),
        "width": round(box["right"] - left - 2 * INFO_PAD, 2),
        "top": round(top, 2),
        "lines": int((box["bottom"] - INFO_PAD + (line - INFO_SIZE) / 2 - top) // line),
        "tab": box.get("tab", 0.0) if separate else 0.0,
    }


INFO_PAGE = (11, 500, 33)
# Guide p.17: the page after a property's first page when it has features and
# more than one additional photograph. The features are set as numbered
# points under their tab, between the photographs and the footer.
FEATURES_BOX = (11, 498, 14)
NUMBER_INDENT = 11
# Other text regions: (font size, width, lines), measured on the reference.
# Guide p.11 (the supervising body) and p.12 (the selling agent) share one
# layout, both set as the Infath page is: the title in Ruaq Bold 19.56, the
# text in Ruaq Light 17.04 on 25.07 pt lines, justified in a 330.1 pt column
# whose right edge (463.4) the logo and the title share; ten lines fit above
# the contact row. A longer text is set smaller, down to PROFILE_MIN.
PROFILE_TEXT = (17.04, 330.1, 10)
PROFILE_LINE = 25.07
PROFILE_FONT = "RuaqArabic-Light"
PROFILE_MIN = 11.0
# A logo on these pages (an agent's, or another body's): the box it is fitted
# in, and the frame the upload editor shows it in.
AGENT_LOGO = (145.2, 67.0)
# The agent's extra contact text sits under the numbers on the contact page.
CONTACT_EXTRA = (10, 360, 2)
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


# Property types whose page is set upright or wide when the layout is "auto".
PORTRAIT_KINDS = ("برج", "أبراج", "ابراج", "عمارة", "عمائر", "tower", "building")
LANDSCAPE_KINDS = ("فيلا", "فيللا", "مزرعة", "أرض", "ارض", "villa", "farm", "land")


def image_frames():
    """The frame each uploaded photograph is shown in, as [width, height] in
    points, so the upload form can let the author place it in that frame."""
    from .art import COVER_PHOTO, path_box, shapes

    def size(box):
        x0, y0, x1, y1 = box
        return [round(x1 - x0, 2), round(y1 - y0, 2)]

    return {
        "main": {
            "landscape": size(path_box(shapes()["photo_landscape"])),
            "portrait": size(path_box(shapes()["photo_portrait"])),
        },
        "additional": size(path_box(shapes()["images"][0])),
        # The first two additional photographs of a property with features
        # sit in the smaller windows of its features page (guide p.17).
        "features": size(path_box(shapes()["images_features"][1])),
        # The features page's large window, above them.
        "features_large": size(path_box(shapes()["images_features"][0])),
        "cover": {f"infath-{n}": size(box) for n, box in COVER_PHOTO.items()},
        # A logo on a profile page (the agent's, or another supervising body's).
        "logo": list(AGENT_LOGO),
        # How an "auto" layout is chosen from the property type; with neither
        # word, the photograph's own orientation decides.
        "portrait_kinds": list(PORTRAIT_KINDS),
        "landscape_kinds": list(LANDSCAPE_KINDS),
    }


def property_layout(item):
    prop = item["property_data"]
    selected = prop.get("booklet_layout", "auto")
    if selected != "auto":
        return selected
    kind = unicodedata.normalize("NFKC", prop.get("property_type", "")).lower()
    if any(word in kind for word in PORTRAIT_KINDS):
        return "portrait"
    if any(word in kind for word in LANDSCAPE_KINDS):
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
        # A run wider than a line breaks inside, as the page breaks it.
        bare = token.rstrip()
        pieces = (
            split_word(bare, size, width, name)
            if text_width(bare, size, name) > width
            else [bare]
        )
        for n, piece in enumerate(pieces):
            last = n == len(pieces) - 1
            part = piece + (token[len(bare) :] if last else "")
            if used and used + text_width(piece, size, name) > width:
                if lines == max_lines:
                    return consumed, lines
                lines, used = lines + 1, 0.0
            used += text_width(part, size, name)
            consumed += len(part)
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


def profile_lines(size):
    """Lines of the profile text at a size (its line height scales with it)."""
    return int(
        PROFILE_TEXT[2] * PROFILE_LINE // (PROFILE_LINE * size / PROFILE_TEXT[0])
    )


def profile_size(text):
    """Largest size (guide p.11: 17.04 pt on 25.07 pt lines) that sets a
    profile text (the supervising body's, or the agent's) on its one page.

    A longer text is set smaller, and below PROFILE_MIN it has to be shortened
    (reported in the workflow).
    """
    size = PROFILE_TEXT[0]
    while True:
        fitted = fit_length(
            text, size, PROFILE_TEXT[1], profile_lines(size), PROFILE_FONT
        )
        if fitted[0] >= len(text.rstrip()):
            return size, True
        if size <= PROFILE_MIN:
            return PROFILE_MIN, False
        size = max(PROFILE_MIN, round(size - 0.25, 2))


def profile_page(kind, text):
    """A profile page: the text broken into justified lines at its size."""
    text = (text or "").strip()
    size, _ = profile_size(text)
    return {
        "kind": kind,
        "text": text,
        "size": size,
        "line_height": round(PROFILE_LINE * size / PROFILE_TEXT[0], 2),
        "lines": justified(text, size, PROFILE_TEXT[1], PROFILE_FONT),
    }


# Letters that join the next one: a kashida (tatweel) may follow them.
JOINING = set("بتثجحخسشصضطظعغفقكلمنهيئـ")
TATWEEL = "ـ"


def split_word(token, size, width, name):
    """A run with no space, wider than a line, as pieces that each fit one
    (repeated letters, a long code): the page breaks it there too."""
    pieces, current = [], ""
    for character in token:
        if current and text_width(current + character, size, name) > width:
            pieces.append(current)
            current = character
        else:
            current += character
    return pieces + [current]


def wrap_lines(text, size, width, name):
    """Text broken into lines as the page breaks it; each is (line, ends_paragraph).

    A run with no space wider than a line is broken inside (split_word), so
    no line is ever wider than width.
    """
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for token in TOKENS.findall(paragraph):
            if text_width(token.rstrip(), size, name) > width:
                if current.strip():
                    lines.append((current.rstrip(), False))
                *whole, current = split_word(token.rstrip(), size, width, name)
                lines += [(piece, False) for piece in whole]
                current += token[len(token.rstrip()) :]
                continue
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
        value = number(value, language, True)
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


# The summary's column headings (white on the band): Ruaq Medium 6.48.
SUMMARY_HEAD = (6.48, "RuaqArabic-Medium")
SUMMARY_PAD = 6.0  # space beside a cell's widest line
# A long word may still be split inside its cell (cell_text): no column is
# made wider than this just to hold one.
SUMMARY_WORD = 70.0


def summary_heading(key, language="ar"):
    from .labels import label

    return label("area_short" if key == "area" else key, language)


def summary_columns(items, language="ar"):
    """Column edges (right to left) shared by the summary's pages, fitted to
    the values: each column as wide as its widest value on one line (and its
    heading), so a short column (the participation amount) gives its room to
    the columns with more text. When the values cannot all stand on one line
    the widest columns give way first, never below their longest word or
    heading word; the table keeps the guide's outer edges."""
    total = SUMMARY_COLS[0] - SUMMARY_COLS[-1]
    natural, least = [], []
    for key in SUMMARY_FIELDS:
        values = [summary_value(item, key, language) for item in items] or ["-"]
        if key == "deed_number":
            # Several deeds stand one under another: the widest deed counts.
            values = [deed for value in values for deed in value.split(" ")]
        heading = summary_heading(key, language)
        head = text_width(heading, *SUMMARY_HEAD)
        head_word = max(text_width(w, *SUMMARY_HEAD) for w in heading.split())
        words = [w for value in values for w in value.split()] or ["-"]
        # A cell holds lines up to 94% of its inner width (cell_text): a
        # column for a line of width w is w / 0.94 + 4 wide.
        natural.append(
            max(head, max(cell_width(v) for v in values) / 0.94 + 4) + SUMMARY_PAD
        )
        least.append(
            max(
                head_word,
                min(SUMMARY_WORD, max(cell_width(w) for w in words)) / 0.94 + 4,
            )
            + SUMMARY_PAD
        )
    widths = list(natural)
    # Too wide: the column with the longest text takes two lines first (it
    # would wrap anyway), and so on, so short values keep their one line.
    for c in sorted(range(len(widths)), key=lambda c: -natural[c]):
        if sum(widths) <= total:
            break
        widths[c] = max(least[c], (natural[c] - SUMMARY_PAD) * 0.6 + SUMMARY_PAD)
    if sum(widths) > total and sum(least) >= total:
        widths = [m * total / sum(least) for m in least]
    elif sum(widths) > total:
        # Still too wide: the widest columns narrow to a common width.
        wanted, low, high = list(widths), 0.0, max(widths)
        for _ in range(50):
            cap = (low + high) / 2
            if sum(max(m, min(w, cap)) for w, m in zip(wanted, least)) > total:
                high = cap
            else:
                low = cap
        widths = [max(m, min(w, low)) for w, m in zip(wanted, least)]
    # Room to spare is shared out evenly, so the table keeps its width.
    spare = (total - sum(widths)) / len(widths)
    widths = [w + spare for w in widths]
    edges, x = [SUMMARY_COLS[0]], SUMMARY_COLS[0]
    for width in widths:
        x -= width
        edges.append(round(x, 2))
    edges[-1] = SUMMARY_COLS[-1]
    return edges


def summary_pages(items, language="ar"):
    """Summary tables with every value shown whole, at the reference size.

    Columns are fitted to the values (summary_columns). A value too long for
    its column still wraps inside its cell and its row grows. A page takes at
    most SUMMARY_ROWS properties (fewer when wrapped rows fill it down to the
    footer first), and its rows share the table's height evenly.
    """
    space = SUMMARY_LIMIT - SUMMARY_TOP
    cols = summary_columns(items, language)
    heads = [
        [
            line
            for line, _ in wrap_lines(
                summary_heading(key, language),
                SUMMARY_HEAD[0],
                cols[i] - cols[i + 1] - 3,
                SUMMARY_HEAD[1],
            )
        ]
        for i, key in enumerate(SUMMARY_FIELDS)
    ]
    pages, rows, needs, lines = [], [], [], []

    def close():
        heights = spread(needs, space, SUMMARY_MAX_ROW)
        bottoms, y = [], SUMMARY_TOP
        for height in heights:
            y += height
            bottoms.append(round(y, 2))
        pages.append(
            {
                "kind": "summary",
                "rows": rows,
                "bottoms": bottoms,
                "lines": lines,
                "cols": cols,
                "heads": heads,
            }
        )

    for item in items:
        texts = {
            key: cell_text(
                summary_value(item, key, language),
                cols[i] - cols[i + 1] - 4,
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


# A property's optional pages, in the guide's order; an author may reorder
# them (PropertyData.page_order).
OPTIONAL_PAGES = ("features", "boundaries", "information", "images", "rentals")


def page_order(prop):
    chosen = [k for k in prop.get("page_order") or [] if k in OPTIONAL_PAGES]
    chosen = list(dict.fromkeys(chosen))
    return chosen + [k for k in OPTIONAL_PAGES if k not in chosen]


def features_of(prop):
    return [f.strip() for f in prop.get("features", []) if f.strip()]


def info_entries(item, include_lists, with_features=True):
    """Box content in reference order: features, notes, then free text.

    Features that have their own page (guide p.17) are left out of the box.
    """
    prop = item["property_data"]
    entries = []
    if include_lists:
        features = features_of(prop) if with_features else []
        if features:
            entries.append({"heading": "features"})
            entries += [{"number": n, "text": f} for n, f in enumerate(features, 1)]
        notes = [n.strip() for n in (item.get("notes") or "").split("\n") if n.strip()]
        if notes:
            entries.append({"heading": "notes"})
            entries += [{"number": n, "text": t} for n, t in enumerate(notes, 1)]
    if prop.get("additional_information", "").strip():
        entries.append({"text": prop["additional_information"].strip()})
    landmarks = [
        m for m in prop.get("landmarks") or [] if (m.get("text") or "").strip()
    ]
    if landmarks:
        # Nearby landmarks after the text, three to a row, each beside its icon.
        entries.append({"heading": "landmarks"})
        entries += [
            {"landmarks": landmarks[i : i + LANDMARKS_PER_ROW]}
            for i in range(0, len(landmarks), LANDMARKS_PER_ROW)
        ]
    return entries


# A row of landmarks: three to a row, an icon (LANDMARK_ICON points) beside
# its name on up to two lines, set between these sizes to fit its cell.
LANDMARKS_PER_ROW = 3
LANDMARK_ICON = 18.0
LANDMARK_ROW = 26.0  # height of a row, in points
LANDMARK_SIZE, LANDMARK_MIN = 8.5, 6.5


def landmark_size(items, width):
    """The size at which every name of a row fits its cell on two lines."""
    cell = width / LANDMARKS_PER_ROW - LANDMARK_ICON - 6
    size = LANDMARK_SIZE
    while size > LANDMARK_MIN and any(
        len(wrap_lines(m["text"], size, cell * 0.96, "RuaqArabic-Light")) > 2
        for m in items
    ):
        size = round(size - 0.25, 2)
    return size


def fill_box(entries, size, width, capacity):
    """Entries that fit a text region, and the entries that continue after it."""
    shown, used = [], 0
    for index, entry in enumerate(entries):
        text = entry.get("text", "")
        indent = NUMBER_INDENT if "number" in entry else 0
        if "landmarks" in entry:
            # Its own height, in lines of this size; its names fitted to the width.
            entry = {**entry, "size": landmark_size(entry["landmarks"], width)}
            need = -(-LANDMARK_ROW // (1.4 * size))
        else:
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


def closing(auction, prop, index):
    """When bidding closes on a property (electronic auctions): its own date
    and time if given; otherwise the auction's last day, at the first closing
    time plus the interval for each property before it. Returns (date, time)
    as ISO strings, either possibly empty."""
    from datetime import date, datetime, timedelta

    from .formatting import as_date, as_time

    own_date = as_date(prop.get("auction_close_date"))
    own_time = as_time(prop.get("auction_close_time"))
    day = own_date or as_date(auction.get("auction_end_date"))
    moment = own_time
    first = as_time(auction.get("first_close_time"))
    if not moment and first:
        step = timedelta(minutes=(auction.get("close_interval_minutes") or 0) * index)
        at = datetime.combine(day or date(2000, 1, 1), first) + step
        moment = at.time()
        # Past midnight, the closing falls on the next day (unless one is given).
        if day and not own_date:
            day = at.date()
    return (day.isoformat() if day else "", moment.strftime("%H:%M") if moment else "")


def description_fit(text, layout):
    """The description set in its region (see DESCRIPTION): the size, its line
    height, the region's top, the lines printed (justified, every one within
    the width) and the text that continues on another page ("" when none)."""
    region = DESCRIPTION[layout]
    ratio = region["line"] / region["size"]
    # The block's top stays where the reference size puts the first line.
    top = region["base"] - region["line"] / 2 - region["size"] * 0.366
    room = region["bottom"] - top
    size = region["size"]
    while True:
        line = round(size * ratio, 2)
        lines = wrap_lines(text, size, region["width"] * 0.98, DESCRIPTION_FONT)
        capacity = max(1, int(room // line))
        if len(lines) <= capacity or size <= DESCRIPTION_MIN:
            break
        size = max(DESCRIPTION_MIN, round(size - 0.25, 2))
    shown, rest = lines[:capacity], lines[capacity:]
    return {
        "size": size,
        "line_height": line,
        "top": round(top, 2),
        # Every line but a paragraph's last is filled to the width.
        "lines": [
            {
                "text": row
                if last or not row
                else kashida(row, size, region["width"] * 0.985, DESCRIPTION_FONT),
                "last": last,
            }
            for row, last in shown
        ],
        "rest": "".join(t + ("\n" if last else " ") for t, last in rest).strip(),
    }


def compose(project, items):
    from .boundaries import deed_pages, deeds_differ, sides_layout
    from .facts import property_facts
    from .labels import label

    auction = project["auction"]
    cover = COVERS[auction["selected_cover_template_id"]]
    electronic = auction["auction_type"] in ("electronic", "hybrid")
    edition = auction.get("booklet_edition") or "print"
    # Guide order: cover, the supervising body (Infath), the selling agent
    # (one page each, set alike), the auction.
    from .supervisor import INFATH

    supervisor = project.get("supervisor") or INFATH
    agent = project.get("selling_agent", {})
    pages = [
        {"kind": "cover", "cover_number": cover.display_order},
        profile_page("introduction", supervisor.get("text")),
        profile_page("agent", agent.get("description")),
    ]
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
        per_deed = deeds_differ(prop)
        beside = None if per_deed else sides_layout(boundaries, layout)
        not_fit = beside is None
        if prop.get("include_boundaries_page"):
            beside = None  # the author put them on a page of their own
        separate_boundaries = beside is None
        include_info = prop.get("include_information_page", True)
        links = [k for k in LINK_ORDER if prop.get(k)] + sorted(
            k for k in prop if k.endswith("_link") and prop[k] and k not in LINK_ORDER
        )
        item["qr_links"] = [
            {"label": k, "url": prop[k], "image": qr(prop[k], "#3cbebb", 0)}
            for k in links
        ]
        # The description fills its region, set smaller when longer; what
        # does not fit even then continues on description pages.
        written = item.get("description", "") or ""
        fitted = description_fit(written.strip() or item.get("title", ""), layout)
        description = [""] + measured_chunks(fitted["rest"], *INFO_PAGE)
        # The photographs: the main one on the property's page, the
        # additional ones three to a photographs page (guide p.18), the
        # features' own on the features page.
        assets = item.get("image_assets", [])
        main_photo = assets[:1]
        own_features = [a for a in assets[1:] if a.get("category") == "features"]
        extras = [a for a in assets[1:] if a.get("category") != "features"]
        if not prop.get("include_images_page", True):
            extras = []
        # Guide p.17 and the notes (p.12): the features have a page of their
        # own, never the additional-information box.
        features = features_of(prop) if prop.get("include_features_page", True) else []
        region = info_region(layout, edition, separate_boundaries)
        shown, rest, info_size = fit_box(
            info_entries(item, include_info, with_features=False),
            INFO_SIZE,
            region["width"],
            region["lines"],
        )
        close_date, close_time = closing(auction, prop, index - 1)
        close = electronic and bool(close_date or close_time)
        pages.append(
            {
                "kind": "property",
                "item": item,
                "layout": layout,
                "variant": layout + ("-close" if close else ""),
                "close_date": close_date,
                "close_time": close_time,
                "edition": edition,
                "separate_boundaries": separate_boundaries,
                "boundaries": beside,
                "description": fitted,
                "facts": property_facts(
                    prop, layout, auction.get("document_language") or "ar"
                ),
                "info": shown,
                "info_size": info_size,
                "info_region": region,
                "additional_information": "".join(
                    e["text"] for e in shown if set(e) == {"text"}
                ),
                # Optional pages the property's data calls for whatever the
                # author chose: text that continues, boundaries that do not
                # fit (or one box per deed).
                "auto": {
                    "information": bool(
                        rest or description[1:] or item["qr_links"][PAGE_LINKS:]
                    ),
                    "boundaries": per_deed or not_fit,
                },
            }
        )
        # Each optional page group, placed after the property's page in the
        # order the author chose (page_order), else the guide's.
        groups = {key: [] for key in OPTIONAL_PAGES}
        if features:
            # A large photograph above, two smaller beneath: the features'
            # own, else the main one above and additional ones beneath.
            photos = own_features[:3] or main_photo
            while len(photos) < 3 and extras:
                photos, extras = photos + extras[:1], extras[1:]
            entries = [{"number": n, "text": f} for n, f in enumerate(features, 1)]
            listed, more, size = fit_box(entries, *FEATURES_BOX)
            groups["features"].append(
                {
                    "kind": "features",
                    "item": item,
                    "images": photos,
                    "entries": listed,
                    "size": size,
                }
            )
            for group in paginate(more, *INFO_PAGE):
                groups["features"].append(
                    {
                        "kind": "information",
                        "item": item,
                        "heading": "features",
                        "entries": group,
                        "text": "",
                    }
                )
        if per_deed:
            for group in deed_pages(
                prop,
                label("deed_box", auction.get("document_language") or "ar"),
                label("length_of", auction.get("document_language") or "ar"),
                lambda side: label(side, auction.get("document_language") or "ar"),
            ):
                groups["boundaries"].append(
                    {"kind": "boundaries", "item": item, **group}
                )
        elif separate_boundaries:
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
                groups["boundaries"].append(
                    {"kind": "boundaries", "item": item, "rows": group}
                )
        information = groups["information"]
        for group in chunks(item["qr_links"][PAGE_LINKS:], 4):
            information.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "property_links",
                    "links": group,
                    "text": "",
                }
            )
        for text in description[1:]:
            information.append(
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
                    information.append(
                        {
                            "kind": "information",
                            "item": item,
                            "heading": field,
                            "text": text,
                        }
                    )
        for group in paginate(rest, *INFO_PAGE):
            information.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "additional_information",
                    "entries": group,
                    "text": "".join(e["text"] for e in group if set(e) == {"text"}),
                }
            )
        for images in chunks(extras, 3):
            groups["images"].append({"kind": "images", "item": item, "images": images})
        rentals = [
            r
            for r in prop.get("rental_contracts", [])
            if any(v not in (None, "") for v in r.values())
        ]
        if prop.get("include_rentals_page", True):
            groups["rentals"] += rental_pages(
                item, rentals, auction.get("document_language")
            )
        for key in page_order(prop):
            pages += groups[key]
    from .terms import terms_page

    pages.append(terms_page(auction))
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
