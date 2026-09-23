from decimal import Decimal

from sqlalchemy import select
from ..banner_schemas import BannerConfig
from ..models import ProjectImage, ProjectItem, SellingAgent

SIZES = {
    "10x3": {"layout": "panoramic", "width_mm": 1000, "height_mm": 300},
    "15x5": {"layout": "panoramic", "width_mm": 1500, "height_mm": 500},
    "4x2": {"layout": "landscape", "width_mm": 400, "height_mm": 200},
    "6x3": {"layout": "landscape", "width_mm": 600, "height_mm": 300},
    "10x5": {"layout": "landscape", "width_mm": 1000, "height_mm": 500},
    "2x2": {"layout": "square", "width_mm": 200, "height_mm": 200},
}


def review_banners(db, project):
    config = BannerConfig.model_validate(project.banner_config or {})
    items = db.scalars(
        select(ProjectItem)
        .where(ProjectItem.project_id == project.id)
        .order_by(ProjectItem.sequence_number, ProjectItem.created_at)
    ).all()
    known = {item.id for item in items}
    errors = []

    def need(value, field, section, item=None):
        if value in (None, "", 0) or (field == "area" and Decimal(str(value)) <= 0):
            errors.append({"field": field, "section": section, "item": item})

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
    need(len(selected), "properties", "items")
    if len(selected) > 100:
        errors.append({"field": "property_limit", "section": "template", "item": None})

    def fits(value, field, limit, section, item=None):
        if len(str(value or "")) > limit:
            errors.append(
                {"field": field, "section": section, "item": item, "limit": limit}
            )

    a = project.auction or {}
    for field, limit in {
        "auction_name": 60,
        "license_number": 24,
        "auction_contact_number": 18,
        "legal_announcement_text": 220,
        "court_decision_text": 120,
        "physical_location": 70,
        "electronic_platform_name": 40,
    }.items():
        fits(a.get(field), field, limit, "auction")
    for field in (
        "auction_name",
        "license_number",
        "auction_contact_number",
        "legal_announcement_text",
        "booklet_url",
    ):
        need(a.get(field), field, "auction")
    electronic = a.get("auction_type") in ("electronic", "hybrid")
    physical = a.get("auction_type") in ("physical", "hybrid")
    for field in (
        (
            "auction_start_date",
            "auction_end_date",
            "start_time",
            "end_time",
            "electronic_platform_name",
        )
        if electronic
        else ("auction_date", "start_time")
    ):
        need(a.get(field), field, "auction")
    if physical:
        need(a.get("physical_location"), "physical_location", "auction")
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    data = agent.data if agent else {}
    need(data.get("name"), "agent_name", "images")
    fits(data.get("name"), "agent_name", 60, "images")
    images = db.scalars(
        select(ProjectImage).where(
            ProjectImage.project_id == project.id, ProjectImage.item_id.is_(None)
        )
    ).all()
    need(any(i.id == data.get("logo_image_id") for i in images), "agent_logo", "images")
    # The auction icon is a fixed identity asset; only the name varies.
    for item in selected:
        for field in (
            "property_type",
            "district",
            "usage",
            "area",
            "deed_number",
            "plan_number",
            "plot_number",
            "execution_request_number",
        ):
            fits(item.property_data.get(field), field, 32, "items", item.title)
        for field in (
            "property_type",
            "district",
            "area",
            "deed_number",
            "plan_number",
            "plot_number",
            "execution_request_number",
        ):
            need(item.property_data.get(field), field, "items", item.title)
        if config.size not in ("10x3", "15x5"):
            need(item.property_data.get("usage"), "usage", "items", item.title)
    return {
        "valid": not errors,
        "missing": errors,
        "count": len(selected),
        "config": config.model_dump(),
        "template": SIZES[config.size],
    }
