"""The agent's logo larger or smaller, from the live preview: its own size in
the booklet, on the boards and on the posts."""

import re
from io import BytesIO

import pymupdf
import pytest
from PIL import Image
from test_auctions import add, create_auction, generate, pdf, property_input
from test_banners import campaign

from app.generation.marketing.compose import layout, logo_room


# The logo on a post, in its preview's HTML: its width in points.
LOGO = r'<img class="layer"[^>]*width:([\d.]+)pt'


def logo():
    data = BytesIO()
    Image.new("RGB", (900, 300), (20, 60, 160)).save(data, "PNG")
    return data.getvalue()


def with_logo(admin, p):
    r = admin.post(
        f"/api/projects/{p}/images",
        files={"file": ("logo.png", logo())},
        data={"category": "agent_logo"},
    )
    assert r.status_code == 200, r.text
    agent = admin.get(f"/api/projects/{p}").json()["selling_agent"]
    r = admin.put(
        f"/api/projects/{p}/selling-agent",
        json={k: agent.get(k, "") for k in ("name", "description", "phone", "website")}
        | {"logo_image_id": r.json()["id"]},
    )
    assert r.status_code == 200, r.text


def scale(admin, p, kind, value):
    return admin.put(
        f"/api/projects/{p}/agent-logo-scales", json={"kind": kind, "scale": value}
    )


def footer_logo(document):
    """The agent's logo in a booklet's footer: (width, height), points."""
    page = next(pg for pg in document if "بيان" in pg.get_text() or pg.number == 4)
    rects = [
        r
        for image in page.get_images(full=True)
        for r in page.get_image_rects(image[0])
        if r.y0 > 760
    ]
    assert rects
    return rects[0]


def test_each_kind_of_output_has_its_own_logo_size(admin):
    p = create_auction(admin, "physical")
    add(admin, p, property_input())
    url = f"/api/projects/{p}/agent-logo-scales"
    assert admin.get(url).json() == {"booklet": 1.0, "banner": 1.0, "social": 1.0}
    r = scale(admin, p, "social", 0.6)
    assert r.status_code == 200
    assert r.json() == {"booklet": 1.0, "banner": 1.0, "social": 0.6}
    assert admin.get(url).json()["social"] == 0.6
    # Out of range, or an unknown kind: refused.
    assert scale(admin, p, "social", 0.1).status_code == 422
    assert scale(admin, p, "social", 3).status_code == 422
    assert scale(admin, p, "poster", 1).status_code == 422
    # Saving the project's form keeps it (the form does not carry it).
    detail = admin.get(f"/api/projects/{p}").json()["project"]
    assert admin.put(f"/api/projects/{p}", json=detail).status_code == 200
    assert admin.get(url).json()["social"] == 0.6


def test_the_size_sets_the_logo_in_the_booklet_and_issues_only_it_again(admin):
    p = create_auction(admin, "physical")
    add(admin, p, property_input())
    with_logo(admin, p)
    first = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, first), filetype="pdf") as document:
        full = footer_logo(document)
    assert scale(admin, p, "booklet", 0.5).status_code == 200
    outputs = admin.get(f"/api/projects/{p}").json()["outputs"]
    assert outputs[0]["status"] == "NEEDS_REGENERATION"
    second = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, second), filetype="pdf") as document:
        half = footer_logo(document)
    assert half.width == pytest.approx(full.width / 2, abs=0.2)
    assert half.x0 == pytest.approx(full.x0, abs=0.1)
    # Larger: it stays above the footer's bar.
    assert scale(admin, p, "booklet", 1.5).status_code == 200
    third = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, third), filetype="pdf") as document:
        large = footer_logo(document)
    assert large.width > full.width and large.y1 <= 822


def test_the_size_sets_the_logo_on_boards_and_keeps_it_under_its_label(admin):
    p, _ = campaign(admin)
    assert (
        admin.put(
            f"/api/projects/{p}/banner-config",
            json={"auto_size": False, "size": "4x2"},
        ).status_code
        == 200
    )
    with_logo(admin, p)

    def board():
        r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
        assert r.status_code == 200, r.text
        with pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf") as doc:
            page = doc[0]
            rects = [
                x
                for image in page.get_images(full=True)
                for x in page.get_image_rects(image[0])
            ]
            return min(rects, key=lambda x: x.width)

    full = board()
    assert scale(admin, p, "banner", 0.5).status_code == 200
    half = board()
    assert half.width == pytest.approx(full.width / 2, abs=0.5)
    assert (half.x0 + half.x1) / 2 == pytest.approx((full.x0 + full.x1) / 2, abs=0.5)


def test_a_larger_logo_grows_only_into_free_room():
    name = "board-landscape-physical"
    box = next(s for s in layout()[name]["slots"] if s["key"] == "agent_logo")["box"]
    usual = logo_room(name, box, [])
    larger = logo_room(name, box, [], scale=1.5)
    assert larger[2] - larger[0] >= usual[2] - usual[0]
    # The label above it and the tabs under it stay clear.
    assert larger[1] >= 154 and larger[3] <= 186


def test_the_size_sets_the_logo_in_the_live_preview_of_a_post(admin):
    p = create_auction(admin, "physical", workspace="project")
    add(admin, p, property_input())
    with_logo(admin, p)

    def width():
        r = admin.post(
            f"/api/projects/{p}/marketing-preview",
            json={"kind": "social", "config": {"headline": "مزاد"}},
        )
        assert r.status_code == 200, r.text
        return float(re.search(LOGO, r.json()["html"])[1])

    before = width()
    assert scale(admin, p, "social", 0.5).status_code == 200
    assert width() == pytest.approx(before / 2, abs=0.5)
