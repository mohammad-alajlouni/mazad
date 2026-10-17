from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..auth import current_user, current_admin
from ..config import settings
from ..db import get_db
from ..generation.engine import build_content
from ..models import AIGeneration, SystemSetting
from ..schemas import Branding
from ..services.ai import AIService
from ..services.storage import LocalStorage
from .common import audit, get_project, upload_bytes

router = APIRouter(dependencies=[Depends(current_user)], tags=["settings"])


@router.get("/settings")
def read_settings(db=Depends(get_db)):
    row = db.get(SystemSetting, "global")
    return {
        "branding": row.data if row else Branding().model_dump(),
        "ai": {
            "available": bool(settings().ai_api_key),
            "model": settings().ai_model,
            "provider": "OpenAI-compatible",
        },
        "max_upload_mb": settings().max_upload_mb,
    }


@router.put("/settings", dependencies=[Depends(current_admin)])
def save_settings(body: Branding, db=Depends(get_db)):
    row = db.get(SystemSetting, "global")
    old = row.data if row else {}
    if body.logo_key != old.get("logo_key", ""):
        raise HTTPException(400, "Use the logo upload endpoint to change the logo")
    if not row:
        row = SystemSetting(id="global")
        db.add(row)
    row.data = body.model_dump()
    audit(db, "Settings updated", "Organization branding")
    db.commit()
    return row.data


@router.post("/settings/logo", dependencies=[Depends(current_admin)])
async def logo(file: UploadFile = File(...), db=Depends(get_db)):
    key = LocalStorage().image(await upload_bytes(file))
    row = db.get(SystemSetting, "global")
    if not row:
        row = SystemSetting(id="global", data=Branding().model_dump())
        db.add(row)
    row.data = {**row.data, "logo_key": key}
    db.commit()
    return row.data


class AIInput(BaseModel):
    output_language: Literal["en", "ar"] | None = None
    purpose: str = Field(pattern="^(summary|description|social_content|analysis)$")


@router.post("/projects/{id}/ai")
async def ai_generate(id: str, body: AIInput, db=Depends(get_db)):
    p = get_project(db, id)
    content = build_content(db, p, "asset_study", body.output_language)
    result = await AIService().generate(
        body.purpose,
        {
            "project": p.name,
            "items": [
                {
                    k: v
                    for k, v in i.items()
                    if k not in ("images", "image_assets", "qr_links")
                }
                for i in content["items"]
            ],
        },
        output_language=content["output_language"],
    )
    record = AIGeneration(
        project_id=id,
        purpose=body.purpose,
        status=result["status"],
        text=result["text"],
    )
    db.add(record)
    db.commit()
    return {**result, "id": record.id}


# Infath as the booklet shows it (guide p.11 and its logo on the pages): an
# administrator may change its logo and introduction text without editing any
# design. Kept in its own settings row; empty values keep the guide's.
class InfathIdentity(BaseModel):
    title: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=3000)
    phone: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=200)
    social: str = Field(default="", max_length=300)


def infath_view(row):
    from ..generation.booklet.supervisor import FIELDS, INFATH

    data = row.data if row else {}
    return {
        "values": {key: data.get(f"infath_{key}", "") for key in FIELDS},
        "defaults": {key: INFATH[key] for key in FIELDS},
        "has_logo": bool(data.get("logo_key")),
    }


@router.get("/settings/infath")
def read_infath(db=Depends(get_db)):
    return infath_view(db.get(SystemSetting, "infath"))


@router.put("/settings/infath", dependencies=[Depends(current_admin)])
def save_infath(body: InfathIdentity, db=Depends(get_db)):
    from ..services.booklet_text import text_issue

    if text_issue(body.text):
        raise HTTPException(422, "Introduction text is too long for its page")
    row = db.get(SystemSetting, "infath")
    if not row:
        row = SystemSetting(id="infath", data={})
        db.add(row)
    row.data = {
        **row.data,
        **{f"infath_{k}": v.strip() for k, v in body.model_dump().items()},
    }
    audit(db, "Settings updated", "Infath identity")
    db.commit()
    return infath_view(row)


@router.post("/settings/infath/logo", dependencies=[Depends(current_admin)])
async def infath_logo(file: UploadFile = File(...), db=Depends(get_db)):
    key = LocalStorage().image(await upload_bytes(file))
    row = db.get(SystemSetting, "infath")
    if not row:
        row = SystemSetting(id="infath", data={})
        db.add(row)
    row.data = {**row.data, "logo_key": key}
    audit(db, "Settings updated", "Infath identity")
    db.commit()
    return infath_view(row)


@router.delete("/settings/infath/logo", dependencies=[Depends(current_admin)])
def reset_infath_logo(db=Depends(get_db)):
    row = db.get(SystemSetting, "infath")
    if row and row.data.get("logo_key"):
        row.data = {k: v for k, v in row.data.items() if k != "logo_key"}
        audit(db, "Settings updated", "Infath identity")
        db.commit()
    return infath_view(row)


@router.get("/settings/infath/logo")
def infath_logo_file(db=Depends(get_db)):
    from fastapi import Response

    row = db.get(SystemSetting, "infath")
    key = row.data.get("logo_key") if row else None
    if not key:
        raise HTTPException(404, "Image not found")
    return Response(
        LocalStorage().read(key),
        media_type="image/png" if key.endswith(".png") else "image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )
