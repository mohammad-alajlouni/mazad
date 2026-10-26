"""Where the guide's boards (p.28-33) and social posts (p.35-37) put each
value, in the guide's own page coordinates (points).

scripts/extract_marketing_art.py reads this with the guide itself: it takes
each design ("مثال") out of its page as vectors, removes what varies (the
sample values, the placeholders, the photograph) and measures every slot from
the guide's own text (font, size, colour, baseline and alignment), writing
templates/infath/assets/marketing/. Nothing here is drawn by hand: the fixed
design is the guide's, and each value takes the place of the guide's sample.

Slot kinds:
- text: the guide's sample spans (matched by their text, "at" the nearest
  point when the sample repeats) are replaced by the value, set in their font,
  size and colour on their baseline, aligned as given;
- line: a value where the guide drew its sample as outlines: the outlines in
  "erase" go, the value is set as given (size, baseline, alignment);
- phone: the contact number, outlined in the guide: its font size and letter
  spacing are measured from the outlines;
- qr / image: a box the value fills (the booklet's QR code, the agent's logo);
- photo: the photograph's own cut-corner frame (the guide's clip path);
- icon: the auction icon, laid over the guide's small raster one;
- accent: the coloured block behind a headline's first word, moved with it.
"""

B = "board"
TEAL, NAVY, WHITE = "#00a3a2", "#121a45", "#ffffff"


def T(key, *spans, align="right", maxw=None, at=None, lines=1):
    return {
        "key": key,
        "kind": "text",
        "spans": list(spans),
        "align": align,
        "maxw": maxw,
        "at": at,
        "lines": lines,
    }


def L(
    key, erase, x, base, size, color, align="right", maxw=60, weight=500, sample=None
):
    return {
        "sample": sample,
        "key": key,
        "kind": "line",
        "erase": erase,
        "x": x,
        "base": base,
        "size": size,
        "color": color,
        "align": align,
        "maxw": maxw,
        "weight": weight,
    }


def BOX(key, kind, erase, box=None):
    return {"key": key, "kind": kind, "erase": erase, "box": box or erase}


FACTS = ("district", "area", "plan_number", "plot_number", "deed", "execution")


def facts(spans):
    """The facts' values under their tabs: (key, sample, centre, tab width)."""
    return [T(k, *s, align="center", maxw=w, at=at) for k, s, at, w in spans]


