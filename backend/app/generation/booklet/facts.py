"""The property's facts on its first page (guide p.15 and p.19), fitted.

Each fact sits on its reference baseline, its label (teal) on the right and
its value (navy) beside it. A value too long for its line is set smaller
(fit.fact_size); the plan and plot numbers may also take further lines, and
the deeds stand under one "deed number" label, two to a line. The facts
below a longer one move down; when the column would reach what follows it,
the wrapped values are set smaller and closer until it fits.
"""

import re

from .composer import split_word, text_width
from .fit import fact_size, fact_text, fact_width, family

# Columns: label right edge, value right edge, the facts and their reference
# baselines, and the lowest baseline the column's last line may reach.
COLUMNS = {
    "portrait": [
        {
            "label": 564.8,
            "value": 486.7,
            "rows": [
                ("property_type", 189.7),
                ("deed_number", 207.7),
                ("plan_number", 225.6),
                ("plot_number", 243.6),
                ("area", 273.2),
                ("usage", 291.2),
                ("district", 309.2),
                ("participation_amount", 327.1),
                ("execution_request_number", 346.4),
            ],
            # The guide leaves a wider gap after the plot number: a longer
            # fact above it takes from that gap before moving the rest.
            "gap": (3, 11.6),
            "limit": 366.0,
        }
    ],
    "landscape": [
        {
            "label": 550.0,
            "value": 482.6,
            "rows": [
                ("property_type", 454.9),
                ("deed_number", 472.9),
                ("plan_number", 490.9),
                ("plot_number", 508.8),
            ],
            "gap": None,
            # Above the additional-information tab (its top stands at 555).
            "limit": 550.0,
        },
        {
            "label": 384.5,
            "value": 306.1,
            "rows": [
                ("area", 454.9),
                ("usage", 472.9),
                ("district", 490.9),
                ("participation_amount", 508.8),
                ("execution_request_number", 528.1),
            ],
            "gap": None,
            "limit": 552.0,
        },
    ],
}
# Values that may take more than one line, at this size and line pitch first.
WRAPPED = ("deed_number", "plan_number", "plot_number")
WRAP_SIZE, WRAP_PITCH = 8.5, 10.5
# Many deeds in a narrow column (eight in the landscape page) are set as small
# as this, lines this close for each point of size, before anything overlaps.
WRAP_FLOOR, PITCH_RATIO = 6.0, 1.12
FONT = {"l": "LamaSans-Medium", "r": "RuaqArabic-Medium"}
MARGIN = 0.96  # measured widths differ slightly between renderers


def deeds(prop):
    return [
        str(value).strip()
        for value in [prop.get("deed_number"), *(prop.get("extra_deed_numbers") or [])]
        if str(value or "").strip()
    ]


def wrap(text, size, width, fam):
    """A value broken into lines no wider than width: between words, after a
    slash ("3/471"), and inside a run too long for a line."""
    font, limit = FONT[fam], width * MARGIN
    parts = []  # each piece, and what joins it to the next
    for word in text.split():
        pieces = re.findall(r"[^/]+/?|/", word)
        parts += [
            (piece, "" if i < len(pieces) - 1 else " ")
            for i, piece in enumerate(pieces)
        ]
    lines, current = [], ""
    for piece, glue in parts:
        candidate = current + piece
        if current.strip() and text_width(candidate.rstrip(), size, font) > limit:
            lines.append(current.rstrip())
            current = piece
        else:
            current = candidate
        if text_width(current.rstrip(), size, font) > limit:
            *whole, current = split_word(current.rstrip(), size, limit, font)
            lines += whole
        current += glue
    if current.strip():
        lines.append(current.rstrip())
    # A line break separates the parts already: no separator ends or starts a line.
    lines = [re.sub(r"^\s*[-–،,]\s*|\s*[-–،,]\s*$", "", line) for line in lines]
    return [line for line in lines if line] or [""]


def deed_lines(prop, size, width):
    """The deeds two to a line ("a - b") where two fit, else one."""
    numbers, lines = deeds(prop), []
    while numbers:
        pair = f"{numbers[0]} - {numbers[1]}" if len(numbers) > 1 else ""
        if pair and text_width(pair, size, FONT["l"]) <= width * MARGIN:
            lines.append(pair)
            numbers = numbers[2:]
        else:
            lines += wrap(numbers[0], size, width, "l")
            numbers = numbers[1:]
    return lines or ["-"]


def value_lines(prop, key, layout, size, language):
    width = fact_width(layout, key)
    if key == "deed_number" and len(deeds(prop)) > 1:
        return deed_lines(prop, size, width)
    text = fact_text(prop, key, language) or "-"
    return wrap(text, size, width, family(text))


def column_facts(prop, layout, column, language):
    """One column's rows at the largest wrapped size that keeps it above its
    limit: each row is its key, label baseline, value size and family, and
    value lines with their baselines."""
    size, pitch = WRAP_SIZE, WRAP_PITCH
    while True:
        rows, shift = [], 0.0
        for n, (key, base) in enumerate(column["rows"]):
            if column["gap"] and n == column["gap"][0] + 1:
                shift = max(0.0, shift - column["gap"][1])
            text = fact_text(prop, key, language) or "-"
            fam = family(text)
            lines = [text]
            value_size = fact_size(prop, key, layout, language)
            if key in WRAPPED:
                # One line while the value fits it at the wrapped size or
                # larger; a longer one takes further lines at that size.
                many = key == "deed_number" and len(deeds(prop)) > 1
                one_line = (
                    text_width(text, size, FONT[fam])
                    <= fact_width(layout, key) * MARGIN
                )
                if many or not one_line:
                    value_size = size
                    lines = value_lines(prop, key, layout, size, language)
                    fam = "l" if many else fam
            top = base + shift
            rows.append(
                {
                    "key": key,
                    "base": round(top, 2),
                    "size": value_size,
                    "family": fam,
                    "lines": [
                        {"text": line, "base": round(top + pitch * i, 2)}
                        for i, line in enumerate(lines)
                    ],
                }
            )
            shift += pitch * (len(lines) - 1)
        bottom = rows[-1]["lines"][-1]["base"]
        if bottom <= column["limit"] or size <= WRAP_FLOOR:
            return rows
        # Smaller, and closer: two deeds then share a line in a narrow column.
        size = max(WRAP_FLOOR, round(size - 0.25, 2))
        pitch = round(size * PITCH_RATIO + 1, 2)


def property_facts(prop, layout, language="ar"):
    """Every column of the property's facts, fitted (see column_facts)."""
    return [
        {
            "label": column["label"],
            "value": column["value"],
            "rows": column_facts(prop, layout, column, language),
        }
        for column in COLUMNS[layout]
    ]
