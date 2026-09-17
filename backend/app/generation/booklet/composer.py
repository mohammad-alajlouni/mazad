"""Pure page composition from the same normalized snapshot used by all outputs."""

from uuid import UUID

from .codes import barcode, qr
from .registry import COVERS

FIELDS = (
    "property_type",
    "city",
    "district",
    "usage",
    "area",
    "deed_number",
    "plan_number",
    "plot_number",
    "execution_request_number",
    "participation_amount",
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


def text_chunks(value, size=1600):
    # Preserve all characters, including whitespace/newlines and long unbroken tokens.
    result = []
    while value:
        end = min(size, len(value))
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
    for text in text_chunks(agent.get("description", "")) or [""]:
        pages.append({"kind": "agent", "text": text})
    auction_page = {"kind": "auction"}
    pages.append(auction_page)
    for field in ("legal_announcement_text", "court_decision_text"):
        parts = text_chunks(auction.get(field, ""), 300)
        auction_page[field] = parts[0] if parts else ""
        for text in text_chunks("".join(parts[1:])):
            pages.append({"kind": "information", "heading": field, "text": text})
    for rows in chunks(items, 8):
        pages.append({"kind": "summary", "rows": rows})
    for index, item in enumerate(items, 1):
        item["number"] = index
        prop = item["property_data"]
        item["qr_links"] = [
            {"label": k, "url": v, "image": qr(v)}
            for k, v in prop.items()
            if k.endswith("_link") and v
        ]
        description = text_chunks(item.get("description", ""), 450)
        pages.append(
            {
                "kind": "property",
                "item": item,
                "description": description[0] if description else "",
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
                    boundaries.get(side + "_description", ""), 800
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
        "pages": pages,
        "cover_id": cover.id,
        "auction_qrs": [
            {"label": k, "url": v, "image": qr(v)}
            for k, v in auction.items()
            if k.endswith("_url") and v
        ],
        "barcode": barcode("P-" + str(UUID(project["id"]).int)),
    }
