import base64
import json
import unicodedata
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from weasyprint import HTML

from ..models import (
    GeneratedFile,
    GeneratedOutput,
    ProjectImage,
    ProjectItem,
    RentalContract,
    SellingAgent,
    SystemSetting,
    Template,
)
from ..services.storage import LocalStorage
from .generators import GENERATORS

TEMPLATE_ROOT = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATE_ROOT), autoescape=select_autoescape(["html"])
)


def direction(value):
    for char in str(value):
        bidi = unicodedata.bidirectional(char)
        if bidi in ("R", "AL"):
            return "rtl"
        if bidi == "L":
            return "ltr"
    return "ltr"


env.filters["direction"] = direction


def record_dict(record):
    return {
        c.name: str(getattr(record, c.name))
        if c.name in ("quantity", "financial_value")
        else getattr(record, c.name)
        for c in record.__table__.columns
        if c.name not in ("created_at",)
    }


def snapshot(db, project):
    storage = LocalStorage()
    images = db.scalars(
        select(ProjectImage)
        .where(ProjectImage.project_id == project.id)
        .order_by(ProjectImage.sequence_number, ProjectImage.created_at)
    ).all()

    def image_data(image):
        return (
            "data:image/jpeg;base64,"
            + base64.b64encode(storage.read(image.key)).decode()
        )

    project_data = record_dict(project)
    agent = db.scalar(select(SellingAgent).where(SellingAgent.project_id == project.id))
    project_data["selling_agent"] = agent.data if agent else {}
    project_data["agent_logo"] = next(
        (
            image_data(i)
            for i in images
            if i.id == project_data["selling_agent"].get("logo_image_id")
            and not i.item_id
        ),
        "",
    )
    project_data["cover_image"] = next(
        (
            image_data(i)
            for i in reversed(images)
            if i.category == "cover" and not i.item_id
        ),
        "",
    )
    project_data["auction_logo"] = next(
        (
            image_data(i)
            for i in images
            if i.category == "auction_logo" and not i.item_id
        ),
        "",
    )
    project_data["images"] = [image_data(i) for i in images if not i.item_id]
    items = []
    for item in db.scalars(
        select(ProjectItem)
        .where(ProjectItem.project_id == project.id)
        .order_by(ProjectItem.sequence_number, ProjectItem.created_at)
    ):
        data = record_dict(item)
        data["line_total"] = str(
            (Decimal(data["quantity"]) * Decimal(data["financial_value"])).quantize(
                Decimal(".01")
            )
        )
        own = sorted(
            [i for i in images if i.item_id == item.id],
            key=lambda i: (i.category != "main", i.sequence_number, i.created_at),
        )
        data["images"] = [image_data(i) for i in own]
        data["image_assets"] = [
            {
                "id": i.id,
                "src": image_data(i),
                "orientation": i.orientation,
                "caption": i.caption,
            }
            for i in own
        ]
        data["property_data"] = {
            **data["property_data"],
            "rental_contracts": [
                r.data
                for r in db.scalars(
                    select(RentalContract)
                    .where(RentalContract.item_id == item.id)
                    .order_by(RentalContract.sequence_number)
                )
            ],
        }
        reference = data["attributes"].get("image_reference")
        # References may only resolve to already-uploaded assets from this project.
        if reference:
            data["images"] += [
                image_data(i)
                for i in images
                if reference in (i.id, i.key)
                and i.item_id in (None, item.id)
                and image_data(i) not in data["images"]
            ]
        if reference:
            for image in images:
                if (
                    reference in (image.id, image.key)
                    and image.item_id in (None, item.id)
                    and all(a["id"] != image.id for a in data["image_assets"])
                ):
                    data["image_assets"].append(
                        {
                            "id": image.id,
                            "src": image_data(image),
                            "orientation": image.orientation,
                            "caption": image.caption,
                        }
                    )
        items.append(data)
    return project_data, items


