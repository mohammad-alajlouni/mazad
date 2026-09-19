from fastapi import APIRouter, Depends, HTTPException
from ..auth import current_user
from ..db import get_db
from ..banner_schemas import BannerConfig
from ..services.banners import SIZES, review_banners
from .common import get_project, invalidate

router = APIRouter(dependencies=[Depends(current_user)], tags=["banners"])


@router.get("/banner-templates")
def templates():
    return [
        {
            "id": k,
            **v,
            "scale": "1:10",
            "preview": "/banner-references/" + v["layout"] + ".png",
        }
        for k, v in SIZES.items()
    ]


@router.get("/projects/{id}/banner-review")
def review(id: str, db=Depends(get_db)):
    return review_banners(db, get_project(db, id))


@router.put("/projects/{id}/banner-config")
def configure(id: str, body: BannerConfig, db=Depends(get_db)):
    project = get_project(db, id, True)
    if project.workspace_type not in ("project", "banners"):
        raise HTTPException(400, "Use the banner workspace")
    from sqlalchemy import select
    from ..models import ProjectItem

    known = set(db.scalars(select(ProjectItem.id).where(ProjectItem.project_id == id)))
    if (
        len(body.property_ids) != len(set(body.property_ids))
        or not set(body.property_ids) <= known
    ):
        raise HTTPException(400, "Invalid banner property selection")
    project.banner_config = body.model_dump()
    invalidate(db, project, output_types={"banners"})
    db.commit()
    return project.banner_config
