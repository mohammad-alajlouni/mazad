from pathlib import Path
from io import BytesIO

import pymupdf
import pytest
import zxingcpp
from PIL import Image
from test_auctions import add, property_input, pdf
from test_workflow import image_data

from app.services.banners import SIZES


def campaign(c, kind="physical", workspace="banners"):
    r = c.post(
        "/api/projects",
        json={
            "name": "حملة بنرات تجريبية",
            "code": "BOARD-" + kind,
            "workspace_type": workspace,
            "auction": {
                "auction_name": "مزاد آفاق",
                "auction_type": kind,
                "document_language": "ar",
                "auction_date": "2026-10-10",
                "auction_start_date": "2026-10-10",
                "auction_end_date": "2026-10-12",
                "start_time": "16:00",
                "end_time": "18:00",
                "physical_location": "الرياض — قاعة المزاد",
                "electronic_platform_name": "منصة المزادات",
                "license_number": "420000053",
                "auction_contact_number": "0555000000",
                "legal_announcement_text": "بإشراف مركز الإسناد والتصفية إنفاذ — إعلان تجريبي للمعاينة فقط.",
                "booklet_url": "https://example.com/booklet/demo",
            },
        },
    )
    assert r.status_code == 201, r.text
    p = r.json()["id"]
    for category in ["auction_logo", "agent_logo"]:
        r = c.post(
            f"/api/projects/{p}/images",
            files={"file": ("logo.png", image_data())},
            data={"category": category},
        )
        assert r.status_code == 200, r.text
    assert (
        c.put(
            f"/api/projects/{p}/selling-agent",
            json={"name": "وكيل تجريبي", "logo_image_id": r.json()["id"]},
        ).status_code
        == 200
    )
    body = property_input()
    body["property_data"].update(
        {"usage": "سكني", "execution_request_number": "123456789"}
    )
    i = add(c, p, body)
    return p, i


@pytest.mark.parametrize("size", list(SIZES))
def test_banner_sizes_preview_approval(admin, size):
    p, i = campaign(
        admin,
        "hybrid" if size == "2x2" else "electronic" if size == "15x5" else "physical",
    )
    assert (
        admin.put(f"/api/projects/{p}/banner-config", json={"size": size}).status_code
        == 200
    )
    review = admin.get(f"/api/projects/{p}/banner-review").json()
    assert review["valid"], review
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    o = r.json()[0]
    assert o["banner"]["size"] == size and o["banner"]["scale"] == "1:10"
    data = pdf(admin, o)
    out = Path(__file__).resolve().parents[2] / "output/pdf"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"banner-{size}.pdf").write_bytes(data)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert len(doc) == 1
        page = doc[0]
        assert page.rect.width == pytest.approx(
            SIZES[size]["width_mm"] * 72 / 25.4, abs=0.1
        )
        assert page.rect.height == pytest.approx(
            SIZES[size]["height_mm"] * 72 / 25.4, abs=0.1
        )
        assert "0555000000" in page.get_text()
        assert "123456789" in page.get_text()
        for block in page.get_text("blocks"):
            assert block[0] >= 0 and block[2] <= page.rect.width
            assert block[1] >= 0 and block[3] <= page.rect.height
    png = next(f for f in o["files"] if f["media_type"] == "image/png")
    raw = admin.get("/api/files/" + png["id"]).content
    (out / f"banner-{size}.png").write_bytes(raw)
    im = Image.open(BytesIO(raw))
    assert im.width == 2400
    assert "https://example.com/booklet/demo" in [
        r.text for r in zxingcpp.read_barcodes(im)
    ]
    assert admin.get("/api/files/" + png["id"] + "?download=true").status_code == 409
    assert (
        admin.put(
            "/api/outputs/" + o["id"], json={"review_text": "ignored"}
        ).status_code
        == 409
    )
    approved = admin.post("/api/outputs/" + o["id"] + "/approve")
    assert approved.status_code == 200
    o = approved.json()
    data = pdf(admin, o)
    png = next(f for f in o["files"] if f["media_type"] == "image/png")
    assert admin.get("/api/files/" + png["id"] + "?download=true").status_code == 200
    new = admin.post("/api/outputs/" + o["id"] + "/regenerate")
    assert new.status_code == 200 and new.json()["id"] != o["id"]
    assert pdf(admin, o) == data


def test_banner_validation_selection_and_workspace_isolation(admin):
    p, first = campaign(admin)
    body = property_input(2)
    body["property_data"].update({"usage": "سكني", "execution_request_number": "98765"})
    second = add(admin, p, body)
    assert admin.get("/api/dashboard").json()["total_projects"] == 0
    assert len(admin.get("/api/banner-templates").json()) == 6
    assert (
        admin.put(
            f"/api/projects/{p}/banner-config", json={"size": "unknown"}
        ).status_code
        == 422
    )
    for ids in [["foreign"], [first, first]]:
        assert (
            admin.put(
                f"/api/projects/{p}/banner-config", json={"property_ids": ids}
            ).status_code
            == 400
        )
    assert (
        admin.put(
            f"/api/projects/{p}/banner-config", json={"property_ids": [second]}
        ).status_code
        == 200
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    assert len(r.json()[0]["files"]) == 2
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["social_content"]}
        ).status_code
        == 400
    )
    body["property_data"]["execution_request_number"] = ""
    admin.put(f"/api/projects/{p}/items/{second}", json=body)
    r = admin.get(f"/api/projects/{p}/banner-review").json()
    assert not r["valid"] and any(
        x["field"] == "execution_request_number" for x in r["missing"]
    )
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["banners"]}
        ).status_code
        == 422
    )
    body["property_data"]["execution_request_number"] = "1" * 33
    admin.put(f"/api/projects/{p}/items/{second}", json=body)
    assert any(
        x.get("limit") == 32
        for x in admin.get(f"/api/projects/{p}/banner-review").json()["missing"]
    )
    admin.delete(f"/api/projects/{p}/items/{second}")
    assert not admin.get(f"/api/projects/{p}/banner-review").json()["valid"]
    assert (
        admin.put(
            f"/api/projects/{p}/banner-config", json={"property_ids": []}
        ).status_code
        == 200
    )
    assert admin.get(f"/api/projects/{p}/banner-review").json()["valid"]
    detail = admin.get(f"/api/projects/{p}").json()
    assert (
        admin.put(
            f"/api/projects/{p}",
            json={**detail["project"], "workspace_type": "booklet"},
        ).status_code
        == 400
    )
    assert admin.get("/api/projects/not-owned/banner-review").status_code == 404


