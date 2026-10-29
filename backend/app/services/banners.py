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

# Boards without a usage line (the guide's panoramic designs).
PANORAMIC = ("10x3", "15x5")

# Infath's table of board sizes («اللوحات الإعلانية»): by the kind of property,
# then its area in m² (the first band whose upper bound the area reaches not).
AREA_SIZES = (
    # Raw land: 200 - 1,000, 1,001 - 5,000, 5,001 - 20,000, 20,001 - 100,000, more.
    (
        ("أرض", "ارض", "اراضي", "أراضي"),
        (
            (1000, "4x2"),
            (5000, "6x3"),
            (20000, "10x3"),
            (100000, "10x5"),
            (None, "15x5"),
        ),
    ),
    # Rest house, farm.
    (("استراحة", "استراحه", "مزرعة", "مزرعه"), ((None, "4x2"),)),
    # Palace (2,501 and more).
    (("قصر",), ((None, "6x3"),)),
    # Residential or commercial building.
    (("عمارة", "عماره", "مبنى", "برج", "مجمع"), ((None, "6x3"),)),
    # Apartment.
    (("شقة", "شقه"), ((None, "2x2"),)),
    # Villa: up to 500, then to 2,500; larger ones are boarded as palaces.
    (
        ("فيلا", "فيلة", "فله", "فلة", "دوبلكس"),
        ((500, "2x2"), (2500, "4x2"), (None, "6x3")),
    ),
)


def court_from(auction):
    """The court as the boards' supervision line names it, from the auction's
    court decision: «وبقرار من محكمة التنفيذ …» gives «بقرار من محكمة التنفيذ …»
    (the line adds its own «و»)."""
    text = str((auction or {}).get("court_decision_text") or "").strip()
    text = text.split("\n")[0].strip()
    return text[1:] if text.startswith("وب") else text


def size_for(prop):
    """The board size Infath's table gives a property (by its kind, then its
    area), or None when its kind is not in the table."""
    kind = str((prop or {}).get("property_type") or "")
    try:
        area = Decimal(str((prop or {}).get("area") or 0))
    except ArithmeticError:
        area = Decimal(0)
    for words, bands in AREA_SIZES:
        if any(word in kind for word in words):
            for upper, size in bands:
                if upper is None or area <= upper:
                    return size
    return None


def item_sizes(config, items):
    """Each property's board size: chosen for it, else from Infath's table,
    else the campaign's size. items: (id, property_data) pairs."""
    return {
        id: config.item_sizes.get(id) or size_for(data) or config.size
        for id, data in items
    }


def campaign_sizes(config, items):
    """The sizes a campaign issues, in the order SIZES lists them."""
    if not config.auto_size:
        return config.sizes
    used = set(item_sizes(config, items).values())
    return [size for size in SIZES if size in used] or [config.size]


# Longest court decision a banner campaign accepts (the guide's boards name
# the court on their supervision line, see BannerConfig.court_name).
COURT_LIMIT = 200


def design_overflows(project, items, banner=None, social=None):
    """Values longer than their place in the guide's design (see
    generation/marketing): reported where they are entered."""
    from ..generation.marketing.compose import review

    found = review(
        {"auction": project.auction or {}},
        [
            {"title": i.title, "property_data": i.property_data, "images": []}
            for i in items
        ],
        banner=banner,
        social=social,
    )
    sections = {"court_name": "template", "headline": "template", "tagline": "template"}
    return [
        {
            **row,
            "section": sections.get(
                row["field"], "items" if row["item"] else "auction"
            ),
        }
        for row in found
    ]


def issued_sizes(db, project):
    """The sizes a campaign's boards are issued in (one output each)."""
    config = BannerConfig.model_validate(project.banner_config or {})
    items = db.execute(
        select(ProjectItem.id, ProjectItem.property_data).where(
            ProjectItem.project_id == project.id
        )
    ).all()
    chosen = [
        (id, data)
        for id, data in items
        if not config.property_ids or id in config.property_ids
    ]
    return campaign_sizes(config, chosen)


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
        "court_decision_text": COURT_LIMIT,
        "physical_location": 70,
        "electronic_platform_name": 40,
    }.items():
        fits(a.get(field), field, limit, "auction")
    for field in ("auction_name", "license_number", "legal_announcement_text"):
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
    # The boards' number: the auction's own, else the agent's (settings).
    need(
        a.get("auction_contact_number") or data.get("phone"),
        "auction_contact_number",
        "auction",
    )
    need(data.get("name"), "agent_name", "images")
    fits(data.get("name"), "agent_name", 60, "images")
    images = db.scalars(
        select(ProjectImage).where(
            ProjectImage.project_id == project.id, ProjectImage.item_id.is_(None)
        )
    ).all()
    need(any(i.id == data.get("logo_image_id") for i in images), "agent_logo", "images")
    # The auction icon is a fixed identity asset; only the name varies.
    sizes = item_sizes(config, [(i.id, i.property_data) for i in selected])
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
        boards = [sizes[item.id]] if config.auto_size else config.sizes
        if any(size not in PANORAMIC for size in boards):
            need(item.property_data.get("usage"), "usage", "items", item.title)
    # Each size has its own design: a value must fit every one it is set in.
    issued = campaign_sizes(config, [(i.id, i.property_data) for i in selected])
    for size in issued:
        boards = (
            [i for i in selected if sizes[i.id] == size]
            if config.auto_size
            else selected
        )
        for row in design_overflows(
            project, boards, banner={**config.model_dump(), "size": size}
        ):
            if row not in errors:
                errors.append(row)
    return {
        "valid": not errors,
        "missing": errors,
        "count": len(selected),
        "config": config.model_dump(),
        "template": SIZES[config.size],
        "templates": {size: SIZES[size] for size in issued},
        # Each property's board size (auto_size: from Infath's table).
        "item_sizes": sizes,
        "auto_sizes": {i.id: size_for(i.property_data) for i in selected},
    }
