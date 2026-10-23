"""The Real Estate General Authority's reports, filled: the auction closing
form and the outputs report.

Both templates were taken apart once by scripts/extract_report_art.py: each
page as it is without the auction's own content (placed under the values as
vectors on export, its picture in the live preview), and every value's place,
font, size and colour measured from the template (layout.json). A page here
is that page with this auction's values set where and as the template sets
them: smaller only when a value is longer than the template's room for it.
"""

import json
import re
from functools import lru_cache

from ..booklet.assets import ASSETS
from ..booklet.composer import wrap_lines
from ..booklet.formatting import MONTHS_AR, as_date, auction_days, number
from ..forms.compose import deeds, fitted

ART = ASSETS / "reports"
FONT_FILES = {
    "RuaqArabic-Light": "identity/RuaqArabic-Light.ttf",
    "RuaqArabic-Medium": "identity/RuaqArabic-Medium.ttf",
    "RuaqArabic-Bold": "identity/RuaqArabic-Bold.ttf",
    # The template's Latin (an address, an e-mail); Ruaq has none.
    "NotoSans-Regular": "reports/NotoSans-Regular.ttf",
}
LATIN = re.compile(r"[A-Za-z@_]+")
SMALLEST = 0.6  # a value is set no smaller than this share of the template's
ROWS = 10  # the report's tables: rows on a page, as the template has them
CLOSING_ROWS = 17
PHOTOS = 10
# Room for single lines (points): the space the template leaves them.
ROOM = {
    "footer_name": 190,
    "title": 1100,
    "court": 980,
    "period": 980,
    "boards_line": 850,
    "x_line": 860,
    "tiktok_line": 860,
    "reason_title": 800,
    "address": 172,
    "phone": 172,
    "email": 172,
}
STATUS = {"sold": "مباع", "unsold": "غير مباع"}
SALE = {"sold": "تم البيع", "unsold": "غير مباع"}
CHANNEL_CONTENT = {
    "x": "منشورات",
    "tiktok": "فيديوهات",
    "whatsapp": "رسالة",
    "sms": "رسالة",
}
INTRO_REST = (
    "يهدف هذا التقرير إلى استعراض جميع أعمال المزاد منذ تاريخ الإسناد وحتى "
    "انتهاء إقامة المزاد، متضمنًا تفاصيل الأنشطة التسويقية المنفذة، وعدد "
    "المشاركين، وقائمة الأصول المباعة وغير المباعة، وأسباب عدم البيع، وذلك "
    "التزامًا بالضوابط والإجراءات المعتمدة."
)


@lru_cache(maxsize=1)
def layout():
    return json.loads((ART / "layout.json").read_text())


@lru_cache(maxsize=8)
def face(name):
    from PIL import ImageFont

    return ImageFont.truetype(str(ASSETS / FONT_FILES[name]), 100)


def runs(text, main):
    """The text in runs of one font: Latin in Noto Sans, as the template sets
    it; everything else (words, figures) in the slot's Ruaq."""
    out, at = [], 0
    for m in LATIN.finditer(text):
        if m.start() > at:
            out.append((text[at : m.start()], main))
        out.append((m.group(), "NotoSans-Regular"))
        at = m.end()
    if at < len(text):
        out.append((text[at:], main))
    return out


def width(text, main, size):
    return (
        sum(
            face(f).getlength(part, direction="rtl") / 100 * size
            for part, f in runs(text, main)
        )
        * 1.02
    )


def main_font(slot):
    return slot["font"] if slot["font"].startswith("Ruaq") else "RuaqArabic-Medium"