@pytest.mark.parametrize("size", ["10x3", "4x2", "2x2"])
def test_english_board(admin, size):
    p, _ = campaign(admin, "electronic")
    admin.put(f"/api/projects/{p}/banner-config", json={"size": size})
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["banners"], "output_language": "en"},
    )
    assert r.status_code == 200, r.text
    with pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf") as doc:
        assert len(doc) == 1 and "For sale" in doc[0].get_text()
        assert "Execution request" in doc[0].get_text()
        for b in doc[0].get_text("blocks"):
            assert (
                b[0] >= 0
                and b[1] >= 0
                and b[2] <= doc[0].rect.width
                and b[3] <= doc[0].rect.height
            )


def test_banner_source_change_preserves_approved_version(admin):
    p, item = campaign(admin)
    o = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]}).json()[0]
    approved = admin.post(f"/api/outputs/{o['id']}/approve").json()
    old_bytes = pdf(admin, approved)
    body = property_input()
    body["property_data"].update(
        {"usage": "سكني", "execution_request_number": "99999", "area": "0"}
    )
    admin.put(f"/api/projects/{p}/items/{item}", json=body)
    assert any(
        e["field"] == "area"
        for e in admin.get(f"/api/projects/{p}/banner-review").json()["missing"]
    )
    assert admin.post(f"/api/outputs/{o['id']}/regenerate").status_code == 422
    body["property_data"]["area"] = "1200"
    admin.put(f"/api/projects/{p}/items/{item}", json=body)
    new = admin.post(f"/api/outputs/{o['id']}/regenerate")
    assert new.status_code == 200 and new.json()["id"] != o["id"]
    assert pdf(admin, approved) == old_bytes


def board(size, legal, court):
    """A banner of one size rendered with the given announcement texts:
    (html, whether every bounded text stays in its box)."""
    from fastapi import HTTPException
    from weasyprint import HTML

    from app.generation.engine import render_html, safe_fetch
    from app.generation.preflight import check_layout
    from app.services.banners import SIZES

    content = {
        "project": {
            "auction": {
                "auction_name": "مزاد آفاق",
                "auction_type": "hybrid",
                "auction_date": "2026-10-10",
                "auction_start_date": "2026-10-10",
                "auction_end_date": "2026-10-12",
                "start_time": "16:00",
                "end_time": "18:00",
                "physical_location": "الرياض",
                "electronic_platform_name": "منصة",
                "license_number": "420000053",
                "auction_contact_number": "0555000000",
                "legal_announcement_text": legal,
                "court_decision_text": court,
                "booklet_url": "https://example.com/b",
            },
            "selling_agent": {"name": "وكيل"},
            "agent_logo": "",
        },
        "items": [{"title": "عقار", "property_data": {"property_type": "أرض"}}],
        "banner": {**SIZES[size], "size": size, "scale": "1:10"},
        "output_language": "ar",
        "branding": {},
    }
    html = render_html(content, "infath/board.html")
    try:
        check_layout(HTML(string=html, url_fetcher=safe_fetch).render(), content)
    except HTTPException:
        return html, False
    return html, True


def words(length, source):
    text = ""
    while len(text) < length:
        text += (" " if text else "") + source[len(text.split()) % len(source)]
    return text[:length].rstrip()


def test_every_banner_size_holds_the_longest_announcement_and_court_decision():
    """A court decision is usually long: beside a full announcement every
    banner size holds the longest one the forms accept. Long text is set only
    a little smaller (90%); a usual one keeps the full size."""
    import re

    from app.services.banners import COURT_LIMIT, LEGAL_SMALL, SIZES

    assert COURT_LIMIT == 200 and LEGAL_SMALL[0] >= 0.9
    sources = [
        "وبقرار من محكمة التنفيذ بالرياض رقم 4471234567 وتاريخ 1447/03/15 القاضي ببيع العقارات المملوكة للمدين بالمزاد العلني".split(),
        "وبقرار من محكمة التنفيذ ومحكمة الأحوال الشخصية بمدينة الرياض الصادر بتاريخ الخامس عشر من شهر ربيع الأول".split(),
    ]

    def size_of(html):
        return float(re.findall(r"\.legal\{font-size:([\d.]+)pt", html)[-1])

    for size in SIZES:
        usual, fits = board(size, words(75, sources[1]), words(40, sources[0]))
        assert fits, size
        for source in sources:
            longest, fits = board(size, words(220, source), words(COURT_LIMIT, source))
            assert fits, (size, source[:3])
            assert size_of(longest) == pytest.approx(size_of(usual) * 0.9, rel=0.001)
