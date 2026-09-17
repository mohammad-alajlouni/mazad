import asyncio
import json
from pathlib import Path

import httpx
import pymupdf
import pytest
from test_workflow import item, project, workbook

from app.config import settings
from app.generation.generators import GENERATORS
from app.services.ai import AIService


@pytest.mark.parametrize("language", ["en", "ar"])
def test_output_language_snapshot_and_pdf(admin, language, tmp_path):
    p = project(admin, "MIX-123", "مشروع Atlas 2026")
    item(admin, p, "مولد Generator A-01")
    response = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": list(GENERATORS), "output_language": language},
    )
    assert response.status_code == 200, response.text
    outputs = response.json()
    for output in outputs:
        assert output["content"]["output_language"] == language
        assert output["project_name"] == "مشروع Atlas 2026"
        file = next(f for f in output["files"] if f["media_type"] == "application/pdf")
        pdf = admin.get("/api/files/" + file["id"]).content
        (tmp_path / f"{language}-{output['output_type']}.pdf").write_bytes(pdf)
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
            assert "MIX-123" in text
            assert "\ufffd" not in text
            assert (
                ("تجريبي" in text)
                if language == "ar"
                else ("DEVELOPMENT TEMPLATE" in text)
            )
            if language == "ar":
                for label in (
                    "Quantity",
                    "Not supplied",
                    "Technical information",
                    "provided",
                    "missing",
                    "DEVELOPMENT TEMPLATE",
                ):
                    assert label not in text
    # Changing the organization default must not silently change an existing output.
    config = admin.get("/api/settings").json()["branding"]
    config["default_language"] = "ar" if language == "en" else "en"
    assert admin.put("/api/settings", json=config).status_code == 200
    regenerated = admin.post("/api/outputs/" + outputs[0]["id"] + "/regenerate").json()
    assert regenerated["content"]["output_language"] == language
    default_output = admin.post(
        f"/api/projects/{p}/generate", json={"types": ["asset_study"]}
    ).json()[0]
    assert default_output["content"]["output_language"] == config["default_language"]
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"output_language": "fr"}
        ).status_code
        == 422
    )


def test_localizable_errors_and_excel_issues(admin):
    result = admin.post("/api/projects", json={"name": " ", "code": "X"}).json()
    assert result["code"] == "VALIDATION_ERROR"
    assert result["violations"][0]["field"] == "name"
    p = project(admin)
    result = admin.post(
        "/api/projects", json={"name": "duplicate", "code": "DEMO"}
    ).json()
    assert result["code"] == "A_PROJECT_WITH_THIS_REFERENCE_ALREADY_EXISTS"
    preview = admin.post(
        f"/api/projects/{p}/imports/preview",
        files={"file": ("test.xlsx", workbook([{"title": "bad", "quantity": -1}]))},
    ).json()
    assert preview["rows"][0]["issues"][0]["type"] == "greater_than"
    assert preview["rows"][0]["errors"]  # Legacy API field remains available.


@pytest.mark.parametrize("language,expected", [("ar", "Arabic"), ("en", "English")])
def test_ai_explicit_language(monkeypatch, language, expected):
    monkeypatch.setattr(settings(), "ai_api_key", "test-provider-key")

    async def success(*args, **kwargs):
        prompt = kwargs["json"]["messages"][0]["content"]
        assert "Write in " + expected in prompt
        assert "Preserve names, identifiers" in prompt
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Draft"}}]},
            request=httpx.Request("POST", "https://example.test"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", success)
    assert (
        asyncio.run(
            AIService().generate(
                "summary", {"name": "مشروع Atlas"}, output_language=language
            )
        )["status"]
        == "DRAFT"
    )


def test_translation_resources_have_parity():
    root = Path(__file__).parents[2]
    en = json.loads((root / "frontend/messages/en.json").read_text())
    ar = json.loads((root / "frontend/messages/ar.json").read_text())
    assert en.keys() == ar.keys()
    for namespace in en:
        assert en[namespace].keys() == ar[namespace].keys()
        assert all(ar[namespace].values())
