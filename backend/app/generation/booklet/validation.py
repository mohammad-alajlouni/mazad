from sqlalchemy import select

from ...models import ProjectImage, ProjectItem, SellingAgent


def validate_project(db, project):
    a = project.auction or {}
    errors = []
    warnings = []

    def required(field, value):
        if not value:
            errors.append({"field": field, "code": "required"})

    required("auction.auction_name", a.get("auction_name"))
    required(
        "auction.auction_date", a.get("auction_date") or a.get("auction_start_date")
    )
    required("auction.start_time", a.get("start_time"))
    if a.get("auction_type") in ("physical", "hybrid"):
        required("auction.physical_location", a.get("physical_location"))
    if a.get("auction_type") in ("electronic", "hybrid"):
        required("auction.electronic_platform_name", a.get("electronic_platform_name"))
        required("auction.electronic_platform_url", a.get("electronic_platform_url"))
        required("auction.auction_end_date", a.get("auction_end_date"))
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    required("selling_agent.name", agent and agent.data.get("name"))
    items = db.scalars(
        select(ProjectItem)
        .where(ProjectItem.project_id == project.id)
        .order_by(ProjectItem.sequence_number, ProjectItem.created_at)
    ).all()
    required("properties", items)
    images = db.scalars(
        select(ProjectImage).where(ProjectImage.project_id == project.id)
    ).all()
    rows = []
    for i, item in enumerate(items, 1):
        p = item.property_data
        for field in ("property_type", "city"):
            required(f"properties.{i}.{field}", p.get(field))
        missing = [
            k
            for k in ("district", "area", "deed_number", "plan_number", "plot_number")
            if p.get(k) in ("", None)
        ]
        owned = [im for im in images if im.item_id == item.id]
        if not owned:
            warnings.append(
                {"field": f"properties.{i}.main_image", "code": "missing_image"}
            )
        for field in missing:
            warnings.append(
                {"field": f"properties.{i}.{field}", "code": "missing_optional"}
            )
        rows.append(
            {
                "id": item.id,
                "sequence_number": i,
                "title": item.title,
                **p,
                "missing_main_image": not owned,
                "additional_image_count": max(0, len(owned) - 1),
            }
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "auction": a,
        "selling_agent": agent.data if agent else {},
        "properties": rows,
        "property_count": len(rows),
    }