def line(slot, text, room=None, x=None, base=None, align=None):
    """One line in a slot's style, at the template's size or smaller to fit."""
    text = " ".join(str(text or "").split())
    if not text:
        return None
    main = main_font(slot)
    room = room or ROOM.get(slot.get("key"), 400)
    size = slot["size"]
    natural = width(text, main, size)
    scale = 1.0 if natural <= room else max(SMALLEST, room / natural)
    return {
        "key": slot.get("key"),
        "text": text,
        "x": round(slot["x"] if x is None else x, 2),
        "base": round(slot["base"] if base is None else base, 2),
        "align": align or slot["align"],
        "dir": "ltr" if (align or slot["align"]) == "left" else "rtl",
        "font": main,
        "size": round(size * scale, 3),
        "color": slot["color"],
        "runs": [{"text": t, "font": f} for t, f in runs(text, main)],
        "fits": natural * SMALLEST <= room,
    }


def paragraph(slot, text, last_base):
    """Justified lines between the template's edges, as many as fit above
    last_base (smaller type when the text is longer)."""
    main = main_font(slot)
    room = slot["x1"] - slot["x0"]
    scale = 1.0
    while True:
        size = slot["size"] * scale
        pitch = slot["pitch"] * scale
        lines = []
        for block in str(text or "").split("\n"):
            if not block.strip():
                continue
            broken = [ln for ln, _ in wrap_lines(block.strip(), size, room, main) if ln]
            lines += [(ln, n == len(broken) - 1) for n, ln in enumerate(broken)]
        fits = slot["base"] + pitch * (len(lines) - 1) <= last_base
        if fits or scale <= SMALLEST:
            return {
                "x0": slot["x0"],
                "width": round(room, 2),
                "font": main,
                "size": round(size, 3),
                "color": slot["color"],
                "lines": [
                    {
                        "text": ln,
                        "base": round(slot["base"] + pitch * n, 2),
                        "last": last,
                        "runs": [{"text": t, "font": f} for t, f in runs(ln, main)],
                    }
                    for n, (ln, last) in enumerate(lines)
                ],
                "fits": fits,
            }
        scale = round(scale - 0.04, 2)


def slots_of(kind):
    return {s["key"]: s for s in layout()["report"][kind]["slots"]}


# Values as the template writes them.


def bare_name(auction):
    name = (auction.get("auction_name") or "").strip()
    return re.sub(r"^مزاد\s+", "", name) or name


def day_month(day):
    return f"{day.day} {MONTHS_AR[day.month - 1]}"


def period(report, auction):
    start, end = auction_days(auction)
    start = as_date(report.get("period_from")) or start
    end = as_date(report.get("period_to")) or end or start
    if not start:
        return ""
    if not end or end == start:
        return f"بتاريخ {day_month(start)} {start.year}م"
    if (start.year, start.month) == (end.year, end.month):
        return f"خلال الفترة من {start.day} إلى {end.day} {MONTHS_AR[end.month - 1]} {end.year}م"
    if start.year == end.year:
        return f"خلال الفترة من {day_month(start)} إلى {day_month(end)} {end.year}م"
    return f"خلال الفترة من {day_month(start)} {start.year}م إلى {day_month(end)} {end.year}م"


def company(agent):
    name = (agent.get("name") or "").strip()
    return name if name.startswith("شركة") else f"شركة {name}" if name else ""


def intro(project, report):
    """The template's introduction, word for word, with this auction's names."""
    if (report.get("intro") or "").strip():
        return report["intro"]
    a = project.get("auction") or {}
    court = report.get("court") or "محكمة التنفيذ"
    by = company(project.get("selling_agent") or {})
    first = (
        f"تم إسناد مزاد {bare_name(a)} ل{by} من قبل مركز الإسناد والتصفية (إنفاذ) "
        f"وبقرار من {court}،وذلك وفق الخطة المعتمدة وآلية العمل المحددة لوكيل البيع."
    )
    return first + "\n" + INTRO_REST


def boards_line(count):
    noun = "لوحات دعائية" if 3 <= count <= 10 else "لوحة دعائية"
    return (
        f"تم تركيب عدد ( {count} {noun} ) وفق الخطة المعتمدة، وتمت إزالتها خلال "
        "يومي عمل بعد انتهاء المزاد التزاماً بالضوابط."
    )


