"""The guide's boards and social posts, with the auction's values.

«دليل التسويق والهوية البصرية للمزادات» (V2) shows each design once, with
sample values (pp. 28-37). scripts/extract_marketing_art.py took each design
out of the guide as it is, without its samples, and measured every sample:
its font, size, colour, baseline, alignment and room (layout.json). A page
here is that design, unchanged, with the auction's values set exactly where
and as the guide sets its samples: the same font and size (smaller only when
a value is longer than the room the guide gives it), the same colour, on the
same baseline and edge.
"""

import json
import re
from functools import lru_cache

from ..booklet.assets import ASSETS
from ..booklet.formatting import MONTHS_AR, as_date, as_time, number

ART = ASSETS / "marketing"
# The guide's fonts, by the name it embeds. Its date in the Instagram post and
# the story is set in LamaSans SemiBold, a weight the identity does not ship:
# Medium, the nearest, stands in.
FONT_FILES = {
    "RuaqArabic-Light": "identity/RuaqArabic-Light.ttf",
    "RuaqArabic-Medium": "identity/RuaqArabic-Medium.ttf",
    "RuaqArabic-Bold": "identity/RuaqArabic-Bold.ttf",
    "LamaSans-Light": "identity/LamaSans-Light.ttf",
    "LamaSans-Regular": "LamaSans-Regular.otf",
    "LamaSans-Medium": "identity/LamaSans-Medium.ttf",
    "LamaSans-SemiBold": "identity/LamaSans-Medium.ttf",
    "LamaSans-Bold": "LamaSans-Bold.otf",
    "LamaSans-Black": "identity/LamaSans-Black.ttf",
}
DEFAULT_FONT = {
    ("r", 400): "RuaqArabic-Light",
    ("r", 500): "RuaqArabic-Medium",
    ("r", 700): "RuaqArabic-Bold",
    ("l", 400): "LamaSans-Light",
    ("l", 500): "LamaSans-Medium",
    ("l", 700): "LamaSans-Bold",
    ("l", 900): "LamaSans-Black",
}
# A value longer than the guide's room is set smaller, down to this share of
# the guide's size; beyond it the value is reported at data entry.
SMALLEST = 0.6
MARGIN = 1.03  # shaping differences between the measurer and the page
# The guide's day names (its boards write الاثنين without hamza).
WEEKDAYS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
# Figures and Latin words, which the guide (and Ruaq, without Latin
# letters) leaves to Lama.
FIGURES = re.compile(r"[0-9A-Za-z]+(?:[:/.,٫'_\-]*[ ]?[0-9A-Za-z]+)*")


@lru_cache(maxsize=1)
def layout():
    return json.loads((ART / "layout.json").read_text())


@lru_cache(maxsize=16)
def font(name):
    from PIL import ImageFont

    return ImageFont.truetype(str(ASSETS / FONT_FILES[name]), 100)


@lru_cache(maxsize=32)
def dark_behind(name, box):
    """Whether the design is dark under a box (a white logo stands there)."""
    from PIL import Image, ImageStat

    image = Image.open(ART / f"{name}.png").convert("L")
    k = image.width / layout()[name]["size"][0]
    x0, y0, x1, y1 = (round(v * k) for v in box)
    return ImageStat.Stat(image.crop((x0, y0, x1, y1))).mean[0] < 128


def board_template(size, auction_type):
    from ...services.banners import SIZES

    kind = "electronic" if auction_type == "electronic" else "physical"
    return f"board-{SIZES[size]['layout']}-{kind}"


def post_template(config):
    if config["format"] == "story":
        return f"story-announcement-{config['theme']}"
    name = "instagram" if config["format"] == "instagram" else "x"
    return f"{name}-{config['post_kind']}-{config['theme']}"


# Values, written as the guide writes its samples.


def slash(day):
    return f"{day.year}/{day.month:02d}/{day.day:02d}" if day else ""