BOARDS = {
    # p.28 - the panoramic board (10 x 3 m, 15 x 5 m), at the hall.
    "board-panoramic-physical": {
        "page": 28,
        "board": [97.88, 287.27, 661.26, 456.15],
        "stroke": 0.515,
        "slots": [
            BOX("qr", "qr", [118, 311.5, 155.5, 348], [120.3, 313.1, 153.5, 346.3]),
            T("property_type", "فيلا سكنية", align="center", maxw=78),
            T("supervision", "بإشراف", maxw=345),
            {
                "key": "phone",
                "kind": "phone",
                "erase": [460, 386, 652, 413],
                "align": "right",
                "maxw": 215,
                "sample": "920011513",
            },
            T("date", "2023/11/01", maxw=44),
            T("time", "04", "مساء", maxw=40),
            T("place", "قاعة جدة البحر", align="center", maxw=70),
            T("auction_name", "درة البحر", maxw=40),
            BOX("agent_logo", "image", [180, 395.5, 237, 416.5], [181, 396, 236, 416]),
            T("license", "4 2 0 00 00 1 07", align="center", maxw=62),
            *facts(
                [
                    ("district", ["النور"], (553.7, 448), 46),
                    ("area", ["9271.71", "متر مربع"], (497.1, 448), 51),
                    ("plan_number", ["10"], (435.9, 448), 51),
                    ("plot_number", ["10"], (379.4, 448), 51),
                    ("deed", ["430107012766"], (305.5, 448), 73),
                    ("execution", ["154584687412365"], (213.6, 448), 87),
                ]
            ),
        ],
    },
    # p.29 - the panoramic board of an electronic auction.
    "board-panoramic-electronic": {
        "page": 29,
        "board": [97.88, 287.27, 661.26, 456.15],
        "stroke": 0.515,
        "slots": [
            BOX("qr", "qr", [117.5, 312, 151.5, 345.5], [119.6, 313.7, 149.8, 343.9]),
            T("property_type", "فيلا سكنية", align="center", maxw=76),
            T("supervision", "بإشراف", maxw=345),
            {
                "key": "phone",
                "kind": "phone",
                "erase": [474, 381, 653, 406],
                "align": "right",
                "maxw": 200,
                "sample": "920011513",
            },
            T("start_label", "يبدأ الاثنين", maxw=42),
            T("start_date", "2024/11/01", maxw=42),
            T("start_time", "الساعة", "10:00", "م", maxw=42, at=(436, 402)),
            T("end_label", "ينتهي الخميس", maxw=42),
            T("end_date", "2024/11/04", maxw=42),
            T("end_time", "الساعة", "06:00", "م", maxw=42, at=(380, 402)),
            T("place", "قاعة جدة البحر", align="center", maxw=60),
            T("auction_name", "درة البحر", maxw=38),
            BOX("agent_logo", "image", [177, 391.5, 234, 411.5], [178, 392, 233, 411]),
            T("license", "4 2 0 00 00 1 07", align="center", maxw=62),
            *facts(
                [
                    ("district", ["النور"], (568.6, 446), 50),
                    ("area", ["9271.71", "متر مربع"], (508.2, 446), 55),
                    ("plan_number", ["10"], (442.8, 446), 55),
                    ("plot_number", ["10"], (382.5, 446), 55),
                    ("deed", ["430107012766"], (303.5, 446), 78),
                    ("execution", ["154584687412365"], (205.4, 446), 93),
                ]
            ),
        ],
    },
    # p.30 - the landscape board (4 x 2, 6 x 3, 10 x 5 m), at the hall.
    "board-landscape-physical": {
        "page": 30,
        "board": [197.95, 287.35, 635.94, 506.35],
        "stroke": 0.579,
        "slots": [
            BOX("qr", "qr", [219.5, 312, 277, 369.5], [221.8, 314.4, 274.8, 367.3]),
            T("property_type", "فيلا سكنية", align="center", maxw=100),
            T("supervision", "بإشراف", maxw=190),
            T("day_label", "يوم الأربعاء", maxw=34),
            T("date", "2023/11/01", maxw=34),
            T("time", "04", "مساء", maxw=34),
            T("place", "قاعة جدة البحر", maxw=36),
            {
                "key": "phone",
                "kind": "phone",
                "erase": [217, 436, 402, 463],
                "align": "left",
                "maxw": 185,
                "sample": "920011513",
            },
            T("license", "4 2 0 00 00 1 07", align="center", maxw=62),
            T("auction_name", "درة البحر", maxw=34),
            BOX(
                "agent_logo", "image", [500, 444.5, 557.5, 463.5], [501, 445, 557, 463]
            ),
            *facts(
                [
                    ("district", ["النور"], (556.0, 495), 40),
                    ("usage", ["تجاري"], (507.6, 495), 40),
                    ("area", ["9271.71", "متر مربع"], (461.5, 495), 40),
                    ("plan_number", ["10"], (415.0, 495), 40),
                    ("plot_number", ["10"], (367.7, 495), 40),
                    ("deed", ["430107012766"], (320.1, 495), 40),
                    ("execution", ["154584687412365"], (272.7, 495), 40),
                ]
            ),
        ],
    },
    # p.31 - the landscape board of an electronic auction.
    "board-landscape-electronic": {
        "page": 31,
        "board": [209.49, 293.67, 590.33, 484.09],
        "stroke": 0.579,
        "slots": [
            BOX("qr", "qr", [230, 322, 273.5, 365.5], [232.2, 324.2, 271.4, 363.4]),
            T("property_type", "فيلا سكنية", align="center", maxw=95),
            T("supervision", "بإشراف", maxw=140),
            T("start_label", "يبدأ الاثنين", maxw=36),
            T("start_date", "2024/11/01", maxw=36),
            T("start_time", "الساعة", "10:00", "م", maxw=36, at=(541, 374)),
            T("end_label", "ينتهي الخميس", maxw=36),
            T("end_date", "2024/11/04", maxw=36),
            T("end_time", "الساعة", "06:00", "م", maxw=36, at=(541, 388)),
            T("place", "قاعة جدة البحر", maxw=36),
            {
                "key": "phone",
                "kind": "phone",
                "erase": [216, 420, 390, 445],
                "align": "left",
                "maxw": 172,
                "sample": "920011513",
            },
            T("license", "4 2 0 00 00 1 07", align="center", maxw=56),
            T("auction_name", "درة البحر", maxw=30),
            BOX("agent_logo", "image", [472, 430, 522, 446], [473, 431, 521.5, 445.5]),
            *facts(
                [
                    ("district", ["النور"], (531.2, 474), 35),
                    ("area", ["9271.71", "متر مربع"], (489.6, 474), 38),
                    ("plan_number", ["10"], (444.6, 474), 38),
                    ("plot_number", ["10"], (403.2, 474), 38),
                    ("deed", ["430107012766"], (348.8, 474), 54),
                    ("execution", ["154584687412365"], (281.3, 474), 64),
                ]
            ),
        ],
    },
}

