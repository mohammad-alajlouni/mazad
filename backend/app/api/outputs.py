from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auth import current_user
from ..db import get_db
from ..generation.booklet.validation import validate_project
from ..generation.engine import build_content, render
from ..generation.generators import GENERATORS
from ..models import (
    AIGeneration,
    GeneratedFile,
    GeneratedOutput,
    Project,
    ProjectItem,
    Template,
    now,
)
from ..services.ai import AIService
from ..services.storage import LocalStorage
from .common import audit, get_output, get_project, output_view

router = APIRouter(dependencies=[Depends(current_user)], tags=["outputs"])


@router.get("/output-types")
def output_types():
    return [{"key": k, "title": g.title} for k, g in GENERATORS.items()]


class GenerationInput(BaseModel):
    types: list[str] = Field(
        default_factory=lambda: list(GENERATORS), min_length=1, max_length=8
    )
    use_ai: bool = False
    output_language: Literal["en", "ar"] | None = None


@router.post("/projects/{id}/generate")
async def generate(id: str, body: GenerationInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    if any(k not in GENERATORS for k in body.types):
        raise HTTPException(400, "Unknown output type")
    if not db.scalar(
        select(ProjectItem.id).where(ProjectItem.project_id == id).limit(1)
    ):
        raise HTTPException(400, "Add at least one item before generating outputs")
    if (
        "project_booklet" in body.types
        and p.auction
        and not validate_project(db, p)["valid"]
    ):
        raise HTTPException(422, "Complete the auction review before generation")
    if p.workspace_type == "banners":
        if set(body.types) != {"banners"}:
            raise HTTPException(400, "Use the banner workspace")
        from ..services.banners import review_banners

        if not review_banners(db, p)["valid"]:
            raise HTTPException(422, "Complete the banner review before generation")
    if p.workspace_type == "social":
        if set(body.types) != {"social_content"} or body.use_ai:
            raise HTTPException(400, "Use the social workspace")
        from ..services.social import review_social

        if not review_social(db, p)["valid"]:
            raise HTTPException(422, "Complete the social review before generation")
    result = []
    for kind in dict.fromkeys(body.types):
        template = db.scalar(select(Template).where(Template.output_type == kind))
        if not template:
            raise HTTPException(
                503, "Templates are not initialized. Run the bootstrap command."
            )
        content = build_content(db, p, kind, body.output_language)
        if body.use_ai:
            ai = await AIService().generate(
                "social content" if kind == "social_content" else "summary",
                {
                    "project": {
                        k: v
                        for k, v in content["project"].items()
                        if k
                        not in (
                            "images",
                            "image_assets",
                            "qr_links",
                            "agent_logo",
                            "auction_logo",
                            "cover_image",
                        )
                    },
                    "items": [
                        {
                            k: v
                            for k, v in i.items()
                            if k
                            not in (
                                "images",
                                "image_assets",
                                "qr_links",
                                "agent_logo",
                                "auction_logo",
                                "cover_image",
                            )
                        }
                        for i in content["items"]
                    ],
                },
                output_language=content["output_language"],
            )
            content["ai_status"] = ai["status"]
            content["ai_message"] = ai["message"]
            if ai["text"]:
                content["review_text"] = ai["text"]
            db.add(
                AIGeneration(
                    project_id=id, purpose=kind, status=ai["status"], text=ai["text"]
                )
            )
        o = GeneratedOutput(
            project_id=id,
            output_type=kind,
            content=content,
            template_id=template.id,
            revision=p.revision,
        )
        db.add(o)
        db.flush()
        render(db, o)
        audit(db, "Output generated", f"{GENERATORS[kind].title} · {p.name}")
        result.append(o)
    db.commit()
    return [output_view(db, o) for o in result]


@router.get("/outputs")
def outputs(db=Depends(get_db)):
    return [
        output_view(db, o)
        for o in db.scalars(
            select(GeneratedOutput)
            .join(Project, Project.id == GeneratedOutput.project_id)
            .where(Project.owner_id == db.info.get("user_id"))
            .order_by(GeneratedOutput.created_at.desc())
        )
    ]


@router.get("/outputs/{id}")
def output(id: str, db=Depends(get_db)):
    return output_view(db, get_output(db, id))


class ReviewInput(BaseModel):
    review_text: str = Field(max_length=30000)


@router.put("/outputs/{id}")
def edit_output(id: str, body: ReviewInput, db=Depends(get_db)):
    o = get_output(db, id)
    if o.status == "NEEDS_REGENERATION":
        raise HTTPException(409, "Source data changed. Regenerate first.")
    if o.content.get("booklet") or o.content.get("banner") or o.content.get("social"):
        raise HTTPException(409, "Edit auction data and regenerate the booklet")
    o.content = {**o.content, "review_text": body.review_text}
    o.status = "DRAFT"
    o.approved_at = None
    render(db, o)
    audit(db, "Output edited", id)
    db.commit()
    return output_view(db, o)


@router.post("/outputs/{id}/approve")
def approve(id: str, db=Depends(get_db)):
    o = get_output(db, id)
    p = get_project(db, o.project_id, True)
    if o.revision != p.revision or o.status == "NEEDS_REGENERATION":
        raise HTTPException(409, "Source data changed. Regenerate before approval.")
    if o.status == "APPROVED":
        return output_view(db, o)
    o.status = "APPROVED"
    o.approved_at = now()
    render(db, o)
    audit(db, "Output approved", f"{o.output_type} · {p.name}")
    db.commit()
    return output_view(db, o)


@router.post("/outputs/{id}/regenerate")
def regenerate(id: str, db=Depends(get_db)):
    o = get_output(db, id)
    p = get_project(db, o.project_id, True)
    output_language = o.content.get("output_language", "en")
    if o.output_type == "project_booklet" and p.auction:
        if not validate_project(db, p)["valid"]:
            raise HTTPException(422, "Complete the auction review before generation")
        if o.approved_at:
            o = GeneratedOutput(
                project_id=p.id,
                output_type=o.output_type,
                template_id=o.template_id,
                content={},
                revision=p.revision,
            )
            db.add(o)
            db.flush()
    if o.output_type == "banners" and p.workspace_type == "banners":
        from ..services.banners import review_banners

        if not review_banners(db, p)["valid"]:
            raise HTTPException(422, "Complete the banner review before generation")
        if o.approved_at:
            o = GeneratedOutput(
                project_id=p.id,
                output_type=o.output_type,
                template_id=o.template_id,
                content={},
                revision=p.revision,
            )
            db.add(o)
            db.flush()
    if o.output_type == "social_content" and p.workspace_type == "social":
        from ..services.social import review_social

        if not review_social(db, p)["valid"]:
            raise HTTPException(422, "Complete the social review before generation")
        if o.approved_at:
            o = GeneratedOutput(
                project_id=p.id,
                output_type=o.output_type,
                template_id=o.template_id,
                content={},
                revision=p.revision,
            )
            db.add(o)
            db.flush()
    o.content = build_content(db, p, o.output_type, output_language)
    o.status = "DRAFT"
    o.revision = p.revision
    o.approved_at = None
    render(db, o)
    audit(db, "Output regenerated", id)
    db.commit()
    return output_view(db, o)


@router.get("/files/{id}")
def generated_file(id: str, download: bool = False, db=Depends(get_db)):
    file = db.get(GeneratedFile, id)
    if not file:
        raise HTTPException(404, "File not found")
    o = get_output(db, file.output_id)
    if download and o.status != "APPROVED":
        raise HTTPException(409, "Approve this output before exporting it")
    suffix = file.key.rsplit(".", 1)[-1]
    filename = f"{o.output_type}.{suffix}"
    if o.content.get("social"):
        filename = f"social-{o.content['social']['format']}-{file.id[:8]}.{suffix}"
    if o.content.get("banner"):
        filename = f"banner-{o.content['banner']['size']}-{file.id[:8]}.{suffix}"
    if o.content.get("booklet"):
        import re

        code = re.sub(r"[^a-zA-Z0-9_-]", "-", o.content["project"]["code"])[:70]
        filename = f"auction-{code}-{o.created_at:%Y-%m-%d}.{suffix}"
    return Response(
        LocalStorage().read(file.key),
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
