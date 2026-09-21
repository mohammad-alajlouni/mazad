from io import BytesIO
from pathlib import Path
import pymupdf
import pytest
from PIL import Image
from sqlalchemy import select
from test_banners import campaign
from test_auctions import pdf, property_input, add
from test_workflow import image_data
from app.db import SessionLocal
from app.models import GeneratedOutput
from app.services.social import FORMATS

DESIGNS = [
    (f, k, t)
    for f in FORMATS
    for k in ("announcement", "property")
    for t in ("white", "teal", "navy")
    if (f == "story" or t != "navy") and (f != "story" or k == "announcement")
]


def social(
    c, kind="physical", format="instagram", post_kind="announcement", theme="white"
):
    p, i = campaign(c, kind, workspace="social")
    for data in [{"category": "cover"}, {"category": "main", "item_id": i}]:
        r = c.post(
            f"/api/projects/{p}/images",
            files={"file": ("photo.png", image_data())},
            data=data,
        )
        assert r.status_code == 200, r.text
    r = c.put(
        f"/api/projects/{p}/social-config",
        json={
            "format": format,
            "post_kind": post_kind,
            "theme": theme,
            "headline": "فرص عقارية مميزة",
            "tagline": "في وجهة واعدة استثماريًا",
            "caption": "نص مرافق تجريبي فقط",
        },
    )
    assert r.status_code == 200, r.text
    return p, i


@pytest.mark.parametrize("format,post_kind,theme", DESIGNS)
@pytest.mark.parametrize("kind", ["physical", "electronic", "hybrid"])
def test_social_dimensions_and_content(admin, format, post_kind, theme, kind):
    p, i = social(admin, kind, format, post_kind, theme)
    assert admin.get(f"/api/projects/{p}/social-review").json()["valid"]
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["social_content"]})
    assert r.status_code == 200, r.text
    o = r.json()[0]
    assert o["preflight"]["passed"] and o["preflight"]["page_count"] == 1
    assert o["social"]["width_px"] == 1080
    png = next(f for f in o["files"] if f["media_type"] == "image/png")
    raw = admin.get("/api/files/" + png["id"]).content
    im = Image.open(BytesIO(raw))
    assert im.size == (1080, FORMATS[format]["height_px"])
    if format == "x":
        # Inspect pixels, not PDF text extraction: a leaked SVG clip can hide
        # text that remains present in the PDF's searchable text layer.
        foreground = (0, 20, 71) if theme == "white" else (255, 255, 255)
        for region in [(907, 40, 1032, 136), (48, 556, 613, 638)]:
            # The native navy logo uses its own source color.
            expected = (0, 54, 93) if theme == "white" and region[0] == 907 else foreground
            pixels = im.convert("RGB").crop(region).getdata()
            assert (
                sum(max(abs(c - e) for c, e in zip(p, expected)) < 12 for p in pixels)
                > 300
            )
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as doc:
        assert len(doc) == 1
        text = doc[0].get_text()
        assert "0555000000" in text
        if post_kind == "property":
            assert "0011" in text
        if kind != "physical":
            assert "2026-10-12" in text
    txt = next(f for f in o["files"] if f["media_type"].startswith("text/"))
    caption = admin.get("/api/files/" + txt["id"]).text
    assert "420000053" in caption and "إعلان تجريبي للمعاينة فقط" in caption
    assert "نص مرافق تجريبي فقط" in caption
    if kind == "hybrid":
        out = Path(__file__).resolve().parents[2] / "output/social"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{format}-{post_kind}-{theme}.png").write_bytes(raw)
        (out / f"{format}-{post_kind}-{theme}.pdf").write_bytes(pdf(admin, o))