# p.32 - the square board (2 x 2 m), at the hall or hybrid; p.33 electronic.
# Both draw their schedule, property type and licence as outlines.
SQUARE = [
    BOX("qr", "qr", None, None),
    {
        "key": "property_type",
        "kind": "line",
        "erase": [99, 357, 153, 373],
        "fit": [100.88, 151.64, "فيلا سكنية", "r", 500],
        "align": "center",
        "x": 126.26,
        "color": WHITE,
        "maxw": 90,
    },
    T("supervision", "بإشراف", maxw=165),
    {
        "key": "phone",
        "kind": "phone",
        "erase": None,
        "align": "left",
        "maxw": 200,
        "sample": "920011513",
    },
    T("auction_name", "درة البحر", maxw=34),
    BOX("icon", "icon", None, None),
    *facts(
        [
            ("district", ["النور"], (332.9, 453), 33),
            ("usage", ["تجاري"], (290.7, 453), 33),
            ("area", ["9271.71", "متر مربع"], (250.4, 453), 33),
            ("plan_number", ["10"], (209.9, 453), 33),
            ("plot_number", ["10"], (168.7, 453), 33),
            ("deed", ["430107012766"], (127.3, 453), 33),
            ("execution", ["154584687412365"], (86.0, 453), 33),
        ]
    ),
]


P33_FACTS = {
    s["key"]: s
    for s in facts(
        [
            ("district", ["النور"], (260.9, 453.5), 26),
            ("usage", ["تجاري"], (230.1, 453.5), 26),
            ("area", ["9271.71", "متر مربع"], (200.9, 453.5), 26),
            ("plan_number", ["10"], (171.3, 453.5), 26),
            ("plot_number", ["10"], (141.3, 453.5), 26),
            ("deed", ["430107012766"], (111.1, 453.5), 26),
            ("execution", ["154584687412365"], (81.0, 453.5), 26),
        ]
    )
}


def square(page, schedule, phone_erase, licence, qr, agent, icon):
    slots = []
    for slot in SQUARE:
        slot = dict(slot)
        if slot["key"] == "qr":
            slot["erase"], slot["box"] = qr
        if slot["key"] == "phone":
            slot["erase"] = phone_erase
        if slot["key"] == "icon":
            slot["erase"] = slot["box"] = icon
        if page == 33 and slot["key"] in P33_FACTS:
            slot = P33_FACTS[slot["key"]]
        if page == 33 and slot["key"] == "property_type":
            slot["erase"] = [99, 356, 153, 372]
            slot["fit"] = [100.88, 151.64, "فيلا سكنية", "r", 500]
        slots.append(slot)
    return slots + schedule + [licence, BOX("agent_logo", "image", *agent)]


