import asyncio
from io import BytesIO

import pandas as pd
import pymupdf
import pytest
from PIL import Image

from app.config import settings
from app.generation.generators import GENERATORS
from app.services.ai import AIService
from app.services.ingestion import normalize, parse_excel


def project(c, code="DEMO", name="مشروع المعدات"):
    r = c.post(
        "/api/projects",
        json={
            "name": name,
            "code": code,
            "customer": "شركة التطوير",
            "description": "دراسة الأصول والمعدات",
            "location": "عمّان",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def item(c, p, title="معدات صناعية"):
    r = c.post(
        f"/api/projects/{p}/items",
        json={
            "title": title,
            "reference": "A-01",
            "quantity": 2,
            "financial_value": "1500.50",
            "description": "معدات موثوقة للاستخدام الصناعي",
            "specifications": "قدرة عالية، استهلاك منخفض",
            "technical_information": "تم الفحص الفني",
            "attributes": {"condition": "Good"},
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def workbook(rows):
    data = BytesIO()
    with pd.ExcelWriter(data, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Assets")
    return data.getvalue()


def image_data():
    data = BytesIO()
    Image.new("RGB", (900, 600), (91, 123, 98)).save(data, "PNG")
    return data.getvalue()


def generate(c, p, types=None):
    r = c.post(
        f"/api/projects/{p}/generate",
        json={"types": types or list(GENERATORS), "use_ai": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_authentication_and_logout(client):
    assert client.get("/api/projects").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "admin@example.com", "password": "wrong"}
        ).status_code
        == 401
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Test-password-for-suite-123"},
    )
    assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
    token = client.cookies.get("session")
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.set("session", token)
    assert client.get("/api/projects").status_code == 401


def test_login_throttle(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login", json={"email": "none", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"email": "none", "password": "wrong"}
        ).status_code
        == 429
    )


def test_normalization():
    assert (
        normalize(
            {"title": "  Asset  ", "quantity": "2", "financial_value": "1,200.50"}
        )["financial_value"]
        == "1200.50"
    )
    assert normalize({"title": "  Asset  "})["title"] == "Asset"
    with pytest.raises(ValueError):
        normalize({"title": " "})
    with pytest.raises(ValueError):
        normalize({"title": "Asset", "quantity": -1})
    with pytest.raises(ValueError):
        normalize({"title": "Asset", "financial_value": "NaN"})


def test_excel_mapping_and_errors():
    rows = parse_excel(
        workbook(
            [
                {"Custom name": "A", "Price": "1,200.50", "Extra": "X"},
                {"Custom name": "", "Price": -2},
            ]
        ),
        "test.xlsx",
        {"Custom name": "title", "Price": "financial_value"},
    )
    assert rows[0]["data"]["title"] == "A"
    assert rows[0]["data"]["attributes"]["Extra"] == "X"
    assert rows[1]["errors"]


def test_project_manual_and_duplicate(admin):
    p = project(admin)
    item(admin, p)
    detail = admin.get("/api/projects/" + p).json()
    assert detail["items"][0]["quantity"] in (2, "2.0000")
    assert (
        admin.post(
            "/api/projects", json={"name": "duplicate", "code": "DEMO"}
        ).status_code
        == 409
    )
    assert (
        admin.post("/api/projects", json={"name": " ", "code": "BAD"}).status_code
        == 422
    )


def test_excel_preview_commit_and_replay(admin):
    p = project(admin)
    data = workbook(
        [
            {"Item name": "Imported", "Quantity": 3, "Value": 40},
            {"Item name": None, "Quantity": -1, "Value": 5},
        ]
    )
    response = admin.post(
        f"/api/projects/{p}/imports/preview", files={"file": ("sample.xlsx", data)}
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["valid_count"] == 1 and preview["invalid_count"] == 1
    assert admin.get("/api/projects/" + p).json()["items"] == []
    url = f"/api/projects/{p}/imports/{preview['id']}/commit"
    assert admin.post(url).json() == {"imported": 1, "skipped": 1}
    assert admin.post(url).status_code == 409
    assert len(admin.get("/api/projects/" + p).json()["items"]) == 1


def test_complete_eight_output_flow(admin, tmp_path):
    p = project(admin)
    first = item(admin, p)
    data = workbook(
        [
            {
                "Item name": "مولد احتياطي",
                "Quantity": 1,
                "Value": 3500,
                "Specifications": "قدرة ٢٠ كيلوواط",
            }
        ]
    )
    preview = admin.post(
        f"/api/projects/{p}/imports/preview", files={"file": ("sample.xlsx", data)}
    ).json()
    assert (
        admin.post(f"/api/projects/{p}/imports/{preview['id']}/commit").status_code
        == 200
    )
    assert (
        admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("real.png", image_data())},
            data={"item_id": first},
        ).status_code
        == 200
    )
    outputs = generate(admin, p)
    assert len(outputs) == 8
    for o in outputs:
        assert o["status"] == "DRAFT"
        assert o["content"]["ai_status"] == "UNAVAILABLE"
        pdf_file = next(f for f in o["files"] if f["media_type"] == "application/pdf")
        pdf = admin.get("/api/files/" + pdf_file["id"])
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        with pymupdf.open(stream=pdf.content, filetype="pdf") as document:
            assert len(document) > 0
            if o["output_type"] == "project_booklet":
                assert len(document) >= 3
                assert any(page.get_images() for page in document)
                assert any(
                    "مشروع" in page.get_text() or "المعدات" in page.get_text()
                    for page in document
                )
        assert (
            admin.get("/api/files/" + pdf_file["id"] + "?download=true").status_code
            == 409
        )
        if o["output_type"] == "social_content":
            edited = admin.put(
                "/api/outputs/" + o["id"],
                json={"review_text": "Reviewed social copy / محتوى معتمد للمراجعة"},
            ).json()
            assert edited["status"] == "DRAFT"
        approved = admin.post("/api/outputs/" + o["id"] + "/approve")
        assert approved.status_code == 200, approved.text
        approved = approved.json()
        assert approved["status"] == "APPROVED" and approved["approved_at"]
        for f in approved["files"]:
            r = admin.get("/api/files/" + f["id"] + "?download=true")
            assert (
                r.status_code == 200
                and "attachment" in r.headers["content-disposition"]
            )
            if f["media_type"] == "image/png":
                assert r.content.startswith(b"\x89PNG")
    assert admin.get("/api/dashboard").json()["approved_outputs"] == 8


def test_source_changes_invalidate_and_regeneration(admin):
    p = project(admin)
    item(admin, p)
    o = generate(admin, p, ["project_booklet"])[0]
    first_file = o["files"][0]["id"]
    old = admin.get("/api/files/" + first_file).content
    assert admin.post("/api/outputs/" + o["id"] + "/approve").status_code == 200
    item(admin, p, "Another asset")
    assert admin.post("/api/outputs/" + o["id"] + "/approve").status_code == 409
    assert (
        admin.put("/api/outputs/" + o["id"], json={"review_text": "edit"}).status_code
        == 409
    )
    regenerated = admin.post("/api/outputs/" + o["id"] + "/regenerate").json()
    assert regenerated["status"] == "DRAFT"
    new = admin.get("/api/files/" + regenerated["files"][0]["id"]).content
    with (
        pymupdf.open(stream=old, filetype="pdf") as a,
        pymupdf.open(stream=new, filetype="pdf") as b,
    ):
        assert len(b) > len(a)
    assert admin.get("/api/files/" + first_file).status_code == 404


def test_project_isolation(admin):
    a = project(admin, "A", "PROJECT_ALPHA")
    ai = item(admin, a, "ALPHA_PRIVATE")
    b = project(admin, "B", "PROJECT_BETA")
    item(admin, b, "BETA_PRIVATE")
    assert (
        admin.post(
            f"/api/projects/{b}/images",
            files={"file": ("asset.png", image_data())},
            data={"item_id": ai},
        ).status_code
        == 400
    )
    assert (
        admin.put(f"/api/projects/{b}/items/{ai}", json={"title": "oops"}).status_code
        == 404
    )
    for o in generate(admin, b):
        f = next(f for f in o["files"] if f["media_type"] == "application/pdf")
        with pymupdf.open(
            stream=admin.get("/api/files/" + f["id"]).content, filetype="pdf"
        ) as pdf:
            text = "".join(p.get_text() for p in pdf)
            assert "ALPHA_PRIVATE" not in text and "PROJECT_ALPHA" not in text
    preview = admin.post(
        f"/api/projects/{a}/imports/preview",
        files={"file": ("test.xlsx", workbook([{"title": "X"}]))},
    ).json()
    assert (
        admin.post(f"/api/projects/{b}/imports/{preview['id']}/commit").status_code
        == 404
    )


def test_file_validation_and_csrf(admin):
    p = project(admin)
    assert (
        admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("bad.png", b"<script>bad</script>")},
        ).status_code
        == 400
    )
    assert (
        admin.post(
            f"/api/projects/{p}/imports/preview",
            files={"file": ("bad.xlsx", b"not excel")},
        ).status_code
        == 400
    )
    assert (
        admin.post(
            f"/api/projects/{p}/imports/preview",
            files={"file": ("bad.csv", b"not excel")},
        ).status_code
        == 400
    )
    assert (
        admin.post(
            "/api/projects",
            json={"name": "bad", "code": "bad"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert "ai_api_key" not in admin.get("/api/settings").text


def test_ai_missing_key():
    result = asyncio.run(AIService().summarize({"title": "Example"}))
    assert result["status"] == "UNAVAILABLE"


def test_ai_provider_failure(monkeypatch):
    import httpx

    monkeypatch.setattr(settings(), "ai_api_key", "test-provider-key")

    async def failure(*args, **kwargs):
        raise httpx.ConnectError("Offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", failure)
    assert (
        asyncio.run(AIService().generate_description({"title": "Example"}))["status"]
        == "ERROR"
    )


def test_ai_provider_contract(monkeypatch):
    import httpx

    monkeypatch.setattr(settings(), "ai_api_key", "test-provider-key")

    async def success(*args, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer test-provider-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Draft copy"}}]},
            request=httpx.Request("POST", "https://example.test"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", success)
    service = AIService()
    for method in (
        service.summarize,
        service.generate_description,
        service.generate_social_content,
        service.analyze_item,
    ):
        assert asyncio.run(method({"title": "Sample"}))["status"] == "DRAFT"


def test_booklet_grows_beyond_twenty_pages(admin):
    p = project(admin, "LARGE", "Large booklet")
    for index in range(22):
        item(admin, p, f"Asset {index + 1}")
    o = generate(admin, p, ["project_booklet"])[0]
    pdf = admin.get("/api/files/" + o["files"][0]["id"]).content
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        assert len(document) >= 23
        text = "".join(page.get_text() for page in document)
        assert "Asset 1" in text and "Asset 22" in text
