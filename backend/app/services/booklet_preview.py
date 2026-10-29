"""Read-only draft rendering. Shares composer, artwork and PDF engine with export."""

import base64
from functools import lru_cache
from io import BytesIO
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..auction_schemas import AuctionData, PropertyData, SellingAgentInput
from ..generation.booklet.composer import compose
from ..generation.engine import render_html, snapshot


class PreviewImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    src: str = Field(max_length=3000000)
    category: Literal[
        "agent_logo", "auction_logo", "cover", "main", "additional", "features"
    ]
    item_id: str | None = Field(default=None, max_length=100)
    # Additional photographs picked together with this one: together they
    # decide which pages a property gets (the features page needs two).
    more: list[Annotated[str, Field(max_length=3000000)]] = Field(
        default_factory=list, max_length=11
    )
    # The main photograph picked in the same form and not stored yet.
    main: str | None = Field(default=None, max_length=3000000)


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # A workflow step or a page kind: each part of the forms shows its own page.
    stage: Literal[
        "auction",
        "agent",
        "items",
        "images",
        "closing",
        "generate",
        "cover",
        "introduction",
        "terms",
        "participation",
        "contact",
        # A property's own pages: the one the field being edited prints on.
        "property",
        "features",
        "boundaries",
        "information",
        "photos",  # its additional photographs' page
        "rentals",
    ] = "auction"
    page: int | None = Field(default=None, ge=0, le=20000)
    auction: dict[str, Any] = Field(default_factory=dict, max_length=30)
    agent: dict[str, Any] = Field(default_factory=dict, max_length=12)
    item: dict[str, Any] | None = None
    image: PreviewImage | None = None


@lru_cache(maxsize=100)
def adapter(model, key):
    return TypeAdapter(model.model_fields[key].rebuild_annotation())


def draft_values(model, values):
    """Accept incomplete input, retaining only typed fields and safe QR destinations."""
    result = model().model_dump(mode="json")
    for key, value in values.items():
        if key not in model.model_fields:
            continue
        try:
            normalized = adapter(model, key).validate_python(value)
            if isinstance(normalized, str):
                normalized = normalized.strip()
                if len(normalized) > 20000:
                    continue
                if key == "website" and normalized and "://" not in normalized:
                    normalized = "https://" + normalized  # typed as www.aayan.com
                if key.endswith(("_url", "_link")) or key == "website":
                    url = urlsplit(normalized)
                    if not (
                        url.scheme in ("http", "https")
                        and url.hostname
                        and not url.username
                        and not any(c.isspace() for c in normalized)
                    ):
                        normalized = ""
            result[key] = adapter(model, key).dump_python(normalized, mode="json")
        except (ValidationError, ValueError, TypeError):
            pass
    return result


def transient_image(value):
    try:
        if not value.startswith(
            (
                "data:image/jpeg;base64,",
                "data:image/png;base64,",
                "data:image/webp;base64,",
            )
        ):
            raise ValueError()
        data = base64.b64decode(value.split(",", 1)[1], validate=True)
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 12000000:
                raise ValueError()
            image.load()
            transparent = "A" in image.getbands() or "transparency" in image.info
            image = image.convert("RGBA" if transparent else "RGB")
            image.thumbnail((1200, 1200))
            stream = BytesIO()
            image.save(
                stream,
                format="PNG" if transparent else "JPEG",
                **({} if transparent else {"quality": 85}),
            )
            return (
                "data:image/png;base64," if transparent else "data:image/jpeg;base64,"
            ) + base64.b64encode(stream.getvalue()).decode(), (
                "portrait" if image.height > image.width else "landscape"
            )
    except Exception as exc:
        raise HTTPException(422, "Invalid preview image") from exc


