"""Both forms, filled: the project's data where it holds the value, the
author's entries (FormsData) for the rest.

The request form keeps the authority's pages as they are (booklet-art like:
forms/request-N.pdf under the text on export, its PNG in the live preview);
each value stands in its field's own box, set smaller (and on a second line
where the box is tall enough) so it never leaves it. The statement and agents
tables repeat their page when there are more properties than rows, as the
form says ("يمكن تكرار البيان").

The study form is Infath's sheet (one per property), laid out as a document.
"""

import json
from functools import lru_cache
from pathlib import Path

from ..booklet.composer import text_width, wrap_lines
from ..booklet.formatting import as_date, as_time, auction_days, money, number
from .questions import QUESTIONS, SECTIONS

FORMS = Path(__file__).resolve().parents[2] / "templates/infath/assets/forms"
FONT = {"r": "RuaqArabic-Medium", "l": "LamaSans-Medium"}
SIZE, MINIMUM, PAD = 9.5, 6.0, 3.0
WRAP_AT = 8.0  # below this size a value may take further lines
LINE = 1.25  # line pitch per point of size, for values on two lines
STATEMENT_ROWS, AGENT_ROWS = 14, 4
USAGES = {"سكني": "سكني", "تجاري": "تجاري"}
STATUS = {
    "free": "بدون قيود",
    "seized": "محجوز",
    "mortgaged": "مرهون",
    "stopped": "موقوف",
}


@lru_cache(maxsize=1)
def geometry():
    return json.loads((FORMS / "request-fields.json").read_text())


def family(text):
    """Lama for figures, Latin, e-mails and links; Ruaq for Arabic words."""
    arabic = sum("؀" <= c <= "ۿ" for c in text)
    return "r" if arabic * 2 >= len(text.replace(" ", "")) else "l"


def fitted(text, box, size=SIZE):
    """A value in its box: the largest size up to `size` at which it fits on
    one line; from WRAP_AT down, on as many lines as the box's height holds.
    Marked "overflow" when it does not fit even at the smallest size (the
    forms step reports it)."""
    text = " ".join(str(text or "").split())
    if not text:
        return None
    x0, y0, x1, y1 = box
    width, height = x1 - x0 - 2 * PAD, y1 - y0
    fam = family(text)
    current = size
    while True:
        lines = [
            line for line, _ in wrap_lines(text, current, width, FONT[fam]) if line
        ]
        one = len(lines) == 1 and text_width(text, current, FONT[fam]) <= width
        several = current <= WRAP_AT and len(lines) * current * LINE <= height + 0.5
        if one or several or current <= MINIMUM:
            result = {
                "box": [round(v, 2) for v in box],
                "lines": lines,
                "size": current,
                "family": fam,
            }
            if not (one or several):
                result["overflow"] = True
            return result
        current = max(MINIMUM, round(current - 0.25, 2))


def deeds(prop):
    return [
        str(v).strip()
        for v in [prop.get("deed_number"), *(prop.get("extra_deed_numbers") or [])]
        if str(v or "").strip()
    ]


def clock(value):
    moment = as_time(value)
    if not moment:
        return ""
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} " + ("ص" if moment.hour < 12 else "م")


