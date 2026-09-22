import base64
import pymupdf
from test_auctions import create_auction, add, property_input
from test_workflow import image_data


def test_preview_updates_unsaved_drafts_without_mutating_project(admin):
    p = create_auction(admin, workspace="booklet")
    i = add(admin, p, property_input())
    original = admin.get(f"/api/projects/{p}").json()
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={
            "stage": "auction",
            "auction": {
                "auction_name": "LIVE_UNSAVED",
                "auction_type": "physical",
                "physical_location": "LIVE_VENUE",
                "start_time": "",
            },
        },
    )
    assert r.status_code == 200, r.text
    preview = r.json()
    assert "LIVE_UNSAVED" in preview["html"] and "LIVE_VENUE" in preview["html"]
    assert preview["saved"] is False
    # Fonts and artwork are linked for the browser cache, not re-sent each time.
    assert "/api/booklet-assets/" in preview["html"]
    assert "data:font" not in preview["html"] and len(preview["html"]) < 400_000
    assert preview["pages"][preview["page"]]["kind"] == "auction"
    assert preview["pages"][preview["page"]]["step"] == "auction"
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={
            "stage": "items",
            "item": {
                "id": i,
                "title": "LIVE_PROPERTY",
                "property_data": {"property_type": "LIVE_TYPE", "area": "not-a-number"},
            },
        },
    )
    assert r.status_code == 200, r.text
    assert "LIVE_TYPE" in r.json()["html"]
    after = admin.get(f"/api/projects/{p}").json()
    assert (
        after["project"] == original["project"] and after["items"] == original["items"]
    )
    assert after["outputs"] == []
    assert r.headers["cache-control"] == "no-store, private"


def test_preview_final_page_uses_identical_pdf_rendering(admin):
    """The browser preview is the export page: rendering its HTML with the
    linked assets gives the exported PDF page."""
    from weasyprint import HTML, default_url_fetcher

    from test_auctions import generate, pdf

    p = create_auction(admin, workspace="booklet")
    add(admin, p, property_input())
    output = generate(admin, p)

    def fetch(url, *args, **kwargs):
        if url.startswith("data:"):
            return default_url_fetcher(url)
        response = admin.get(url.replace("http://testserver", ""))
        assert response.status_code == 200, url
        return {"string": response.content, "mime_type": response.headers["content-type"]}

    with pymupdf.open(stream=pdf(admin, output), filetype="pdf") as document:
        for index in [0, 3, 5]:
            expected = (
                document[index].get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25)).samples
            )
            response = admin.post(
                f"/api/projects/{p}/booklet-preview", json={"page": index}
            )
            assert response.status_code == 200, response.text
            page = HTML(
                string=response.json()["html"],
                base_url="http://testserver/",
                url_fetcher=fetch,
            ).write_pdf()
            import numpy as np

            with pymupdf.open(stream=page, filetype="pdf") as rendered:
                actual = np.frombuffer(
                    rendered[0].get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25)).samples,
                    dtype=np.uint8,
                ).astype(int)
            target = np.frombuffer(expected, dtype=np.uint8).astype(int)
            delta = np.abs(actual - target)
            assert delta.mean() < 0.05, (index, delta.mean(), delta.max())
            assert (delta > 16).mean() < 0.0005, (index, delta.mean(), delta.max())


def test_preview_rejects_foreign_items_and_does_not_fetch_urls(admin):
    p = create_auction(admin, workspace="booklet")
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={"stage": "items", "item": {"id": "foreign"}},
    )
    assert r.status_code == 404
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={
            "auction": {"electronic_platform_url": "file:///etc/passwd"},
            "agent": {"name": "<script>alert(1)</script>"},
            "stage": "agent",
        },
    )
    assert r.status_code == 200, r.text
    html = r.json()["html"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "<script>" not in html
    assert "file:///etc/passwd" not in html
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={"image": {"src": "https://example.com/a.png", "category": "cover"}},
    )
    assert r.status_code == 422
    r = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={
            "stage": "agent",
            "image": {
                "src": "data:image/png;base64,"
                + base64.b64encode(image_data()).decode(),
                "category": "agent_logo",
            },
        },
    )
    assert r.status_code == 200, r.text


def test_transparent_logo_survives_upload_snapshot_and_preview(admin):
    from io import BytesIO
    from PIL import Image
    from app.db import SessionLocal
    from app.models import Project
    from app.generation.engine import snapshot
    from app.services.booklet_preview import transient_image

    p = create_auction(admin, workspace="booklet")
    stream = BytesIO()
    Image.new("RGBA", (40, 40), (20, 100, 150, 0)).save(stream, "PNG")
    data = stream.getvalue()
    upload = admin.post(
        f"/api/projects/{p}/images",
        data={"category": "agent_logo"},
        files={"file": ("logo.png", data, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    image_id = upload.json()["id"]
    response = admin.get(f"/api/images/{image_id}")
    assert response.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(response.content)).getpixel((0, 0))[3] == 0
    agent = admin.put(
        f"/api/projects/{p}/selling-agent",
        json={"name": "Transparent", "logo_image_id": image_id},
    )
    assert agent.status_code == 200, agent.text
    with SessionLocal() as db:
        project, _ = snapshot(db, db.get(Project, p))
        assert project["agent_logo"].startswith("data:image/png;base64,")
    transient, _ = transient_image(
        "data:image/png;base64," + base64.b64encode(data).decode()
    )
    assert transient.startswith("data:image/png;base64,")
    assert (
        Image.open(BytesIO(base64.b64decode(transient.split(",")[1]))).getpixel((0, 0))[
            3
        ]
        == 0
    )


def test_extra_property_links_and_agent_contact_are_not_lost(admin):
    from test_auctions import generate, pdf

    p = create_auction(admin, workspace="booklet")
    agent = admin.put(
        f"/api/projects/{p}/selling-agent",
        json={
            "name": "Agent",
            "contact_information": "ADDITIONAL_CONTACT_INFORMATION",
            "phone": "0555000000",
        },
    )
    assert agent.status_code == 200, agent.text
    body = property_input()
    for key in (
        "survey_link",
        "rental_information_link",
        "additional_images_link",
        "location_link",
        "other_document_link",
    ):
        body["property_data"][key] = f"https://example.com/{key}"
    add(admin, p, body)
    with pymupdf.open(
        stream=pdf(admin, generate(admin, p)), filetype="pdf"
    ) as document:
        assert "ADDITIONAL_CONTACT_INFORMATION" in "".join(
            page.get_text() for page in document
        )
        urls = {link.get("uri") for page in document for link in page.get_links()}
        for key in (
            "survey_link",
            "rental_information_link",
            "additional_images_link",
            "location_link",
            "other_document_link",
        ):
            assert f"https://example.com/{key}" in urls


def test_additional_photo_preview_focuses_the_page_containing_it(admin):
    p = create_auction(admin, workspace="booklet")
    item = add(admin, p, property_input())
    uploaded = admin.post(
        f"/api/projects/{p}/images",
        data={"item_id": item, "category": "main"},
        files={"file": ("main.png", image_data(), "image/png")},
    )
    assert uploaded.status_code == 200
    response = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={
            "stage": "images",
            "image": {
                "src": "data:image/png;base64,"
                + base64.b64encode(image_data()).decode(),
                "category": "additional",
                "item_id": item,
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["pages"][response.json()["page"]]["kind"] == "images"
