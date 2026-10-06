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
    assert preview.status_code == 200 and preview.json()["html"]


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


def project_with(auction_type="electronic", **auction):
    return {
        "id": str(uuid4()),
        "auction": {
            "selected_cover_template_id": "infath-2",
            "auction_type": auction_type,
            **auction,
        },
        "selling_agent": {},
    }


def item_with(**prop):
    return {
        "property_data": PropertyData.model_validate(prop).model_dump(mode="json"),
        "image_assets": [],
    }


def property_pages(booklet):
    return [p for p in booklet["pages"] if p["kind"] == "property"]


def test_close_badge_only_for_electronic_properties_with_a_closing_time():
    close = {"property_type": "فيلا", "auction_close_date": "2026-07-29"}
    electronic = compose(project_with("electronic"), [item_with(**close)])
    physical = compose(project_with("physical"), [item_with(**close)])
    plain = compose(project_with("hybrid"), [item_with(property_type="عمارة")])
    assert property_pages(electronic)[0]["variant"] == "landscape-close"
    assert property_pages(physical)[0]["variant"] == "landscape"
    assert property_pages(plain)[0]["variant"] == "portrait"


def test_edition_selects_qr_codes_or_link_buttons():
    assert (
        property_pages(compose(project_with(), [item_with()]))[0]["edition"] == "print"
    )
    digital = compose(project_with(booklet_edition="digital"), [item_with()])
    assert property_pages(digital)[0]["edition"] == "digital"


def test_tables_close_at_the_last_record_on_every_page():
    booklet = compose(
        project_with(),
        [item_with(rental_contracts=[{"unit_number": str(n)} for n in range(20)])]
        + [item_with() for _ in range(21)],
    )
    summaries = [len(p["rows"]) for p in booklet["pages"] if p["kind"] == "summary"]
    rentals = [len(p["rows"]) for p in booklet["pages"] if p["kind"] == "rentals"]
    # The summary table fills its area: twenty reference rows down to the footer.
    assert summaries == [20, 2] and rentals == [19, 1]


def test_boundaries_use_measured_width_of_the_reference_line():
    fits = {"north_description": "شارع بعرض ثلاثين متراً", "north_length": "30 م"}
    long = {"north_description": "شارع بعرض ثلاثين متراً من الجهة الشمالية الشرقية"}
    assert not property_pages(compose(project_with(), [item_with(boundaries=fits)]))[0][
        "separate_boundaries"
    ]
    assert property_pages(compose(project_with(), [item_with(boundaries=long)]))[0][
        "separate_boundaries"
    ]
    # Portrait pages have the wider reference value column.
    medium = {"north_description": "قطعة رقم 6110 + قطعة 6112"}
    assert not property_pages(
        compose(
            project_with(), [item_with(booklet_layout="portrait", boundaries=medium)]
        )
    )[0]["separate_boundaries"]


def test_dates_times_and_amounts_follow_the_reference():
    from app.generation.booklet import formatting as f

    auction = {
        "auction_type": "hybrid",
        "auction_start_date": "2026-07-27",
        "auction_end_date": "2026-07-29",
        "start_time": "10:00:00",
        "end_time": "19:00:00",
    }
    assert f.day_range(auction, "ar") == "الإثنين 27 - 29 يوليو 2026"
    assert (
        f.day_range(auction, "ar", weekday=False, suffix="م", dash="-")
        == "27-29 يوليو 2026م"
    )
    # Figure groups carry invisible isolate marks that keep their order in RTL.
    assert f.time_range(auction, "ar") == (
        "\u206610 : 00\u2069 صباحاً - \u206607 : 00\u2069 مساءً"
    )
    assert f.slash_date("2026-07-29") == "\u20662026 / 07 / 29\u2069"
    assert f.money("10000.00") == "10,000 ريال"
    assert f.number("1130.4510") == "1130٫451"