def shared(project, items):
    """What both forms take from the project's data, as the forms print it: for the
    auction ("request") and each property (by id)."""
    auction = project.get("auction") or {}
    agent = project.get("selling_agent") or {}
    start, end = auction_days(auction)
    cities = list(
        dict.fromkeys(
            (i["property_data"].get("city") or "").strip()
            for i in items
            if (i["property_data"].get("city") or "").strip()
        )
    )
    request = {
        "org_name": agent.get("name") or "",
        "fal_license": auction.get("license_number") or "",
        "auction_name": auction.get("auction_name") or "",
        "properties_count": str(len(items)) if items else "",
        "method": auction.get("auction_type") or "",
        "platform_name": auction.get("electronic_platform_name") or ""
        if auction.get("auction_type") != "physical"
        else "",
        "city": "، ".join(cities),
        "venue": auction.get("physical_location") or ""
        if auction.get("auction_type") != "electronic"
        else "",
        "start": start.isoformat() if start else "",
        "end": end.isoformat() if end else "",
        "start_time": clock(auction.get("start_time")),
    }
    properties = {}
    for item in items:
        prop = item["property_data"]
        rentals = [
            r
            for r in prop.get("rental_contracts") or []
            if any(v not in (None, "") for v in r.values())
        ]
        properties[item["id"]] = {
            "title": item.get("title") or "",
            "deed": " - ".join(deeds(prop)),
            "deeds": deeds(prop),
            "area": number(prop.get("area"), "ar", True),
            "property_type": prop.get("property_type") or "",
            "usage": prop.get("usage") or "",
            "city": prop.get("city") or "",
            "district": prop.get("district") or "",
            "entry_amount": money(prop.get("participation_amount")),
            "location_link": prop.get("location_link") or "",
            "features": "\n".join(
                f.strip() for f in prop.get("features") or [] if f.strip()
            ),
            # A property with rental contracts in the booklet is rented.
            "rented": "yes" if rentals else "",
        }
    return {"request": request, "properties": properties}


def own(forms, item_id):
    return (forms.get("properties") or {}).get(item_id) or {}


