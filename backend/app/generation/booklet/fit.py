"""Fixed booklet boxes: set a value smaller to fit, or report it at data entry.

The same measurements drive the template (font size) and the workflow checks,
so a value accepted in its step always renders without a preflight failure.
"""

from .composer import property_layout, text_width
from .formatting import money, number, uses_digits

FONTS = {
    ("r", 400): "RuaqArabic-Light",
    ("r", 500): "RuaqArabic-Medium",
    ("r", 700): "RuaqArabic-Bold",
    ("l", 400): "LamaSans-Light",
    ("l", 500): "LamaSans-Medium",
    ("l", 700): "LamaSans-Black",
}
MARGIN = 1.03  # shaping and justification differences between measurer and page


def measured(text, size, family, weight):
    return text_width(str(text), size, FONTS[(family, weight)]) * MARGIN


def fit_size(text, width, size, minimum, family="r", weight=500):
    """Largest size up to `size` at which text fits width, never below minimum."""
    full = measured(text, size, family, weight)
    if not text or full <= width:
        return size
    return max(minimum, round(size * width / full, 2))


def fits(text, width, minimum, family="r", weight=500):
    return not text or measured(text, minimum, family, weight) <= width


def longest(text, width, minimum, family="r", weight=500):
    """Approximate character count that fits, for the message shown to the user."""
    full = measured(text, minimum, family, weight)
    return max(1, int(len(text) * width / full)) if full else len(text)


# Property facts: (value width in points) per layout, and sizes 10 -> 7.5 pt.
FACT_WIDTH = {
    "landscape": {
        "property_type": 95,
        "deed_number": 95,
        "plan_number": 95,
        "plot_number": 95,
        "area": 105,
        "usage": 105,
        "district": 105,
        "participation_amount": 105,
        "execution_request_number": 150,
    },
    "portrait": {"execution_request_number": 150},
}
PORTRAIT_FACT = 140
FACT_SIZE, FACT_MINIMUM = 10, 7.5


def fact_width(layout, key):
    if layout == "portrait":
        return FACT_WIDTH["portrait"].get(key, PORTRAIT_FACT)
    return FACT_WIDTH["landscape"][key]


def fact_text(prop, key, language="ar"):
    raw = prop.get(key)
    if key == "participation_amount":
        return money(raw, language)
    if key == "area":
        return number(raw, language)
    return "" if raw in (None, "") else str(raw)


def family(text):
    return "l" if uses_digits(text) else "r"


def fact_size(prop, key, layout, language="ar"):
    text = fact_text(prop, key, language)
    # Reference sizes: figures in Lama at 10 pt, words in Ruaq at 10.06 pt.
    size = FACT_SIZE if family(text) == "l" else 10.06
    return fit_size(
        text, fact_width(layout, key), size, FACT_MINIMUM, family(text), 500
    )


# Single-line boxes outside the property page: (width, size, minimum, family, weight).
BOXES = {
    "auction_name": (315, 23.09, 14, "r", 700),
    "agent_name": (390, 19.78, 13, "r", 700),
    "physical_location": (330, 13.48, 9.5, "r", 500),
    "electronic_platform_name": (330, 13.48, 9.5, "r", 500),
    "participation_name": (200, 12.59, 8.5, "r", 400),
    # Contact page items wrap on two 118 pt lines beneath their icons; 200 pt of
    # measured text always breaks into two such lines.
    "contact_item": (200, 10.4, 7.5, "r", 500),
}


def box_size(key, text):
    width, size, minimum, fam, weight = BOXES[key]
    return fit_size(text, width, size, minimum, fam, weight)


def booklet_issues(auction, agent, items, language="ar"):
    """Values too long for their fixed booklet box even at the minimum size."""
    issues = []

    def check(section, field, text, width, minimum, fam, weight, item=None):
        if not fits(text, width, minimum, fam, weight):
            issues.append(
                {
                    "section": section,
                    "field": field,
                    "item": item,
                    "limit": longest(text, width, minimum, fam, weight),
                }
            )

    name = auction.get("auction_name", "")
    for key, section, text in (
        ("auction_name", "auction", name),
        ("physical_location", "auction", auction.get("physical_location", "")),
        (
            "electronic_platform_name",
            "auction",
            auction.get("electronic_platform_name", ""),
        ),
        ("agent_name", "agent", agent.get("name", "")),
    ):
        width, _, minimum, fam, weight = BOXES[key]
        check(section, key, text, width, minimum, fam, weight)
    width, _, minimum, fam, weight = BOXES["contact_item"]
    for key in ("physical_location", "electronic_platform_name"):
        check("auction", key, auction.get(key, ""), width, minimum, fam, weight)
    if auction.get("auction_type") in ("electronic", "hybrid"):
        width, _, minimum, fam, weight = BOXES["participation_name"]
        check(
            "auction",
            "auction_name",
            f"إختيار مزاد ( {name} )",
            width,
            minimum,
            fam,
            weight,
        )
    for item in items:
        prop = item["property_data"]
        layout = property_layout(item)
        for key in FACT_WIDTH["landscape"]:
            text = fact_text(prop, key, language)
            check(
                "items",
                key,
                text,
                fact_width(layout, key),
                FACT_MINIMUM,
                family(text),
                500,
                item.get("title"),
            )
    return issues
