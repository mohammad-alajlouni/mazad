from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auction_schemas import SellingAgentInput
from ..auth import current_user
from ..db import get_db
from ..generation.booklet.assets import ASSETS
from ..generation.booklet.registry import COVERS, cover_options
from ..generation.booklet.validation import validate_project
from ..models import ProjectImage, ProjectItem, SellingAgent, User
from .common import get_project, invalidate

router = APIRouter(dependencies=[Depends(current_user)], tags=["auctions"])


@router.get("/booklet-templates")
def templates():
    return cover_options()


@router.get("/booklet-templates/{id}/thumbnail")
def thumbnail(id: str):
    if id not in COVERS:
        raise HTTPException(404, "Template not found")
    return Response(
        (ASSETS / f"thumb-{COVERS[id].display_order}.png").read_bytes(),
        media_type="image/png",
    )


PREVIEW_ASSET_TYPES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}


@lru_cache(maxsize=2)
def fixed_page_image(kind):
    """The original introduction and terms pages as images for the live preview."""
    import pymupdf

    if kind == "introduction":
        name, clip = "reference-introduction.pdf", None
    else:
        name, clip = "booklet-art/terms.pdf", pymupdf.Rect(110, 110, 505, 692)
    with pymupdf.open(ASSETS / name) as document:
        return (
            document[0]
            .get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip)
            .tobytes("png")
        )


@lru_cache(maxsize=16)
def reduced_artwork(path):
    """Large artwork (cover photographs) at screen resolution for the preview."""
    from io import BytesIO

    from PIL import Image

    with Image.open(path) as image:
        image.thumbnail((1240, 1754))
        out = BytesIO()
        if image.mode in ("RGBA", "LA", "P"):
            image.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
        image.convert("RGB").save(out, format="JPEG", quality=86)
        return out.getvalue(), "image/jpeg"


@router.get("/booklet-assets/{path:path}")
def booklet_asset(path: str):
    """Fonts and fixed artwork for the live preview, cached by the browser."""
    headers = {"Cache-Control": "private, max-age=86400"}
    if path in ("page/introduction.png", "page/terms.png"):
        kind = path.split("/")[1].removesuffix(".png")
        return Response(fixed_page_image(kind), media_type="image/png", headers=headers)
    target = (ASSETS / path).resolve()
    if (
        not target.is_relative_to(ASSETS.resolve())
        or target.suffix not in PREVIEW_ASSET_TYPES
        or not target.is_file()
    ):
        raise HTTPException(404, "Asset not found")
    if target.suffix == ".png" and target.stat().st_size > 400_000:
        data, media = reduced_artwork(target)
        return Response(data, media_type=media, headers=headers)
    return Response(
        target.read_bytes(),
        media_type=PREVIEW_ASSET_TYPES[target.suffix],
        headers=headers,
    )


@router.put("/projects/{id}/selling-agent")
def save_agent(id: str, body: SellingAgentInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    from ..services.agent_profile import complete

    if complete(db.get(User, p.owner_id)):
        raise HTTPException(409, "Update selling agent information in account settings")
    if body.logo_image_id:
        image = db.get(ProjectImage, body.logo_image_id)
        if not image or image.project_id != id or image.item_id:
            raise HTTPException(400, "Logo must belong to this project")
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == id))
    if not agent:
        agent = SellingAgent(project_id=id)
        db.add(agent)
    agent.data = body.model_dump(mode="json")
    invalidate(db, p)
    db.commit()
    return agent.data


class OrderInput(BaseModel):
    item_ids: list[str] = Field(max_length=5000)


@router.put("/projects/{id}/item-order")
def reorder(id: str, body: OrderInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    items = {
        i.id: i
        for i in db.scalars(select(ProjectItem).where(ProjectItem.project_id == id))
    }
    if len(body.item_ids) != len(items) or set(body.item_ids) != set(items):
        raise HTTPException(400, "Provide every project item exactly once")
    for n, key in enumerate(body.item_ids, 1):
        items[key].sequence_number = n
    invalidate(db, p)
    db.commit()
    return {"ok": True}


@router.get("/projects/{id}/review")
def review(id: str, db=Depends(get_db)):
    return validate_project(db, get_project(db, id))


from ..services.booklet_preview import PreviewInput, preview


@router.post("/projects/{id}/booklet-preview")
def booklet_preview(
    id: str, body: PreviewInput, response: Response, db=Depends(get_db)
):
    response.headers["Cache-Control"] = "no-store, private"
    return preview(db, get_project(db, id), body)


# Names the cover can hold: a short phrase after the fixed word «مزاد».
NAME_WORDS, NAME_LENGTH = 4, 30


def clean_names(text, prefix="مزاد"):
    """The suggested names from the AI's reply: one per line, without numbers,
    quotes, the cover's own «مزاد», or anything not a short name."""
    import re

    names = []
    for line in str(text or "").splitlines():
        name = re.sub(r"^[\s\-*•\d.)٠-٩]+", "", line).strip(" \"'«»“”.،,:")
        if name.startswith(prefix + " "):
            name = name[len(prefix) :].strip()
        if (
            name
            and len(name) <= NAME_LENGTH
            and len(name.split()) <= NAME_WORDS
            and re.fullmatch(r"[\w\s\-]+", name)
            and name not in names
        ):
            names.append(name)
    return names[:6]


@router.post("/projects/{id}/name-suggestions")
async def name_suggestions(id: str, db=Depends(get_db)):
    """Names for the auction suggested by the AI from its properties (cities,
    districts, kinds); an empty list when the AI is unavailable (the form then
    suggests its own)."""
    from ..services.ai import AIService

    p = get_project(db, id)
    auction = p.auction or {}
    language = auction.get("document_language") or "ar"
    facts = [
        {
            k: (i.property_data or {}).get(k)
            for k in ("city", "district", "property_type", "usage")
            if (i.property_data or {}).get(k)
        }
        for i in db.scalars(select(ProjectItem).where(ProjectItem.project_id == id))
    ][:30]
    result = await AIService().generate(
        "list of six distinct, short and attractive names for a Saudi real-estate "
        "auction, inspired by the properties' cities, districts and kinds; one "
        "name per line, two or three words each, no numbering, no quotes, and "
        "without the word «مزاد» (the cover adds it)",
        {
            "properties": facts,
            "auction_type": auction.get("auction_type"),
            "current_name": auction.get("auction_name") or "",
        },
        output_language=language,
    )
    return {"status": result["status"], "names": clean_names(result["text"])}
