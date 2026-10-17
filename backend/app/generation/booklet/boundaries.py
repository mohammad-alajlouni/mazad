"""The property's boundaries and lengths on its first page (guide p.15, p.19).

The four boundary descriptions stand beside their labels, each on as many
lines as it needs at a size that shrinks a little when they need more room;
the rows below move down. In portrait the lengths section (its tab and two
rows) moves down with them, as far as the additional-information tab allows.
The lengths stand two to a row, as in the guide: north and south on the
right, east and west on the left. Only boundaries that do not fit even so go
to a page of their own (see composer: separate boundaries).
"""

from .composer import text_width, wrap_lines

SIDES = ("north", "south", "east", "west")
FONT = "LamaSans-Medium"
LABEL_SIZE = 10.06
SIZE, MINIMUM = 9.6, 7.0
LINE = 1.15  # line pitch of a description's lines, per point of size
ROW_GAP = 5.0  # added space between two rows when one takes several lines
MARGIN = 0.97  # measured widths differ slightly between renderers

GEOMETRY = {
    "portrait": {
        "label": 564.8,
        "value": 486.7,
        # From the value's right edge to the photograph's frame.
        "width": 136.0,
        "first": 413.3,
        "pitch": 19.0,  # the guide's distance between two boundary rows
        "rows_end": 470.3,  # the last row's reference baseline
        # The lengths section: its tab, its two rows, and how far it may move
        # down before reaching the additional-information tab.
        "tab": (536.5, 499.6),
        "lengths": [528.3, 546.3],
        "pairs": [(564.8, 524.0, 40.0), (468.9, 428.0, 40.0)],
        "room": 42.0,
    },
    "landscape": {
        "label": 194.9,
        "value": 143.5,
        # From the value's right edge to the page margin.
        "width": 103.0,
        "first": 455.7,
        "pitch": 19.0,
        "rows_end": 512.5,
        "tab": None,  # the vertical tabs stay where the guide draws them
        "lengths": [560.6, 578.5],
        # Half of the width between the tab and the margin for each pair.
        "pairs": [(196.0, 160.0, 40.0), (112.0, 76.0, 40.0)],
        # The rows may run on to just above the lengths tab.
        "room": 20.0,
    },
}


def description_lines(text, size, width):
    lines = [line for line, _ in wrap_lines(text, size, width * MARGIN, FONT) if line]
    return lines or ["-"]


def length_size(text, width):
    full = text_width(text, LABEL_SIZE, FONT)
    if not text or full <= width * MARGIN:
        return LABEL_SIZE
    return max(MINIMUM, round(LABEL_SIZE * width * MARGIN / full, 2))


def sides_layout(boundaries, layout):
    """Where everything stands, or None when the boundaries need a page of
    their own: {"rows": [{side, base, size, lines: [{text, base}]}],
    "lengths": [{side, label, value, width, base, size, text}],
    "shift": how far the lengths section moved down}."""
    g = GEOMETRY[layout]
    texts = {s: (boundaries.get(s + "_description") or "").strip() for s in SIDES}
    size = SIZE
    while True:
        line = round(size * LINE, 2)
        rows, base = [], g["first"]
        for side in SIDES:
            lines = description_lines(texts[side], size, g["width"])
            # A row of several lines is centred on its label's line.
            first = base - (len(lines) - 1) * line / 2 if len(lines) > 1 else base
            # Rows keep clear of each other: more than a line apart.
            first = max(first, rows[-1]["bottom"] + line + ROW_GAP if rows else first)
            rows.append(
                {
                    "side": side,
                    "base": round(first + (len(lines) - 1) * line / 2, 2),
                    "size": size,
                    "lines": [
                        {"text": text, "base": round(first + i * line, 2)}
                        for i, text in enumerate(lines)
                    ],
                    "bottom": first + (len(lines) - 1) * line,
                }
            )
            base = max(base + g["pitch"], rows[-1]["bottom"] + g["pitch"] * 0.75)
        shift = max(0.0, rows[-1]["bottom"] - g["rows_end"])
        if shift <= g["room"]:
            break
        if size <= MINIMUM:
            return None
        size = max(MINIMUM, round(size - 0.2, 2))
    # The lengths: north and south on the right, east and west on the left.
    lengths = []
    for column, sides in zip(g["pairs"], (("north", "south"), ("east", "west"))):
        label, value, width = column
        for row, side in enumerate(sides):
            text = (boundaries.get(side + "_length") or "").strip() or "-"
            if "\n" in text:
                return None
            lengths.append(
                {
                    "side": side,
                    "label": label,
                    "value": value,
                    "width": width,
                    "base": round(g["lengths"][row] + (shift if g["tab"] else 0), 2),
                    "size": length_size(text, width),
                    "text": text,
                }
            )
    # A length too long for its place even at the smallest size: a page of its own.
    if any(
        text_width(item["text"], item["size"], FONT) > item["width"] * MARGIN + 0.5
        for item in lengths
    ):
        return None
    for row in rows:
        row.pop("bottom")
    return {"rows": rows, "lengths": lengths, "shift": round(shift, 2)}