def hours(value, minutes=False, short=False):
    """04 مساء (the physical boards), 10:00 م (the electronic ones)."""
    moment = as_time(value)
    if not moment:
        return ""
    hour = moment.hour % 12 or 12
    figure = (
        f"{hour:02d}:{moment.minute:02d}" if minutes or moment.minute else f"{hour:02d}"
    )
    if short:
        return f"{figure} {'ص' if moment.hour < 12 else 'م'}"
    return f"{figure} {'صباحا' if moment.hour < 12 else 'مساء'}"


def days(a):
    if a.get("auction_type") == "electronic":
        start = as_date(a.get("auction_start_date"))
        return start, as_date(a.get("auction_end_date")) or start
    day = as_date(a.get("auction_date")) or as_date(a.get("auction_start_date"))
    return day, day


def day_line(a):
    """الخميس 11 - 14 مارس 2024, as the X post writes it."""
    start, end = days(a)
    if not start:
        return ""
    month = MONTHS_AR[start.month - 1]
    if not end or end == start:
        text = f"{start.day} {month} {start.year}"
    elif (start.year, start.month) == (end.year, end.month):
        text = f"{start.day} - {end.day} {month} {start.year}"
    else:
        text = f"{start.day} {month} - {end.day} {MONTHS_AR[end.month - 1]} {end.year}"
    return f"{WEEKDAYS[start.weekday()]} {text}"


def place(a):
    if a.get("auction_type") == "electronic":
        return a.get("electronic_platform_name") or ""
    return a.get("physical_location") or ""


def bare_name(a):
    """The auction's name beside the guide's fixed «مـزاد» (and after «في
    مزاد»): a name that starts with the word itself does not repeat it."""
    name = (a.get("auction_name") or "").strip()
    return re.sub(r"^مزاد\s+", "", name) or name


def area(value):
    text = number(value)
    return f"{text} متر مربع" if text else ""


def supervision(a, court):
    """بإشراف مركز الإسناد والتصفية - إنفاذ، و <the court>: the guide's line,
    with the court in place of its dots (the line ends at Infath without
    one)."""
    if a.get("supervisor") == "other" and a.get("supervisor_title"):
        body = f"بإشراف {a['supervisor_title']}"
    else:
        body = "بإشراف مركز الإسناد والتصفية - إنفاذ"
    return f"{body}، و{court}" if court else body


def contact_number(project):
    """The auction's own contact number, else the selling agent's (account
    settings)."""
    a = project.get("auction") or {}
    agent = project.get("selling_agent") or {}
    return a.get("auction_contact_number") or agent.get("phone") or ""


def values(project, item, count, extra):
    """Every slot's value for one page (item is None on an announcement)."""
    a = project.get("auction") or {}
    d = (item or {}).get("property_data") or {}
    if item and a.get("auction_type") in ("electronic", "hybrid"):
        # A property's bidding closes when the booklet says it does: its own
        # date and time, else the auction's closing schedule at its place.
        from ..booklet.composer import closing

        close_date, close_time = closing(a, d, item.get("position", 0))
        a = {
            **a,
            "auction_end_date": close_date or a.get("auction_end_date"),
            "end_time": close_time or a.get("end_time"),
        }
    start, end = days(a)
    start_time, end_time = a.get("start_time"), a.get("end_time")
    times = " - ".join(t for t in (hours(start_time, True), hours(end_time, True)) if t)
    return {
        "property_type": d.get("property_type") or "",
        "supervision": supervision(a, extra.get("court_name")),
        "phone": contact_number(project),
        "phone_text": contact_number(project),
        "date": slash(start),
        "time": hours(start_time),
        "day_label": f"يوم {WEEKDAYS[start.weekday()]}" if start else "",
        "start_label": f"يبدأ {WEEKDAYS[start.weekday()]}" if start else "",
        "start_date": slash(start),
        "start_time": f"الساعة {hours(start_time, True, True)}" if start_time else "",
        "end_label": f"ينتهي {WEEKDAYS[end.weekday()]}" if end else "",
        "end_date": slash(end),
        "end_time": f"الساعة {hours(end_time, True, True)}" if end_time else "",
        "place": place(a),
        # Not a slot: which place icon the line takes (guide p.13).
        "auction_type": a.get("auction_type") or "physical",
        "auction_name": bare_name(a),
        "license": a.get("license_number") or "",
        "district": d.get("district") or "",
        "usage": d.get("usage") or "",
        "area": area(d.get("area")),
        "plan_number": d.get("plan_number") or "",
        "plot_number": d.get("plot_number") or "",
        "deed": d.get("deed_number") or "",
        "execution": d.get("execution_request_number") or "",
        "city": d.get("city") or "",
        "count": str(count),
        "time_line": times,
        "date_line": day_line(a),
        "place_line": f"المكان/ {place(a)}" if place(a) else "",
        "headline": extra.get("headline") or "",
        "tagline": extra.get("tagline") or "",
        "auction_line": f"في مزاد {bare_name(a)}" if bare_name(a) else "",
    }


