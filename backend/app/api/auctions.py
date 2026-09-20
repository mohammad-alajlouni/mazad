from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auction_schemas import SellingAgentInput
from ..auth import current_user
from ..db import get_db
from ..generation.booklet.assets import ASSETS
from ..generation.booklet.registry import COVERS, cover_options
from ..generation.booklet.validation import validate_project
from ..models import ProjectImage, ProjectItem, SellingAgent
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


@router.put("/projects/{id}/selling-agent")
def save_agent(id: str, body: SellingAgentInput, db=Depends(get_db)):
    p = get_project(db, id, True)
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