def request_pages(project, items, forms):
    """The request form's pages: [{"sheet": N, "size", "texts", "ticks"}]."""
    g = geometry()
    data = shared(project, items)
    auto, entered = data["request"], forms.get("request") or {}
    filed = as_date(entered.get("date"))
    date_text = f"{filed.day:02d}/{filed.month:02d}/{filed.year}" if filed else ""

    def page(sheet, values, ticks=(), rows=None, table=None):
        fields = g["pages"][sheet - 1]["fields"]
        texts = [
            fitted(text, fields[name])
            for name, text in {"date": date_text, **values}.items()
            if name in fields
        ]
        if table:
            for row, cells in zip(g["tables"][str(sheet)], rows or []):
                texts += [
                    fitted(text, row[column], 7.5)
                    for column, text in cells.items()
                    if column in row
                ]
        return {
            "sheet": sheet,
            "size": g["pages"][sheet - 1]["size"],
            "texts": [t for t in texts if t],
            "ticks": [fields[name] for name in ticks if name in fields],
        }

    pages = [
        page(
            1,
            {
                "org_name": auto["org_name"],
                "cr_number": entered.get("cr_number"),
                "unified_number": entered.get("unified_number"),
                "fal_license": entered.get("fal_license") or auto["fal_license"],
                **{
                    f"{who}_{key}": entered.get(f"{who}_{key}")
                    for who in ("manager", "crier")
                    for key in ("name", "id", "mobile", "email")
                },
            },
        )
    ]
    start, end = as_date(auto["start"]), as_date(auto["end"])
    method = {
        "electronic": "method_electronic",
        "physical": "method_physical",
        "hybrid": "method_all",
    }.get(auto["method"])
    ticks = [method] if method else []
    for choice, prefix in (("receive", "receive"), ("refund", "refund")):
        if entered.get(choice):
            ticks.append(f"{prefix}_{entered[choice]}")
    if entered.get("entry_type"):
        ticks.append(f"entry_{entered['entry_type']}")
    if entered.get("disposal"):
        ticks.append(f"disposal_{entered['disposal']}")
    pages.append(
        page(
            2,
            {
                "auction_name": auto["auction_name"],
                "properties_count": auto["properties_count"],
                "units_count": entered.get("units_count"),
                "city": auto["city"],
                "platform_name": auto["platform_name"],
                "venue": auto["venue"],
                "stream_link": entered.get("stream_link"),
                **(
                    {
                        "start_day": f"{start.day:02d}",
                        "start_month": f"{start.month:02d}",
                        "start_year": str(start.year),
                    }
                    if start
                    else {}
                ),
                **(
                    {
                        "end_day": f"{end.day:02d}",
                        "end_month": f"{end.month:02d}",
                        "end_year": str(end.year),
                    }
                    if end
                    else {}
                ),
                "start_time": auto["start_time"],
                "receive_other_text": entered.get("receive_other")
                if entered.get("receive") == "other"
                else "",
                "keeping": entered.get("keeping"),
                "receive_days": entered.get("receive_days"),
                "refund_other_text": entered.get("refund_other")
                if entered.get("refund") == "other"
                else "",
                "refund_days": entered.get("refund_days"),
                "award_minutes": entered.get("award_minutes"),
            },
            ticks,
        )
    )
    # Page 3: the auctioned property. With several properties (or owners)
    # they stand in the statement (page 4), as the form asks.
    values, ticks = {}, []
    if len(items) == 1:
        item = items[0]
        p, mine = data["properties"][item["id"]], own(forms, item["id"])
        values = {
            "owner": mine.get("owner"),
            "deed": p["deed"],
            "agent_name": mine.get("agent_name"),
            "agency_number": mine.get("agency_number"),
            "age": mine.get("age"),
            "area": p["area"],
            "usage": p["usage"],
            "property_type": p["property_type"],
            "min_price": money(mine.get("min_price")) or mine.get("min_price"),
            "entry_amount": p["entry_amount"],
        }
        status = mine.get("status")
        if status:
            ticks.append(f"status_{status}")
            if status == "other":
                values["status_other_text"] = mine.get("status_other")
    elif items:
        values["owner"] = "حسب جدول البيان المرفق (صفحة 4)"
    for ruling in entered.get("rulings") or []:
        ticks.append(f"rulings_{ruling}")
    if "other" in (entered.get("rulings") or []):
        values["rulings_other_text"] = entered.get("rulings_other")
    if entered.get("ownership"):
        ticks.append(f"ownership_{entered['ownership']}")
        if entered["ownership"] == "other":
            values["ownership_other_text"] = entered.get("ownership_other")
    for key, prefix in (
        ("rights", "rights"),
        ("dispute", "dispute"),
        ("value_info", "value"),
        ("offplan", "offplan"),
        ("contribution", "contribution"),
    ):
        answer = (entered.get(key) or {}).get("answer")
        if answer:
            ticks.append(f"{prefix}_{answer}")
            if answer == "yes":
                values[f"{prefix}_text"] = (entered.get(key) or {}).get("text")
    pages.append(page(3, values, ticks))
    # Page 4: the statement, fourteen properties to a page.
    rows = []
    for n, item in enumerate(items, 1):
        p, mine = data["properties"][item["id"]], own(forms, item["id"])
        rows.append(
            {
                "number": str(n),
                "owner": mine.get("owner"),
                "deed": p["deed"],
                "contract": entered.get("contract_number"),
                "area": p["area"],
                "property_type": p["property_type"],
                "usage": p["usage"],
                "age": mine.get("age"),
                "city": " / ".join(x for x in (p["city"], p["district"]) if x),
                "disclosure": mine.get("disclosure")
                or STATUS.get(mine.get("status") or "", ""),
                "min_price": number(mine.get("min_price"), "ar", True)
                or mine.get("min_price"),
                "entry_amount": number(
                    item["property_data"].get("participation_amount"), "ar", True
                ),
                "estimated_value": number(mine.get("estimated_value"), "ar", True)
                or mine.get("estimated_value"),
            }
        )
    for group in chunks(rows, STATEMENT_ROWS) or [[]]:
        pages.append(page(4, {}, rows=group, table=True))
    # Page 5: the agents, four to a page.
    agents = []
    for item in items:
        p, mine = data["properties"][item["id"]], own(forms, item["id"])
        if (mine.get("agent_name") or "").strip():
            agents.append(
                {
                    "owner": mine.get("owner"),
                    "deed": p["deed"],
                    "agent_name": mine.get("agent_name"),
                    "agency_number": mine.get("agency_number"),
                }
            )
    for n, row in enumerate(agents, 1):
        row["number"] = str(n)
    for group in chunks(agents, AGENT_ROWS) or [[]]:
        pages.append(page(5, {}, rows=group, table=True))
    pages.append(
        page(
            6,
            {
                "declarant": entered.get("declarant"),
                "unified_number": entered.get("unified_number"),
                "org_name": auto["org_name"],
            },
        )
    )
    return pages


def chunks(rows, size):
    return [rows[n : n + size] for n in range(0, len(rows), size)]


