import base64
import json
import unicodedata
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
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


def nums(value):
    """Figures as isolated left-to-right runs in Lama, as the reference sets them."""
    import re

    from markupsafe import Markup, escape

    text = "" if value in (None, "") else str(value)
    parts = re.split(r"(\d+(?:\s?[:/٫,.]\s?\d+)*)", text)
    # In Arabic text a spaced separator ("08 : 31", "2026 / 07 / 29") splits the
    # figures into separate right-to-left pieces and reverses them. The Unicode
    # isolate marks (LRI ... PDI) keep each run left-to-right as one unit; both
    # WeasyPrint (Pango/FriBidi) and browsers honour them.
    return Markup(
        "".join(
            f'<span class="num">⁦{escape(part)}⁩</span>'
            if index % 2
            else escape(part)
            for index, part in enumerate(parts)
        )
    )


env.filters["nums"] = nums


def record_dict(record):
    return {
        c.name: str(getattr(record, c.name))
        if c.name in ("quantity", "financial_value")
        else getattr(record, c.name)
        for c in record.__table__.columns
        if c.name not in ("created_at",)
    }


def snapshot(db, project, linked_photos=False):
    """Project data for rendering. With linked_photos, photographs are URLs the
    browser loads once and caches (live preview); logos stay embedded because
    they are measured and trimmed before placement."""
    storage = LocalStorage()
    images = db.scalars(
        select(ProjectImage)
        .where(ProjectImage.project_id == project.id)
        .order_by(ProjectImage.sequence_number, ProjectImage.created_at)
    ).all()

    def image_data(image):
        if linked_photos and image.category not in ("agent_logo", "auction_logo"):
            return f"/api/images/{image.id}?size=preview"
        return (
            "data:image/png;base64,"
            if image.key.endswith(".png")
            else "data:image/jpeg;base64,"
        ) + base64.b64encode(storage.read(image.key)).decode()

    project_data = record_dict(project)
    if project.auction:
        from ..auction_schemas import AuctionData

        project_data["auction"] = AuctionData.model_validate(
            project.auction
        ).model_dump(mode="json")
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
    if kind == "banners" and project.workspace_type in ("project", "banners"):
        from ..banner_schemas import BannerConfig

        config = BannerConfig.model_validate(project.banner_config or {})
        items = [
            i
            for i in items
            if not config.property_ids or i["id"] in config.property_ids
        ]
    if kind == "social_content" and project.workspace_type in ("project", "social"):
        from ..services.social import social_configuration

        social_config = social_configuration(project)
        items = [
            i
            for i in items
            if not social_config.property_ids or i["id"] in social_config.property_ids
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
    if kind == "banners" and project.workspace_type in ("project", "banners"):
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
            "data:image/png;base64,"
            if logo.endswith(".png")
            else "data:image/jpeg;base64,"
        ) + base64.b64encode(LocalStorage().read(logo)).decode()
    if kind == "project_booklet" and project.auction:
        from .booklet.composer import compose

        content["booklet"] = compose(project_data, items)
    if kind == "social_content" and project.workspace_type in ("project", "social"):
        from ..services.social import FORMATS, caption

        content["social"] = {
            **social_config.model_dump(),
            **FORMATS[social_config.format],
        }
        content["review_text"] = caption(project_data, social_config, items, language)
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
    from .booklet.composer import current_booklet

    content, upgraded = current_booklet(dict(output.content))
    if upgraded:
        # Keep the stored plan (and the page list shown to users) consistent.
        output.content = {**output.content, "booklet": content["booklet"]}
    if output.output_type == "banners" and content["project"].get("auction"):
        template_file = "infath/banners.html"
    if content.get("banner"):
        template_file = "infath/board.html"
    if content.get("social"):
        template_file = "infath/social.html"
    if content.get("booklet"):
        template_file = "infath/booklet.html"
    html = render_html(content, template_file, output.status, font_data, font_bold)

    from .preflight import check_layout, inspect_pdf

    document = HTML(string=html, url_fetcher=safe_fetch).render()
    check_layout(document, content)
    from .booklet.art import original_pdf_artwork

    pdf = original_pdf_artwork(document.write_pdf(), content)
    preflight = inspect_pdf(pdf, content)
    if preflight:
        output.content = {**output.content, "preflight": preflight}

    files = [("pdf", "application/pdf", pdf)]
    if output.output_type == "banners" or content.get("social"):
        import pymupdf

        with pymupdf.open(stream=pdf, filetype="pdf") as document:
            for page in document:
                files.append(
                    (
                        "png",
                        "image/png",
                        page.get_pixmap(
                            matrix=pymupdf.Matrix(
                                (
                                    content["social"]["width_px"]
                                    if content.get("social")
                                    else 2400
                                )
                                / page.rect.width,
                                (
                                    content["social"]["width_px"]
                                    if content.get("social")
                                    else 2400
                                )
                                / page.rect.width,
                            )
                            if content.get("banner") or content.get("social")
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


def safe_fetch(url, *args, **kwargs):
    from weasyprint import default_url_fetcher

    if not url.startswith("data:"):
        raise ValueError("External resource loading is disabled")
    return default_url_fetcher(url)


def render_html(
    content,
    template_file="infath/booklet.html",
    status="DRAFT",
    font_data="",
    font_bold="",
    preview=False,
):
    content.setdefault(
        "output_language", content.get("branding", {}).get("default_language", "en")
    )
    labels = document_messages(content["output_language"])
    from .identity import load_identity

    try:
        identity, identity_asset = load_identity()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            503, "Official design assets are unavailable or invalid"
        ) from exc
    from .booklet.assets import asset
    from .booklet.codes import qr

    if preview:
        # The browser fetches fonts and artwork once from cacheable URLs.
        def asset(name):
            return "/api/booklet-assets/" + name

        def identity_asset(name):
            return "/api/booklet-assets/identity/" + name

    from .booklet.composer import FIELDS, RENTAL_FIELDS, SUMMARY_FIELDS
    from .booklet.labels import label

    from .social_art import photo_frame
    from .booklet import fit, formatting
    from .booklet.art import (
        page_shape,
        photo,
        shape_in,
        table_lines,
        rentals_column,
        shapes,
        summary_column,
        logo_fit,
        white_logo,
    )

    return env.get_template(template_file).render(
        **content,
        t=lambda key, **values: labels.get(key, key).format(**values),
        status=status,
        preview=preview,
        font_data=font_data,
        font_bold=font_bold,
        asset=asset,
        identity=identity,
        identity_asset=identity_asset,
        photo_frame=photo_frame,
        photo=photo,
        page_shape=page_shape,
        shape_in=shape_in,
        table_lines=table_lines,
        summary_column=summary_column,
        rentals_column=rentals_column,
        white_logo=white_logo,
        logo_fit=logo_fit,
        shapes=shapes,
        fmt=formatting,
        fit=fit,
        has_digits=formatting.uses_digits,
        qr=qr,
        bt=lambda key: label(key, content["output_language"]),
        display=lambda value: "-" if value in (None, "") else str(value),
        property_fields=FIELDS,
        summary_fields=SUMMARY_FIELDS,
        rental_fields=RENTAL_FIELDS,
    )