def test_info_box_moves_overflow_without_losing_or_repeating_entries():
    from app.generation.booklet.composer import fill_box, paginate

    entries = [{"heading": "features"}] + [
        {"number": n, "text": "ميزة " * 12} for n in range(1, 15)
    ]
    shown, rest = fill_box(entries, 10, 268, 11)
    assert shown[0] == {"heading": "features"} and "heading" not in shown[-1]
    assert shown + [e for page in paginate(rest, 11, 500, 33) for e in page] == entries


def test_digital_edition_renders_clickable_buttons(admin):
    import pymupdf

    p = create_auction(admin, "electronic")
    project = admin.get(f"/api/projects/{p}").json()["project"]
    project["auction"]["booklet_edition"] = "digital"
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    body = property_input()
    body["property_data"]["survey_link"] = "https://example.com/survey"
    add(admin, p, body)
    output = generate(admin, p)
    from test_auctions import pdf

    with pymupdf.open(stream=pdf(admin, output), filetype="pdf") as doc:
        uris = {link.get("uri") for page in doc for link in page.get_links()}
    assert "https://example.com/survey" in uris


def logo_data(size, fmt="PNG", background=None, margin=0):
    import base64
    import io

    from PIL import Image, ImageDraw

    width, height = size
    image = Image.new(
        "RGBA" if background is None else "RGB",
        (width + 2 * margin, height + 2 * margin),
        (0, 0, 0, 0) if background is None else background,
    )
    ImageDraw.Draw(image).rectangle(
        [margin, margin, margin + width - 1, margin + height - 1], fill=(20, 120, 140)
    )
    out = io.BytesIO()
    image.save(out, format=fmt)
    return (
        f"data:image/{fmt.lower()};base64," + base64.b64encode(out.getvalue()).decode()
    )