BOARDS["board-square-physical"] = {
    "page": 32,
    "board": [56.48, 161.07, 359.86, 464.44],
    "stroke": 0.622,
    "slots": square(
        32,
        [
            {
                "key": "day_label",
                "kind": "line",
                "erase": [290, 243.5, 317, 251],
                "fit": [292.06, 315.34, "يوم الأربعاء", "r", 500],
                "align": "right",
                "x": 315.34,
                "color": WHITE,
                "maxw": 30,
            },
            {
                "key": "date",
                "kind": "line",
                "erase": [291, 251.2, 316.5, 256],
                "fit": [292.86, 315.21, "2023/11/01", "l", 500],
                "align": "right",
                "x": 315.21,
                "color": WHITE,
                "maxw": 30,
            },
            {
                "key": "time",
                "kind": "line",
                "erase": [295.5, 263.5, 317, 269.5],
                "fit": [297.33, 315.81, "04 مساء", "r", 500],
                "align": "right",
                "x": 315.81,
                "color": WHITE,
                "maxw": 30,
            },
            {
                "key": "place",
                "kind": "line",
                "erase": [287, 281, 317, 288],
                "fit": [288.79, 315.49, "قاعة جدة البحر", "r", 500],
                "align": "right",
                "x": 315.49,
                "color": WHITE,
                "maxw": 30,
            },
        ],
        [66, 396, 263, 424],
        {
            "key": "license",
            "kind": "line",
            "erase": [279.5, 410.5, 346, 421],
            "fit": [281.07, 344.0, "4200000107", "r", 500, "spaced"],
            "align": "center",
            "x": 312.54,
            "color": "#434245",
            "maxw": 66,
        },
        ([186.5, 345, 218.5, 377], [188.66, 347.12, 216.49, 374.95]),
        ([288, 354, 335, 369.5], [289, 355, 334, 369]),
        [319, 305, 333, 323],
    ),
}
BOARDS["board-square-electronic"] = {
    "page": 33,
    "board": [56.48, 161.07, 359.86, 464.44],
    "stroke": 0.622,
    "slots": square(
        33,
        [
            T("start_label", "يبدأ الاثنين", maxw=32),
            T("start_date", "2024/11/01", maxw=32),
            T("start_time", "الساعة", "10:00", "م", maxw=32, at=(306, 250)),
            T("end_label", "ينتهي الخميس", maxw=32),
            T("end_date", "2024/11/04", maxw=32),
            T("end_time", "الساعة", "06:00", "م", maxw=32, at=(306, 273)),
            T("place", "قاعة جدة البحر", maxw=32),
        ],
        [66, 396, 276, 425],
        {
            "key": "license",
            "kind": "line",
            "erase": [292, 425.5, 347.5, 434],
            "fit": [293.52, 345.76, "4200000107", "r", 500, "spaced"],
            "align": "center",
            "x": 319.64,
            "color": "#434245",
            "maxw": 66,
        },
        ([185.5, 346.5, 217.5, 378.5], [187.62, 348.54, 215.4, 376.32]),
        ([288, 348, 336, 363], [289, 349, 335, 362.5]),
        [320, 304, 334, 321],
    ),
}


def value_box(key, r, size, color):
    """A value in one of the property post's boxes, the guide's fields: the
    box stays, the value is written in it from its right."""
    return L(
        key,
        None,
        r[2] - 1.2,
        r[3] - (r[3] - r[1] - size * 0.72) / 2 - 0.1,
        size,
        color,
        maxw=r[2] - r[0] - 2.4,
    )


# The X post's lines, drawn as outlines, left to right as the guide sets them.
X_LINES = {
    "time_line": "04:00 مساءً - 10:00 مساءً",
    "date_line": "الخميس 11 - 14 مارس 2024",
    "place_line": "المكان / اسم المنصة",
}


