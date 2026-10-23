"""The auction's official forms: the authority's request form and Infath's
study, filled from the project's data and the author's entries, each
issued on its own."""

import os

import pymupdf
from test_auctions import add, create_auction, pdf, property_input

from app.generation.forms.compose import fitted, geometry
from app.generation.forms.questions import QUESTIONS

ENTRIES = {
    "request": {
        "date": "2026-10-01",
        "cr_number": "1010123456",
        "unified_number": "7001234567",
        "manager_name": "محمد عبدالله",
        "manager_id": "1012345678",
        "manager_mobile": "0555000111",
        "manager_email": "manager@example.com",
        "crier_name": "سالم أحمد",
        "crier_id": "1098765432",
        "crier_mobile": "0555000222",
        "crier_email": "crier@example.com",
        "units_count": "2",
        "receive": "transfer",
        "keeping": "حساب بنكي مخصص للمزاد",
        "receive_days": "3",
        "refund": "cheque",
        "refund_days": "3",
        "entry_type": "deposit",
        "award_minutes": "دقيقتان",
        "disposal": "sale",
        "rulings": ["none"],
        "ownership": "full",
        "rights": {"answer": "no"},
        "dispute": {"answer": "yes", "text": "رهن لصالح بنك"},
        "value_info": {"answer": "no"},
        "offplan": {"answer": "no"},
        "contribution": {"answer": "no"},
        "declarant": "محمد عبدالله",
        "contract_number": "C-2026-77",
    },
    "study": {"category": "د", "manager": "هيا عسيري"},
}


def entries_for(items):
    return {
        **ENTRIES,
        "properties": {
            item: {
                "owner": "ورثة عبدالرحمن",
                "age": "12 سنة",
                "status": "mortgaged",
                "min_price": "500000",
                "estimated_value": "900000",
                "agent_name": "فهد سعد" if n == 0 else "",
                "agency_number": "445566" if n == 0 else "",
                "answers": {key: {"answer": "yes"} for key in QUESTIONS},
                "estimated_price": "850000",
                "indicative_value": "870000",
                "defects": "تشققات في الجدران",
                "location_note": "يوجد اختلاف بسيط في الأطوال",
            }
            for n, item in enumerate(items)
        },
    }


def project_with(admin, count=1, cover="infath-2"):
    p = create_auction(admin, kind="electronic", cover=cover)
    items = [add(admin, p, property_input(n)) for n in range(1, count + 1)]
    return p, items


def test_forms_take_the_project_values_and_list_what_is_missing(admin):
    p, items = project_with(admin)
    view = admin.get(f"/api/projects/{p}/forms").json()
    shared = view["shared"]
    assert shared["request"]["auction_name"] == "مزاد آفاق العقاري"
    assert shared["request"]["properties_count"] == "1"
    prop = shared["properties"][items[0]]
    assert prop["deed"] == "0011" and prop["area"] == "1,200"
    assert prop["entry_amount"].startswith("25,000")
    missing = {(m["form"], m["field"]) for m in view["missing"]}
    assert ("request", "cr_number") in missing and ("study", "category") in missing
    saved = admin.put(f"/api/projects/{p}/forms", json=entries_for(items))
    assert saved.status_code == 200, saved.text
    assert saved.json()["missing"] == []
    # Another project of the author starts with its establishment and staff.
    other, _ = project_with(admin, cover="infath-3")
    carried = admin.get(f"/api/projects/{other}/forms").json()["forms"]["request"]
    assert carried["cr_number"] == "1010123456" and carried["date"] is None


def test_the_request_form_is_the_authoritys_own_pages_filled(admin, tmp_path):
    p, items = project_with(admin, 2)
    admin.put(f"/api/projects/{p}/forms", json=entries_for(items))
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["auction_request", "property_study"]},
    )
    assert r.status_code == 200, r.text
    request, study = r.json()
    assert request["preflight"]["passed"] and study["preflight"]["passed"]
    with pymupdf.open(stream=pdf(admin, request), filetype="pdf") as doc:
        # Six pages, the statement lying across as in the authority's file.
        assert len(doc) == 6
        assert doc[3].rect.width > doc[3].rect.height
        text = "".join(page.get_text() for page in doc)
        for value in ("1010123456", "مزاد آفاق العقاري", "manager@example.com"):
            assert value in text, value
        assert "0012" in doc[3].get_text()  # the second property's deed
        assert "فهد سعد" in doc[4].get_text()  # the agents' table
        # The authority's drawing is under the text, as vectors.
        assert len(doc[0].get_drawings()) > 50
        if os.environ.get("FORMS_OUT"):
            doc.save(tmp_path / "request.pdf")
    with pymupdf.open(stream=pdf(admin, study), filetype="pdf") as doc:
        text = "".join(page.get_text() for page in doc)
        assert "نموذج مطابقة المعلومات" in text and "هيا عسيري" in text
        assert len(doc) >= 2  # one study per property


def test_the_live_preview_shows_unsaved_values(admin):
    p, items = project_with(admin, 2)
    forms = entries_for(items)
    forms["request"]["cr_number"] = "9999999999"
    r = admin.post(
        f"/api/projects/{p}/forms-preview",
        json={"form": "request", "forms": forms, "page": 0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "9999999999" in body["html"] and len(body["pages"]) == 6
    r = admin.post(
        f"/api/projects/{p}/forms-preview",
        json={"form": "study", "forms": forms, "item": items[1]},
    )
    assert r.json()["page"] == 1 and "0012" in r.json()["html"]
    statement = admin.post(
        f"/api/projects/{p}/forms-preview",
        json={"form": "request", "page": 3},
    ).json()
    assert statement["width_pt"] > statement["height_pt"]


def test_values_shrink_then_wrap_inside_their_box():
    box = geometry()["pages"][1]["fields"]["keeping"]
    short = fitted("حساب بنكي", box)
    assert short["size"] == 9.5 and len(short["lines"]) == 1
    long = fitted("حساب بنكي مخصص لأموال المتنافسين لدى بنك محلي معتمد " * 3, box)
    assert long["size"] <= 8 and len(long["lines"]) >= 2 and "overflow" not in long
    assert fitted("كلام " * 400, box).get("overflow")


def test_each_form_is_issued_alone_without_the_booklet(admin):
    """A project's forms need its data, not its booklet: with the booklet's
    own requirements unmet (no closing pages, no photographs), each form is
    issued by itself and nothing else is generated."""
    r = admin.post(
        "/api/projects",
        json={
            "name": "نماذج فقط",
            "code": "FORMS-ONLY",
            "workspace_type": "project",
            "auction": {"auction_name": "مزاد النماذج", "auction_type": "physical"},
        },
    )
    assert r.status_code == 201, r.text
    p = r.json()["id"]
    item = add(admin, p, property_input(1))
    assert not admin.get(f"/api/projects/{p}/review").json()["valid"]
    admin.put(f"/api/projects/{p}/forms", json=entries_for([item]))
    for kind in ("auction_request", "property_study"):
        r = admin.post(f"/api/projects/{p}/generate", json={"types": [kind]})
        assert r.status_code == 200, r.text
        assert [o["output_type"] for o in r.json()] == [kind]
        assert pdf(admin, r.json()[0]).startswith(b"%PDF")
    outputs = admin.get(f"/api/projects/{p}").json()["outputs"]
    assert sorted(o["output_type"] for o in outputs) == [
        "auction_request",
        "property_study",
    ]
