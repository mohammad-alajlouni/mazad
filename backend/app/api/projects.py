from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..auth import current_user
from ..db import get_db
from ..models import (
    AuditLog,
    GeneratedOutput,
    Project,
    ProjectImage,
    ProjectItem,
    RentalContract,
    SellingAgent,
)
from ..schemas import ItemInput, ProjectInput
from ..services.properties import item_view, save_item
from .common import audit, get_project, invalidate, output_view

router = APIRouter(dependencies=[Depends(current_user)], tags=["projects"])


@router.get("/dashboard")
def dashboard(db=Depends(get_db)):
    return {
        "total_projects": db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.owner_id == db.info.get("user_id"),
                Project.workspace_type.in_(("project", "booklet")),
            )
        ),
        "draft_projects": db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.status == "DRAFT",
                Project.owner_id == db.info.get("user_id"),
                Project.workspace_type.in_(("project", "booklet")),
            )
        ),
        "approved_outputs": db.scalar(
            select(func.count())
            .select_from(GeneratedOutput)
            .join(Project, Project.id == GeneratedOutput.project_id)
            .where(
                GeneratedOutput.status == "APPROVED",
                Project.owner_id == db.info.get("user_id"),
                Project.workspace_type.in_(("project", "booklet")),
            )
        ),
        "projects": db.scalars(
            select(Project)
            .where(
                Project.owner_id == db.info.get("user_id"),
                Project.workspace_type.in_(("project", "booklet")),
            )
            .order_by(Project.created_at.desc())
            .limit(6)
        ).all(),
        "activity": db.scalars(
            select(AuditLog)
            .where(AuditLog.owner_id == db.info.get("user_id"))
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        ).all(),
    }


@router.get("/projects")
def projects(db=Depends(get_db)):
    return db.scalars(
        select(Project)
        .where(Project.owner_id == db.info.get("user_id"))
        .order_by(Project.created_at.desc())
    ).all()


@router.post("/projects", status_code=201)
def create_project(body: ProjectInput, db=Depends(get_db)):
    data = body.model_dump(mode="json")
    data["auction"] = data["auction"] or {}
    p = Project(owner_id=db.info["user_id"], **data)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A project with this reference already exists")
    audit(db, "Project created", p.name)
    db.commit()
    return p


@router.get("/projects/{id}")
def project_detail(id: str, db=Depends(get_db)):
    p = get_project(db, id)
    return {
        "project": p,
        "selling_agent": (
            agent.data
            if (
                agent := db.scalar(
                    select(SellingAgent).where(SellingAgent.project_id == id)
                )
            )
            else {}
        ),
        "items": [
            item_view(db, i)
            for i in db.scalars(
                select(ProjectItem)
                .where(ProjectItem.project_id == id)
                .order_by(ProjectItem.sequence_number, ProjectItem.created_at)
            ).all()
        ],
        "images": db.scalars(
            select(ProjectImage).where(ProjectImage.project_id == id)
        ).all(),
        "outputs": [
            output_view(db, o)
            for o in db.scalars(
                select(GeneratedOutput)
                .where(GeneratedOutput.project_id == id)
                .order_by(GeneratedOutput.created_at.desc())
            )
        ],
    }


@router.put("/projects/{id}")
def update_project(id: str, body: ProjectInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    if body.workspace_type != p.workspace_type:
        raise HTTPException(400, "Workspace type cannot be changed")
    for k, v in body.model_dump(mode="json").items():
        if k == "auction" and v is None:
            continue
        setattr(p, k, v)
    invalidate(db, p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Project reference already exists")
    return p


@router.post("/projects/{id}/items", status_code=201)
def create_item(id: str, body: ItemInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    item = save_item(db, id, body.model_dump())
    invalidate(db, p)
    db.commit()
    return item_view(db, item)


@router.put("/projects/{id}/items/{item_id}")
def update_item(id: str, item_id: str, body: ItemInput, db=Depends(get_db)):
    p = get_project(db, id, True)
    item = db.get(ProjectItem, item_id)
    if not item or item.project_id != id:
        raise HTTPException(404, "Item not found")
    save_item(db, id, body.model_dump(), item)
    invalidate(db, p)
    db.commit()
    return item_view(db, item)


@router.delete("/projects/{id}/items/{item_id}")
def delete_item(id: str, item_id: str, db=Depends(get_db)):
    p = get_project(db, id, True)
    item = db.get(ProjectItem, item_id)
    if not item or item.project_id != id:
        raise HTTPException(404, "Item not found")
    for img in db.scalars(select(ProjectImage).where(ProjectImage.item_id == item_id)):
        db.delete(img)
    for rental in db.scalars(
        select(RentalContract).where(RentalContract.item_id == item_id)
    ):
        db.delete(rental)
    db.delete(item)
    invalidate(db, p)
    db.commit()
    return {"ok": True}
