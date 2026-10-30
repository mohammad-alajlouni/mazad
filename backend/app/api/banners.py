from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
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


@router.get("/projects/{id}/banner-sizes")
def banner_sizes(id: str, db=Depends(get_db)):
    """Each property's board size by Infath's table (None: its kind is not
    in the table, the campaign's size stands)."""
    from sqlalchemy import select

    from ..models import ProjectItem
    from ..services.banners import size_for

    get_project(db, id)
    return {
        item.id: size_for(item.property_data)
        for item in db.scalars(select(ProjectItem).where(ProjectItem.project_id == id))
    }


LOGO_OUTPUTS = {
    "booklet": "project_booklet",
    "banner": "banners",
    "social": "social_content",
}


class AgentLogoScale(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["booklet", "banner", "social"]
    scale: float = Field(ge=0.4, le=1.5)


@router.get("/projects/{id}/agent-logo-scales")
def agent_logo_scales(id: str, db=Depends(get_db)):
    """The agent's logo's size on each kind of output (1 when not set)."""
    saved = get_project(db, id).agent_logo_scales or {}
    return {kind: saved.get(kind, 1.0) for kind in LOGO_OUTPUTS}


@router.put("/projects/{id}/agent-logo-scales")
def set_agent_logo_scale(id: str, body: AgentLogoScale, db=Depends(get_db)):
    """Set from the live preview, at once: that kind's outputs issue again."""
    project = get_project(db, id, True)
    project.agent_logo_scales = {
        **(project.agent_logo_scales or {}),
        body.kind: round(body.scale, 2),
    }
    invalidate(db, project, output_types={LOGO_OUTPUTS[body.kind]})
    db.commit()
    return {kind: project.agent_logo_scales.get(kind, 1.0) for kind in LOGO_OUTPUTS}


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
        or not set(body.item_sizes) <= known
    ):
        raise HTTPException(400, "Invalid banner property selection")
    project.banner_config = body.model_dump()
    invalidate(db, project, output_types={"banners"})
    db.commit()
    return project.banner_config


from ..services.marketing_preview import MarketingPreviewInput, preview  # noqa: E402


@router.post("/projects/{id}/marketing-preview")
def marketing_preview(
    id: str, body: MarketingPreviewInput, response: Response, db=Depends(get_db)
):
    """The board or post being prepared, as the forms stand (unsaved)."""
    response.headers["Cache-Control"] = "no-store, private"
    return preview(db, get_project(db, id), body)
