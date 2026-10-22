"""Live preview of the guide's boards and social posts, as the forms stand."""

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import Field, ValidationError

from ..banner_schemas import BannerConfig
from ..generation.engine import render_html
from ..generation.marketing.compose import field_of, marketing_content
from .booklet_preview import PreviewInput, drafted
from .social import FORMATS, social_configuration


class MarketingPreviewInput(PreviewInput):
    kind: Literal["banner", "social"] = "banner"
    # The template step's unsaved choices (BannerConfig or SocialConfig).
    config: dict[str, Any] | None = Field(default=None, max_length=20)


def preview(db, project, body):
    workspace = "banners" if body.kind == "banner" else "social"
    if project.workspace_type not in ("project", workspace):
        raise HTTPException(400, "Use the " + workspace + " workspace")
    p, items, focused, _ = drafted(db, project, body)
    try:
        if body.kind == "banner":
            config = BannerConfig.model_validate(
                project.banner_config or {} if body.config is None else body.config
            )
        else:
            config = social_configuration(project, body.config)
    except ValidationError as error:
        raise HTTPException(422, "Invalid template settings") from error
    chosen = config.property_ids
    items = [i for i in items if not chosen or i["id"] in chosen or i["id"] == focused]
    content = {"project": p, "items": items, "output_language": "ar"}
    if body.kind == "banner":
        from .banners import SIZES

        content["banner"] = {**SIZES[config.size], **config.model_dump()}
    else:
        content["social"] = {**config.model_dump(), **FORMATS[config.format]}
    if not items and (body.kind == "banner" or config.post_kind == "property"):
        raise HTTPException(409, "Add a property first")
    marketing = marketing_content(content)
    auction = p.get("auction") or {}
    pages = marketing["pages"]
    selected = body.page
    if selected is None and focused:
        titles = [i["title"] for i in items if i["id"] == focused]
        selected = next(
            (n for n, page in enumerate(pages) if titles and page["item"] == titles[0]),
            None,
        )
    selected = min(selected or 0, len(pages) - 1)
    width, height = pages[selected]["size"]
    # The browser renders this page directly: export sets the same template
    # through WeasyPrint, with the guide's design as vectors beneath.
    html = render_html(
        {
            "marketing": {**marketing, "pages": [pages[selected]]},
            "output_language": "ar",
        },
        "infath/marketing.html",
        preview=True,
    )
    return {
        "html": html,
        "page": selected,
        "pages": [{"kind": page["name"], "item": page["item"]} for page in pages],
        "width_pt": width,
        "height_pt": height,
        # Values longer than their place in the design (set at the smallest
        # size; generation waits until they are shortened).
        "overflow": [
            {"page": n, "item": page["item"], "field": field_of(t["key"], auction)}
            for n, page in enumerate(pages)
            for t in page["texts"]
            if not t["fits"] and field_of(t["key"], auction)
        ],
    }
