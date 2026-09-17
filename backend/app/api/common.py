import logging

from fastapi import HTTPException
from sqlalchemy import select

from ..config import settings
from ..models import (
    AuditLog,
    GeneratedFile,
    GeneratedOutput,
    Project,
)

logger = logging.getLogger(__name__)


def get_project(db, id, lock=False):
    query = select(Project).where(
        Project.id == id, Project.owner_id == db.info.get("user_id")
    )
    if lock:
        query = query.with_for_update()
    p = db.scalar(query)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def get_output(db, id):
    o = db.get(GeneratedOutput, id)
    if not o:
        raise HTTPException(404, "Output not found")
    get_project(db, o.project_id, True)
    return db.scalar(
        select(GeneratedOutput)
        .where(GeneratedOutput.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def audit(db, action, detail):
    logger.info("%s: %s", action, detail)
    db.add(AuditLog(action=action, detail=detail, owner_id=db.info.get("user_id")))


def invalidate(db, project):
    project.revision += 1
    for o in db.scalars(
        select(GeneratedOutput).where(GeneratedOutput.project_id == project.id)
    ):
        o.status = "NEEDS_REGENERATION"
        if not o.content.get("booklet"):
            o.approved_at = None


def output_view(db, o):
    content = {
        k: v
        for k, v in o.content.items()
        if k not in ("items", "project", "logo", "booklet")
    }
    return {
        "id": o.id,
        "project_id": o.project_id,
        "project_name": o.content["project"]["name"],
        "output_type": o.output_type,
        "status": o.status,
        "content": content,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "approved_at": o.approved_at,
        "official_booklet": bool(o.content.get("booklet")),
        "cover_id": o.content.get("booklet", {}).get("cover_id"),
        "page_manifest": [
            {"kind": p["kind"], "property_number": p.get("item", {}).get("number")}
            for p in o.content.get("booklet", {}).get("pages", [])
        ],
        "files": [
            {"id": f.id, "media_type": f.media_type}
            for f in db.scalars(
                select(GeneratedFile)
                .where(GeneratedFile.output_id == o.id)
                .order_by(GeneratedFile.created_at)
            )
        ],
    }


async def upload_bytes(file):
    data = await file.read(settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds upload limit")
    return data