# Setting a value in its slot.


def main_font(slot):
    return slot.get("font") or DEFAULT_FONT[(slot["family"], slot["weight"])]


def runs(text, slot):
    """The value in runs of one font, (text, font, size, spacing): figures in
    Lama, as the guide sets them (unless the slot's figures are Ruaq's, as the
    phone's and the licence's are), each with the guide's tracking."""
    main = main_font(slot)
    spacing = slot.get("spacing", slot.get("tracking", 0) * slot["size"])
    if slot["family"] == "l" or slot.get("digits") == "r":
        return [(text, main, slot["size"], spacing)]
    figures = slot.get("lama_font") or "LamaSans-Medium"
    size = slot.get("lama_size") or slot["size"]
    tracked = slot.get("lama_tracking", 0) * size
    out, at = [], 0
    for match in FIGURES.finditer(text):
        if match.start() > at:
            out.append((text[at : match.start()], main, slot["size"], spacing))
        out.append((match.group(), figures, size, tracked))
        at = match.end()
    if at < len(text):
        out.append((text[at:], main, slot["size"], spacing))
    return out


def width(text, slot, scale=1.0):
    """The value's width in the guide's points at scale."""
    parts = runs(text, slot)
    total = sum(
        font(name).getlength(part) / 100 * size * MARGIN + spacing * len(part)
        for part, name, size, spacing in parts
    )
    words = slot.get("word_spacing", 0) * slot["size"] * text.count(" ")
    return (total + words - parts[-1][3]) * scale


def wrap(text, slot, scale, lines):
    """Words broken into at most `lines` lines of the slot's room, or None."""
    out = [""]
    for word in text.split():
        trial = f"{out[-1]} {word}".strip()
        if width(trial, slot, scale) <= slot["maxw"] or not out[-1]:
            out[-1] = trial
        elif len(out) < lines:
            out.append(word)
        else:
            return None
    if any(width(line, slot, scale) > slot["maxw"] for line in out):
        return None
    return out


def fitted(text, slot):
    """(lines, scale, fits): the value on the slot's lines, as large as the
    guide sets it or smaller to fit, down to SMALLEST."""
    count = len(slot["bases"])
    scale = 1.0
    while True:
        lines = wrap(text, slot, scale, count) if count > 1 else [text]
        if lines and (count > 1 or width(text, slot, scale) <= slot["maxw"]):
            return lines, scale, True
        if scale <= SMALLEST:
            return (lines or [text]), SMALLEST, False
        scale = max(SMALLEST, round(scale - 0.02, 2))


# The boards' supervision line keeps this far (guide points) from a box
# beside it (the property type's) or from its panel's edge, and is set on
# one line down to ONE_LINE_MIN of the guide's size; a longer one takes two
# lines where the panel has room under it (else smaller, down to SMALLEST).
SUPERVISION_GAP = 6.0
ONE_LINE_MIN = 0.7


