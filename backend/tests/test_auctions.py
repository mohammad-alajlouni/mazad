import base64
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pymupdf
import pytest
import zxingcpp
from PIL import Image
from sqlalchemy import select
from test_workflow import image_data, workbook

from app.auth import hasher
from app.db import SessionLocal
from app.generation.booklet.codes import barcode, qr
from app.models import GeneratedOutput, RentalContract, User
from app.services.ingestion import normalize, parse_excel


def create_auction(c, kind="hybrid", cover="infath-2", workspace="project"):
    response = c.post(
        "/api/projects",
        json={
            "name": "مزاد العقارات التجريبي",
            "workspace_type": workspace,
            "code": "AUCTION-" + kind + "-" + cover,
            "auction": {
                "auction_name": "مزاد آفاق العقاري",
                "auction_type": kind,
                "auction_date": "2026-10-10",
                "auction_start_date": "2026-10-10",
                "auction_end_date": "2026-10-12",
                "start_time": "16:00",
                "end_time": "18:00",
                "physical_location": "الرياض - قاعة المزاد",
                "electronic_platform_name": "منصة المزادات",
                "electronic_platform_url": "https://example.com/auction/a",
                "auction_location_url": "https://example.com/location/a",
                "selected_cover_template_id": cover,
                "document_language": "ar",
                "license_number": "420000053",
                "supervising_authority": "مركز الإسناد والتصفية - إنفاذ",
                "court_decision_text": "بيانات تجريبية لا تمثل إعلان بيع حقيقي.",
            },
        },
    )
    assert response.status_code == 201, response.text
    p = response.json()["id"]
    response = c.put(
        f"/api/projects/{p}/selling-agent",
        json={
            "name": "شركة آفاق العقارية",
            "description": "وكيل بيع متخصص في تسويق العقارات وإدارة المزادات.",
            "phone": "0555000000",
            "website": "https://example.com",
        },
    )
    assert response.status_code == 200, response.text
    return p


def property_input(n=1):
    return {
        "title": f"عقار تجريبي {n}",
        "description": "عقار في موقع مميز بالقرب من الخدمات والطرق الرئيسية.",
        "property_data": {
            "property_type": "أرض سكنية",
            "city": "الرياض",
            "district": "النرجس",
            "area": "1200",
            "deed_number": f"001{n}",
            "plan_number": "05",
            "plot_number": str(n),
            "participation_amount": "25000",
            "location_link": f"https://example.com/property/{n}",
            "auction_close_date": "2026-10-12",
            "auction_close_time": "18:00",
        },
    }


