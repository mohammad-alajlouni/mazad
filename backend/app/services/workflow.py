"""The field contract and saved-stage readiness for auction publication flows."""

from .banners import review_banners
from .social import review_social
from ..generation.booklet.validation import validate_project

AUCTION_COMMON = [
    "auction_name",
    "license_number",
    "auction_contact_number",
    "supervising_authority",
    "booklet_url",
    "contact_url",
    "legal_announcement_text",
    "court_decision_text",
]
AUCTION_BY_TYPE = {
    "physical": [
        "auction_date",
        "start_time",
        "end_time",
        "physical_location",
        "auction_location_url",
    ],
    "electronic": [
        "auction_start_date",
        "auction_end_date",
        "start_time",
        "end_time",
        "electronic_platform_name",
        "electronic_platform_url",
    ],
    "hybrid": [
        "auction_start_date",
        "auction_end_date",
        "start_time",
        "end_time",
        "physical_location",
        "auction_location_url",
        "electronic_platform_name",
        "electronic_platform_url",
    ],
}


def workflow(db, project):
    scope = project.workspace_type
    stages = {
        key: {"valid": True, "missing": []}
        for key in ["auction", "agent", "items", "images"]
    }
    rules = {
        "auction": {},
        "property_required": ["property_type", "city"],
        "agent_required": ["name"],
        "agent_logo_required": scope != "booklet",
    }
    for kind, visible in AUCTION_BY_TYPE.items():
        required = ["auction_name", "start_time"]
        required += (
            ["auction_date", "physical_location"]
            if kind == "physical"
            else [
                "auction_start_date",
                "auction_end_date",
                "end_time",
                "electronic_platform_name",
            ]
        )
        if kind != "physical" and scope in ("project", "booklet"):
            required += ["electronic_platform_url"]
        if kind == "hybrid":
            required += ["physical_location"]
        if scope != "booklet":
            required += [
                "license_number",
                "auction_contact_number",
                "legal_announcement_text",
            ]
        if scope in ("project", "banners"):
            required += ["booklet_url"]
        rules["auction"][kind] = {
            "visible": AUCTION_COMMON + visible,
            "required": required,
        }
    if scope in ("project", "banners"):
        rules["property_required"] += [
            "district",
            "area",
            "deed_number",
            "plan_number",
            "plot_number",
            "execution_request_number",
        ]
        if scope == "project" or (project.banner_config or {}).get(
            "size", "4x2"
        ) not in ("10x3", "15x5"):
            rules["property_required"] += ["usage"]
    elif (
        scope == "social"
        and (project.social_config or {}).get("post_kind") == "property"
    ):
        rules["property_required"] += ["district", "area", "deed_number"]

    def issue(section, field, item=None, limit=None):
        value = {"field": field, "item": item, "limit": limit}
        if value not in stages[section]["missing"]:
            stages[section]["missing"].append(value)
        stages[section]["valid"] = False

    a = project.auction or {}
    for field in rules["auction"][a.get("auction_type", "physical")]["required"]:
        if a.get(field) in ("", None):
            issue("auction", field)
    from sqlalchemy import select
    from ..models import ProjectItem
    from decimal import Decimal

    for item in db.scalars(
        select(ProjectItem).where(ProjectItem.project_id == project.id)
    ):
        for field in rules["property_required"]:
            value = item.property_data.get(field)
            if value in (None, "") or (field == "area" and Decimal(str(value)) <= 0):
                issue("items", field, item.title)
    # Combine the same publication-specific checks used at generation time.
    checks = []
    if scope in ("project", "banners"):
        checks.append(review_banners(db, project))
    if scope in ("project", "social"):
        checks.append(review_social(db, project))
    for check in checks:
        for row in check["missing"]:
            section = row["section"]
            if section == "template":
                continue
            if row["field"] in ("agent_name", "agent_logo"):
                section = "agent"
            issue(section, row["field"], row.get("item"), row.get("limit"))
    booklet = validate_project(db, project)
    if scope in ("project", "booklet"):
        for row in booklet["errors"]:
            path = row["field"].split(".")
            section = {"selling_agent": "agent", "properties": "items"}.get(
                path[0], "auction"
            )
            issue(section, path[-1], path[1] if len(path) > 2 else None)
    # Common projects support either social design without asking for pictures again.
    if scope == "project":
        from sqlalchemy import select
        from ..models import ProjectItem, ProjectImage

        images = db.scalars(
            select(ProjectImage).where(ProjectImage.project_id == project.id)
        ).all()
        for item in db.scalars(
            select(ProjectItem).where(ProjectItem.project_id == project.id)
        ):
            if not any(i.item_id == item.id and i.category == "main" for i in images):
                issue("images", "main_image", item.title)
        if not any(i.category == "cover" and not i.item_id for i in images):
            issue("images", "campaign_image")
    return {"rules": rules, "stages": stages}
