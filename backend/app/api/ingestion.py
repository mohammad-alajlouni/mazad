import json
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from PIL import Image
from sqlalchemy import func, select

from ..auth import current_user
from ..db import get_db
from ..models import ExcelImport, ExcelImportRow, ProjectImage, ProjectItem
from ..services.ingestion import DEFAULT_MAPPING, PROPERTY_TARGETS, parse_excel
from ..services.properties import save_item
from ..services.storage import LocalStorage
from .common import audit, get_project, invalidate, upload_bytes

router = APIRouter(dependencies=[Depends(current_user)], tags=["ingestion"])


@router.post("/projects/{id}/images")
async def upload_image(
    id: str,
    file: UploadFile = File(...),
    item_id: str | None = Form(None),
    category: Literal[
        "main", "additional", "cover", "auction_logo", "agent_logo"
    ] = Form("additional"),
    caption: str = Form("", max_length=300),
    db=Depends(get_db),
):
    p = get_project(db, id, True)
    if item_id:
        item = db.get(ProjectItem, item_id)
        if not item or item.project_id != id:
            raise HTTPException(400, "Item does not belong to this project")
    key = LocalStorage().image(await upload_bytes(file))
    with Image.open(BytesIO(LocalStorage().read(key))) as im:
        orientation = "portrait" if im.height > im.width else "landscape"
    if category == "main":
        for old in db.scalars(
            select(ProjectImage).where(
                ProjectImage.project_id == id,
                ProjectImage.item_id == item_id,
                ProjectImage.category == "main",
            )
        ):
            old.category = "additional"
    image = ProjectImage(
        project_id=id,
        item_id=item_id,
        key=key,
        category=category,
        caption=caption,
        orientation=orientation,
        sequence_number=(
            db.scalar(
                select(func.max(ProjectImage.sequence_number)).where(
                    ProjectImage.project_id == id
                )
            )
            or 0
        )
        + 1,
    )
    db.add(image)
    invalidate(db, p)
    db.commit()
    return image


@router.get("/images/{id}")
def image(id: str, db=Depends(get_db)):
    img = db.get(ProjectImage, id)
    if not img:
        raise HTTPException(404, "Image not found")
    get_project(db, img.project_id)
    return Response(
        LocalStorage().read(img.key),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/excel-mapping")
def excel_mapping():
    return DEFAULT_MAPPING


@router.post("/projects/{id}/imports/preview")
async def preview_import(
    id: str, file: UploadFile = File(...), mapping: str = Form(""), db=Depends(get_db)
):
    get_project(db, id)
    try:
        custom = json.loads(mapping) if mapping else None
    except ValueError:
        raise HTTPException(400, "Mapping must be valid JSON")
    if custom is not None and not isinstance(custom, dict):
        raise HTTPException(400, "Mapping must be a JSON object")
    rows = parse_excel(await upload_bytes(file), file.filename or "", custom)
    imp = ExcelImport(project_id=id, filename=(file.filename or "workbook")[:255])
    db.add(imp)
    db.flush()
    for row in rows:
        db.add(
            ExcelImportRow(
                import_id=imp.id,
                **{
                    k: v
                    for k, v in row.items()
                    if k in ("sheet", "row_number", "data", "errors")
                },
            )
        )
    audit(db, "Excel preview", f"{len(rows)} rows for {id}")
    db.commit()
    return {
        "id": imp.id,
        "rows": rows,
        "columns": list({c["header"]: c for r in rows for c in r["columns"]}.values()),
        "target_fields": sorted(
            PROPERTY_TARGETS
            | {
                "title",
                "reference",
                "category",
                "description",
                "quantity",
                "financial_value",
                "notes",
                "specifications",
                "technical_information",
                "image_reference",
                "__ignore__",
            }
        ),
        "valid_count": sum(not r["errors"] for r in rows),
        "invalid_count": sum(bool(r["errors"]) for r in rows),
    }


@router.post("/projects/{id}/imports/{import_id}/commit")
def commit_import(id: str, import_id: str, db=Depends(get_db)):
    p = get_project(db, id, True)
    imp = db.scalar(
        select(ExcelImport).where(ExcelImport.id == import_id).with_for_update()
    )
    if not imp or imp.project_id != id:
        raise HTTPException(404, "Import not found")
    if imp.status != "PREVIEW":
        raise HTTPException(409, "This workbook preview has already been imported")
    rows = db.scalars(
        select(ExcelImportRow).where(ExcelImportRow.import_id == import_id)
    ).all()
    count = 0
    for row in rows:
        if not row.errors:
            save_item(db, id, row.data)
            count += 1
    if count == 0:
        raise HTTPException(400, "No valid rows to import")
    imp.status = "IMPORTED"
    invalidate(db, p)
    audit(db, "Excel imported", f"{count} valid rows for {p.name}")
    db.commit()
    return {"imported": count, "skipped": len(rows) - count}