def add(c, p, body):
    r = c.post(f"/api/projects/{p}/items", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def generate(c, p):
    r = c.post(f"/api/projects/{p}/generate", json={"types": ["project_booklet"]})
    assert r.status_code == 200, r.text
    return r.json()[0]


def pdf(c, o):
    r = c.get("/api/files/" + o["files"][0]["id"])
    assert r.status_code == 200
    return r.content


def test_manual_auction_end_to_end(admin):
    p = create_auction(admin)
    body = property_input()
    body["property_data"].update(
        {
            "features": [
                "قريب من الخدمات",
                "واجهة على شارع رئيسي",
                "موقع مميز",
                "شبكة مياه",
                "شبكة كهرباء",
                "مداخل متعددة",
            ],
            "additional_information": "معلومات إضافية بشأن معاينة العقار.",
            "boundaries": {
                "north_description": "شارع بعرض ثلاثين متراً",
                "north_length": "30 م",
                "south_description": "قطعة مجاورة",
                "south_length": "30 م",
                "east_description": "شارع",
                "east_length": "40 م",
                "west_description": "قطعة مجاورة",
                "west_length": "40 م",
            },
            "rental_contracts": [
                {
                    "unit_number": str(i),
                    "property_type": "محل تجاري",
                    "annual_rent_value": "12000",
                    "contract_start_date": "2026-01-01",
                    "contract_end_date": "2026-12-31",
                }
                for i in range(21)
            ],
        }
    )
    first = add(admin, p, body)
    second = add(admin, p, property_input(2))
    for i, size in enumerate(
        [(900, 600), (600, 900), (900, 600), (900, 600), (900, 600)]
    ):
        stream = BytesIO()
        Image.new("RGB", size, (80 + i * 25, 130, 140)).save(stream, "PNG")
        r = admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("photo.png", stream.getvalue())},
            data={
                "item_id": first,
                "category": "main" if i == 0 else "additional",
                "caption": f"صورة العقار {i + 1}",
            },
        )
        assert r.status_code == 200, r.text
    stream = BytesIO()
    Image.new("RGB", (500, 900), (165, 145, 110)).save(stream, "PNG")
    assert (
        admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("portrait.png", stream.getvalue())},
            data={"item_id": second, "category": "main"},
        ).status_code
        == 200
    )
    review = admin.get(f"/api/projects/{p}/review").json()
    assert review["valid"]
    assert review["properties"][0]["additional_image_count"] == 4
    detail = admin.get(f"/api/projects/{p}").json()
    assert len(detail["items"][0]["property_data"]["rental_contracts"]) == 21
    with SessionLocal() as db:
        assert len(db.scalars(select(RentalContract)).all()) == 21
    o = generate(admin, p)
    assert o["status"] == "DRAFT"
    assert o["cover_id"] == "infath-2"
    kinds = [page["kind"] for page in o["page_manifest"]]
    assert (
        kinds.count("property") == 2
        and kinds.count("rentals") == 2  # 21 contracts, 19 rows per reference page
        and kinds.count("images") == 2
        and kinds.count("boundaries") == 0
        and "participation" in kinds
    )
    data = pdf(admin, o)
    path = Path(__file__).resolve().parents[2] / "output/pdf/auction-manual.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert len(doc) >= len(kinds)
        assert "عقار" in "".join(page.get_text() for page in doc)
        assert any("Ruaq" in str(font) for page in doc for font in page.get_fonts())
        decoded = set()
        for page in doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            decoded.update(r.text for r in zxingcpp.read_barcodes(im))
        assert (
            "https://example.com/property/1" in decoded
            and "https://example.com/property/2" in decoded
        )
        # The reference contact page carries the auction QR and no project barcode.
        assert "https://example.com/auction/a" in decoded
        assert ("P-" + str(UUID(p).int)) not in decoded
    approved = admin.post("/api/outputs/" + o["id"] + "/approve").json()
    assert approved["status"] == "APPROVED"
    assert (
        admin.get(
            "/api/files/" + approved["files"][0]["id"] + "?download=true"
        ).status_code
        == 200
    )
    approved_bytes = pdf(admin, approved)
    # Regeneration creates a new draft and preserves the approved version and file.
    regenerated = admin.post("/api/outputs/" + o["id"] + "/regenerate")
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["id"] != o["id"]
    assert pdf(admin, approved) == approved_bytes
    # Edit, reorder, delete and maintain relational integrity.
    body["property_data"]["rental_contracts"] = []
    body["title"] = "عقار معدل"
    assert admin.put(f"/api/projects/{p}/items/{first}", json=body).status_code == 200
    assert (
        admin.put(
            f"/api/projects/{p}/item-order", json={"item_ids": [second, first]}
        ).status_code
        == 200
    )
    assert admin.get(f"/api/projects/{p}").json()["items"][0]["id"] == second
    assert admin.delete(f"/api/projects/{p}/items/{first}").status_code == 200
    with SessionLocal() as db:
        assert not db.scalars(select(RentalContract)).all()


