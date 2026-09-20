import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import Field, ValidationError
from sqlalchemy import select
from ..auth import current_user
from ..auction_schemas import SellingAgentInput
from ..db import get_db
from ..models import User, Project
from ..services.agent_profile import complete, initial_profile, apply_profile
from ..services.storage import LocalStorage
from .common import audit, invalidate, upload_bytes

router = APIRouter(prefix="/account/profile", tags=["account"])


class AgentProfileInput(SellingAgentInput):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    phone: str = Field(min_length=1, max_length=100)
    logo_image_id: str = Field(default="", max_length=0)


def view(db, user):
    data = initial_profile(db, user)
    has_logo = bool(data.pop("logo_key", ""))
    return {"values": data, "has_logo": has_logo, "complete": complete(user)}


@router.get("")
def get_profile(response: Response, user=Depends(current_user), db=Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return view(db, user)


@router.get("/logo")
def profile_logo(user=Depends(current_user), db=Depends(get_db)):
    key = initial_profile(db, user).get("logo_key")
    if not key:
        raise HTTPException(404, "Image not found")
    return Response(
        LocalStorage().read(key),
        media_type="image/png" if key.endswith(".png") else "image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


@router.put("")
async def save_profile(
    data: str = Form(..., max_length=30000),
    file: UploadFile | None = File(None),
    user=Depends(current_user),
    db=Depends(get_db),
):
    try:
        values = AgentProfileInput.model_validate(json.loads(data)).model_dump(
            mode="json"
        )
    except (ValueError, ValidationError):
        raise HTTPException(422, "Complete your selling agent profile")
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    key = initial_profile(db, user).get("logo_key")
    if file:
        key = LocalStorage().image(await upload_bytes(file))
    if not key:
        raise HTTPException(422, "Complete your selling agent profile")
    values.pop("logo_image_id", None)
    user.agent_profile = {**values, "logo_key": key}
    for project in db.scalars(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.id)
        .with_for_update()
    ):
        if apply_profile(db, user, project):
            invalidate(db, project)
    audit(db, "Account profile updated", user.email)
    db.commit()
    return view(db, user)