def study_pages(project, items, forms):
    """Infath's study, one sheet per property."""
    data = shared(project, items)
    auction = project.get("auction") or {}
    agent = project.get("selling_agent") or {}
    study = forms.get("study") or {}
    pages = []
    for n, item in enumerate(items, 1):
        p, mine = data["properties"][item["id"]], own(forms, item["id"])
        answers = mine.get("answers") or {}

        def answer(key, answers=answers, p=p):
            given = (answers.get(key) or {}).get("answer") or ""
            # A rented property in the booklet answers its question.
            if key == "rented" and not given:
                given = p["rented"]
            return {"answer": given, "note": (answers.get(key) or {}).get("note", "")}

        pages.append(
            {
                "number": n,
                "project_name": study.get("project_name")
                or auction.get("auction_name")
                or "",
                "city": p["city"],
                "category": study.get("category") or "",
                "manager": study.get("manager") or "",
                "deed": p["deed"],
                "location_link": p["location_link"],
                "area": p["area"],
                "property_type": p["property_type"],
                "location_note": mine.get("location_note") or "",
                "sections": [
                    {
                        "number": number_,
                        "title": title,
                        "rows": [
                            {"question": question, **answer(key)}
                            for key, question in rows
                        ],
                    }
                    for number_, title, rows in SECTIONS
                ],
                "age": mine.get("age") or "",
                "estimated_price": money(mine.get("estimated_price"))
                or mine.get("estimated_price")
                or "",
                "indicative_value": money(mine.get("indicative_value"))
                or mine.get("indicative_value")
                or "",
                "defects": mine.get("defects") or "",
                "features": mine.get("features") or p["features"],
                "agent": agent.get("name") or "",
            }
        )
    return pages


# What the author still has to enter, for the forms step's checklist.
REQUEST_FIELDS = (
    "date",
    "cr_number",
    "unified_number",
    "manager_name",
    "manager_id",
    "manager_mobile",
    "manager_email",
    "crier_name",
    "crier_id",
    "crier_mobile",
    "crier_email",
    "receive",
    "keeping",
    "receive_days",
    "refund",
    "refund_days",
    "entry_type",
    "award_minutes",
    "disposal",
    "ownership",
    "declarant",
)
DISCLOSURES = ("rights", "dispute", "value_info", "offplan", "contribution")


def missing(project, items, forms):
    """[{"form", "field", "item"}]: each value the forms still lack."""
    entered = forms.get("request") or {}
    auto = shared(project, items)["request"]
    found = [
        {"form": "request", "field": key, "item": None}
        for key in REQUEST_FIELDS
        if not str(entered.get(key) or "").strip()
    ]
    if not (entered.get("fal_license") or auto["fal_license"]):
        found.append({"form": "request", "field": "fal_license", "item": None})
    if not entered.get("rulings"):
        found.append({"form": "request", "field": "rulings", "item": None})
    found += [
        {"form": "request", "field": key, "item": None}
        for key in DISCLOSURES
        if not (entered.get(key) or {}).get("answer")
    ]
    study = forms.get("study") or {}
    found += [
        {"form": "study", "field": key, "item": None}
        for key in ("category", "manager")
        if not str(study.get(key) or "").strip()
    ]
    for item in items:
        mine = own(forms, item["id"])
        found += [
            {"form": "request", "field": key, "item": item["id"]}
            for key in ("owner", "age", "status", "min_price", "estimated_value")
            if not str(mine.get(key) or "").strip()
        ]
        answers = mine.get("answers") or {}
        rented = shared(project, [item])["properties"][item["id"]]["rented"]
        unanswered = [
            key
            for key in QUESTIONS
            if not (answers.get(key) or {}).get("answer")
            and not (key == "rented" and rented)
        ]
        if unanswered:
            found.append(
                {
                    "form": "study",
                    "field": "answers",
                    "item": item["id"],
                    "count": len(unanswered),
                }
            )
        found += [
            {"form": "study", "field": key, "item": item["id"]}
            for key in ("estimated_price", "indicative_value")
            if not str(mine.get(key) or "").strip()
        ]
    return found


def overflows(pages):
    """Values too long for their box even at the smallest size."""
    return [
        text["lines"][0][:30]
        for page in pages
        for text in page.get("texts", [])
        if text.get("overflow")
    ]