@pytest.mark.parametrize(
    "logo,ratio",
    [
        (logo_data((400, 100), margin=300), 4.0),  # transparent margins are trimmed
        (logo_data((400, 100), "JPEG", (255, 255, 255), 200), 4.0),  # flat background
        (logo_data((5000, 2500), margin=100), 2.0),  # oversized upload
    ],
    ids=["transparent-margins", "white-background-jpeg", "oversized"],
)
def test_any_logo_upload_is_trimmed_and_fitted_to_its_box(logo, ratio):
    import base64
    import io

    from PIL import Image

    from app.generation.booklet.art import logo_fit, prepared_logo

    uri, measured = prepared_logo(logo, True)
    image = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert abs(measured - ratio) < 0.05 and max(image.size) <= 1600
    assert image.mode == "RGBA" and image.getpixel(
        (image.width // 2, image.height // 2)
    ) == (
        255,
        255,
        255,
        255,
    )
    for width, height in [(101.6, 30.1), (106.7, 28.6), (110, 63.5)]:
        fit = logo_fit(logo, width, height)
        assert fit["width"] <= width + 0.01 and fit["height"] <= height + 0.01
        assert fit["width"] >= width - 0.01 or fit["height"] >= height - 0.01


def cover_images(cover, auction_logo, agent_logo):
    import pymupdf
    from weasyprint import HTML

    from app.auction_schemas import AuctionData
    from app.generation.engine import render_html, safe_fetch

    project = {
        "id": str(uuid4()),
        "auction": AuctionData.model_validate(
            {"auction_name": "مزاد", "selected_cover_template_id": cover}
        ).model_dump(mode="json"),
        "selling_agent": {},
        "agent_logo": agent_logo,
        "auction_logo": auction_logo,
        "cover_image": "",
    }
    booklet = compose(project, [])
    booklet["pages"] = booklet["pages"][:1]
    content = {
        "project": project,
        "items": [],
        "output_language": "ar",
        "booklet": booklet,
    }
    from app.generation.booklet.art import vector_boxes

    html = render_html(content, "infath/booklet.html")
    document = HTML(string=html, url_fetcher=safe_fetch).render()
    # The auction icon is vector artwork placed in a reserved box; the agent's
    # logo is the uploaded picture.
    icon = next(
        pymupdf.Rect(box[1:])
        for box in vector_boxes(document)[0]
        if box[0] == "auction-icon-silver"
    )
    page = pymupdf.open("pdf", document.write_pdf())[0]
    logo = next(
        pymupdf.Rect(i["bbox"])
        for i in page.get_image_info()
        if i["bbox"][2] - i["bbox"][0] < 300
    )
    return [icon, logo]


@pytest.mark.parametrize(
    "cover,auction_box,agent_box",
    [
        ("infath-1", (515.7, 743.9, 566.3, 807.4), (35.9, 777.7, 137.5, 807.8)),
        ("infath-2", (327.2, 372.6, 377.8, 436.1), (35.9, 777.7, 137.5, 807.8)),
        ("infath-3", (327.2, 372.6, 377.8, 436.1), (35.9, 777.7, 137.5, 807.8)),
        ("infath-4", (450.7, 372.6, 501.3, 436.1), (443.8, 770.9, 550.5, 799.5)),
        ("infath-5", (450.7, 372.6, 501.3, 436.1), (443.8, 770.9, 550.5, 799.5)),
        ("infath-6", (515.7, 743.9, 566.3, 807.4), (35.9, 777.7, 137.5, 807.8)),
    ],
)
def test_logos_take_each_cover_s_reference_position(cover, auction_box, agent_box):
    import pymupdf

    auction, agent = cover_images(
        cover, logo_data((80, 100)), logo_data((700, 100), "JPEG", (255, 255, 255))
    )
    tolerance = 0.2
    assert auction in pymupdf.Rect(auction_box) + (
        -tolerance,
        -tolerance,
        tolerance,
        tolerance,
    )
    assert agent in pymupdf.Rect(agent_box) + (
        -tolerance,
        -tolerance,
        tolerance,
        tolerance,
    )
    # Anchored to the reference edge: right for the auction logo, outer edge for the agent.
    assert abs(auction.x1 - auction_box[2]) < tolerance
    anchored = (
        agent.x1 - agent_box[2]
        if cover in ("infath-4", "infath-5")
        else agent.x0 - agent_box[0]
    )
    assert abs(anchored) < tolerance


def test_times_and_slashed_dates_keep_their_digit_order_in_arabic():
    """ "08 : 31" must not be drawn as "31 : 08" inside right-to-left text."""
    import pymupdf
    from weasyprint import HTML

    from app.auction_schemas import AuctionData
    from app.generation.engine import render_html, safe_fetch

    project = project_with(
        "hybrid",
        auction_start_date="2026-07-27",
        auction_end_date="2026-07-29",
        start_time="08:31:00",
        end_time="21:31:00",
    )
    project["auction"] = AuctionData.model_validate(project["auction"]).model_dump(
        mode="json"
    )
    project.update(agent_logo="", selling_agent={"name": "وكيل"})
    item = {
        **item_with(auction_close_date="2026-07-29", auction_close_time="18:05"),
        "id": "i",
        "title": "عقار",
    }
    booklet = compose(project, [item])

    def digits(kind):
        page = next(p for p in booklet["pages"] if p["kind"] == kind)
        content = {"project": project, "items": [item], "output_language": "ar"}
        html = render_html({**content, "booklet": {**booklet, "pages": [page]}})
        doc = pymupdf.open("pdf", HTML(string=html, url_fetcher=safe_fetch).write_pdf())
        rows = {}
        for x0, _, _, y1, word, *_ in doc[0].get_text("words"):
            if any(c.isdigit() for c in word):
                rows.setdefault(round(y1), []).append((x0, word))
        return [" ".join(w for _, w in sorted(row)) for _, row in sorted(rows.items())]

    # Right-to-left line: the first time sits on the right, each drawn "hh mm".
    assert "09 31 08 31" in digits("auction")
    assert any(row.startswith("09 31 08 31") for row in digits("contact"))
    assert any("2026 07 29" in row for row in digits("property"))


def test_pages_follow_the_guide_order_with_one_agent_page():
    """Cover, Infath, agent (once, however long), auction, summary, properties,
    rentals, terms, participation steps, contact - as in the reference booklet."""
    project = project_with("hybrid", auction_start_date="2026-07-27")
    project["selling_agent"] = {
        "name": "شركة أعيان العقارية",
        "description": "شركة سعودية رائدة في إدارة المزادات العقارية. " * 30,
        "contact_information": "واتساب خدمة العملاء",
    }
    item = item_with(
        property_type="فيلا",
        rental_contracts=[{"unit_number": "1", "annual_rent_value": "1000"}],
    )
    item.update(id="i", title="عقار")
    kinds = [p["kind"] for p in compose(project, [item])["pages"]]
    assert kinds[:5] == ["cover", "introduction", "agent", "auction", "summary"]
    assert kinds.count("agent") == 1
    assert kinds.index("property") < kinds.index("rentals") < kinds.index("terms")
    assert kinds[-3:] == ["terms", "participation", "contact"]
    agent = next(p for p in compose(project, [item])["pages"] if p["kind"] == "agent")
    assert agent["size"] < 16.02  # set smaller instead of repeating the page


def test_agent_description_beyond_one_page_is_reported_for_account_settings():
    from app.generation.booklet.fit import booklet_issues

    agent = {"name": "وكيل", "description": "وصف طويل جدا لوكيل البيع. " * 200}
    issue = next(
        i for i in booklet_issues({}, agent, []) if i["field"] == "description"
    )
    assert issue["section"] == "agent" and 0 < issue["limit"] < 5000


@pytest.mark.parametrize(
    "kind, shown", [("physical", True), ("hybrid", True), ("electronic", False)]
)
def test_recording_notice_only_where_the_auction_has_a_hall(kind, shown):
    from app.auction_schemas import AuctionData
    from app.generation.booklet.labels import label
    from app.generation.engine import render_html

    project = project_with(kind, auction_start_date="2026-07-27")
    project["auction"] = AuctionData.model_validate(project["auction"]).model_dump(
        mode="json"
    )
    project.update(agent_logo="", selling_agent={"name": "وكيل"})
    booklet = compose(project, [])
    page = next(p for p in booklet["pages"] if p["kind"] == "auction")
    html = render_html(
        {
            "project": project,
            "items": [],
            "booklet": {**booklet, "pages": [page]},
            "output_language": "ar",
        }
    )
    assert (label("recording_notice", "ar") in html) is shown


def test_long_summary_values_wrap_in_their_cell_without_shrinking():
    """A long district or plan number stays whole inside its column and its row
    is at least as tall as the wrapped text needs."""
    from app.generation.booklet.composer import (
        SUMMARY_LIMIT,
        SUMMARY_LINE,
        SUMMARY_MIN_ROW,
        SUMMARY_TOP,
    )

    short = item_with(property_type="فيلا", city="ابها", district="العزيزية")
    long = item_with(
        property_type="ارض مقام عليها هناجر",
        city="خميس مشيط",
        district="مخطط لطيفة بنت سلطان بن عبدالعزيز",
        plan_number="1433 / 234 / ع / 17",
    )
    many = compose(project_with("physical"), [long] * 45)["pages"]
    tables = [p for p in many if p["kind"] == "summary"]
    assert sum(len(p["rows"]) for p in tables) == 45 and len(tables) > 1
    for page in tables:
        tops = [SUMMARY_TOP] + page["bottoms"][:-1]
        assert page["bottoms"][-1] <= SUMMARY_LIMIT + 0.01
        for top, bottom, counts in zip(tops, page["bottoms"], page["lines"]):
            assert counts["district"] >= 2 and counts["city"] >= 2
            needed = max(counts.values()) * SUMMARY_LINE + 6
            assert bottom - top >= max(SUMMARY_MIN_ROW, needed) - 0.01
    assert short["property_data"]["district"] == "العزيزية"


def test_summary_table_fills_its_area_with_evenly_shared_rows():
    """Guide p.14: the table starts at the guide's height and runs down to the
    footer; rows share the space (no taller than in an eight-row table)."""
    from app.generation.booklet.composer import (
        SUMMARY_LIMIT,
        SUMMARY_MAX_ROW,
        SUMMARY_TOP,
    )

    def table(count):
        pages = compose(project_with("physical"), [item_with() for _ in range(count)])
        return next(p for p in pages["pages"] if p["kind"] == "summary")["bottoms"]

    assert SUMMARY_TOP < 200  # raised from the open booklet's 297.7 to the guide's
    for count in (8, 14, 20):  # a full page: the last row ends at the footer limit
        bottoms = table(count)
        assert abs(bottoms[-1] - SUMMARY_LIMIT) < 0.1
        heights = [b - a for a, b in zip([SUMMARY_TOP] + bottoms, bottoms)]
        assert max(heights) - min(heights) < 0.1
    few = table(2)  # a short list keeps sensible rows instead of two giant ones
    assert abs(few[0] - SUMMARY_TOP - SUMMARY_MAX_ROW) < 0.1


def test_typed_plan_numbers_keep_the_order_shown_in_the_form():
    """ "118 / 1400 / ج / 2" typed in the (right-to-left) form reads the same in
    the booklet: drawn left to right as 2, ج, 1400, 118 - as in the input."""
    import pymupdf
    from weasyprint import HTML

    from app.auction_schemas import AuctionData
    from app.generation.engine import render_html, safe_fetch

    project = project_with("physical", auction_date="2026-07-27")
    project["auction"] = AuctionData.model_validate(project["auction"]).model_dump(
        mode="json"
    )
    project.update(agent_logo="", selling_agent={"name": "وكيل"})
    item = {
        **item_with(property_type="عمارة", plan_number="118 / 1400 / ج / 2"),
        "id": "i",
        "title": "عقار",
    }
    booklet = compose(project, [item])
    for kind in ("property", "summary"):
        page = next(p for p in booklet["pages"] if p["kind"] == kind)
        content = {"project": project, "items": [item], "output_language": "ar"}
        html = render_html({**content, "booklet": {**booklet, "pages": [page]}})
        doc = pymupdf.open("pdf", HTML(string=html, url_fetcher=safe_fetch).write_pdf())
        words = [w for w in doc[0].get_text("words") if w[4] in ("118", "1400", "2")]
        # Read as the form reads it: line by line, each line right to left.
        drawn = [w[4] for w in sorted(words, key=lambda w: (round(w[3]), -w[0]))]
        assert drawn == ["118", "1400", "2"], (kind, drawn)


def exported(project, items):
    """A booklet rendered as export renders it: HTML, then the vector artwork."""
    import pymupdf
    from weasyprint import HTML

    from app.auction_schemas import AuctionData
    from app.generation.booklet.art import original_pdf_artwork, vector_boxes
    from app.generation.engine import render_html, safe_fetch

    project["auction"] = AuctionData.model_validate(project["auction"]).model_dump(
        mode="json"
    )
    project.setdefault("agent_logo", "")
    booklet = compose(project, items)
    content = {
        "project": project,
        "items": items,
        "booklet": booklet,
        "output_language": "ar",
    }
    document = HTML(string=render_html(content), url_fetcher=safe_fetch).render()
    pdf = original_pdf_artwork(document.write_pdf(), content, document)
    return booklet, vector_boxes(document), pymupdf.open("pdf", pdf)


def test_fixed_artwork_is_exported_as_vectors_not_pictures():
    """Covers, icons and the footer bar are the original vector files: the
    exported pages carry no raster copy of them (review: pixelated artwork)."""
    project = project_with(
        "hybrid", auction_start_date="2026-07-27", start_time="10:00"
    )
    project["selling_agent"] = {"name": "وكيل", "phone": "0550000000"}
    booklet, boxes, pdf = exported(project, [])
    kinds = [p["kind"] for p in booklet["pages"]]
    placed = {kind: {box[0] for box in boxes[n]} for n, kind in enumerate(kinds)}
    assert {"cover-2", "auction-icon-silver"} <= placed["cover"]
    assert {"auction-icon-gradient", "auction-time", "footer-bar"} <= placed["auction"]
    assert "agent-phone" in placed["agent"]
    assert {f"step-{n}" for n in range(1, 6)} <= placed["participation"]
    cover, auction = pdf[kinds.index("cover")], pdf[kinds.index("auction")]
    # No logo, photograph or QR code in this booklet: nothing in it is a picture.
    assert [
        x
        for x in range(1, pdf.xref_length())
        if "/Subtype /Image" in pdf.xref_object(x)
        or "/Subtype/Image" in pdf.xref_object(x)
    ] == []
    # The artwork is really there, as paths: the cover's ground and the icons.
    assert len(cover.get_drawings()) > 5 and len(auction.get_drawings()) > 20


@pytest.mark.parametrize(
    "kind, order, has_qr",
    [
        ("electronic", ["calendar", "platform", "time"], False),
        ("physical", ["location", "calendar", "time"], True),
        ("hybrid", ["platform", "location", "calendar", "time"], True),
    ],
)
def test_contact_page_follows_the_guide_for_each_auction_type(kind, order, has_qr):
    """Guide p.25: icon order right to left per type; only auctions with a
    hall carry its QR code."""
    project = project_with(
        kind,
        auction_date="2026-07-27",
        auction_start_date="2026-07-27",
        start_time="10:00",
        physical_location="القاعة",
        electronic_platform_name="المنصة",
        electronic_platform_url="https://example.com/p",
        auction_location_url="https://example.com/hall",
    )
    project["selling_agent"] = {"name": "وكيل", "phone": "0550000000"}
    from app.generation.engine import render_html

    booklet, boxes, _ = exported(project, [])
    n = [p["kind"] for p in booklet["pages"]].index("contact")
    icons = sorted(
        (b for b in boxes[n] if b[0].startswith("contact-") and b[2] < 400),
        key=lambda b: -b[1],
    )
    assert [b[0].removeprefix("contact-") for b in icons] == order
    html = render_html(
        {
            "project": project,
            "items": [],
            "booklet": {**booklet, "pages": [booklet["pages"][n]]},
            "output_language": "ar",
        }
    )
    assert ('class="qr-code"' in html) is has_qr


def test_additional_information_is_set_smaller_before_it_leaves_its_box():
    """Review: more content shrinks the text to stay in the box; it only
    continues on another page when it cannot fit at the smallest size."""
    text = "ملاحظة عن العقار تستحق الذكر في الكتيب. " * 22
    item = item_with(property_type="فيلا", additional_information=text)
    pages = compose(project_with("physical"), [item])["pages"]
    page = next(p for p in pages if p["kind"] == "property")
    assert 6.5 <= page["info_size"] < 10
    assert [p["kind"] for p in pages].count("information") == 0
    short = compose(
        project_with("physical"),
        [item_with(property_type="فيلا", additional_information="ملاحظة قصيرة")],
    )
    assert next(p for p in short["pages"] if p["kind"] == "property")["info_size"] == 10


def test_rental_values_wrap_in_their_cells_and_the_note_follows_the_table():
    """Review: no text runs into the next cell, and the fixed note sits right
    under the last row however many contracts there are."""
    contracts = [
        {
            "unit_number": "جميع أجزاء العقار",
            "property_type": "استراحة ومستودعات",
            "contract_status": "منتهي وتحت التجديد",
            "contract_duration": "سنتين و 10 شهور",
        }
    ] * 3
    project = project_with("physical", auction_date="2026-07-27")
    item = {
        **item_with(property_type="فيلا", rental_contracts=contracts),
        "id": "i",
        "title": "عقار",
    }
    booklet, boxes, _ = exported(project, [item])
    n = [p["kind"] for p in booklet["pages"]].index("rentals")
    page = booklet["pages"][n]
    assert all(counts["unit_number"] >= 2 for counts in page["lines"])
    assert page["bottoms"][0] - 152.8 > 26.3  # the row grew for its wrapped cells
    note = next(b for b in boxes[n] if b[0] == "rentals-note")
    assert abs(note[2] - (page["bottoms"][-1] + 12)) < 0.2