# A property of several deeds whose boundaries differ: one framed box per
# deed, its number on the box's tab (the guide's boundaries page, p.16, with
# its frame and tab drawn to the height each deed needs). Boxes follow each
# other down the page; a deed longer than what is left starts on the next
# page, and one longer than a page continues in a box of its own there.
BOX = {
    "left": 25.91,
    "right": 568.52,
    "top": 36.0,  # the first tab's top
    "bottom": 747.5,  # the lowest frame bottom, above the footer
    "tab_right": 549.81,
    "tab_height": 29.92,
    "tab_min": 109.22,  # the guide's tab width
    "frame": 10.72,  # from a tab's top to its frame's top
    "first": 56.0,  # from a tab's top to the first baseline
    "gap": 8.15,  # from a frame's bottom to the next tab's top
    "pad": 22.0,  # from the last baseline to the frame's bottom
    "corner": 46.3,  # the frame's cut corner (bottom left)
    "label": 538.0,  # the lines' right edge (each side's starts with its label)
    "text_left": 56.0,
}
BOX_SIZE, BOX_LINE, BOX_ROW_GAP = 12.0, 18.0, 7.0
BOX_FONT, TITLE_FONT, TITLE_SIZE = "RuaqArabic-Light", "RuaqArabic-Medium", 13.0


def deed_numbers(prop):
    return [
        str(value or "").strip()
        for value in [prop.get("deed_number"), *(prop.get("extra_deed_numbers") or [])]
    ]


def deeds_differ(prop):
    """True when each of the property's deeds has its own boundaries box."""
    numbers = [n for n in deed_numbers(prop) if n]
    return bool(prop.get("deeds_differ")) and len(numbers) > 1


def side_text(boundaries, side, length_word):
    text = (boundaries.get(side + "_description") or "").strip()
    length = (boundaries.get(side + "_length") or "").strip()
    if length:
        text = f"{text}، {length_word} {length}" if text else f"{length_word} {length}"
    return text or "-"


def frame_path(top, bottom):
    x0, x1, c = BOX["left"], BOX["right"], BOX["corner"]
    return (
        f"M{x0} {top}L{x1} {top}L{x1} {bottom}L{x0 + c:.2f} {bottom}"
        f"L{x0} {bottom - c:.2f}L{x0} {top}"
    )


def tab_path(top, width):
    r, h = BOX["tab_right"], BOX["tab_height"]
    left = r - width
    return (
        f"M{left:.2f} {top + h:.2f}L{r - 8.59:.2f} {top + h:.2f}L{r} {top + h - 8.59:.2f}"
        f"L{r} {top}L{left + 12.43:.2f} {top}L{left:.2f} {top + 12.43:.2f}"
        f"L{left:.2f} {top + h:.2f}"
    )


def deed_pages(prop, title_word, length_word, side_label):
    """The boundaries pages of a property whose deeds differ:
    [{"boxes": [{title, tab, tab_width, top, bottom, rows: [{side, base,
    lines: [{text, base}]}]}], "frames": [paths], "tabs": [paths]}].
    Each side starts with its label ("شمالاً:"), the text running on after
    it, as in the notes' example; side_label(side) gives the label."""
    b = BOX
    width = (b["label"] - b["text_left"]) * MARGIN
    extra = prop.get("deed_boundaries") or []
    deeds = []
    for n, number in enumerate(deed_numbers(prop)):
        if not number:
            continue
        own = (
            prop.get("boundaries")
            if n == 0
            else (extra[n - 1] if n - 1 < len(extra) else {})
        )
        own = own or {}
        rows = []
        for side in SIDES:
            # The label (set a little heavier) takes the first line's start.
            head = f"{side_label(side)}: "
            lines = [
                line
                for line, _ in wrap_lines(
                    head + side_text(own, side, length_word), BOX_SIZE, width, BOX_FONT
                )
                if line
            ]
            lines[0] = lines[0][len(head) :]
            rows.append((side, lines))
        title = f"{title_word} {number}"
        tab_width = max(b["tab_min"], text_width(title, TITLE_SIZE, TITLE_FONT) + 34)
        deeds.append((title, min(tab_width, b["tab_right"] - b["left"] - 20), rows))

    pages, page, cursor = [], None, b["top"]

    def open_box(title, tab_width):
        nonlocal page, cursor
        least = b["first"] + b["pad"] + BOX_LINE  # a box shows one line at least
        if page is None or cursor + least > b["bottom"]:
            page = {"boxes": []}
            pages.append(page)
            cursor = b["top"]
        box = {
            "title": title,
            "tab": round(cursor, 2),
            "tab_width": round(tab_width, 2),
            "rows": [],
        }
        page["boxes"].append(box)
        return box, cursor + b["first"]

    def close_box(box, last):
        nonlocal cursor
        top = box["tab"] + b["frame"]
        bottom = max(last + b["pad"], top + b["corner"] + 40)
        box["top"], box["bottom"] = round(top, 2), round(bottom, 2)
        cursor = bottom + b["gap"]

    for title, tab_width, rows in deeds:
        # A deed that fits on what is left of the page stays whole; else it
        # starts on the next page.
        height = (
            b["first"]
            + b["pad"]
            + sum(len(lines) * BOX_LINE for _, lines in rows)
            + BOX_ROW_GAP * 3
            - BOX_LINE
        )
        if (
            page is not None
            and cursor + height > b["bottom"]
            and height <= b["bottom"] - b["top"]
        ):
            page = None
        box, base = open_box(title, tab_width)
        last = base
        for r, (side, lines) in enumerate(rows):
            if r:
                base += BOX_ROW_GAP
            row = None
            for n, line in enumerate(lines):
                if base + b["pad"] > b["bottom"]:
                    close_box(box, last)
                    page = None
                    box, base = open_box(title, tab_width)
                    row = None
                if row is None:
                    # The label only where the side starts, not where it
                    # continues in the next box.
                    row = {"side": side, "label": n == 0, "lines": []}
                    box["rows"].append(row)
                row["lines"].append({"text": line, "base": round(base, 2)})
                last = base
                base += BOX_LINE
        close_box(box, last)
    for page in pages:
        page["frames"] = [frame_path(x["top"], x["bottom"]) for x in page["boxes"]]
        page["tabs"] = [tab_path(x["tab"], x["tab_width"]) for x in page["boxes"]]
    return pages
