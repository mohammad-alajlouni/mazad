from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ..auth import current_user
from ..db import get_db
from ..models import ProjectItem
from ..social_schemas import SocialConfig
from ..services.social import FORMATS, review_social
from .common import get_project, invalidate

router = APIRouter(dependencies=[Depends(current_user)], tags=["social"])


@router.get("/social-templates")
def templates():
    return [
        {"id": key, **value, "preview": f"/social-references/{key}.png"}
        for key, value in FORMATS.items()
    ]


@router.get("/projects/{id}/social-review")
def review(id: str, db=Depends(get_db)):
    return review_social(db, get_project(db, id))


@router.put("/projects/{id}/social-config")
def configure(id: str, body: SocialConfig, db=Depends(get_db)):
    p = get_project(db, id, True)
    if p.workspace_type not in ("project", "social"):
        raise HTTPException(400, "Use the social workspace")
    known = set(db.scalars(select(ProjectItem.id).where(ProjectItem.project_id == id)))
    if (
        len(body.property_ids) != len(set(body.property_ids))
        or not set(body.property_ids) <= known
    ):
        raise HTTPException(400, "Invalid banner property selection")
    p.social_config = body.model_dump()
    invalidate(db, p, output_types={"social_content"})
    db.commit()
    return p.social_config
