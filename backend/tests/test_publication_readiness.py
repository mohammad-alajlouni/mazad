"""Everything the booklet, banners and posts need is settled in its own step,
and the live preview stays fast (linked assets, no PDF round trip)."""

import base64
from io import BytesIO

from PIL import Image
from test_auctions import add, create_auction, property_input


def workflow(admin, p):
    return admin.get(f"/api/projects/{p}").json()["workflow"]


def test_limits_of_every_output_reach_the_form_rules(admin):
    p = create_auction(admin)
    limits = workflow(admin, p)["rules"]["limits"]
    # Posts are the tightest for these fields, banners for the others.
    assert limits["auction_name"] == 48 and limits["deed_number"] == 28
    assert limits["plan_number"] == 32 and limits["court_decision_text"] == 120


def test_values_too_wide_for_the_booklet_are_reported_in_their_step(admin):
    p = create_auction(admin)
    body = property_input()
    body["property_data"]["deed_number"] = "1234567890" * 2 + "123456"  # 26 figures
    add(admin, p, body)
    items = workflow(admin, p)["stages"]["items"]
    issue = next(i for i in items["missing"] if i["field"] == "deed_number")
    assert not items["valid"] and issue["limit"] and issue["limit"] < 26
    # A normal deed number is not reported.
    q = create_auction(admin, cover="infath-3")
    add(admin, q, property_input())
    assert not any(
        i["field"] == "deed_number"
        for i in workflow(admin, q)["stages"]["items"]["missing"]
    )


def test_fixed_boxes_shrink_long_values_before_rejecting_them():
    from app.generation.booklet.fit import BOXES, box_size, fact_size, fits

    prop = {"deed_number": "12345678901234567890"}
    size = fact_size(prop, "deed_number", "landscape")
    assert 7.5 <= size < 10
    assert fact_size({"deed_number": "542104012563"}, "deed_number", "landscape") == 10
    name = "مزاد " + "أعيان حائل " * 3
    width, full, _, family, weight = BOXES["auction_name"]
    assert box_size("auction_name", name) < full
    assert fits(name, width, box_size("auction_name", name), family, weight)


def test_live_preview_assets_are_cacheable_and_contained(admin):
    ok = admin.get("/api/booklet-assets/identity/RuaqArabic-Light.ttf")
    assert ok.status_code == 200 and "max-age" in ok.headers["cache-control"]
    assert admin.get("/api/booklet-assets/booklet-art/landscape.svg").status_code == 200
    page = admin.get("/api/booklet-assets/page/terms.png")
    assert page.status_code == 200 and page.content.startswith(b"\x89PNG")
    for path in ("../../config.py", "booklet-art/terms.pdf", "missing.png"):
        assert admin.get("/api/booklet-assets/" + path).status_code == 404


def test_preview_photographs_are_reduced_and_cached(admin):
    p = create_auction(admin)
    item = add(admin, p, property_input())
    image = Image.new("RGB", (3000, 2000), (20, 120, 140))
    stream = BytesIO()
    image.save(stream, format="JPEG")
    uploaded = admin.post(
        f"/api/projects/{p}/images",
        data={"category": "main", "item_id": item},
        files={"file": ("photo.jpg", stream.getvalue(), "image/jpeg")},
    )
    assert uploaded.status_code in (200, 201), uploaded.text
    image_id = uploaded.json()["id"]
    preview = admin.get(f"/api/images/{image_id}?size=preview")
    assert "max-age" in preview.headers["cache-control"]
    assert max(Image.open(BytesIO(preview.content)).size) <= 1400
    # The live preview links the photograph instead of embedding it.
    html = admin.post(
        f"/api/projects/{p}/booklet-preview", json={"stage": "items", "page": 5}
    ).json()["html"]
    assert f"/api/images/{image_id}?size=preview" in html


def test_opaque_logo_is_not_turned_into_a_white_block():
    from app.generation.booklet.art import prepared_logo

    noise = Image.effect_noise((200, 100), 80).convert("RGB")
    stream = BytesIO()
    noise.save(stream, format="PNG")
    uri, _ = prepared_logo(
        "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode(), True
    )
    result = Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert result.convert("RGB").getextrema() != ((255, 255), (255, 255), (255, 255))