def x_post(white, kind, d):
    """The X post (p.35): white on the right, teal on the left."""
    color = TEAL if white else WHITE
    slots = [
        BOX("agent_logo", "image", d["agent"], d["agent"]),
        T("auction_name", "درة البحر", maxw=36),
        {"key": "photo", "kind": "photo", "clip": d["clip"]},
        BOX("icon", "icon", None, d["icon"]),
    ]
    for key, (erase, x, base) in d["lines"].items():
        slots.append(
            L(
                key,
                erase,
                x,
                base,
                4.12,
                color,
                maxw=d.get("linew", 48),
                sample=X_LINES[key],
            )
        )
    if kind == "announcement":
        slots.append(T("count", "4", maxw=40))
    for key, r in d.get("boxes", {}).items():
        slots.append(value_box(key, r, 4.6, "#00365d" if white else WHITE))
    return slots


def ig_post(white, kind, d):
    """The Instagram post (p.36): white on the right, teal on the left."""
    slots = [
        T("auction_name", "درة البحر", align="center", maxw=24),
        {"key": "photo", "kind": "photo", "clip": d["clip"]},
        BOX("agent_logo", "image", d["agent"], d["agent"]),
        BOX("icon", "icon", None, d["icon"]),
        T("count", "4", align="center", maxw=7),
        T("day_label", "يوم الأربعاء", align="center", maxw=26),
        T("date", "2023/11/01", align="center", maxw=26),
        T("place", "معارض الظهران الدولية", "(اكسبو الظهران)", maxw=48, lines=2),
    ]
    if kind == "announcement":
        slots += [
            {"key": "accent", "kind": "accent", "rect": d["accent"]},
            T("headline", "نص تجريبي", maxw=84),
            T("phone_text", "920011513", maxw=52),
        ]
    for key, r in d.get("boxes", {}).items():
        slots.append(value_box(key, r, 3.3, "#00365d" if white else WHITE))
    return slots


