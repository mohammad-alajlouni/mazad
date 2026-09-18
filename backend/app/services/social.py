from decimal import Decimal
from sqlalchemy import select
from ..models import ProjectItem, ProjectImage, SellingAgent
from ..social_schemas import SocialConfig

FORMATS = {
    "x": {"width_px": 1080, "height_px": 660, "reference_page": 35},
    "instagram": {"width_px": 1080, "height_px": 1080, "reference_page": 36},
    "story": {"width_px": 1080, "height_px": 1920, "reference_page": 37},
}


def review_social(db, project):
    config = SocialConfig.model_validate(project.social_config or {})
    items = db.scalars(
        select(ProjectItem)
        .where(ProjectItem.project_id == project.id)
        .order_by(ProjectItem.sequence_number, ProjectItem.created_at)
    ).all()
    images = db.scalars(
        select(ProjectImage).where(ProjectImage.project_id == project.id)
    ).all()
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    a = project.auction or {}
    errors = []

    def check(value, field, section, limit=None, item=None):
        if value in (None, "", 0) or (field == "area" and Decimal(str(value)) <= 0):
            errors.append({"field": field, "section": section, "item": item})
        elif limit and len(str(value)) > limit:
            errors.append(
                {"field": field, "section": section, "item": item, "limit": limit}
            )

    known = {i.id for i in items}
    if (
        len(config.property_ids) != len(set(config.property_ids))
        or not set(config.property_ids) <= known
    ):
        errors.append(
            {"field": "property_selection", "section": "template", "item": None}
        )
    selected = [
        i for i in items if not config.property_ids or i.id in config.property_ids
    ]
    check(len(selected), "properties", "items")
    if len(selected) > 30:
        errors.append({"field": "property_limit", "section": "template", "item": None})
    check(config.headline, "headline", "template", 48)
    for key, limit in {
        "auction_name": 48,
        "license_number": 24,
        "auction_contact_number": 18,
        "legal_announcement_text": 220,
    }.items():
        check(a.get(key), key, "auction", limit)
    if a.get("auction_type") in ("electronic", "hybrid"):
        for key in ("auction_start_date", "auction_end_date", "start_time", "end_time"):
            check(a.get(key), key, "auction")
        check(
            a.get("electronic_platform_name"), "electronic_platform_name", "auction", 40
        )
    else:
        for key in ("auction_date", "start_time"):
            check(a.get(key), key, "auction")
    if a.get("auction_type") in ("physical", "hybrid"):
        check(a.get("physical_location"), "physical_location", "auction", 60)
    data = agent.data if agent else {}
    check(data.get("name"), "agent_name", "images", 48)
    check(
        any(i.id == data.get("logo_image_id") and not i.item_id for i in images),
        "agent_logo",
        "images",
    )
    check(
        any(i.category == "auction_logo" and not i.item_id for i in images),
        "auction_logo",
        "images",
    )
    if config.post_kind == "announcement":
        check(
            any(i.category == "cover" and not i.item_id for i in images),
            "campaign_image",
            "images",
        )
    for item in selected:
        if config.post_kind == "property":
            for key in ("property_type", "city", "district", "area", "deed_number"):
                check(item.property_data.get(key), key, "items", 28, item.title)
            check(
                any(i.item_id == item.id and i.category == "main" for i in images),
                "main_image",
                "images",
                item=item.title,
            )
    return {
        "valid": not errors,
        "missing": errors,
        "count": len(selected) if config.post_kind == "property" else 1,
        "property_count": len(selected),
        "config": config.model_dump(),
        "template": FORMATS[config.format],
    }


def caption(project, config, items, language):
    """Deterministic companion text: no generated regulatory wording or dates."""
    a = project["auction"]
    ar = language == "ar"
    lines = [config.caption, config.headline, config.tagline, a["auction_name"]]
    for key, label in [
        ("legal_announcement_text", "الإعلان النظامي" if ar else "Legal announcement"),
        ("court_decision_text", "قرار المحكمة" if ar else "Court decision"),
        ("license_number", "رقم الترخيص" if ar else "License number"),
        ("auction_date", "تاريخ المزاد" if ar else "Auction date"),
        ("auction_start_date", "تاريخ البداية" if ar else "Start date"),
        ("auction_end_date", "تاريخ النهاية" if ar else "End date"),
        ("start_time", "وقت البداية" if ar else "Start time"),
        ("end_time", "وقت النهاية" if ar else "End time"),
        ("physical_location", "الموقع" if ar else "Location"),
        ("electronic_platform_name", "المنصة" if ar else "Platform"),
        ("auction_contact_number", "التواصل" if ar else "Contact"),
    ]:
        electronic = a.get("auction_type") in ("electronic", "hybrid")
        if (
            key
            in (
                "auction_start_date",
                "auction_end_date",
                "end_time",
                "electronic_platform_name",
            )
            and not electronic
        ):
            continue
        if key == "auction_date" and electronic:
            continue
        if key == "physical_location" and a.get("auction_type") == "electronic":
            continue
        if a.get(key):
            lines.append(f"{label}: {a[key]}")
    lines.append(("عدد العقارات" if ar else "Property count") + f": {len(items)}")
    for item in items:
        d = item["property_data"]
        lines.append(item["title"] + " — " + str(d.get("deed_number", "")))
    return "\n".join(v for v in lines if v)
