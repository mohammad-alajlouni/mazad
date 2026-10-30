"""The banner notes (الملاحظات الأهم للبنرات): each note and what answers it."""

import base64
from io import BytesIO

import pymupdf
import pytest
from PIL import Image
from test_auctions import add, pdf, property_input
from test_banners import campaign
from test_booklet_reference import item_with

from app.generation.marketing.compose import (
    layout,
    marketing_content,
    label_centre,
    supervision_left,
)
from app.services.banners import SIZES, court_from, size_for

COURT = "بقرار محكمة التنفيذ وبحكم محكمة الأحوال الشخصية"


@pytest.mark.parametrize(
    "kind, area, size",
    [
        ("أرض خام", 800, "4x2"),
        ("أرض سكنية", 1001, "6x3"),
        ("ارض", 5001, "10x3"),
        ("أرض", 20001, "10x5"),
        ("أرض تجارية", 100001, "15x5"),
        ("فيلا", 450, "2x2"),
        ("فيلا سكنية", 2500, "4x2"),
        ("استراحة", 900, "4x2"),
        ("مزرعة", 50000, "4x2"),
        ("قصر", 3000, "6x3"),
        ("عمارة سكنية تجارية", 700, "6x3"),
        ("شقة", 120, "2x2"),
        ("محل", 50, None),
    ],
)
def test_each_property_has_the_size_infaths_table_gives_it(kind, area, size):
    assert size_for({"property_type": kind, "area": str(area)}) == size


def test_boards_are_issued_each_in_its_propertys_size(admin):
    """Notes: a board's size follows its property's area as soon as it is
    entered; a size chosen for a property stands instead."""
    p, first = campaign(admin)  # أرض سكنية 1200 m² -> 6 x 3
    body = property_input(2)
    body["property_data"].update(
        {
            "property_type": "فيلا",
            "area": "450",
            "usage": "سكني",
            "execution_request_number": "1",
        }
    )
    villa = add(admin, p, body)
    sizes = admin.get(f"/api/projects/{p}/banner-sizes").json()
    assert sizes == {first: "6x3", villa: "2x2"}
    review = admin.get(f"/api/projects/{p}/banner-review").json()
    assert review["valid"], review
    assert list(review["templates"]) == ["6x3", "2x2"]
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    issued = {o["banner"]["size"]: o for o in r.json()}
    assert set(issued) == {"6x3", "2x2"}
    for size, o in issued.items():
        with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as doc:
            assert len(doc) == 1  # one property in each size
            assert round(doc[0].rect.width) == round(
                SIZES[size]["width_mm"] * 72 / 25.4
            )
    # Changed by hand for one property.
    r = admin.put(
        f"/api/projects/{p}/banner-config", json={"item_sizes": {villa: "4x2"}}
    )
    assert r.status_code == 200, r.text
    review = admin.get(f"/api/projects/{p}/banner-review").json()
    assert review["item_sizes"] == {first: "6x3", villa: "4x2"}
    # The preview shows each property's board in its size.
    r = admin.post(
        f"/api/projects/{p}/marketing-preview",
        json={"kind": "banner", "config": {"item_sizes": {villa: "2x2"}}, "page": 1},
    )
    assert r.json()["width_pt"] == pytest.approx(200 * 72 / 25.4, rel=0.001)
    # A property of another campaign cannot be sized here.
    assert (
        admin.put(
            f"/api/projects/{p}/banner-config", json={"item_sizes": {"x": "4x2"}}
        ).status_code
        == 400
    )


def test_the_supervision_line_never_reaches_the_box_beside_it():
    """Notes: «محكمة التنفيذ» ran into the property type's box: the line keeps
    clear of it (or of the panel's edge), and on one line whatever its length."""
    for name in [n for n in layout() if n.startswith("board-")]:
        left = supervision_left(name)
        slot = next(s for s in layout()[name]["slots"] if s["key"] == "supervision")
        assert left >= slot["x"] - slot["maxw"]
    for kind in ("physical", "electronic", "hybrid"):
        for size in SIZES:
            project = {
                "auction": {
                    "auction_name": "مزاد طويق",
                    "auction_type": kind,
                    "auction_date": "2026-10-10",
                    "auction_start_date": "2026-10-10",
                    "start_time": "16:00:00",
                    "court_decision_text": "و" + COURT,
                },
                "selling_agent": {},
                "agent_logo": "",
            }
            content = {
                "project": project,
                "items": [{**item_with(property_type="فيلا"), "title": "x", "id": "i"}],
                "banner": {**SIZES[size], "size": size, "court_name": ""},
            }
            page = marketing_content(content)["pages"][0]
            line = next(t for t in page["texts"] if t["key"] == "supervision")
            assert line["fits"], (kind, size)
            # One line, always: two would be refused.
            assert len(line["lines"]) == 1, (kind, size)
            # Filled from the auction's court decision, its «و» once.
            text = " ".join(x["text"] for x in line["lines"])
            assert "وبقرار محكمة التنفيذ" in text and "ووبقرار" not in text
            k = page["size"][0] / page["view"][0]
            left = supervision_left(page["name"])
            assert line["extent"][0] >= left - 0.5, (kind, size)
            assert line["x"] <= page["size"][0]
            assert k > 0


def test_the_court_is_filled_from_the_auction():
    assert court_from({"court_decision_text": "وبقرار من محكمة التنفيذ"}) == (
        "بقرار من محكمة التنفيذ"
    )
    assert court_from({"court_decision_text": "بقرار محكمة جدة\nسطر آخر"}) == (
        "بقرار محكمة جدة"
    )
    assert court_from({}) == ""


def test_the_agents_logo_stands_centred_under_its_label():
    """Notes: the logo went left of «وكيل البيع القضائي» when the auction's name
    left it no room on the right: it stays centred under the label, whatever
    the name's length."""
    logo = BytesIO()
    Image.new("RGB", (900, 300), (20, 20, 20)).save(logo, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(logo.getvalue()).decode()
    for kind in ("physical", "electronic"):
        for size in SIZES:
            for name in ("مزاد طويق", "مزاد أعيان الرياض", "مزاد أعيان الرياض الكبرى"):
                project = {
                    "auction": {
                        "auction_name": name,
                        "auction_type": kind,
                        "auction_date": "2026-10-10",
                        "auction_start_date": "2026-10-10",
                        "start_time": "16:00:00",
                    },
                    "selling_agent": {},
                    "agent_logo": uri,
                }
                content = {
                    "project": project,
                    "items": [
                        {**item_with(property_type="فيلا"), "title": "x", "id": "i"}
                    ],
                    "banner": {**SIZES[size], "size": size, "court_name": ""},
                }
                page = marketing_content(content)["pages"][0]
                slot = next(
                    s
                    for s in layout()[page["name"]]["slots"]
                    if s["key"] == "agent_logo"
                )
                k = page["size"][0] / page["view"][0]
                x, _, width, _ = page["logo"]["box"]
                centre = label_centre(page["name"], tuple(slot["box"]))
                assert abs((x + width / 2) / k - centre) < 0.05, (kind, size, name)