@pytest.mark.parametrize(
    "kind,cover",
    [
        ("physical", "infath-1"),
        ("electronic", "infath-3"),
        ("hybrid", "infath-4"),
        ("physical", "infath-5"),
        ("physical", "infath-6"),
    ],
)
def test_types_covers_and_fixed_pages(admin, kind, cover):
    p = create_auction(admin, kind, cover)
    add(admin, p, property_input())
    assert len(admin.get("/api/booklet-templates").json()) == 6
    assert admin.get(f"/api/booklet-templates/{cover}/thumbnail").content.startswith(
        b"\x89PNG"
    )
    o = generate(admin, p)
    assert o["cover_id"] == cover
    kinds = [v["kind"] for v in o["page_manifest"]]
    assert ("participation" in kinds) == (kind != "physical")
    assert not any(v in kinds for v in ("rentals", "images", "boundaries"))
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as doc:
        # Actual selected background appears as an embedded image on the PDF cover.
        from app.generation.booklet.assets import ASSETS

        expected = Image.open(ASSETS / f"cover-{cover[-1]}.png").convert("RGB")
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1, 1))
        actual = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        e = expected.getpixel((int(expected.width * 0.08), int(expected.height * 0.2)))
        a = actual.getpixel((int(actual.width * 0.08), int(actual.height * 0.2)))
        assert max(abs(x - y) for x, y in zip(e, a)) < 15


def test_excel_auction_end_to_end(admin):
    p = create_auction(admin, "electronic")
    data = workbook(
        [
            {
                "المدينة": "الرياض",
                "نوع العقار": "أرض سكنية",
                "الحي": "النرجس",
                "المساحة": "١٬٢٠٠",
                "رقم الصك": "00123",
                "رقم القطعة": "5",
                "Custom survey": "https://example.com/survey/1",
            }
        ]
    )
    url = f"/api/projects/{p}/imports/preview"
    preview = admin.post(url, files={"file": ("properties.xlsx", data)}).json()
    assert preview["valid_count"] == 1 and preview["columns"]
    import json

    preview = admin.post(
        url,
        files={"file": ("properties.xlsx", data)},
        data={"mapping": json.dumps({"Custom survey": "property.survey_link"})},
    ).json()
    assert not preview["invalid_count"]
    assert (
        admin.post(f"/api/projects/{p}/imports/{preview['id']}/commit").json()[
            "imported"
        ]
        == 1
    )
    item = admin.get(f"/api/projects/{p}").json()["items"][0]
    assert (
        item["property_data"]["deed_number"] == "00123"
        and item["property_data"]["area"] == "1200"
    )
    manual = normalize({"title": item["title"], "property_data": item["property_data"]})
    assert (
        manual["property_data"]["survey_link"] == item["property_data"]["survey_link"]
    )
    assert admin.get(f"/api/projects/{p}/review").json()["valid"]
    o = generate(admin, p)
    data = pdf(admin, o)
    path = Path(__file__).resolve().parents[2] / "output/pdf/auction-excel.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert any("00123" in page.get_text() for page in doc)
    approved = admin.post("/api/outputs/" + o["id"] + "/approve").json()
    assert (
        admin.get(
            "/api/files/" + approved["files"][0]["id"] + "?download=true"
        ).status_code
        == 200
    )


def test_validation_and_mapping(admin):
    p = create_auction(admin)
    assert admin.get(f"/api/projects/{p}/review").json()["valid"] is False
    assert (
        admin.post(
            f"/api/projects/{p}/generate", json={"types": ["project_booklet"]}
        ).status_code
        == 400
    )
    bad = property_input()
    bad["property_data"]["survey_link"] = "file:///etc/passwd"
    assert admin.post(f"/api/projects/{p}/items", json=bad).status_code == 422
    rows = parse_excel(
        workbook(
            [
                {"نوع العقار": "أرض", "المساحة": "bad"},
                {"نوع العقار": "أرض", "المساحة": "bad"},
            ]
        ),
        "a.xlsx",
    )
    assert all(r["errors"] for r in rows) and "Duplicate row" in rows[1]["errors"]
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Report heading"])
    ws.append([])
    ws.append(["نوع العقار", "المدينة", "المساحة"])
    ws.append(["أرض", "الرياض", 100])
    out = BytesIO()
    wb.save(out)
    parsed = parse_excel(out.getvalue(), "a.xlsx")
    assert parsed[0]["row_number"] == 4 and not parsed[0]["errors"]