def x_line(report):
    posts, paid, unpaid = (
        report.get("x_posts"),
        report.get("x_paid"),
        report.get("x_unpaid"),
    )
    if posts is None:
        return ""
    text = f"تم نشر عدد ( {posts} ) منشورات عبر الحساب الرسمي"
    parts = []
    if paid is not None:
        parts.append(f"( {paid} ) حملة إعلانية مدفوعة")
    if unpaid is not None:
        parts.append(f"( {unpaid} ) منشورات ترويجية غير مدفوعة")
    return text + ("، منها " + " و".join(parts) if parts else "") + "."


def tiktok_line(report):
    count = report.get("tiktok_videos")
    if count is None:
        return ""
    return f"تم نشر عدد ( {count} ) فيديوهات ترويجية عبر منصة تيك توك."


def money(value):
    # An amount typed with words stays as typed (number() keeps it).
    text = str(value or "").replace(",", "").strip()
    return number(text, grouping=True) if text else ""


def slash(value):
    day = as_date(value)
    return f"{day.year}/{day.month:02d}/{day.day:02d}" if day else ""


def asset_name(prop):
    area = number(prop.get("area"), grouping=True)
    parts = [prop.get("property_type") or ""]
    if area:
        parts.append(f"{area} م2")
    if prop.get("district"):
        parts.append(f"في {prop['district']}")
    return " ".join(p for p in parts if p)


# The outputs report's pages.


def common(kind, project):
    s = slots_of(kind)
    page = {
        "kind": kind,
        "size": layout()["report"][kind]["size"],
        "art": f"reports/report@{layout()['report'][kind]['page']}",
        "preview": f"reports/report-{kind}.png",
        "texts": [],
        "paragraphs": [],
        "tables": [],
        "images": [],
        "frames": [],
        "logo": None,
        "item": "",
    }
    if "agent_logo" in s and project.get("agent_logo"):
        page["logo"] = {"src": project["agent_logo"], "box": s["agent_logo"]["box"]}
    if "footer_name" in s:
        page["texts"].append(
            line(s["footer_name"], bare_name(project.get("auction") or {}))
        )
    return page, s


def table_page(page, slot, rows, values):
    """A table of the template's grid with len(rows) body rows (redrawn when
    the template's own rows are not kept)."""
    xs, ys = slot["columns"], slot["rows"]
    top, header, pitch = ys[0], ys[1], ys[2] - ys[1]
    bottom = header + pitch * len(rows)
    if not slot["keep"]:
        merged = slot["merged"]
        free = [c for c in range(len(xs) - 1) if c not in merged]
        left = xs[min(free)] if merged else xs[0]
        lines = [[x, top, x, bottom] for x in xs]
        lines += [[xs[0], top, xs[-1], top], [xs[0], header, xs[-1], header]]
        lines += [
            [left, header + pitch * n, xs[-1], header + pitch * n]
            for n in range(1, len(rows))
        ]
        lines.append([xs[0], bottom, xs[-1], bottom])
        page["tables"].append(
            {"lines": lines, "stroke": slot["stroke"], "width": slot["stroke_width"]}
        )
    style = {**slot, "align": "center"}
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if value is None or c in slot["merged"]:
                continue
            cell = line(
                style,
                value,
                room=xs[c + 1] - xs[c] - 10,
                x=(xs[c] + xs[c + 1]) / 2,
                base=header + pitch * r + slot["base_offset"],
            )
            if cell:
                page["texts"].append({**cell, "key": f"{slot['key']}.{r}.{c}"})
    for c in slot["merged"]:
        value = values.get(c)
        middle = header + pitch * len(rows) / 2
        cell = line(
            style,
            value,
            room=xs[c + 1] - xs[c] - 10,
            x=(xs[c] + xs[c + 1]) / 2,
            base=middle + slot["base_offset"] - pitch / 2,
        )
        if cell:
            page["texts"].append({**cell, "key": f"{slot['key']}.merged.{c}"})
    return bottom


