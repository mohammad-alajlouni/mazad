"""Read-only draft rendering. Shares composer, artwork and PDF engine with export."""

import base64
from functools import lru_cache
from io import BytesIO
from typing import Any, Literal
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
    category: Literal["agent_logo", "auction_logo", "cover", "main", "additional"]
    item_id: str | None = Field(default=None, max_length=100)


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


def preview(db, project, body):
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
            item = next((i for i in items if i["id"] == body.image.item_id), None)
            if not item:
                raise HTTPException(404, "Item not found")
            photo = {"src": source, "orientation": orientation, "caption": ""}
            item["image_assets"] = (
                ([photo] + item["image_assets"][1:])
                if category == "main"
                else item["image_assets"] + [photo]
            )
            focused = item["id"]
    booklet = compose(p, items)
    pages = booklet["pages"]
    selected = body.page
    if selected is None and body.image and body.image.category == "additional":
        selected = next(
            (
                n
                for n, page in enumerate(pages)
                if page["kind"] == "images" and photo in page["images"]
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
        }.get(body.stage, body.stage)
        selected = next(
            (
                n
                for n, page in enumerate(pages)
                if page["kind"] == kind
                and (not focused or page.get("item", {}).get("id") == focused)
            ),
            0,
        )
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
    }


def page_step(page):
    """The workflow step whose fields fill a booklet page."""
    kind = page["kind"]
    if kind in ("summary", "property", "boundaries", "rentals") or (
        kind == "information" and page.get("item")
    ):
        return "items"
    if kind == "images":
        return "images"
    if kind in ("terms", "participation", "contact"):
        return "closing"
    return "auction"
