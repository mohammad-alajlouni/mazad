"""The booklet notes (ملاحظات المنصة والكتيب): each note and what answers it."""

import json
from io import BytesIO

import pymupdf
from PIL import Image
from test_auctions import add, create_auction, generate, pdf, property_input
from test_booklet_reference import exported, item_with, project_with, property_pages
from test_supervisor import preview
from test_workflow import image_data

from app.generation.booklet.composer import (
    BOUNDARY_PAGE,
    announcement_fit,
    boundary_limit,
    compose,
    schedule,
)


def test_the_summary_follows_a_navy_cover():
    """Cover 6 (a photograph over a navy band) is navy: so are its tables."""
    themes = {
        n: compose(project_with(selected_cover_template_id=f"infath-{n}"), [])["theme"]
        for n in range(1, 7)
    }
    assert themes == {1: "teal", 2: "navy", 3: "teal", 4: "navy", 5: "teal", 6: "navy"}


def test_infath_stands_on_the_auction_logos_line_on_photograph_covers():
    from app.generation.booklet.art import supervisor_logo

    for n in (1, 6):
        html = str(supervisor_logo({}, f"cover-{n}"))
        left = float(html.split("left:")[1].split("pt")[0])
        width = float(html.split("width:")[1].split("pt")[0])
        # cover.html: the auction logo's right edge is 566.3 on these covers.
        assert abs(left + width - 566.3) < 0.01


def test_the_agents_footer_logo_keeps_the_infath_logos_margin():
    project = project_with("physical")
    project["agent_logo"] = (
        "data:image/png;base64," + __import__("base64").b64encode(image_data()).decode()
    )
    booklet, _, document = exported(project, [item_with(property_type="فيلا")])
    n = [p["kind"] for p in booklet["pages"]].index("summary")
    boxes = [
        r
        for img in document[n].get_images(full=True)
        for r in document[n].get_image_rects(img[0])
        if r.y0 > 760
    ]
    assert boxes and min(r.x0 for r in boxes) >= 15.2


def test_announcement_lines_break_between_its_clauses():
    """Notes p.2: the text set smaller (no lower than 14) so that it breaks
    only where a clause starts, in the fewest lines."""
    text = (
        "تعلن شركة أدير العقارية عن البيع بالمزاد العلني وبإشراف من مركز "
        'الإسناد والتصفية "إنفاذ"\nوبقرار من محكمة التنفيذ وبحكم محكمة '
        "الأحوال الشخصية"
    )
    size, height, lines, rest = announcement_fit(text)
    assert lines == [
        "تعلن شركة أدير العقارية عن البيع بالمزاد العلني",
        'وبإشراف من مركز الإسناد والتصفية "إنفاذ"',
        "وبقرار من محكمة التنفيذ وبحكم محكمة الأحوال الشخصية",
    ]
    assert 14 <= size < 19 and rest == ""
    # A text that already breaks well keeps the guide's 19 pt.
    assert announcement_fit("تعلن شركة أعيان العقارية عن البيع بالمزاد العلني")[0] == 19


def test_an_electronic_auction_says_when_it_starts_and_when_it_ends():
    auction = project_with(
        "electronic",
        auction_start_date="2026-11-01",
        auction_end_date="2026-11-04",
        start_time="10:00",
        end_time="21:00",
        first_close_time="16:00",
        close_interval_minutes=30,
    )["auction"]
    items = [item_with() for _ in range(3)]
    plan = schedule(auction, items)
    assert plan == {
        "start": ["2026-11-01", "10:00"],
        "end": ["2026-11-04", "16:00", "21:00"],
    }
    assert schedule({"auction_type": "physical"}, items) is None
    project = project_with(
        "electronic",
        auction_start_date="2026-11-01",
        auction_end_date="2026-11-04",
        start_time="10:00",
        end_time="21:00",
        first_close_time="16:00",
    )
    booklet, _, document = exported(project, items)
    n = [p["kind"] for p in booklet["pages"]].index("auction")
    text = document[n].get_text().replace("⁦", "").replace("⁩", "")
    for words in ("يبدأ المزاد", "ينتهي المزاد", "الموافق", "نوفمبر", "إلى الساعة"):
        assert words in text, words


def test_boundaries_page_runs_to_its_box_and_input_is_limited(admin):
    """Notes p.4: the boundaries page text in 14 pt, up to the box's line; a
    description is limited to what its box holds."""
    assert BOUNDARY_PAGE[:2] == (14, 498)
    limit = boundary_limit()
    assert 200 <= limit <= 400
    p = create_auction(admin)
    add(admin, p, property_input())
    limits = admin.get(f"/api/projects/{p}").json()["workflow"]["rules"]["limits"]
    for side in ("north", "south", "east", "west"):
        assert limits[f"boundary.{side}_description"] == limit
    # A description of that length stays in one box on the boundaries page.
    long = "شارع عرض 15 م ثم قطعة رقم 54 بطول 40 م " * 20
    item = item_with(boundaries={"north_description": long[:limit]})
    pages = [
        p for p in compose(project_with(), [item])["pages"] if p["kind"] == "boundaries"
    ]
    assert len(pages) == 1 and len(pages[0]["rows"]) == 4


