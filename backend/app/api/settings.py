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