def photo_rows(boxes, count):
    """Where count photographs stand: the template's rows of four, the last
    row centred under them as the template centres its last two."""
    full = boxes[:8]
    rows = [full[:4], full[4:8]]
    w = boxes[8][2] - boxes[8][0]
    gap = boxes[8][0] - boxes[9][2]
    centre = (boxes[9][0] + boxes[8][2]) / 2
    places, n, row = [], count, 0
    tops = [rows[0][0][1], rows[1][0][1], boxes[8][1]]
    while n > 0 and row < 3:
        k = min(4, n)
        if k == 4 and row < 2:
            places += rows[row]
        else:
            total = k * w + (k - 1) * gap
            x = centre + total / 2
            for _ in range(k):
                places.append(
                    [x - w, tops[row], x, tops[row] + (boxes[8][3] - boxes[8][1])]
                )
                x -= w + gap
        n -= k
        row += 1
    return places


def outputs_pages(project, items, data, source):
    """The outputs report's pages; source(image) is an image's address."""
    report = data.get("report") or {}
    results = data.get("properties") or {}
    images = data.get("images") or []
    shots = {
        c: [source(i) for i in images if i["category"] == c]
        for c in ("board", "x", "tiktok", "whatsapp", "youtube")
    }
    a = project.get("auction") or {}
    agent = project.get("selling_agent") or {}
    pages = []

    page, s = common("cover", project)
    page["texts"] += [
        line(s["title"], f"مزاد {bare_name(a)}"),
        line(s["court"], f"وبقرار من {report.get('court') or 'محكمة التنفيذ'}"),
        line(s["period"], period(report, a)),
    ]
    pages.append(page)
    pages.append(common("contents", project)[0])
    page, s = common("intro", project)
    page["paragraphs"].append(paragraph(s["intro"], intro(project, report), 640))
    pages.append(page)
    pages.append(common("marketing", project)[0])

    boards = [b for b in report.get("boards") or [] if b.strip()]
    for start in range(0, len(boards), ROWS):
        page, s = common("boards", project)
        page["texts"].append(line(s["boards_line"], boards_line(len(boards))))
        chunk = boards[start : start + ROWS]
        table_page(
            page,
            s["boards_table"],
            [[None, None, b, str(start + n + 1)] for n, b in enumerate(chunk)],
            {
                0: slash(report.get("boards_removed")),
                1: slash(report.get("boards_installed")),
            },
        )
        page["item"] = f"{start + 1}–{start + len(chunk)}"
        pages.append(page)
    for start in range(0, len(shots["board"]), PHOTOS):
        page, s = common("board_photos", project)
        chunk = shots["board"][start : start + PHOTOS]
        for src, box in zip(
            chunk, photo_rows(s["photos"]["boxes"], len(chunk)), strict=True
        ):
            page["images"].append({"src": src, "box": box, "fit": "cover"})
        pages.append(page)

    page, s = common("channels", project)
    t = s["channels_table"]
    channels = report.get("channels") or {}
    rows = [
        [
            (channels.get(key) or {}).get("views") or "",
            (channels.get(key) or {}).get("content") or CHANNEL_CONTENT[key],
            None,
        ]
        for key in ("x", "tiktok", "whatsapp", "sms")
    ]
    table_page(page, t, rows, {})
    pages.append(page)

    if shots["x"] or report.get("x_posts") is not None:
        page, s = common("x", project)
        page["texts"].append(line(s["x_line"], x_line(report)))
        boxes = s["x_shots"]["boxes"]  # middle, right, left
        order = {1: [0], 2: [1, 2], 3: [1, 0, 2]}.get(len(shots["x"]), [])
        for src, n in zip(shots["x"], order, strict=False):
            page["images"].append({"src": src, "box": boxes[n], "fit": "contain"})
        pages.append(page)
    for kind, key, text in (
        ("tiktok", "tiktok_shots", tiktok_line(report)),
        ("whatsapp", "whatsapp_shots", None),
    ):
        if not shots[kind] and not (kind == "tiktok" and text):
            continue
        page, s = common(kind, project)
        if text:
            page["texts"].append(line(s["tiktok_line"], text))
        slot = s[key]
        frames, screens = slot["frames"], slot["screens"]
        chosen = [0, 1] if len(shots[kind]) > 1 else [1] if shots[kind] else []
        shift = 0.0
        if len(chosen) == 1:
            # One screenshot: its frame in the middle of the two.
            shift = (frames[0][0] + frames[1][2]) / 2 - (
                frames[1][0] + frames[1][2]
            ) / 2
        for src, n in zip(shots[kind], chosen, strict=False):
            f, sc = frames[n], screens[n]
            page["frames"].append(
                {
                    "name": f"reports/frames@{layout()['frames'][f'{kind}-{n + 1}']}",
                    "preview": f"reports/frame-{kind}-{n + 1}.png",
                    "box": [f[0] + shift, f[1], f[2] + shift, f[3]],
                }
            )
            page["images"].append(
                {
                    "src": src,
                    "box": [sc[0] + shift, sc[1], sc[2] + shift, sc[3]],
                    "fit": "cover",
                    "radius": 10 if kind == "tiktok" else 4,
                }
            )
        pages.append(page)
    if shots["youtube"]:
        page, s = common("youtube", project)
        page["images"].append(
            {
                "src": shots["youtube"][0],
                "box": s["youtube_shot"]["boxes"][0],
                "fit": "cover",
            }
        )
        pages.append(page)

    page, s = common("participants", project)
    table_page(
        page,
        s["participants_table"],
        [
            [str(report.get(k)) if report.get(k) is not None else "", None]
            for k in ("participants", "interested", "visitors")
        ],
        {},
    )
    pages.append(page)

    rows = []
    for item in items:
        prop = item.get("property_data") or {}
        r = results.get(item["id"]) or {}
        sold = r.get("status") == "sold"
        rows.append(
            [
                SALE.get(r.get("status"), ""),
                money(r.get("value"))
                if sold
                else ("-" if r.get("status") == "unsold" else ""),
                money(r.get("opening_price")),
                asset_name(prop),
            ]
        )
    unsold = any((results.get(i["id"]) or {}).get("status") == "unsold" for i in items)
    chunks = [rows[n : n + ROWS] for n in range(0, len(rows), ROWS)] or [[]]
    for n, chunk in enumerate(chunks):
        page, s = common("assets", project)
        bottom = table_page(page, s["assets_table"], chunk, {})
        if (
            n == len(chunks) - 1
            and unsold
            and (report.get("unsold_reason") or "").strip()
        ):
            title = s["reason_title"]
            gap = title["base"] - s["assets_table"]["rows"][-1]
            title_base = bottom + gap
            page["texts"].append(
                line(title, "سبب عدم بيع الأصل غير المباع:", base=title_base)
            )
            reason = {
                **s["reason"],
                "base": title_base + s["reason"]["base"] - title["base"],
            }
            page["paragraphs"].append(paragraph(reason, report["unsold_reason"], 770))
        page["item"] = (
            f"{n * ROWS + 1}–{n * ROWS + len(chunk)}" if len(chunks) > 1 else ""
        )
        pages.append(page)

    page, s = common("closing", project)
    page["texts"] += [
        line(
            s["address"],
            report.get("address")
            or agent.get("contact_information", "").split("\n")[0][:100],
        ),
        line(s["phone"], report.get("phone") or agent.get("phone") or ""),
        line(s["email"], report.get("email") or ""),
    ]
    pages.append(page)
    for page in pages:
        page["texts"] = [t for t in page["texts"] if t]
    return pages


# The closing form.


def closing_pages(project, items, data, source):
    g = layout()["closing"]
    closing = data.get("closing") or {}
    results = data.get("properties") or {}
    images = {
        i["category"]: source(i)
        for i in data.get("images") or []
        if i["category"] in ("signature", "stamp")
    }
    day = as_date(closing.get("date"))
    header = []
    for key, value in (
        ("date", f"{day.day:02d}/{day.month:02d}/{day.year}" if day else ""),
        ("approval", closing.get("approval_number") or ""),
    ):
        cell = fitted(value, g[key], 10)
        if cell:
            header.append({**cell, "align": "center", "key": key})
    rows = []
    for n, item in enumerate(items):
        prop = item.get("property_data") or {}
        r = results.get(item["id"]) or {}
        status = r.get("status") or ""
        rows.append(
            {
                "number": str(n + 1),
                "deed": " - ".join(deeds(prop)),
                "property_type": prop.get("property_type") or "",
                "usage": prop.get("usage") or "",
                "status": STATUS.get(status, ""),
                "reason": (r.get("reason") or "-")
                if status == "unsold"
                else ("-" if status == "sold" else ""),
                "winner": r.get("winner") or ""
                if status == "sold"
                else ("-" if status == "unsold" else ""),
                "value": money(r.get("value"))
                if status == "sold"
                else ("-" if status == "unsold" else ""),
            }
        )
    pages = []
    for start in range(0, max(len(rows), 1), CLOSING_ROWS):
        texts = list(header)
        for r, row in enumerate(rows[start : start + CLOSING_ROWS]):
            y0, y1 = g["rows"][r]
            for name, (x0, x1) in zip(g["names"], g["columns"], strict=True):
                cell = fitted(row[name], [x0, y0, x1, y1], 9.5)
                if cell:
                    texts.append(
                        {**cell, "align": "center", "key": f"{name}.{start + r}"}
                    )
        page = {
            "kind": "closing_form",
            "size": g["size"],
            "art": "reports/closing",
            "preview": "reports/closing.png",
            "cells": texts,
            "texts": [],
            "paragraphs": [],
            "tables": [],
            "frames": [],
            "logo": None,
            "images": [],
            "item": f"{start + 1}–{min(start + CLOSING_ROWS, len(rows))}"
            if len(rows) > CLOSING_ROWS
            else "",
        }
        for key in ("signature", "stamp"):
            if images.get(key):
                x0, y0, x1, y1 = g[key]
                page["images"].append(
                    {
                        "src": images[key],
                        "box": [x0 + 6, y0 + 4, x1 - 6, y1 - 4],
                        "fit": "contain",
                    }
                )
        pages.append(page)
    return pages


REPORTS = {"auction_closing": "closing", "outputs_report": "outputs"}


def report_pages(kind, project, items, data, source):
    build = closing_pages if REPORTS[kind] == "closing" else outputs_pages
    return build(project, items, data, source)


def overflows(pages):
    out = []
    for n, page in enumerate(pages):
        for t in page.get("texts", []):
            if not t.get("fits", True):
                out.append({"page": n, "field": t["key"]})
        for p in page.get("paragraphs", []):
            if not p["fits"]:
                out.append({"page": n, "field": "paragraph"})
        for c in page.get("cells", []):
            if c.get("overflow"):
                out.append({"page": n, "field": c["key"]})
    return out


def fonts_of(pages):
    used = {"RuaqArabic-Medium"}
    for page in pages:
        for t in page.get("texts", []):
            used |= {t["font"], *(r["font"] for r in t["runs"])}
        for p in page.get("paragraphs", []):
            used |= {p["font"], *(r["font"] for ln in p["lines"] for r in ln["runs"])}
    return {n: FONT_FILES[n] for n in sorted(used)}