@lru_cache(maxsize=None)
def supervision_room(name):
    """(left limit, pitch of a second line or 0) of a board's supervision
    line, measured on the design's own shapes."""
    import pymupdf

    slot = next(s for s in layout()[name]["slots"] if s["key"] == "supervision")
    x, base, size = slot["x"], slot["bases"][0], slot["size"]
    left = x - slot["maxw"]
    with pymupdf.open(ART / f"{name}.pdf") as document:
        page = document[0]
        shapes = sorted(
            (d["rect"] for d in page.get_drawings() if d.get("fill")),
            key=lambda r: r.width * r.height,
        )
        middle = base - size * 0.3
        panel = next(
            (r for r in shapes if r.contains(pymupdf.Point(x - 5, middle))), page.rect
        )
        box = next(
            (
                r
                for r in shapes
                if r.contains(pymupdf.Point(left + 2, middle))
                and r.width * r.height < panel.width * panel.height / 2
            ),
            None,
        )
    limit = (box.x1 if box else panel.x0) + SUPERVISION_GAP
    pitch = round(size * 1.25, 3)
    two = base + pitch + size * 0.3 <= panel.y1 - 2
    return max(left, limit), pitch if two else 0.0


def supervision_slot(name, slot, value):
    """The supervision slot as a board sets this value (see SUPERVISION_GAP)."""
    left, pitch = supervision_room(name)
    slot = {**slot, "maxw": round(slot["x"] - left, 3)}
    if width(value, slot, ONE_LINE_MIN) <= slot["maxw"] or not pitch:
        return slot
    base = slot["bases"][0]
    return {**slot, "bases": [base, round(base + pitch, 3)]}


def text_block(name, slot, value, geometry):
    k, ky, ox, oy = geometry
    lines, scale, fits = fitted(value, slot)
    bases = slot["bases"]
    if len(lines) < len(bases):
        # Fewer lines than the guide's: they keep the middle of its lines.
        middle = (bases[0] + bases[-1]) / 2
        step = bases[1] - bases[0] if len(bases) > 1 else 0
        first = middle - step * (len(lines) - 1) / 2
        bases = [first + step * n for n in range(len(lines))]
    size = slot["size"] * scale
    # Where the value's ink stands, in the guide's points (the logo keeps
    # clear of it).
    spans = []
    for line, base in zip(lines, bases, strict=True):
        w = width(line, slot, scale)
        x0 = {"right": slot["x"] - w, "center": slot["x"] - w / 2, "left": slot["x"]}[
            slot["align"]
        ]
        spans.append([x0, base - size * 0.85, x0 + w, base + size * 0.3])
    return {
        "key": slot["key"],
        "fits": fits,
        "extent": [
            min(e[0] for e in spans),
            min(e[1] for e in spans),
            max(e[2] for e in spans),
            max(e[3] for e in spans),
        ],
        "align": slot["align"],
        "x": round(ox + slot["x"] * k, 3),
        "lines": [
            {"text": line, "base": round(oy + base * ky, 3)}
            for line, base in zip(lines, bases, strict=True)
        ],
        "font": main_font(slot),
        "family": slot["family"],
        "size": round(size * k, 3),
        "runs": [
            [
                {
                    "text": part,
                    "font": f,
                    "size": round(s * scale * k, 3),
                    "spacing": round(sp * scale * k, 3),
                }
                for part, f, s, sp in runs(line, slot)
            ]
            for line in lines
        ],
        "color": slot["color"],
        "word_spacing": round(slot.get("word_spacing", 0) * size * k, 3),
        "spacing": round(
            slot.get("spacing", slot.get("tracking", 0) * slot["size"]) * scale * k, 3
        ),
        "width": round(slot["maxw"] * k, 3),
    }


def qr_path(url):
    """The booklet link's QR code as a path of modules (no quiet zone: the
    guide's box is the code's own edge), and its module count."""
    import qrcode

    from ..booklet.codes import qr

    qr(url)  # validates the destination
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    code.add_data(url)
    code.make(fit=True)
    rows = code.get_matrix()
    d = "".join(
        f"M{x} {y}h1v1h-1z"
        for y, row in enumerate(rows)
        for x, dark in enumerate(row)
        if dark
    )
    return d, len(rows)


