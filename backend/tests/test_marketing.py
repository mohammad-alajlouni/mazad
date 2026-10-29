"""The guide's boards and social posts: its own designs, its values' places,
and the live preview."""

import hashlib
import json
from pathlib import Path

import pymupdf
import pytest
from test_auctions import pdf
from test_banners import campaign
from test_social import social

from app.generation.marketing.compose import layout
from app.services.banners import SIZES

ART = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/marketing"


def test_every_design_is_the_extracted_guide_artwork():
    manifest = json.loads((ART / "manifest.json").read_text())
    for name, design in layout().items():
        for suffix in ("pdf", "png"):
            data = (ART / f"{name}.{suffix}").read_bytes()
            assert manifest["files"][f"{name}.{suffix}"] == (
                hashlib.sha256(data).hexdigest()
            )
        with pymupdf.open(ART / f"{name}.pdf") as doc:
            w, h = design["size"]
            assert doc[0].rect.width == pytest.approx(w, abs=0.01)
            assert doc[0].rect.height == pytest.approx(h, abs=0.01)
        # Every slot the composer fills is measured from the guide.
        for slot in design["slots"]:
            if slot["kind"] == "text":
                assert slot["size"] > 0 and slot["maxw"] > 0 and slot["bases"]


def spans(page):
    found = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = "".join(c["c"] for c in span["chars"]).strip()
                if text:
                    found.append((text, span))
    return found


@pytest.mark.parametrize("size", ["10x3", "4x2", "2x2"])
def test_board_values_stand_on_the_guides_baselines(admin, size):
    p, _ = campaign(admin)
    admin.put(
        f"/api/projects/{p}/banner-config", json={"auto_size": False, "size": size}
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    name = f"board-{SIZES[size]['layout']}-physical"
    design = layout()[name]
    slot = next(s for s in design["slots"] if s["key"] == "execution")
    with pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf") as doc:
        page = doc[0]
        k = page.rect.width / design["size"][0]
        # A ratio within 1 % of the guide's is taken up by the design itself.
        ky = page.rect.height / design["size"][1]
        text, span = next(s for s in spans(page) if s[0] == "123456789")
        # Centred under its tab, on the guide's baseline, at the guide's size.
        x0, _, x1, _ = span["bbox"]
        assert (x0 + x1) / 2 == pytest.approx(slot["x"] * k, abs=0.6 * k)
        assert span["origin"][1] == pytest.approx(slot["bases"][0] * ky, abs=0.4 * k)
        assert span["size"] == pytest.approx(slot["size"] * k, rel=0.01)
        # The guide's design lies beneath: its fixed wording is in the page.
        assert "رﻗﻢ ﻃﻠﺐ اﻟﺘﻨﻔﻴﺬ" in page.get_text()


def test_supervision_line_names_the_court(admin):
    p, _ = campaign(admin)
    admin.put(
        f"/api/projects/{p}/banner-config",
        json={"auto_size": False, "size": "4x2", "court_name": "محكمة التنفيذ بالرياض"},
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    with pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf") as doc:
        text = doc[0].get_text()
        assert "محكمة التنفيذ بالرياض" in text and "......" not in text


def test_board_live_preview_follows_the_unsaved_choices(admin):
    p, i = campaign(admin)
    r = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={
            "kind": "banner",
            "config": {
                "auto_size": False,
                "size": "2x2",
                "court_name": "محكمة التنفيذ بجدة",
            },
            "auction": {"auction_name": "مزاد الواحة", "auction_type": "physical"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pages"] == [{"kind": "board-square-physical", "item": "عقار تجريبي 1"}]
    assert body["width_pt"] == pytest.approx(200 * 72 / 25.4, rel=0.001)
    # The guide's picture beneath, the unsaved values over it.
    assert "/api/booklet-assets/marketing/board-square-physical.png" in body["html"]
    assert "الواحة" in body["html"] and "محكمة التنفيذ بجدة" in body["html"]
    assert body["overflow"] == []
    # Nothing was saved.
    assert (
        admin.get(f"/api/projects/{p}").json()["project"]["banner_config"]["size"]
        == "4x2"
    )
    # An electronic auction gets the guide's electronic board.
    r = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={"kind": "banner", "auction": {"auction_type": "electronic"}},
    )
    assert r.json()["pages"][0]["kind"] == "board-landscape-electronic"
    # A property being entered shows on its own board.
    r = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={
            "kind": "banner",
            "item": {"id": i, "property_data": {"district": "حي الياسمين"}},
        },
    )
    assert "حي الياسمين" in r.json()["html"]


def test_post_live_preview_and_its_overflow(admin):
    p, _ = social(admin, format="instagram")
    r = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={
            "kind": "social",
            "config": {"format": "story", "theme": "navy", "headline": "فرص نادرة"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pages"][0]["kind"] == "story-announcement-navy"
    assert body["width_pt"] == 810 and body["height_pt"] == 1440
    assert "فرص نادرة" in body["html"]
    long = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={"kind": "social", "config": {"headline": "مزاد " * 9}},
    ).json()
    assert {"page": 0, "item": "", "field": "headline"} in long["overflow"]
    # Each workspace previews its own publication.
    assert (
        admin.post(
            f"/api/projects/{p}/marketing-preview", json={"kind": "banner"}
        ).status_code
        == 400
    )
    assert (
        admin.post(
            f"/api/projects/{p}/marketing-preview",
            json={
                "kind": "social",
                "config": {"format": "story", "post_kind": "property"},
            },
        ).status_code
        == 422
    )
