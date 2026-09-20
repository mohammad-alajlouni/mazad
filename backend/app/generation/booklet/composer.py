"""Pure page composition from the same normalized snapshot used by all outputs."""

from uuid import UUID

from .codes import barcode, qr
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
    "unit_number",
    "property_type",
    "contract_status",
    "contract_start_date",
    "contract_end_date",
    "contract_duration",
    "paid_period",
    "next_due_date",
    "annual_rent_value",
)


def chunks(rows, count):
    return [rows[i : i + count] for i in range(0, len(rows), count)]


def text_chunks(value, size=1200, max_lines=26):
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


def compose(project, items):
    auction = project["auction"]
    cover = COVERS[auction["selected_cover_template_id"]]
    pages = [
        {"kind": "cover", "cover_number": cover.display_order},
        {"kind": "introduction"},
    ]
    agent = project.get("selling_agent", {})
    for text in text_chunks(agent.get("description", ""), 400, 8) or [""]:
        pages.append({"kind": "agent", "text": text})
    for text in text_chunks(agent.get("contact_information", "")):
        pages.append(
            {"kind": "information", "heading": "contact_information", "text": text}
        )
    auction_page = {"kind": "auction"}
    pages.append(auction_page)
    for field in ("legal_announcement_text", "court_decision_text"):
        parts = text_chunks(auction.get(field, ""), 125)
        auction_page[field] = parts[0] if parts else ""
        for text in text_chunks("".join(parts[1:])):
            pages.append({"kind": "information", "heading": field, "text": text})
    for rows in chunks(items, 10):
        pages.append({"kind": "summary", "rows": rows})
    for index, item in enumerate(items, 1):
        item["number"] = index
        prop = item["property_data"]
        item["qr_links"] = [
            {"label": k, "url": v, "image": qr(v)}
            for k, v in prop.items()
            if k.endswith("_link") and v
        ]
        description = text_chunks(item.get("description", ""), 260, 3)
        pages.append(
            {
                "kind": "property",
                "item": item,
                "description": description[0] if description else "",
                "additional_information": (
                    text_chunks(prop.get("additional_information", ""), 350) or [""]
                )[0],
            }
        )
        for links in chunks(item["qr_links"][4:], 4):
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "property_links",
                    "links": links,
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
        for field in ("notes", "specifications", "technical_information"):
            for text in text_chunks(item.get(field, "")):
                pages.append(
                    {
                        "kind": "information",
                        "item": item,
                        "heading": field,
                        "text": text,
                    }
                )
        for text in text_chunks(prop.get("additional_information", "")):
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "additional_information",
                    "text": text,
                }
            )
        for text in text_chunks("\n".join("• " + f for f in prop.get("features", []))):
            pages.append(
                {
                    "kind": "information",
                    "item": item,
                    "heading": "features",
                    "text": text,
                }
            )
        for images in chunks(item.get("image_assets", [])[1:], 3):
            pages.append({"kind": "images", "item": item, "images": images})
        boundaries = prop.get("boundaries", {})
        if any(boundaries.values()):
            rows = []
            for side in ("north", "south", "east", "west"):
                for text in text_chunks(
                    boundaries.get(side + "_description", ""), 300, 5
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
        for rows in chunks(prop.get("rental_contracts", []), 10):
            pages.append({"kind": "rentals", "item": item, "rows": rows})
    pages.append({"kind": "terms", "auction_type": auction["auction_type"]})
    if auction["auction_type"] in ("electronic", "hybrid"):
        pages.append({"kind": "participation"})
    pages.append({"kind": "contact"})
    return {
        "layout_version": 2,
        "pages": pages,
        "cover_id": cover.id,
        "auction_qrs": [
            {"label": k, "url": v, "image": qr(v)}
            for k, v in auction.items()
            if k.endswith("_url") and v
        ],
        "barcode": barcode("P-" + str(UUID(project["id"]).int)),
    }