def page(name, size, value_of, images):
    """One output page: name's design across size (points), its slots set.

    The design fills the page's width; a page of another proportion (the
    15 x 5 m board) has it centred on its white. A difference under 1 % (the
    guide's drawings are not cut to the exact ratio) is taken up by the
    design itself.
    """
    design = layout()[name]
    aw, ah = design["size"]
    pw, ph = size
    k = pw / aw
    if abs(ph / (ah * k) - 1) < 0.01:
        ky, oy = ph / ah, 0.0
    else:
        ky, oy = k, (ph - ah * k) / 2
    geometry = (k, ky, 0.0, oy)
    out = {
        "name": name,
        "size": [round(pw, 3), round(ph, 3)],
        "art": [0.0, round(oy, 3), round(pw, 3), round(ah * ky, 3)],
        "texts": [],
        "qr": None,
        "logo": None,
        "photo": None,
        "accent": [],
        "icons": [],
    }

    def box(b):
        x0, y0, x1, y1 = b
        return [
            round(x0 * k, 3),
            round(oy + y0 * ky, 3),
            round((x1 - x0) * k, 3),
            round((y1 - y0) * ky, 3),
        ]

    logo = icons = None
    for slot in design["slots"]:
        kind, key = slot["kind"], slot["key"]
        if kind == "text":
            value = value_of.get(key, "")
            if value and key == "supervision" and name.startswith("board-"):
                slot = supervision_slot(name, slot, value)
            if value:
                out["texts"].append(text_block(name, slot, value, geometry))
        elif kind == "qr" and images.get("qr"):
            d, n = qr_path(images["qr"])
            out["qr"] = {"box": box(slot["box"]), "path": d, "modules": n}
        elif kind == "image" and images.get("logo"):
            logo = slot  # placed once the values are: it keeps clear of them
        elif kind == "photo" and images.get("photo"):
            out["photo"] = {
                "src": images["photo"],
                "frame": slot["box"],
                "clip": slot["path"],
            }
        elif kind == "accent":
            out["accent"].append({"path": slot["path"], "color": slot["color"]})
        elif kind == "place_icon":
            icons = slot
    if icons:
        out["icons"], shift = place_icons(icons, value_of.get("auction_type"))
        for t in out["texts"]:
            if shift and t["key"] in ("place", "place_line") and t["align"] == "right":
                # Beside two icons the line starts further left.
                t["x"] = round(t["x"] - shift * k, 3)
                e = t["extent"]
                t["extent"] = [e[0] - shift, e[1], e[2] - shift, e[3]]
    if logo:
        from ..booklet.art import logo_fit

        room = logo_room(name, logo["box"], [t["extent"] for t in out["texts"]])
        x, y, w, h = box(room)
        white = dark_behind(name, tuple(logo["box"]))
        fit = logo_fit(images["logo"], w, h, white)
        out["logo"] = {
            "src": fit["src"],
            "box": [
                round(x + (w - fit["width"]) / 2, 3),
                round(y + (h - fit["height"]) / 2, 3),
                fit["width"],
                fit["height"],
            ],
        }
    out["view"] = [aw, ah]
    return out


def place_icons(slot, auction_type):
    """The place line's icon by the auction's type (guide p.13): the location
    pin for a hall, the platform for an electronic auction, both side by side
    for a hybrid one. Returns the parts to draw and how far the line moves
    left to make room (guide points)."""
    location, platform = slot["location"], slot["platform"]
    if auction_type == "electronic":
        return [dict(p, dx=0.0) for p in platform["parts"]], 0.0
    if auction_type != "hybrid":
        return [dict(p, dx=0.0) for p in location["parts"]], 0.0
    lb, pb = location["box"], platform["box"]
    gap = (lb[3] - lb[1]) * 0.35
    # Beside the line (right of it), the screen follows the pin to its left;
    # above it (the panoramic boards), the pair is centred where the pin was.
    beside = slot.get("beside", True)
    if beside:
        loc_dx, plat_dx = 0.0, (lb[0] - gap) - pb[2]
        shift = (pb[2] - pb[0]) + gap
    else:
        total = (lb[2] - lb[0]) + gap + (pb[2] - pb[0])
        centre = (lb[0] + lb[2]) / 2
        loc_dx = (centre + total / 2) - lb[2]
        plat_dx = (centre - total / 2) - pb[0]
        shift = 0.0
    return (
        [dict(p, dx=loc_dx) for p in location["parts"]]
        + [dict(p, dx=plat_dx) for p in platform["parts"]],
        shift,
    )