def test_boundaries_moving_away_leave_everything_else_in_place():
    """Notes p.5: on the property's page only the boundaries and lengths go;
    the information box and the links keep their places."""
    links = {
        "location_link": "https://example.com/a",
        "survey_link": "https://example.com/b",
    }
    for layout in ("landscape", "portrait"):
        beside = item_with(booklet_layout=layout, **links)
        moved = item_with(booklet_layout=layout, include_boundaries_page=True, **links)
        a = property_pages(compose(project_with(), [beside]))[0]
        b = property_pages(compose(project_with(), [moved]))[0]
        assert a["boundaries"] and b["boundaries"] is None
        assert a["info_region"] == b["info_region"]
        _, _, one = exported(project_with(), [beside])
        _, _, two = exported(project_with(), [moved])

        def codes(document):
            page = next(pg for pg in document if "معلومات" in pg.get_text())
            return sorted(
                (round(r.x0), round(r.y0))
                for img in page.get_images(full=True)
                for r in page.get_image_rects(img[0])
                if r.width < 40
            )

        assert codes(one) == codes(two)


def test_the_contact_number_is_the_agents_unless_another_is_given(admin):
    """Notes p.9: no asterisk (the number is in the settings); a number given
    stands under it as another one."""
    p = create_auction(admin)
    add(admin, p, property_input())
    detail = admin.get(f"/api/projects/{p}").json()
    for kind, rule in detail["workflow"]["rules"]["auction"].items():
        assert "auction_contact_number" not in rule["required"], kind
    html = preview(admin, p, "contact")
    assert "0555000000" in html  # the agent's (create_auction)
    project = detail["project"]
    project["auction"]["auction_contact_number"] = "920004024"
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    html = preview(admin, p, "contact")
    assert "0555000000" in html and "920004024" in html
    # The boards print the agent's number when the auction has none.
    from app.generation.marketing.compose import contact_number

    assert contact_number({"auction": {}, "selling_agent": {"phone": "0555"}}) == "0555"
    assert contact_number({"auction": {"auction_contact_number": "9200"}}) == "9200"


def test_a_website_needs_no_https():
    from app.auction_schemas import SellingAgentInput
    from app.generation.engine import site

    agent = SellingAgentInput(website="www.aayan.com")
    assert agent.website == "https://www.aayan.com"
    assert site(agent.website) == "www.aayan.com"
    for bad in ("javascript:alert(1)", "www", "https://localhost", "a b.com"):
        try:
            SellingAgentInput(website=bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_names_are_suggested_by_the_ai(admin, monkeypatch):
    from app.api.auctions import clean_names
    from app.services import ai

    assert clean_names("1. درة الملقا\n- «مزاد واحة الرياض»\n" + "كلمة " * 9) == [
        "درة الملقا",
        "واحة الرياض",
    ]
    seen = {}

    async def fake(self, purpose, data, output_language="en"):
        seen.update(data)
        return {"status": "DRAFT", "text": "درة النرجس\nنخبة الرياض", "message": ""}

    monkeypatch.setattr(ai.AIService, "generate", fake)
    p = create_auction(admin)
    add(admin, p, property_input())
    r = admin.post(f"/api/projects/{p}/name-suggestions")
    assert r.status_code == 200 and r.json()["names"] == ["درة النرجس", "نخبة الرياض"]
    assert seen["properties"][0]["district"] == "النرجس"


def test_outputs_keep_pictures_by_reference(admin):
    """Notes p.1 (slowness): an output no longer stores its photographs as
    text; the booklet still prints them, and an output stored before is made
    compact the first time it is listed."""
    from app.db import SessionLocal
    from app.generation.engine import STORED, unpack
    from app.models import GeneratedOutput

    p = create_auction(admin)
    item = add(admin, p, property_input())
    r = admin.post(
        f"/api/projects/{p}/images",
        files={"file": ("photo.png", image_data())},
        data={"category": "main", "item_id": item},
    )
    assert r.status_code == 200
    o = generate(admin, p)
    with SessionLocal() as db:
        row = db.get(GeneratedOutput, o["id"])
        stored = json.dumps(row.content)
        assert STORED in stored and "data:image/jpeg;base64" not in stored
        full = unpack(row.content)
        assert STORED not in json.dumps(full)
        # As an output was stored before: its pictures written in.
        row.content = {k: v for k, v in full.items() if k != "_packed"}
        db.commit()
        big = len(json.dumps(row.content))
    assert len(stored) < big - 50_000  # (a small photograph, written in twice)
    assert admin.get(f"/api/projects/{p}").status_code == 200
    with SessionLocal() as db:
        assert STORED in json.dumps(db.get(GeneratedOutput, o["id"]).content)
    # Approving renders it again: the photograph is printed.
    approved = admin.post(f"/api/outputs/{o['id']}/approve")
    assert approved.status_code == 200, approved.text
    with pymupdf.open(stream=pdf(admin, approved.json()), filetype="pdf") as doc:
        sizes = [
            Image.open(BytesIO(doc.extract_image(img[0])["image"])).size
            for page in doc
            for img in page.get_images(full=True)
        ]
    assert (900, 600) in sizes
