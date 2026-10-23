"""The Real Estate General Authority's reports after the auction: the auction
closing form and the outputs report, on the authority's own templates."""

import hashlib
import unicodedata
import json
from pathlib import Path

import pymupdf
from test_auctions import add, create_auction, pdf, property_input
from test_workflow import image_data

from app.generation.reports.compose import layout

ART = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/reports"


def project_with(admin, count=2):
    p = create_auction(admin, kind="physical")
    items = [add(admin, p, property_input(n)) for n in range(1, count + 1)]
    return p, items


def entries(items):
    return {
        "closing": {"date": "2026-07-29", "approval_number": "7833"},
        "report": {
            "court": "محكمة التنفيذ بحائل",
            "boards": ["الخطة", "الملك عبدالله", "الحائط"],
            "boards_installed": "2026-07-08",
            "boards_removed": "2026-08-01",
            "channels": {"x": {"views": "20,000"}, "sms": {"views": "600"}},
            "x_posts": 7,
            "x_paid": 2,
            "x_unpaid": 3,
            "participants": 8,
            "interested": 38,
            "visitors": 10,
            "unsold_reason": "ارتفاع السعر الابتدائي مقارنة بمتوسط سعر المتر.",
            "address": "12213 Al Olaya St.",
            "phone": "+966-555-405658",
            "email": "re@aayan.sa",
        },
        "properties": {
            items[0]: {
                "status": "sold",
                "winner": "فهد بن سالم الشمري",
                "value": "237000",
                "opening_price": "200000",
            },
            items[1]: {
                "status": "unsold",
                "reason": "لم يتقدم أحد",
                "opening_price": "660000",
            },
        },
    }


def test_the_templates_are_the_authoritys_own_files():
    manifest = json.loads((ART / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((ART / name).read_bytes()).hexdigest() == digest
    with pymupdf.open(ART / "report.pdf") as report:
        assert len(report) == len(layout()["report"]) == 14
        assert all(
            page.rect.width == 1440 and page.rect.height == 810 for page in report
        )
        # The template's fixed wording stays in its pages; the sample auction's
        # own (its name, dates, figures) is gone.
        text = " ".join(page.get_text() for page in report)
        assert "حائل" not in text and "2026" not in text and "aayan" not in text
    with pymupdf.open(ART / "closing.pdf") as closing:
        assert round(closing[0].rect.width) == 842


def test_reports_are_issued_alone_from_the_auction_project(admin):
    p, items = project_with(admin)
    view = admin.get(f"/api/projects/{p}/reports").json()
    assert [x["id"] for x in view["shared"]["properties"]] == items
    saved = admin.put(f"/api/projects/{p}/reports", json=entries(items))
    assert saved.status_code == 200, saved.text
    assert saved.json()["reports"]["properties"][items[0]]["winner"] == (
        "فهد بن سالم الشمري"
    )
    # A signature, uploaded on its own (one: the next replaces it).
    for _ in range(2):
        r = admin.post(
            f"/api/projects/{p}/report-images",
            files={"file": ("sign.png", image_data())},
            data={"category": "signature"},
        )
        assert r.status_code == 200, r.text
    assert [i["category"] for i in r.json()["images"]] == ["signature"]
    image = r.json()["images"][0]["id"]
    assert admin.get(f"/api/projects/{p}/report-images/{image}").status_code == 200

    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["auction_closing"]})
    assert r.status_code == 200, r.text
    output = r.json()[0]
    assert output["output_type"] == "auction_closing"
    with pymupdf.open(stream=pdf(admin, output), filetype="pdf") as doc:
        page = doc[0]
        assert round(page.rect.width) == 842 and round(page.rect.height) == 595
        text = unicodedata.normalize("NFKC", page.get_text())
        # The authority's page, its rows filled from the project and the results.
        assert "يمكن تكرار البيان عند زيادة العقارات" in text
        assert "29/07/2026" in text and "7833" in text
        assert "0011" in text and "مباع" in text and "غير مباع" in text
        assert "237,000" in text and "لم يتقدم أحد" in text
        assert page.get_images()  # the signature

    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["outputs_report"]})
    assert r.status_code == 200, r.text
    with pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf") as doc:
        kinds = len(doc)
        text = unicodedata.normalize("NFKC", " ".join(p.get_text() for p in doc))
        assert all(page.rect.width == 1440 for page in doc)
        # Cover, contents, intro, marketing, boards, channels, X,
        # participants, assets and closing (no screenshots, no TikTok).
        assert kinds == 10
        assert "مزاد آفاق العقاري" in text and "محكمة التنفيذ بحائل" in text
        # (The «الله» ligature extracts as «هللا», as in the template itself.)
        assert "الحائط" in text and "2026/07/08" in text
        assert "تم البيع" in text and "غير مباع" in text and "237,000" in text
        assert "بمتوسط سعر المتر" in text and "re@aayan" in text
    outputs = admin.get(f"/api/projects/{p}").json()["outputs"]
    assert sorted(o["output_type"] for o in outputs) == [
        "auction_closing",
        "outputs_report",
    ]


def test_the_closing_statement_repeats_beyond_seventeen_properties(admin):
    p, items = project_with(admin, 18)
    r = admin.post(
        f"/api/projects/{p}/reports-preview",
        json={"report": "auction_closing", "page": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["kind"] for x in body["pages"]] == ["closing_form", "closing_form"]
    # The second page holds the eighteenth property, numbered on.
    assert body["page"] == 1 and 'data-slot="number.17"' in body["html"]
    assert "/api/booklet-assets/reports/closing.png" in body["html"]


def test_live_preview_shows_unsaved_values(admin):
    p, items = project_with(admin, 1)
    r = admin.post(
        f"/api/projects/{p}/reports-preview",
        json={
            "report": "outputs_report",
            "data": {"report": {"court": "محكمة التنفيذ بجدة", "participants": 12}},
            "page": 0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["width_pt"] == 1440 and body["pages"][0]["kind"] == "cover"
    assert "محكمة التنفيذ بجدة" in body["html"]
    assert "/api/booklet-assets/reports/report-cover.png" in body["html"]
    # Nothing was saved.
    assert (
        admin.get(f"/api/projects/{p}/reports").json()["reports"]["report"]["court"]
        == ""
    )
    bad = admin.post(
        f"/api/projects/{p}/reports-preview",
        json={"report": "outputs_report", "data": {"report": {"x_posts": -1}}},
    )
    assert bad.status_code == 422


def test_reports_belong_to_an_auction_project(admin):
    r = admin.post(
        "/api/projects",
        json={"name": "حملة", "code": "B-1", "workspace_type": "banners"},
    )
    p = r.json()["id"]
    assert admin.get(f"/api/projects/{p}/reports").status_code == 400
    other, items = project_with(admin, 1)
    unknown = admin.put(
        f"/api/projects/{other}/reports",
        json={"properties": {"not-a-property": {"status": "sold"}}},
    )
    assert unknown.status_code == 400
    # A client cannot point a report at a stored file of its choosing.
    forged = admin.put(
        f"/api/projects/{other}/reports",
        json={"images": [{"id": "x", "key": "../../etc/passwd", "category": "stamp"}]},
    )
    assert forged.status_code == 422