@lru_cache(maxsize=32)
def artwork(name):
    """The design's picture, in grey, and its pixels per guide point."""
    from PIL import Image

    image = Image.open(ART / f"{name}.png").convert("L")
    return image, image.width / layout()[name]["size"][0]


def logo_room(name, box, texts, gap=1.5):
    """The guide's box for the selling agent's logo, grown to AGENT_LOGO_SCALE
    as far as the design leaves it free: it stops short of the guide's own
    drawing and of the values beside it, and is never smaller than the
    guide's box."""
    from PIL import ImageChops

    from ..booklet.art import AGENT_LOGO_SCALE

    image, k = artwork(name)
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    inside = image.crop(tuple(round(v * k) for v in box))
    background = sorted(inside.getdata())[len(inside.getdata()) // 2]

    def free(r):
        a, b, c, d = r
        if a < 0 or b < 0 or c * k > image.width or d * k > image.height:
            return False
        for t in texts:
            if a < t[2] + gap and c > t[0] - gap and b < t[3] + gap and d > t[1] - gap:
                return False
        crop = image.crop((round(a * k), round(b * k), round(c * k), round(d * k)))
        if not crop.width or not crop.height:
            return True
        diff = ImageChops.difference(crop, crop.point(lambda _: background))
        return diff.point(lambda v: 255 if v > 40 else 0).getbbox() is None

    grow = AGENT_LOGO_SCALE - 1
    step = 0.25

    def reach(edge):
        """How far one side can move out (the others as in the guide)."""
        most = (w if edge in "lr" else h) * grow
        n = 0.0
        while n + step <= most:
            m = n + step
            strip = {
                "l": (x0 - m - gap, y0, x0, y1),
                "r": (x1, y0, x1 + m + gap, y1),
                "t": (x0, y0 - m - gap, x1, y0),
                "b": (x0, y1, x1, y1 + m + gap),
            }[edge]
            if not free(strip):
                break
            n = m
        return n

    left, right, top, bottom = (reach(e) for e in "lrtb")
    width_ = min(w * AGENT_LOGO_SCALE, w + left + right)
    height = min(h * AGENT_LOGO_SCALE, h + top + bottom)
    # Centred on the guide's box where the room allows, shifted where not.
    a = min(max((x0 + x1 - width_) / 2, x0 - left), x1 + right - width_)
    b = min(max((y0 + y1 - height) / 2, y0 - top), y1 + bottom - height)
    room = [a, b, a + width_, b + height]
    # The corners, too, are free (shrink towards the guide's box if not).
    for _ in range(40):
        if free(room) or room == [x0, y0, x1, y1]:
            break
        room = [
            room[0] + (x0 - room[0]) * 0.1,
            room[1] + (y0 - room[1]) * 0.1,
            room[2] + (x1 - room[2]) * 0.1,
            room[3] + (y1 - room[3]) * 0.1,
        ]
    return room


def banner_pages(project, items, config):
    """One board per property, in the size chosen, as the guide's p. 28-33."""
    from ...services.banners import SIZES

    from ...services.banners import court_from

    a = project.get("auction") or {}
    # The court named on the line: the campaign's, else the auction's decision.
    config = {**config, "court_name": config.get("court_name") or court_from(a)}
    name = board_template(config["size"], a.get("auction_type"))
    spec = SIZES[config["size"]]
    size = (spec["width_mm"] * 72 / 25.4, spec["height_mm"] * 72 / 25.4)
    images = {"qr": a.get("booklet_url"), "logo": project.get("agent_logo")}
    return [
        page(name, size, values(project, item, len(items), config), images)
        | {"item": item.get("title") or ""}
        for item in items
    ]


def photo_of(item):
    """A property's main photograph (its first, the main one leading)."""
    assets = item.get("image_assets") or []
    return (assets[0].get("src") if assets else "") or (item.get("images") or [""])[0]


def social_pages(project, items, config, width_px, height_px):
    """The guide's post (p. 35-37): one announcement, or one per property."""
    name = post_template(config)
    size = (width_px * 0.75, height_px * 0.75)
    base = {"logo": project.get("agent_logo")}
    if config["post_kind"] == "property" and config["format"] != "story":
        return [
            page(
                name,
                size,
                values(project, item, len(items), config),
                base | {"photo": photo_of(item)},
            )
            | {"item": item.get("title") or ""}
            for item in items
        ]
    cover = project.get("cover_image") or next(
        (photo_of(i) for i in items if photo_of(i)), ""
    )
    return [
        page(
            name,
            size,
            values(project, None, len(items), config),
            base | {"photo": cover},
        )
        | {"item": ""}
    ]


def overflows(pages):
    """Values longer than their room even at the smallest size: (page, key)."""
    return [
        {"page": n, "item": p.get("item", ""), "field": t["key"]}
        for n, p in enumerate(pages)
        for t in p["texts"]
        if not t["fits"]
    ]


def marketing_content(content):
    """The pages of a banners or social output (content as build_content
    stores it), and the fonts they use."""
    project, items = content["project"], content["items"]
    if content.get("social"):
        s = content["social"]
        pages = social_pages(project, items, s, s["width_px"], s["height_px"])
    else:
        board = content["banner"]
        sizes = board.get("item_sizes") or {}
        # Each property in its own size (the live preview of a campaign sized
        # by Infath's table); an output holds one size.
        groups = {}
        for item in items:
            groups.setdefault(sizes.get(item.get("id"), board["size"]), []).append(item)
        made = {}
        for size, group in groups.items():
            for item, made_page in zip(
                group,
                banner_pages(project, group, {**board, "size": size}),
                strict=True,
            ):
                made[id(item)] = made_page
        pages = [made[id(item)] for item in items]
    used = {
        name
        for p in pages
        for t in p["texts"]
        for name in [t["font"], *(r["font"] for line in t["runs"] for r in line)]
    }
    return {"pages": pages, "fonts": {n: FONT_FILES[n] for n in sorted(used)}}


# Slots and the entries they show, for the messages at data entry.
FIELDS = {
    "property_type": "property_type",
    "district": "district",
    "usage": "usage",
    "area": "area",
    "plan_number": "plan_number",
    "plot_number": "plot_number",
    "deed": "deed_number",
    "execution": "execution_request_number",
    "city": "city",
    "auction_name": "auction_name",
    "auction_line": "auction_name",
    "license": "license_number",
    "phone": "auction_contact_number",
    "phone_text": "auction_contact_number",
    "headline": "headline",
    "tagline": "tagline",
    "supervision": "court_name",
}


ITEM_FIELDS = {
    "property_type",
    "district",
    "usage",
    "area",
    "plan_number",
    "plot_number",
    "deed_number",
    "execution_request_number",
    "city",
}


def field_of(key, auction):
    """The entry a slot shows (None for values the booklet writes itself)."""
    if key in ("place", "place_line"):
        return (
            "electronic_platform_name"
            if auction.get("auction_type") == "electronic"
            else "physical_location"
        )
    return FIELDS.get(key)


def review(project, items, banner=None, social=None):
    """Values too long for their place in the guide's design even at the
    smallest size: (field, item title or None, characters that fit)."""
    a = project.get("auction") or {}
    if social:
        pages = social_pages({**project, "agent_logo": ""}, items, social, 1080, 1080)
        name = post_template(social)
    else:
        pages = banner_pages({**project, "agent_logo": ""}, items, banner)
        name = board_template(banner["size"], a.get("auction_type"))
    slots = {s["key"]: s for s in layout()[name]["slots"]}
    found = []
    for p in pages:
        for t in p["texts"]:
            field = field_of(t["key"], a)
            if t["fits"] or not field:
                continue
            text = " ".join(line["text"] for line in t["lines"])
            room = slots[t["key"]]["maxw"] * len(slots[t["key"]]["bases"])
            fit = int(len(text) * room / width(text, slots[t["key"]], SMALLEST))
            entry = {
                "field": field,
                "item": p.get("item") or None,
                "limit": max(1, fit),
            }
            if field not in ITEM_FIELDS:
                entry["item"] = None
            if entry not in found:
                found.append(entry)
    return found
