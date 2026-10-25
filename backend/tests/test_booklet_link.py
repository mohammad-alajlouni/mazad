"""What a banner's QR code opens: the booklet, for anyone, without signing in."""

import re
from io import BytesIO

import pymupdf
import zxingcpp
from fastapi.testclient import TestClient
from PIL import Image
from test_banners import campaign
from test_workflow import image_data

from app.main import app


def booklet_project(admin, booklet_url=None, kind="physical"):
    p, item = campaign(admin, kind, workspace="project")
    for category in ["cover", "main"]:
        r = admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("photo.png", image_data())},
            data={
                "category": category,
                **({"item_id": item} if category == "main" else {}),
            },
        )
        assert r.status_code == 200, r.text
    if booklet_url is not None:
        detail = admin.get(f"/api/projects/{p}").json()["project"]
        auction = {**detail["auction"], "booklet_url": booklet_url}
        r = admin.put(f"/api/projects/{p}", json={**detail, "auction": auction})
        assert r.status_code == 200, r.text
    return p


def banner_qr(admin, p):
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    png = next(f for f in r.json()[0]["files"] if f["media_type"] == "image/png")
    image = Image.open(BytesIO(admin.get("/api/files/" + png["id"]).content))
    # The board's code is drawn as the guide draws it (light on teal).
    codes = [c.text for c in zxingcpp.read_barcodes(image)]
    assert len(codes) == 1, codes
    return codes[0]


def test_the_banner_qr_opens_the_booklet_without_signing_in(admin):
    p = booklet_project(admin)
    token = admin.get(f"/api/projects/{p}").json()["project"]["share_token"]
    url = banner_qr(admin, p)
    # The platform's own public link (the field was left as the sample had
    # it, a placeholder: the platform's link stands in).
    assert url == f"http://testserver/api/b/{token}"
    path = url.removeprefix("http://testserver")
    stranger = TestClient(app)  # a phone: no session
    before = stranger.get(path)
    assert before.status_code == 404 and "لم يصدر كتيّب هذا المزاد بعد" in before.text

    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["project_booklet"]})
    assert r.status_code == 200, r.text
    pdf = admin.get(
        "/api/files/"
        + next(
            f["id"]
            for f in r.json()[0]["files"]
            if f["media_type"] == "application/pdf"
        )
    ).content
    count = len(pymupdf.open(stream=pdf, filetype="pdf"))

    page = stranger.get(path)
    assert page.status_code == 200, page.text
    assert page.headers["content-type"].startswith("text/html")
    assert "مزاد آفاق" in page.text
    # Every page of the booklet, as a picture any phone shows.
    pictures = re.findall(r'src="(/api/b/[^"]+/pages/\d+[^"]*)"', page.text)
    assert len(pictures) == count
    for src in (pictures[0], pictures[-1]):
        shown = stranger.get(src.replace("&amp;", "&"))
        assert shown.status_code == 200 and shown.headers["content-type"] == "image/png"
        assert Image.open(BytesIO(shown.content)).width == 1240
    # And the PDF itself, shown in place.
    link = re.search(r'href="(/api/b/[^"]+/pdf[^"]*)"', page.text)[1]
    document = stranger.get(link.replace("&amp;", "&"))
    assert document.status_code == 200 and document.content == pdf
    assert document.headers["content-disposition"].startswith("inline")
    # The approved booklet is the one shown, whatever is issued after it.
    approved = admin.post(f"/api/outputs/{r.json()[0]['id']}/approve")
    assert approved.status_code == 200, approved.text
    final = admin.get(
        "/api/files/"
        + next(
            f["id"]
            for f in approved.json()["files"]
            if f["media_type"] == "application/pdf"
        )
    ).content
    admin.post(f"/api/projects/{p}/generate", json={"types": ["project_booklet"]})
    page = stranger.get(path)
    link = re.search(r'href="(/api/b/[^"]+/pdf[^"]*)"', page.text)[1]
    assert stranger.get(link.replace("&amp;", "&")).content == final
    # Nothing else of the project is open.
    assert stranger.get(f"/api/projects/{p}").status_code == 401
    assert stranger.get("/api/b/not-a-token").status_code == 404


def test_a_link_into_the_platform_is_replaced_and_an_outside_one_kept(admin):
    p = booklet_project(admin, "http://testserver/api/files/123?download=true")
    token = admin.get(f"/api/projects/{p}").json()["project"]["share_token"]
    assert banner_qr(admin, p) == f"http://testserver/api/b/{token}"
    other = booklet_project(admin, "https://infath.gov.sa/booklets/77", "electronic")
    assert banner_qr(admin, other) == "https://infath.gov.sa/booklets/77"


def test_every_project_has_its_own_link(admin):
    first = booklet_project(admin)
    second = booklet_project(admin, kind="hybrid")
    a = admin.get(f"/api/projects/{first}").json()["project"]["share_token"]
    b = admin.get(f"/api/projects/{second}").json()["project"]["share_token"]
    assert a and b and a != b and len(a) >= 12
