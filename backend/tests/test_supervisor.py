"""The cover's own data, and the supervising body: Infath (as an administrator
keeps it) or another body, on the covers, page footers and its own page."""

import base64
from io import BytesIO

import pymupdf
from PIL import Image
from test_accounts import account, login
from test_auctions import add, create_auction, generate, pdf, property_input
from test_workflow import image_data

from app.generation.booklet.supervisor import INFATH


def preview(c, p, kind, auction=None):
    """The preview HTML of the first page of a kind (unsaved auction values)."""
    body = {"stage": "auction", **({"auction": auction} if auction else {})}
    pages = c.post(f"/api/projects/{p}/booklet-preview", json=body).json()["pages"]
    page = next(n for n, x in enumerate(pages) if x["kind"] == kind)
    r = c.post(f"/api/projects/{p}/booklet-preview", json={**body, "page": page})
    assert r.status_code == 200, r.text
    return r.json()["html"]


def picture(colour=(200, 40, 30), size=(400, 200)):
    data = BytesIO()
    Image.new("RGB", size, colour).save(data, "PNG")
    return data.getvalue()


def test_a_cover_shows_the_auction_name_and_date_only_once_entered(admin):
    p = create_auction(admin)
    project = admin.get(f"/api/projects/{p}").json()["project"]
    for cover in range(1, 7):
        auction = {
            **project["auction"],
            "selected_cover_template_id": f"infath-{cover}",
            "auction_name": "",
            "auction_date": None,
            "auction_start_date": None,
            "auction_end_date": None,
        }
        assert (
            admin.put(f"/api/projects/{p}", json={**project, "auction": auction})
        ).status_code == 200
        empty = preview(admin, p, "cover")
        assert "auction-icon-silver" not in empty and "تاريخ المزاد" not in empty
        assert "نوفمبر" not in empty
        assert ">مزاد<" not in empty
        auction.update(
            auction_name="مزاد درة البحر",
            auction_start_date="2026-11-12",
            auction_end_date="2026-11-13",
        )
        assert (
            admin.put(f"/api/projects/{p}", json={**project, "auction": auction})
        ).status_code == 200
        filled = preview(admin, p, "cover")
        assert "auction-icon-silver" in filled and "درة البحر" in filled
        assert "نوفمبر" in filled  # the date (covers 4 and 5 print it unlabelled)


def test_the_assignment_number_is_kept_with_the_auction(admin):
    p = create_auction(admin)
    project = admin.get(f"/api/projects/{p}").json()["project"]
    project["auction"]["assignment_number"] = "AS-2026-114"
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    saved = admin.get(f"/api/projects/{p}").json()["project"]["auction"]
    assert saved["assignment_number"] == "AS-2026-114"


def test_infath_by_default_with_its_page_set_from_its_details(admin):
    p = create_auction(admin)
    html = preview(admin, p, "introduction")
    assert INFATH["title"] in html and "920000100" in html
    assert "infath_sa" in html and "infathauctions" in html
    # The guide's logo, drawn on the page and in every page footer.
    assert html.count("supervisor-logo") == 1
    assert preview(admin, p, "auction").count("supervisor-logo") == 1
    assert preview(admin, p, "cover").count("supervisor-logo") == 1


def test_an_administrator_changes_infath_without_touching_the_designs(admin):
    p = create_auction(admin)
    r = admin.put(
        "/api/settings/infath",
        json={"text": "نص تعريفي محدث لإنفاذ.", "phone": "920000999"},
    )
    assert r.status_code == 200, r.text
    view = admin.get("/api/settings/infath").json()
    assert view["values"]["phone"] == "920000999"
    assert view["defaults"]["phone"] == "920000100"
    html = preview(admin, p, "introduction")
    assert "نص تعريفي محدث لإنفاذ." in html and "920000999" in html
    # Fields left empty keep the guide's.
    assert INFATH["title"] in html
    r = admin.post(
        "/api/settings/infath/logo",
        files={"file": ("logo.png", picture((10, 60, 120)), "image/png")},
    )
    assert r.status_code == 200 and r.json()["has_logo"]
    assert admin.get("/api/settings/infath/logo").status_code == 200
    html = preview(admin, p, "auction")
    assert "data:image/png" in html.split("supervisor-logo")[1][:400]
    # Back to the guide's logo.
    assert admin.delete("/api/settings/infath/logo").json()["has_logo"] is False
    html = preview(admin, p, "auction")
    assert "data:image/svg+xml" in html.split("supervisor-logo")[1][:400]
    # A text too long for its one page is refused.
    long = "نص طويل جداً " * 400
    assert admin.put("/api/settings/infath", json={"text": long}).status_code == 422


def test_only_an_administrator_changes_infath(admin):
    account(admin, "author@example.com")
    with login("author@example.com") as author:
        assert author.get("/api/settings/infath").status_code == 200
        assert author.put("/api/settings/infath", json={"text": "x"}).status_code == 403
        r = author.post(
            "/api/settings/infath/logo",
            files={"file": ("logo.png", picture(), "image/png")},
        )
        assert r.status_code == 403


