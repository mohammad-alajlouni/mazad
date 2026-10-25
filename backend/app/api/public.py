"""The booklet's public link (services/sharing.py): what the auction's QR codes
open. No session: anyone holding the link sees the project's booklet, page by
page as pictures (every phone shows them; many download a PDF instead of
showing it), with the PDF to download.

The booklet shown is the approved one, else the latest issued.
"""

from functools import lru_cache
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from ..db import get_db
from ..models import GeneratedFile, GeneratedOutput, Project
from ..services.storage import LocalStorage

router = APIRouter(tags=["public"])
HEADERS = {"Cache-Control": "public, max-age=300", "X-Robots-Tag": "noindex"}
PAGE_WIDTH = 1240  # pixels: sharp on a phone, light to load


def booklet(db, token):
    """(project, the booklet's PDF file) for a share token, or a 404."""
    project = db.scalar(select(Project).where(Project.share_token == token))
    if project is None:
        raise HTTPException(404, "Booklet not found")
    outputs = db.scalars(
        select(GeneratedOutput)
        .where(
            GeneratedOutput.project_id == project.id,
            GeneratedOutput.output_type == "project_booklet",
        )
        .order_by(GeneratedOutput.created_at.desc())
    ).all()
    outputs.sort(key=lambda o: o.approved_at is None)  # approved first
    for output in outputs:
        file = db.scalar(
            select(GeneratedFile).where(
                GeneratedFile.output_id == output.id,
                GeneratedFile.media_type == "application/pdf",
            )
        )
        if file:
            return project, file
    return project, None


@lru_cache(maxsize=8)
def document(key):
    """The PDF's bytes and page count (cached: a QR code is scanned often)."""
    import pymupdf

    data = LocalStorage().read(key)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return data, len(doc)


@lru_cache(maxsize=64)
def page_png(key, number):
    import pymupdf

    data, _ = document(key)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc[number]
        zoom = PAGE_WIDTH / page.rect.width
        return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes(
            "png"
        )


def page_html(title, body):
    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<style>
body{{margin:0;background:#eef1f4;font-family:system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;color:#12253f}}
header{{position:sticky;top:0;z-index:1;display:flex;gap:12px;align-items:center;justify-content:space-between;
padding:12px 16px;background:#12375c;color:#fff}}
header h1{{margin:0;font-size:17px;font-weight:600}}
header a{{flex:none;color:#12375c;background:#fff;border-radius:8px;padding:8px 12px;text-decoration:none;font-size:14px;font-weight:600}}
main{{max-width:900px;margin:0 auto;padding:12px}}
img{{display:block;width:100%;height:auto;margin:0 0 12px;background:#fff;box-shadow:0 1px 6px #0002}}
p{{text-align:center;padding:48px 16px;font-size:17px}}
</style></head><body>{body}</body></html>"""


@router.get("/b/{token}", response_class=HTMLResponse)
def show(token: str, db=Depends(get_db)):
    try:
        project, file = booklet(db, token)
    except HTTPException:
        return HTMLResponse(
            page_html("كتيّب المزاد", "<p>رابط الكتيّب غير صحيح.</p>"),
            status_code=404,
            headers=HEADERS,
        )
    title = (project.auction or {}).get("auction_name") or project.name
    if file is None:
        return HTMLResponse(
            page_html(title, "<p>لم يصدر كتيّب هذا المزاد بعد.</p>"),
            status_code=404,
            headers={**HEADERS, "Cache-Control": "no-store"},
        )
    _, count = document(file.key)
    pages = "".join(
        f'<img src="/api/b/{escape(token)}/pages/{n}?v={escape(file.id)}" '
        f'alt="صفحة {n + 1}" loading="{"eager" if n < 2 else "lazy"}">'
        for n in range(count)
    )
    body = (
        f'<header><h1>{escape(title)}</h1><a href="/api/b/{escape(token)}/pdf?v='
        f'{escape(file.id)}">تحميل الكتيّب PDF</a></header><main>{pages}</main>'
    )
    return HTMLResponse(page_html(title, body), headers=HEADERS)


@router.get("/b/{token}/pages/{number}")
def page(token: str, number: int, db=Depends(get_db)):
    _, file = booklet(db, token)
    if file is None:
        raise HTTPException(404, "Booklet not found")
    _, count = document(file.key)
    if not 0 <= number < count:
        raise HTTPException(404, "Page not found")
    return Response(page_png(file.key, number), media_type="image/png", headers=HEADERS)


@router.get("/b/{token}/pdf")
def pdf(token: str, db=Depends(get_db)):
    project, file = booklet(db, token)
    if file is None:
        raise HTTPException(404, "Booklet not found")
    data, _ = document(file.key)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            **HEADERS,
            "Content-Disposition": f'inline; filename="booklet-{project.code}.pdf"'.encode(
                "ascii", "ignore"
            ).decode(),
        },
    )
