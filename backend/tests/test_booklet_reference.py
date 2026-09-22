"""Regressions found in the supplied Rabou Biladi booklet and design guide."""

from copy import deepcopy
from uuid import uuid4

import pytest
from app.auction_schemas import PropertyData
from app.generation.booklet.composer import compose
from test_auctions import add, create_auction, generate, property_input


def composition(prop=None, **item_fields):
    project = {
        "id": str(uuid4()),
        "auction": {
            "selected_cover_template_id": "infath-2",
            "auction_type": "electronic",
        },
        "selling_agent": {},
    }
    item = {
        "property_data": PropertyData.model_validate(prop or {}).model_dump(
            mode="json"
        ),
        **item_fields,
    }
    return compose(project, [item])


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("فيلا", "landscape"),
        ("أرض سكنية", "landscape"),
        ("مزرعة", "landscape"),
        ("عمارة", "portrait"),
        ("برج", "portrait"),
    ],
)
def test_layout_uses_property_type_before_uploaded_image(kind, expected):
    booklet = composition(
        {"property_type": kind}, image_assets=[{"src": "", "orientation": "portrait"}]
    )
    assert (
        next(p for p in booklet["pages"] if p["kind"] == "property")["layout"]
        == expected
    )


def test_explicit_layout_overrides_automatic_choice():
    booklet = composition({"property_type": "فيلا", "booklet_layout": "portrait"})
    assert (
        next(p for p in booklet["pages"] if p["kind"] == "property")["layout"]
        == "portrait"
    )


def test_short_boundaries_stay_on_property_long_boundaries_preserve_every_character():
    short = composition(
        {"boundaries": {"north_description": "شارع عرض 30 م", "north_length": "35 م"}}
    )
    assert not any(p["kind"] == "boundaries" for p in short["pages"])
    text = "حد طويل مع تفاصيل متعددة " * 70 + "BOUNDARY_END"
    long = composition({"boundaries": {"north_description": text}})
    assert next(p for p in long["pages"] if p["kind"] == "property")[
        "separate_boundaries"
    ]
    assert (
        "".join(
            r["text"]
            for p in long["pages"]
            if p["kind"] == "boundaries"
            for r in p["rows"]
            if r["side"] == "north"
        )
        == text
    )


def test_additional_information_is_not_repeated():
    text = "معلومة إضافية " * 60
    booklet = composition({"additional_information": text})
    pages = booklet["pages"]
    main = next(p for p in pages if p["kind"] == "property")
    continued = "".join(
        p["text"]
        for p in pages
        if p["kind"] == "information" and p["heading"] == "additional_information"
    )
    assert main["additional_information"] + continued == text.strip()
    assert not any(
        p["kind"] == "information"
        for p in composition({"additional_information": "SHORT"})["pages"]
    )


def test_optional_pages_are_independent_and_preserve_source():
    prop = {
        "include_information_page": False,
        "include_images_page": False,
        "include_rentals_page": False,
        "features": ["FEATURE"],
        "rental_contracts": [{"unit_number": "A"}],
    }
    original = deepcopy(prop)
    booklet = composition(
        prop, notes="NOTES", image_assets=[{"src": "", "orientation": "landscape"}] * 4
    )
    assert not any(
        p["kind"] in ("information", "images", "rentals") for p in booklet["pages"]
    )
    assert prop == original
    assert [p["kind"] for p in booklet["pages"]][-3:] == [
        "terms",
        "participation",
        "contact",
    ]


def test_blank_rentals_are_removed_but_zero_rent_is_preserved():
    prop = PropertyData(
        rental_contracts=[{}, {"unit_number": "  "}, {"annual_rent_value": 0}]
    )
    assert len(prop.rental_contracts) == 1
    assert prop.rental_contracts[0].annual_rent_value == 0


def test_page_settings_persist_and_preview_matches_export(admin):
    p = create_auction(admin)
    body = property_input()
    body["property_data"].update(
        booklet_layout="portrait",
        include_information_page=False,
        include_images_page=False,
        include_rentals_page=False,
        rental_contracts=[{}, {"unit_number": "REAL"}],
    )
    body["notes"] = "HIDDEN_NOTES"
    item_id = add(admin, p, body)
    saved = admin.get(f"/api/projects/{p}").json()["items"][0]["property_data"]
    assert (
        saved["include_rentals_page"] is False and len(saved["rental_contracts"]) == 1
    )
    output = generate(admin, p)
    assert not any(
        p["kind"] in ("rentals", "information") for p in output["page_manifest"]
    )
    preview = admin.post(
        f"/api/projects/{p}/booklet-preview",
        json={"stage": "items", "item": {"id": item_id, "property_data": saved}},
    )
    assert preview.status_code == 200 and preview.json()["fits"]


def test_long_field_cannot_overlap_the_next_property_row(admin):
    p = create_auction(admin)
    body = property_input()
    body["property_data"]["deed_number"] = "1234567890" * 10
    add(admin, p, body)
    response = admin.post(
        f"/api/projects/{p}/generate", json={"types": ["project_booklet"]}
    )
    assert response.status_code == 422
    assert "preflight" in response.text