def drafted(db, project, body):
    """The project with the form's unsaved values (and a picked photograph):
    (project data, items, the property being entered, that photograph)."""
    photo = None
    p, items = snapshot(db, project, linked_photos=True)
    p["auction"] = draft_values(AuctionData, {**p.get("auction", {}), **body.auction})
    a = p["auction"]
    if a["auction_type"] == "physical":
        a.update(
            auction_start_date=None,
            auction_end_date=None,
            electronic_platform_name="",
            electronic_platform_url="",
        )
    else:
        a["auction_date"] = None
        if a["auction_type"] == "electronic":
            a.update(physical_location="", auction_location_url="")
    # The supervising body as the unsaved values make it (Infath, or another
    # body: its details as typed, its logo as stored).
    from sqlalchemy import select

    from ..generation.engine import stored_logo, supervisor_for
    from ..models import ProjectImage
    from .storage import LocalStorage

    logos = db.scalars(
        select(ProjectImage).where(
            ProjectImage.project_id == project.id,
            ProjectImage.category == "supervisor_logo",
        )
    ).all()
    p["supervisor"] = supervisor_for(
        db, a, logos, lambda image: stored_logo(LocalStorage(), image.key)
    )
    p["selling_agent"] = draft_values(
        SellingAgentInput, {**p.get("selling_agent", {}), **body.agent}
    )
    # Only project-owned assets from the already-authorized snapshot are available.
    if "logo_image_id" in body.agent:
        p["agent_logo"] = ""
    if body.agent.get("logo_image_id"):
        from sqlalchemy import select

        from ..models import ProjectImage
        from .storage import LocalStorage

        image = db.scalar(
            select(ProjectImage).where(
                ProjectImage.id == body.agent["logo_image_id"],
                ProjectImage.project_id == project.id,
                ProjectImage.item_id.is_(None),
            )
        )
        if image:
            p["agent_logo"] = (
                "data:image/png;base64,"
                if image.key.endswith(".png")
                else "data:image/jpeg;base64,"
            ) + base64.b64encode(LocalStorage().read(image.key)).decode()
    focused = None
    if body.item is not None:
        focused = body.item.get("id")
        existing = next((i for i in items if i["id"] == focused), None)
        if focused and existing is None:
            raise HTTPException(404, "Item not found")
        record = dict(
            existing
            or {
                "id": str(uuid4()),
                # A new property takes the next place (composer.closing).
                "position": len(items),
                "image_assets": [],
                "images": [],
                "property_data": {},
            }
        )
        for key in [
            "title",
            "description",
            "notes",
            "specifications",
            "technical_information",
        ]:
            value = body.item.get(key, record.get(key, ""))
            if not isinstance(value, str) or len(value) > 20000:
                raise HTTPException(422, "Invalid preview text")
            record[key] = value
        record["property_data"] = draft_values(
            PropertyData, body.item.get("property_data", record["property_data"])
        )
        if existing:
            items[items.index(existing)] = record
        else:
            items.append(record)
        focused = record["id"]
    if body.image:
        source, orientation = transient_image(body.image.src)
        category = body.image.category
        if category in ("agent_logo", "auction_logo", "cover"):
            p["cover_image" if category == "cover" else category] = source
        else:
            # A photograph picked in a property's own form belongs to that
            # property, saved or still being entered.
            owner = body.image.item_id or focused
            item = next((i for i in items if i["id"] == owner), None)
            if not item:
                raise HTTPException(404, "Item not found")
            photo = {
                "src": source,
                "orientation": orientation,
                "caption": "",
                "category": category,
            }
            others = [
                dict(
                    zip(("src", "orientation"), transient_image(src)),
                    caption="",
                    category=category,
                )
                for src in (
                    body.image.more if category in ("additional", "features") else []
                )
            ]
            if category in ("additional", "features") and body.image.main:
                src, shape = transient_image(body.image.main)
                main = {"src": src, "orientation": shape, "caption": ""}
                item["image_assets"] = [main] + item["image_assets"][1:]
            item["image_assets"] = (
                ([photo] + item["image_assets"][1:])
                if category == "main"
                else item["image_assets"] + [photo] + others
            )
            focused = item["id"]
    return p, items, focused, photo


def preview(db, project, body):
    p, items, focused, photo = drafted(db, project, body)
    a = p["auction"]
    booklet = compose(p, items)
    pages = booklet["pages"]
    selected = body.page
    if (
        selected is None
        and body.image
        and body.image.category
        in (
            "additional",
            "features",
        )
    ):
        selected = next(
            (
                n
                for n, page in enumerate(pages)
                if page["kind"] in ("features", "images") and photo in page["images"]
            ),
            None,
        )
    if selected is None:
        kind = {
            "auction": "auction",
            "agent": "agent",
            "items": "property" if focused else "summary",
            "images": "property" if focused else "cover",
            "closing": "contact",
            "generate": "cover",
            "photos": "images",
        }.get(body.stage, body.stage)

        def first(kind):
            return next(
                (
                    n
                    for n, page in enumerate(pages)
                    if page["kind"] == kind
                    and (not focused or page.get("item", {}).get("id") == focused)
                ),
                None,
            )

        # A page the property does not have (boundaries beside its facts, no
        # rentals yet...): its own first page.
        selected = first(kind)
        if selected is None and focused:
            selected = first("property")
        selected = selected or 0
    selected = min(selected, len(pages) - 1)
    content = {
        "project": p,
        "items": items,
        "booklet": {**booklet, "pages": [pages[selected]]},
        "output_language": a["document_language"],
    }
    # The browser renders this page directly: no PDF round trip while typing.
    # Export renders the same template through WeasyPrint and runs preflight.
    html = render_html(content, preview=True)
    return {
        "html": html,
        "page": selected,
        "pages": [
            {
                "kind": page["kind"],
                "item": page.get("item", {}).get("title", ""),
                "step": page_step(page),
            }
            for page in pages
        ],
        "width_pt": 595.276,
        "height_pt": 841.89,
        "saved": False,
        # The property being entered: the optional pages its data calls for
        # (shown as switched on by themselves in its page settings).
        "auto": next(
            (
                page.get("auto")
                for page in pages
                if page["kind"] == "property"
                and focused
                and page["item"].get("id") == focused
            ),
            None,
        ),
    }


def page_step(page):
    """The workflow step whose fields fill a booklet page."""
    kind = page["kind"]
    if kind in ("summary", "property", "boundaries", "rentals") or (
        kind == "information" and page.get("item")
    ):
        return "items"
    if kind in ("features", "images"):
        return "items"  # photographs and features are entered with their property
    if kind in ("terms", "participation", "contact"):
        return "closing"
    return "auction"