X = {
    "x-announcement-white": {
        "board": [439.88, 97.55, 676.68, 241.83],
        "clip": [450.65, 109.58, 581.99, 231.36],
        "agent": [596.5, 107.5, 633, 121],
        "icon": [650, 136, 661, 150],
        "lines": {
            "time_line": ([599, 193.5, 650.4, 202], 649.13, 200.25),
            "date_line": ([599, 207.5, 650.4, 214], 648.94, 212.44),
            "place_line": ([609.5, 219.5, 650.4, 226.5], 649.11, 224.06),
        },
    },
    "x-announcement-teal": {
        "board": [170.05, 97.2, 407.55, 242.18],
        "clip": [181.3, 108.46, 312.65, 231.36],
        "agent": [326.5, 107.5, 363, 121],
        "icon": [380, 135, 392, 150],
        "lines": {
            "time_line": ([330, 193.5, 381, 202], 379.79, 200.25),
            "date_line": ([330, 207.5, 380, 214], 378.55, 212.44),
            "place_line": ([340, 220, 381.5, 227.5], 379.96, 225.01),
        },
    },
    "x-property-white": {
        "board": [439.88, 271.84, 676.68, 416.12],
        "clip": [449.49, 278.26, 550.27, 381.56],
        "agent": [598, 281, 634, 295],
        "icon": [646, 312, 660, 329],
        "linew": 46,
        "lines": {
            "time_line": ([600, 401, 648.5, 407], 647.56, 405.04),
            "date_line": ([531, 401, 580.5, 407], 579.99, 405.06),
            "place_line": ([469.5, 401, 509, 407.2], 508.40, 405.10),
        },
        "boxes": {
            "property_type": [614.51, 347.32, 652.28, 354.05],
            "district": [564.55, 347.32, 602.32, 354.05],
            "area": [614.51, 364.25, 652.28, 370.98],
            "city": [564.55, 364.25, 602.32, 370.98],
            "deed": [583.43, 384.97, 652.28, 391.7],
        },
    },
    "x-property-teal": {
        "board": [170.05, 271.49, 407.55, 416.47],
        "clip": [178.44, 278.26, 279.21, 381.56],
        "agent": [322.5, 281, 363, 295],
        "icon": [375, 312, 389, 329],
        "linew": 46,
        "lines": {
            "time_line": ([329.5, 401, 377.5, 407], 376.9, 405.04),
            "date_line": ([260, 401, 309.8, 407], 308.28, 405.06),
            "place_line": ([199, 401, 238.5, 407.2], 237.74, 405.10),
        },
        "boxes": {
            "property_type": [343.45, 347.32, 381.22, 354.05],
            "district": [293.49, 347.32, 331.26, 354.05],
            "area": [343.45, 364.25, 381.22, 370.98],
            "city": [293.49, 364.25, 331.26, 370.98],
            "deed": [312.37, 384.97, 381.22, 391.7],
        },
    },
}
IG = {
    "instagram-announcement-white": {
        "board": [455.93, 89.92, 617.95, 251.93],
        "clip": [462.28, 115.63, 610.34, 187.55],
        "accent": [592.2, 194.97, 607.28, 209.32],
        "agent": [462, 224, 481.5, 245.5],
        "icon": [490, 223, 499, 235],
    },
    "instagram-announcement-teal": {
        "board": [272.12, 89.59, 434.79, 252.26],
        "clip": [280.14, 116.09, 425.09, 186.46],
        "accent": [406.82, 194.97, 421.9, 209.32],
        "agent": [280, 222, 299, 242.5],
        "icon": [307, 222, 316, 232],
    },
    "instagram-property-white": {
        "board": [455.93, 269.35, 617.95, 431.37],
        "clip": [462.28, 295.07, 608.38, 366.99],
        "agent": [465, 411, 503, 422.5],
        "icon": [586, 372, 599, 389],
        "boxes": {
            "property_type": [536.34, 388.01, 562.66, 392.7],
            "district": [501.27, 388.01, 527.6, 392.7],
            "area": [468.69, 388.01, 495.02, 392.7],
            "city": [536.34, 401.06, 562.66, 405.75],
            "deed": [479.62, 401.06, 527.6, 405.75],
        },
    },
    "instagram-property-teal": {
        "board": [272.12, 269.03, 434.79, 431.7],
        "clip": [279.37, 295.07, 427.53, 366.99],
        "agent": [282.5, 411, 320, 422.5],
        "icon": [403, 372, 416, 389],
        "boxes": {
            "property_type": [353.43, 388.01, 379.76, 392.7],
            "district": [318.37, 388.01, 344.69, 392.7],
            "area": [285.79, 388.01, 312.11, 392.7],
            "city": [353.43, 401.06, 379.76, 405.75],
            "deed": [296.71, 401.06, 344.69, 405.75],
        },
    },
}


def story(name, white):
    """The story (p.37): white, and the teal and navy "further options"."""
    s = {
        "white": {
            "clip": [417.42, 164.97, 556.37, 254.84],
            "accent": [522.2, 266.59, 544.24, 287.57],
            "agent": ([430, 380, 480, 395.5], [430.5, 380.5, 479.5, 395]),
            "icon": [521, 379, 535, 397],
            "erase": [386, 213, 458.5, 264],
            "w": 162,
        },
        "teal": {
            "clip": [599.6, 259.37, 685.48, 314.92],
            "accent": [664.23, 319.21, 677.78, 332.1],
            "agent": ([613, 389.5, 643, 400], [613.5, 390, 642.5, 399.5]),
            "icon": [662, 390, 670, 400],
            "w": 100,
        },
        "navy": {
            "clip": [723.27, 259.37, 809.15, 314.92],
            "accent": [787.78, 319.21, 801.32, 332.1],
            "agent": ([737, 389.5, 766.5, 400], [737.5, 390, 766, 399.5]),
            "icon": [786, 390, 794, 400],
            "w": 100,
        },
    }[name]
    k = s["w"] / 162
    slots = [
        {"key": "photo", "kind": "photo", "clip": s["clip"]},
        {"key": "accent", "kind": "accent", "rect": s["accent"]},
        T("headline", "نص تجريبي", maxw=130 * k),
        T("tagline", "في وجهة واعدة استثماريا", align="center", maxw=135 * k),
        T("auction_line", "في مزاد درة البحر", align="center", maxw=135 * k),
        T("phone_text", "920011513", align="center", maxw=62 * k),
        T("day_label", "يوم الأربعاء", maxw=38 * k),
        T("date", "2023/11/01", maxw=38 * k),
        T("place", "معارض الظهران الدولية", "(اكسبو الظهران)", maxw=54 * k, lines=2),
        T("auction_name", "درة البحر", maxw=26 * k),
        BOX("agent_logo", "image", *s["agent"]),
        BOX("icon", "icon", None, s["icon"]),
    ]
    if "erase" in s:
        slots.append({"key": "stray", "kind": "erase", "erase": s["erase"]})
    return slots