def build_content(db, project, kind, output_language=None):
    project_data, items = snapshot(db, project)
    if kind == "banners" and project.workspace_type == "banners":
        from ..banner_schemas import BannerConfig

        config = BannerConfig.model_validate(project.banner_config or {})
        items = [
            i
            for i in items
            if not config.property_ids or i["id"] in config.property_ids
        ]
    reports = [
        {
            "output_type": o.output_type,
            "status": o.status,
            "created_at": o.created_at.isoformat(),
        }
        for o in db.scalars(
            select(GeneratedOutput).where(GeneratedOutput.project_id == project.id)
        )
    ]
    content = GENERATORS[kind].build(project_data, items, reports)
    if kind == "banners" and project.workspace_type == "banners":
        from ..services.banners import SIZES

        content["banner"] = {**SIZES[config.size], "size": config.size, "scale": "1:10"}
    branding = db.get(SystemSetting, "global")
    content["branding"] = dict(branding.data) if branding else {}
    language = (
        output_language
        or project_data.get("auction", {}).get("document_language")
        or content["branding"].get("default_language", "en")
    )
    content["output_language"] = language
    content["branding"]["default_language"] = language
    labels = document_messages(language)
    if language == "ar":
        content["title"] = labels.get(kind, content["title"])
    if "notice" in content:
        content["notice"] = labels.get(content["notice"], content["notice"])
    if kind == "social_content" and not project_data["description"]:
        content["review_text"] = "\n\n".join(
            [
                project_data["name"],
                labels["Project overview"],
                *[
                    f"{i['title']} ({i['reference']})\n{i['description']}\n{i['specifications']}"
                    for i in items
                ],
            ]
        )
    if kind == "booklet_study_report":
        content["findings"] = [
            i["title"]
            + ": "
            + ", ".join(
                labels[field.replace("_", " ")]
                + ": "
                + labels["provided" if i.get(field) else "missing"]
                for field in (
                    "description",
                    "specifications",
                    "technical_information",
                    "images",
                )
            )
            for i in items
        ]
    logo = content["branding"].get("logo_key")
    if logo:
        content["logo"] = (
            "data:image/jpeg;base64,"
            + base64.b64encode(LocalStorage().read(logo)).decode()
        )
    if kind == "project_booklet" and project.auction:
        from .booklet.composer import compose

        content["booklet"] = compose(project_data, items)
    return content


def document_messages(language):
    locale = "ar" if language == "ar" else "en"
    return json.loads((TEMPLATE_ROOT / "messages" / f"{locale}.json").read_text())


def render(db, output):
    storage = LocalStorage()
    font_data = base64.b64encode(
        (TEMPLATE_ROOT / "fonts/NotoSansArabic-Regular.ttf").read_bytes()
    ).decode()
    font_bold = base64.b64encode(
        (TEMPLATE_ROOT / "fonts/NotoSansArabic-Bold.ttf").read_bytes()
    ).decode()
    template = db.get(Template, output.template_id)
    template_file = template.config.get("file", f"{output.output_type}.html")
    if (TEMPLATE_ROOT / template_file).resolve().parent != TEMPLATE_ROOT.resolve():
        raise ValueError("Invalid template path")
    content = dict(output.content)
    if output.output_type == "banners" and content["project"].get("auction"):
        template_file = "infath/banners.html"
    if content.get("banner"):
        template_file = "infath/board.html"
    if content.get("booklet"):
        template_file = "infath/booklet.html"
    content.setdefault(
        "output_language", content.get("branding", {}).get("default_language", "en")
    )
    labels = document_messages(content["output_language"])
    from .booklet.assets import asset
    from .booklet.codes import qr
    from .booklet.composer import FIELDS, RENTAL_FIELDS, SUMMARY_FIELDS
    from .booklet.labels import label

    html = env.get_template(template_file).render(
        **content,
        t=lambda key, **values: labels.get(key, key).format(**values),
        status=output.status,
        font_data=font_data,
        font_bold=font_bold,
        asset=asset,
        qr=qr,
        bt=lambda key: label(key, content["output_language"]),
        display=lambda value: "-" if value in (None, "") else str(value),
        property_fields=FIELDS,
        summary_fields=SUMMARY_FIELDS,
        rental_fields=RENTAL_FIELDS,
    )

    def safe_fetch(url, *args, **kwargs):
        from weasyprint import default_url_fetcher

        if not url.startswith("data:"):
            raise ValueError("External resource loading is disabled")
        return default_url_fetcher(url)

    pdf = HTML(string=html, url_fetcher=safe_fetch).write_pdf()
    files = [("pdf", "application/pdf", pdf)]
    if output.output_type == "banners":
        import pymupdf

        with pymupdf.open(stream=pdf, filetype="pdf") as document:
            for page in document:
                files.append(
                    (
                        "png",
                        "image/png",
                        page.get_pixmap(
                            matrix=pymupdf.Matrix(
                                2400 / page.rect.width, 2400 / page.rect.width
                            )
                            if content.get("banner")
                            else pymupdf.Matrix(1.3, 1.3)
                        ).tobytes("png"),
                    )
                )
    if output.output_type == "social_content":
        files.append(
            ("txt", "text/plain; charset=utf-8", output.content["review_text"].encode())
        )
    old = db.scalars(
        select(GeneratedFile).where(GeneratedFile.output_id == output.id)
    ).all()
    for file in old:
        db.delete(file)
    for suffix, mime, data in files:
        db.add(
            GeneratedFile(
                output_id=output.id, key=storage.put(data, suffix), media_type=mime
            )
        )
    db.flush()