def test_social_validation_review_and_approval(admin):
    p, i = social(admin)
    assert len(admin.get("/api/social-templates").json()) == 3
    assert admin.get("/api/dashboard").json()["total_projects"] == 0
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["banners"]}
        ).status_code
        == 400
    )
    assert (
        admin.post(
            f"/api/projects/{p}/generate",
            json={"types": ["social_content"], "use_ai": True},
        ).status_code
        == 400
    )
    assert (
        admin.put(
            f"/api/projects/{p}/social-config",
            json={"format": "story", "post_kind": "property"},
        ).status_code
        == 422
    )
    for ids in [["foreign"], [i, i]]:
        assert (
            admin.put(
                f"/api/projects/{p}/social-config", json={"property_ids": ids}
            ).status_code
            == 400
        )
    o = admin.post(
        f"/api/projects/{p}/generate", json={"types": ["social_content"]}
    ).json()[0]
    assert (
        admin.get("/api/files/" + o["files"][0]["id"] + "?download=true").status_code
        == 409
    )
    assert (
        admin.put(
            "/api/outputs/" + o["id"], json={"review_text": "Fake legal text"}
        ).status_code
        == 409
    )
    approved = admin.post("/api/outputs/" + o["id"] + "/approve").json()
    assert approved["status"] == "APPROVED"
    assert (
        admin.get(
            "/api/files/" + approved["files"][0]["id"] + "?download=true"
        ).status_code
        == 200
    )
    raw = pdf(admin, approved)
    admin.put(f"/api/projects/{p}/social-config", json={"headline": "عنوان جديد"})
    new = admin.post("/api/outputs/" + o["id"] + "/regenerate")
    assert new.status_code == 200 and new.json()["id"] != o["id"]
    assert pdf(admin, approved) == raw
    admin.put(f"/api/projects/{p}/social-config", json={"headline": ""})
    assert not admin.get(f"/api/projects/{p}/social-review").json()["valid"]
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["social_content"]}
        ).status_code
        == 422
    )
    assert admin.get("/api/projects/not-owned/social-review").status_code == 404


def test_social_no_photo_and_no_cross_property_image(admin):
    p, i = campaign(admin, workspace="social")
    admin.put(
        f"/api/projects/{p}/social-config",
        json={"headline": "عنوان", "post_kind": "property"},
    )
    check = admin.get(f"/api/projects/{p}/social-review").json()
    assert not check["valid"] and any(
        v["field"] == "main_image" for v in check["missing"]
    )
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["social_content"]}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("format", list(FORMATS))
def test_social_english_and_schedule_caption(admin, format):
    p, _ = social(admin, format=format)
    admin.put(
        f"/api/projects/{p}/social-config",
        json={
            "format": format,
            "headline": "Property opportunities",
            "tagline": "Auction preview",
        },
    )
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["social_content"], "output_language": "en"},
    )
    assert r.status_code == 200, r.text
    o = r.json()[0]
    assert "License number: 420000053" in o["content"]["review_text"]
    assert "End date:" not in o["content"]["review_text"]
    assert o["preflight"]["passed"]


def test_social_overflow_rolls_back_and_selection_count(admin):
    p, i = social(admin)
    admin.put(f"/api/projects/{p}/social-config", json={"headline": "W" * 48})
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["social_content"]})
    assert r.status_code == 422 and r.json()["code"] == "LAYOUT_PREFLIGHT_FAILED"
    assert admin.get(f"/api/projects/{p}").json()["outputs"] == []
    second = add(admin, p, property_input(2))
    admin.put(
        f"/api/projects/{p}/social-config",
        json={"headline": "فرص عقارية", "property_ids": [second]},
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["social_content"]})
    assert r.status_code == 200, r.text
    assert "عدد العقارات: 1" in r.json()[0]["content"]["review_text"]
    admin.put(
        f"/api/projects/{p}/social-config",
        json={"headline": "فرص عقارية", "post_kind": "property"},
    )
    review = admin.get(f"/api/projects/{p}/social-review").json()
    assert any(
        v["field"] == "main_image" and v["item"] == property_input(2)["title"]
        for v in review["missing"]
    )