def test_another_body_supervises_with_its_own_logo_and_page(admin):
    p = create_auction(admin)
    add(admin, p, property_input())
    project = admin.get(f"/api/projects/{p}").json()["project"]
    project["auction"].update(supervisor="other")
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    # Until its logo is uploaded no logo stands in Infath's place.
    assert "supervisor-logo" not in preview(admin, p, "auction")
    # It needs its name, text and logo before the booklet is made.
    stages = admin.get(f"/api/projects/{p}").json()["workflow"]["stages"]
    missing = {m["field"] for m in stages["auction"]["missing"]}
    assert {"supervisor_title", "supervisor_text", "supervisor_logo"} <= missing
    project["auction"].update(
        supervisor_title="الهيئة العامة للعقار",
        supervisor_text="جهة حكومية تشرف على هذا المزاد.",
        supervisor_phone="199011",
        supervisor_website="rega.gov.sa",
        supervisor_social="rega_sa",
    )
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    r = admin.post(
        f"/api/projects/{p}/images",
        data={"category": "supervisor_logo"},
        files={"file": ("logo.png", image_data(), "image/png")},
    )
    assert r.status_code == 200, r.text
    stages = admin.get(f"/api/projects/{p}").json()["workflow"]["stages"]
    missing = {m["field"] for m in stages["auction"]["missing"]}
    assert not {"supervisor_title", "supervisor_text", "supervisor_logo"} & missing
    html = preview(admin, p, "introduction")
    assert "الهيئة العامة للعقار" in html and "199011" in html
    assert INFATH["title"] not in html and "920000100" not in html
    logo = html.split("supervisor-logo")[1][:300]
    assert "data:image/png" in logo
    # Its logo takes Infath's place on the cover and in the footers, too.
    assert (
        "data:image/png" in preview(admin, p, "cover").split("supervisor-logo")[1][:300]
    )
    o = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as document:
        text = document[1].get_text()
        assert "199011" in text and "920000100" not in text


def test_infath_page_is_exported_as_text_and_vectors(admin):
    p = create_auction(admin)
    add(admin, p, property_input())
    o = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as document:
        page = document[1]
        assert "920000100" in page.get_text()
        # The logo is the guide's paths, not a picture: the page holds no more
        # pictures than the agent's (its contact tiles' own).
        assert len(page.get_images()) == len(document[2].get_images())
        assert len(page.get_drawings()) >= 13


def test_old_outputs_without_supervisor_details_show_infath():
    from app.generation.booklet.composer import compose

    project = {
        "id": "x",
        "auction": {
            "selected_cover_template_id": "infath-2",
            "auction_type": "physical",
        },
        "selling_agent": {},
    }
    page = compose(project, [])["pages"][1]
    assert page["kind"] == "introduction"
    assert (
        "".join(line["text"] for line in page["lines"])
        .replace("ـ", "")
        .startswith("مركز الإسناد")
    )
    assert base64  # (imported for the helpers above)


def test_the_terms_are_the_guides_and_may_be_changed_for_an_auction(admin):
    from app.generation.booklet.terms import TERMS

    p = create_auction(admin)
    add(admin, p, property_input())
    rules = admin.get(f"/api/projects/{p}").json()["workflow"]["rules"]
    assert rules["terms_default"] == TERMS
    html = preview(admin, p, "terms")
    assert "terms-title.svg" in html and "يسقط خيار المجلس" in html
    # Changed for this auction: its own terms, as text in the booklet.
    project = admin.get(f"/api/projects/{p}").json()["project"]
    own = TERMS.replace("2.5 %", "2 %") + "\nبند إضافي خاص بهذا المزاد."
    project["auction"]["terms_text"] = own
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    assert "بند إضافي خاص" in preview(admin, p, "terms")
    o = generate(admin, p)
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as document:
        text = "".join(page.get_text() for page in document)
        assert "بند إضافي خاص" in text.replace("ـ", "") or "خاص بهذا" in text
    # Left as the guide's, they follow the guide.
    project["auction"]["terms_text"] = TERMS + "\n"
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    saved = admin.get(f"/api/projects/{p}").json()["project"]["auction"]
    assert saved["terms_text"] == ""
    # Terms too long for their page even at the smallest size are reported.
    project["auction"]["terms_text"] = "\n".join([TERMS] * 3)
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    stages = admin.get(f"/api/projects/{p}").json()["workflow"]["stages"]
    assert any(m["field"] == "terms_text" for m in stages["closing"]["missing"])


def test_longer_terms_are_set_smaller_on_their_one_page():
    from app.generation.booklet.terms import LAST, SIZE, TERMS, terms_page

    page = terms_page({"terms_text": TERMS + "\n" + TERMS.split("\n")[3]})
    assert page["size"] < SIZE
    assert page["terms"][-1]["lines"][-1]["base"] <= LAST
    assert terms_page({})["size"] == SIZE
