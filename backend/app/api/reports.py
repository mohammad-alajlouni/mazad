"""The Real Estate General Authority's reports after the auction: the author's
entries, their images and the live preview. The reports are issued with
POST /projects/{id}/generate (auction_closing, outputs_report)."""

from io import BytesIO
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..auth import current_user
from ..db import get_db
from ..generation.engine import render_html, reports_content, snapshot
from ..generation.generators import REPORT_GENERATORS
from ..generation.reports.compose import overflows
from ..reports_schemas import IMAGE_LIMITS, ImageCategory, ReportsData, ReportsInput
from ..services.storage import LocalStorage
from .common import get_project, invalidate, upload_bytes

router = APIRouter(dependencies=[Depends(current_user)], tags=["reports"])


def auction_project(db, id, write=False):
    """A report belongs to an auction's project (a full project or a booklet)."""
    project = get_project(db, id, write)
    if project.workspace_type not in ("project", "booklet") or not project.auction:
        raise HTTPException(400, "Reports belong to an auction project")
    return project


def stored(project):
    return ReportsData.model_validate(project.reports or {}).model_dump(mode="json")


def view(db, project):
    _, items = snapshot(db, project)
    data = stored(project)
    agent = {}
    from sqlalchemy import select

    from ..models import SellingAgent

    row = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    agent = row.data if row else {}
    return {
        "reports": {k: v for k, v in data.items() if k != "images"},
        "images": [{"id": i["id"], "category": i["category"]} for i in data["images"]],
        "limits": IMAGE_LIMITS,
        # What the project gives the reports, shown as it is.
        "shared": {
            "auction_name": (project.auction or {}).get("auction_name", ""),
            "agent_name": agent.get("name", ""),
            "agent_phone": agent.get("phone", ""),
            "properties": [
                {
                    "id": i["id"],
                    "title": i.get("title") or "",
                    "deed": (i.get("property_data") or {}).get("deed_number", ""),
                    "property_type": (i.get("property_data") or {}).get(
                        "property_type", ""
                    ),
                    "usage": (i.get("property_data") or {}).get("usage", ""),
                    "district": (i.get("property_data") or {}).get("district", ""),
                }
                for i in items
            ],
        },
    }


@router.get("/projects/{id}/reports")
def read_reports(id: str, db=Depends(get_db)):
    return view(db, auction_project(db, id))


@router.put("/projects/{id}/reports")
def save_reports(id: str, body: ReportsInput, db=Depends(get_db)):
    project = auction_project(db, id, True)
    _, items = snapshot(db, project)
    if set(body.properties) - {i["id"] for i in items}:
        raise HTTPException(400, "Unknown property")
    images = stored(project)["images"]
    project.reports = {**body.model_dump(mode="json"), "images": images}
    invalidate(db, project, output_types=set(REPORT_GENERATORS))
    db.commit()
    return view(db, project)


@router.post("/projects/{id}/report-images")
async def add_image(
    id: str,
    file: UploadFile = File(...),
    category: ImageCategory = Form(...),
    db=Depends(get_db),
):
    project = auction_project(db, id, True)
    data = stored(project)
    key = LocalStorage().image(await upload_bytes(file))
    images = data["images"]
    same = [i for i in images if i["category"] == category]
    if IMAGE_LIMITS[category] == 1:
        # One signature, one stamp, one video picture: the newest replaces it.
        images = [i for i in images if i["category"] != category]
    elif len(same) >= IMAGE_LIMITS[category]:
        raise HTTPException(409, "No more images of this kind")
    images.append({"id": uuid4().hex, "key": key, "category": category})
    project.reports = {**data, "images": images}
    invalidate(db, project, output_types=set(REPORT_GENERATORS))
    db.commit()
    return view(db, project)


@router.delete("/projects/{id}/report-images/{image}")
def remove_image(id: str, image: str, db=Depends(get_db)):
    project = auction_project(db, id, True)
    data = stored(project)
    images = [i for i in data["images"] if i["id"] != image]
    if len(images) == len(data["images"]):
        raise HTTPException(404, "Image not found")
    # The file stays: an issued report may hold it.
    project.reports = {**data, "images": images}
    invalidate(db, project, output_types=set(REPORT_GENERATORS))
    db.commit()
    return view(db, project)


@router.get("/projects/{id}/report-images/{image}")
def image_file(id: str, image: str, db=Depends(get_db)):
    project = auction_project(db, id)
    found = next((i for i in stored(project)["images"] if i["id"] == image), None)
    if not found:
        raise HTTPException(404, "Image not found")
    data = LocalStorage().read(found["key"])
    with Image.open(BytesIO(data)) as picture:
        picture.thumbnail((1400, 1400))
        out = BytesIO()
        if picture.mode in ("RGBA", "LA", "P"):
            picture.save(out, format="PNG")
            media = "image/png"
        else:
            picture.convert("RGB").save(out, format="JPEG", quality=85)
            media = "image/jpeg"
    return Response(
        out.getvalue(),
        media_type=media,
        headers={"Cache-Control": "private, max-age=86400"},
    )


class ReportsPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: Literal["auction_closing", "outputs_report"] = "outputs_report"
    # The unsaved entries (ReportsInput), as typed.
    data: dict[str, Any] | None = Field(default=None, max_length=5)
    page: int | None = Field(default=None, ge=0, le=2000)


@router.post("/projects/{id}/reports-preview")
def preview(id: str, body: ReportsPreviewInput, response: Response, db=Depends(get_db)):
    response.headers["Cache-Control"] = "no-store, private"
    project = auction_project(db, id)
    project_data, items = snapshot(db, project, linked_photos=True)
    data = stored(project)
    if body.data is not None:
        try:
            entries = ReportsInput.model_validate(body.data).model_dump(mode="json")
        except ValidationError as error:
            raise HTTPException(422, "Invalid report values") from error
        data = {**entries, "images": data["images"]}
    content = reports_content(
        project_data,
        items,
        data,
        body.report,
        lambda image: f"/api/projects/{project.id}/report-images/{image['id']}",
    )
    pages = content["pages"]
    selected = min(body.page or 0, len(pages) - 1)
    width, height = pages[selected]["size"]
    html = render_html(
        {"reports": {**content, "pages": [pages[selected]]}, "output_language": "ar"},
        "infath/reports.html",
        preview=True,
    )
    return {
        "html": html,
        "page": selected,
        "pages": [{"kind": p["kind"], "item": p.get("item", "")} for p in pages],
        "width_pt": width,
        "height_pt": height,
        "overflow": overflows(pages),
    }