def test_user_isolation(admin):
    p = create_auction(admin)
    i = add(admin, p, property_input())
    o = generate(admin, p)
    image = admin.post(
        f"/api/projects/{p}/images",
        files={"file": ("p.png", image_data())},
        data={"item_id": i},
    ).json()
    with SessionLocal() as db:
        db.add(
            User(
                email="second@example.com",
                password_hash=hasher.hash("second-password-123"),
            )
        )
        db.commit()
    admin.post("/api/auth/logout")
    assert (
        admin.post(
            "/api/auth/login",
            json={"email": "second@example.com", "password": "second-password-123"},
        ).status_code
        == 200
    )
    assert (
        admin.get("/api/projects").json() == []
        and admin.get("/api/outputs").json() == []
    )
    assert admin.get("/api/dashboard").json()["total_projects"] == 0
    assert admin.post(f"/api/projects/{p}/booklet-preview", json={}).status_code == 404
    for path in [
        f"/projects/{p}",
        f"/projects/{p}/review",
        f"/images/{image['id']}",
        f"/outputs/{o['id']}",
        f"/files/{o['files'][0]['id']}",
    ]:
        assert admin.get("/api" + path).status_code == 404, path
    assert (
        admin.put(
            f"/api/projects/{p}/selling-agent", json={"name": "attack"}
        ).status_code
        == 404
    )


def test_codes_decode():
    for uri, expected in [
        (qr("https://example.com/عقار/123"), "https://example.com/عقار/123"),
        (barcode("asset-123"), "asset-123"),
        (
            barcode("P-99814871384035649633548592210319119414"),
            "P-99814871384035649633548592210319119414",
        ),
    ]:
        raw = base64.b64decode(uri.split(",")[1])
        if "svg+xml" in uri:
            doc = pymupdf.open(stream=raw, filetype="svg")
            pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(3, 3))
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            im = Image.open(BytesIO(raw))
        assert expected in [r.text for r in zxingcpp.read_barcodes(im)]
    with pytest.raises(ValueError):
        qr("javascript:alert(1)")


def test_summary_pagination_overflow_and_english(admin):
    p = create_auction(admin, "electronic", "infath-6")
    for n in range(1, 18):
        body = property_input(n)
        if n == 1:
            body["description"] = (
                "وصف طويل للعقار ومعلومات المعاينة. " * 100
            ) + " DESCRIPTION_END"
            body["notes"] = ("ملاحظات هامة حول العقار. " * 100) + " NOTES_END"
            body["property_data"]["features"] = [
                "ميزة إضافية " + str(i) for i in range(40)
            ]
            body["property_data"]["additional_information"] = (
                "تفاصيل إضافية " * 150 + " INFO_END"
            )
            body["property_data"]["boundaries"] = {
                "north_description": "الحد الشمالي " * 150 + " BOUNDARY_END"
            }
        add(admin, p, body)
    result = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["project_booklet"], "output_language": "en"},
    )
    assert result.status_code == 200, result.text
    o = result.json()[0]
    assert [x["kind"] for x in o["page_manifest"]].count("summary") == 2
    with pymupdf.open(stream=pdf(admin, o), filetype="pdf") as doc:
        text = "".join(page.get_text() for page in doc)
        for marker in [
            "DESCRIPTION_END",
            "NOTES_END",
            "INFO_END",
            "BOUNDARY_END",
            "Property summary",
            "Rental contracts",
        ][:-1]:
            assert marker in text
        assert len(doc) > 30
        for page in doc:
            for block in page.get_text("blocks"):
                assert block[0] >= -1 and block[2] <= page.rect.width + 1
                assert block[1] >= -1 and block[3] <= page.rect.height + 1


def test_auction_banner_and_image_isolation(admin):
    p = create_auction(admin, workspace="booklet")
    first = add(admin, p, property_input(1))
    second = add(admin, p, property_input(2))
    image = admin.post(
        f"/api/projects/{p}/images",
        files={"file": ("image.png", image_data())},
        data={"item_id": first, "category": "main"},
    ).json()
    body = property_input(2)
    body["attributes"] = {"image_reference": image["id"]}
    admin.put(f"/api/projects/{p}/items/{second}", json=body)
    o = generate(admin, p)
    with SessionLocal() as db:
        output = db.get(GeneratedOutput, o["id"])
        assert not output.content["items"][1]["image_assets"]
    response = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert response.status_code == 200, response.text
    assert sum(f["media_type"] == "image/png" for f in response.json()[0]["files"]) == 2
