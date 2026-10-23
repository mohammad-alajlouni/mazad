"""Where the Real Estate General Authority's two report templates hold their
values (read by scripts/extract_report_art.py, which measures each one from
the template itself).

- The auction closing form («نموذج إقفال المزاد العقاري»): the authority's own
  page, its table filled row by row.
- The outputs report («تقرير مخرجات»): the template's fourteen pages, each
  kept as it is without the auction's own content (its name, the selling
  agent's logo, dates, figures, photographs and screenshots), which is set
  again where the template sets it.

Coordinates are the template's points (y down). A text slot names its sample
in the template (matched as in the marketing extractor); the extractor reads
its font, size, colour, baseline and edge.
"""

# The selling agent's logo (top left of every page) and the auction's name
# under «مزاد» (bottom right of every page but the last).
LOGO = [78, 78, 184, 152]
FOOTER = {
    "key": "footer_name",
    "kind": "text",
    "sample": "أعيان حائل",
    "align": "right",
}


def text(key, sample, align="right", at=None):
    return {"key": key, "kind": "text", "sample": sample, "align": align, "at": at}


def para(key, samples, pitch):
    """A paragraph, justified between the template's edges, on its lines."""
    return {"key": key, "kind": "para", "samples": samples, "pitch": pitch}


PAGES = {
    "cover": {
        "page": 1,
        "slots": [
            text("title", "مزاد أعيان حائل", "center"),
            text("court", "وبقرار من محكمة التنفيذ", "center"),
            text("period", "خلال الفترة من", "center"),
        ],
    },
    "contents": {"page": 2, "slots": []},
    "intro": {
        "page": 3,
        "slots": [
            para(
                "intro",
                [
                    "تم إسناد مزاد",
                    "وبقرار من محكمة التنفيذ،وذلك",
                    ".البيع",
                    "يهدف هذا التقرير",
                    "إقامة المزاد، متضمنًا",
                    "الأصول المباعة وغير",
                    ".المعتمدة",
                ],
                42.0,
            )
        ],
    },
    "marketing": {"page": 4, "slots": []},
    "boards": {
        "page": 5,
        "slots": [
            text("boards_line", "وفق الخطة المعتمدة، وتمت إزالتها"),
            {
                "key": "boards_table",
                "kind": "table",
                "region": [280, 282, 1120, 665],
                # Installation and removal dates: one cell down the table.
                "merged": [0, 1],
                "body": [287, 322, 1112, 659],
                "sample": "الخطة",
            },
        ],
    },
    "board_photos": {
        "page": 6,
        "slots": [{"key": "photos", "kind": "images", "region": [270, 240, 1130, 640]}],
    },
    "channels": {
        "page": 7,
        "slots": [
            {
                "key": "channels_table",
                "kind": "table",
                "region": [270, 244, 1115, 470],
                "keep": True,  # the channels are the template's own four rows
                "merged": [],
                "body": [277, 293, 840, 463],
                "sample": "600",
            }
        ],
    },
    "x": {
        "page": 8,
        "slots": [
            text("x_line", "منشورات عبر الحساب الرسمي"),
            {"key": "x_shots", "kind": "images", "region": [290, 280, 1110, 560]},
        ],
    },
    "tiktok": {
        "page": 9,
        "slots": [
            text("tiktok_line", "فيديوهات عبر منصة تيك توك"),
            {
                "key": "tiktok_shots",
                "kind": "frames",
                "frames": [[482, 300, 646, 624], [786, 300, 952, 629]],
            },
        ],
    },
    "whatsapp": {
        "page": 10,
        "slots": [
            {
                "key": "whatsapp_shots",
                "kind": "frames",
                "frames": [[455, 302, 704, 647], [750, 302, 998, 647]],
            }
        ],
    },
    "youtube": {
        "page": 11,
        "slots": [
            {"key": "youtube_shot", "kind": "images", "region": [410, 276, 1000, 612]}
        ],
    },
    "participants": {
        "page": 12,
        "slots": [
            {
                "key": "participants_table",
                "kind": "table",
                "region": [275, 244, 1118, 448],
                "keep": True,
                "merged": [],
                "body": [282, 298, 705, 442],
                "sample": "المشاركين",
            }
        ],
    },
    "assets": {
        "page": 13,
        "slots": [
            {
                "key": "assets_table",
                "kind": "table",
                "region": [275, 252, 1122, 636],
                "merged": [],
                "body": [282, 292, 1116, 630],
                "sample": "فيلا سكنية",
            },
            text("reason_title", "سبب عدم بيع الأصل غير المباع"),
            para("reason", ["لم يتم بيع الأصول"], 24.0),
        ],
    },
    "closing": {
        "page": 14,
        "footer": False,
        "slots": [
            text("address", "12213", "left"),
            text("phone", "+966-555-405658", "left"),
            text("email", "re@aayan", "left"),
        ],
    },
}

# The closing form: its table (columns right to left) and boxes.
CLOSING = {
    "columns": [
        "number",
        "deed",
        "property_type",
        "usage",
        "status",
        "reason",
        "winner",
        "value",
    ],
    "date": [31.3, 21.5, 146.2, 37.5],
    "approval": [31.1, 37.0, 110.6, 53.0],
    "signature": [421.1, 496.4, 628.8, 558.0],
    "stamp": [213.1, 496.4, 421.2, 558.0],
}
