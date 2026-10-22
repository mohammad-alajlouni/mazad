"""The auction's official forms: the author's entries, what the booklet
gives them, and their live preview."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from ..auth import current_user
from ..db import get_db
from ..forms_schemas import FormsData
from ..generation.engine import FORM_KINDS, forms_content, render_html, snapshot
from ..generation.forms.compose import missing, overflows, shared
from ..generation.forms.questions import SECTIONS
from ..generation.generators import FORM_GENERATORS
from ..models import Project
from .common import get_project, invalidate

router = APIRouter(dependencies=[Depends(current_user)], tags=["forms"])

# The establishment and the people who run the auction rarely change from one
# auction to the next: a new project starts with the author's last ones.
CARRIED = (
    "cr_number",
    "unified_number",
    "fal_license",
    "manager_name",
    "manager_id",
    "manager_mobile",
    "manager_email",
    "crier_name",
    "crier_id",
    "crier_mobile",
    "crier_email",
    "declarant",
)


def carried_over(db, project):
    """The author's last entered establishment and auction staff."""
    if any((project.forms or {}).get("request", {}).get(k) for k in CARRIED):
        return {}
    for other in db.scalars(
        select(Project)
        .where(Project.owner_id == project.owner_id, Project.id != project.id)
        .order_by(Project.created_at.desc())
        .limit(30)
    ):
        request = (other.forms or {}).get("request") or {}
        if any(request.get(k) for k in CARRIED):
            return {k: request[k] for k in CARRIED if request.get(k)}
    return {}


def view(db, project):
    project_data, items = snapshot(db, project)
    forms = FormsData.model_validate(project.forms or {}).model_dump(mode="json")
    forms["request"] = {**forms["request"], **carried_over(db, project)}
    pages = forms_content(project_data, items, forms, "auction_request")["pages"]
    return {
        "forms": forms,
        "shared": shared(project_data, items),
        "missing": missing(project_data, items, forms),
        "overflow": overflows(pages),
        "sections": [
            {
                "number": number,
                "title": title,
                "questions": [{"key": k, "text": q} for k, q in rows],
            }
            for number, title, rows in SECTIONS
        ],
    }


@router.get("/projects/{id}/forms")
def read_forms(id: str, db=Depends(get_db)):
    return view(db, get_project(db, id))


@router.put("/projects/{id}/forms")
def save_forms(id: str, body: FormsData, db=Depends(get_db)):
    project = get_project(db, id, True)
    _, items = snapshot(db, project)
    known = {i["id"] for i in items}
    if set(body.properties) - known:
        raise HTTPException(400, "Unknown property")
    project.forms = body.model_dump(mode="json")
    invalidate(db, project, output_types=set(FORM_GENERATORS))
    db.commit()
    return view(db, project)


class FormsPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: Literal["request", "study"] = "request"
    # The form's unsaved values (FormsData), as typed.
    forms: dict[str, Any] | None = Field(default=None, max_length=5)
    item: str | None = Field(default=None, max_length=100)
    page: int | None = Field(default=None, ge=0, le=2000)


@router.post("/projects/{id}/forms-preview")
def preview_forms(id: str, body: FormsPreviewInput, db=Depends(get_db)):
    project = get_project(db, id)
    project_data, items = snapshot(db, project)
    try:
        forms = FormsData.model_validate(
            project.forms if body.forms is None else body.forms
        ).model_dump(mode="json")
    except ValidationError as error:
        raise HTTPException(422, "Invalid form values") from error
    kind = next(k for k, v in FORM_KINDS.items() if v == body.form)
    content = forms_content(project_data, items, forms, kind)
    pages = content["pages"]
    if not pages:
        raise HTTPException(409, "Add a property first")
    titles = {i["id"]: i.get("title") or "" for i in items}
    listed = [
        {
            "kind": f"request-{p['sheet']}" if body.form == "request" else "study",
            "item": "" if body.form == "request" else titles[items[n]["id"]],
            "step": "forms",
            "size": p.get("size", [595.276, 841.89]),
        }
        for n, p in enumerate(pages)
    ]
    selected = body.page
    if selected is None and body.form == "study" and body.item in titles:
        selected = next((n for n, i in enumerate(items) if i["id"] == body.item), 0)
    selected = min(selected or 0, len(pages) - 1)
    width, height = listed[selected]["size"]
    if body.form == "study":
        # Infath's sheet runs on: the preview shows it whole, two pages long.
        height = height * 2
    html = render_html(
        {
            "project": project_data,
            "items": items,
            "forms": {**content, "pages": [pages[selected]]},
            "output_language": "ar",
        },
        "infath/forms.html",
        preview=True,
    )
    return {
        "html": html,
        "page": selected,
        "pages": [{k: v for k, v in p.items() if k != "size"} for p in listed],
        "width_pt": width,
        "height_pt": height,
        "saved": False,
        "auto": None,
    }