POSTS = {
    **{
        name: {
            "page": 35,
            "board": d["board"],
            "slots": x_post("white" in name, name.split("-")[1], d),
        }
        for name, d in X.items()
    },
    **{
        name: {
            "page": 36,
            "board": d["board"],
            "slots": ig_post("white" in name, name.split("-")[1], d),
        }
        for name, d in IG.items()
    },
    "story-announcement-white": {
        "page": 37,
        "board": [405.96, 123.22, 567.84, 411.7],
        "slots": story("white", True),
    },
    "story-announcement-teal": {
        "page": 37,
        "board": [592.23, 233.29, 692.85, 412.16],
        "slots": story("teal", False),
    },
    "story-announcement-navy": {
        "page": 37,
        "board": [715.9, 233.29, 816.52, 412.16],
        "slots": story("navy", False),
    },
}
TEMPLATES = {**BOARDS, **POSTS}

# The place line's icon (guide p.13): the location pin for an auction held in
# a hall, the platform (a screen) for an electronic one, both for a hybrid.
# Each design's own icon is taken out of it (these boxes) and set again by the
# auction's type; the platform icon is the guide's own (the teal X post on
# p.35 draws it), in each design's colours.
PLACE_ICONS = {
    "board-panoramic-physical": [346.84, 388.82, 355.75, 397.35],
    "board-panoramic-electronic": [334.6, 385.89, 344.51, 395.37],
    "board-landscape-physical": [601.9, 407.8, 617.1, 422.4],
    "board-landscape-electronic": [557.0, 394.7, 565.0, 402.4],
    "board-square-physical": [321.4, 276.6, 333.9, 288.5],
    "board-square-electronic": [324.8, 280.2, 334.0, 289.0],
    "x-announcement-white": [653.54, 219.65, 658.63, 226.44],
    "x-announcement-teal": [382.51, 218.56, 390.7, 226.63],
    "x-property-white": [512.81, 400.2, 517.9, 406.98],
    "x-property-teal": [242.15, 400.2, 247.23, 406.98],
    "instagram-announcement-white": [559.34, 232.06, 566.74, 239.15],
    "instagram-announcement-teal": [375.1, 230.0, 382.34, 236.93],
    "instagram-property-white": [563.13, 412.28, 570.08, 418.93],
    "instagram-property-teal": [380.22, 412.28, 387.17, 418.93],
    "story-announcement-white": [548.07, 353.31, 556.65, 361.52],
    "story-announcement-teal": [680.11, 374.52, 685.42, 379.6],
    "story-announcement-navy": [803.66, 374.52, 808.96, 379.6],
}
# The design that draws the platform icon, and where that design's location
# pin is taken from instead (its sibling on the same page).
PLATFORM_SOURCE = "x-announcement-teal"
LOCATION_SIBLING = {"x-announcement-teal": "x-property-teal"}
for _name, _box in PLACE_ICONS.items():
    TEMPLATES[_name]["slots"].append(
        {"key": "place_icon", "kind": "place_icon", "box": _box}
    )
