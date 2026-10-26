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


def test_a_long_deed_wraps_in_its_column_instead_of_overlapping(admin):
    """A deed number too long for one line takes further lines in its column
    (the facts beneath move down): the booklet is made, nothing overlaps."""
    p = create_auction(admin)
    body = property_input()
    body["property_data"]["deed_number"] = "1234567890" * 4
    add(admin, p, body)
    response = admin.post(
        f"/api/projects/{p}/generate", json={"types": ["project_booklet"]}
    )
    assert response.status_code == 200, response.text


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


def test_boundaries_use_the_room_they_have_before_leaving_the_page():
    """Notes p.15: the boundaries take as many lines as they need beside their
    labels (the rows below move down), are set gradually smaller only when the
    column runs out, and go to a page of their own only when even that fails."""

    def page(boundaries, **prop):
        item = item_with(boundaries=boundaries, **prop)
        return property_pages(compose(project_with(), [item]))[0]

    import itertools

    def north(plan):
        return plan["boundaries"]["rows"][0]

    # A short boundary is one line at the reference size.
    fits = page({"north_description": "شارع بعرض 30م", "north_length": "30 م"})
    assert not fits["separate_boundaries"]
    assert north(fits)["size"] == 9.6
    assert [x["text"] for x in north(fits)["lines"]] == ["شارع بعرض 30م"]
    assert [x["text"] for x in fits["boundaries"]["rows"][1]["lines"]] == ["-"]
    # Longer: further lines at the same size, the text whole.
    text = "شارع بعرض ثلاثين متراً من الجهة الشمالية الشرقية"
    long = page({"north_description": text * 2})
    assert not long["separate_boundaries"]
    assert north(long)["size"] == 9.6 and len(north(long)["lines"]) > 2
    assert " ".join(x["text"] for x in north(long)["lines"]).split() == (
        (text * 2).split()
    )
    rows = long["boundaries"]["rows"]
    assert all(
        a["lines"][-1]["base"] < b["lines"][0]["base"]
        for a, b in itertools.pairwise(rows)
    )
    # Longer again: set a little smaller rather than leaving the page.
    smaller = page({"north_description": text * 3})
    assert not smaller["separate_boundaries"]
    assert 7.0 <= north(smaller)["size"] < 9.6
    # Too long even so: the boundaries continue on their own page, and the
    # property's page leaves them out entirely.
    far = page({"north_description": text * 6})
    assert far["separate_boundaries"] and far["boundaries"] is None
    # Portrait pages have the wider column: more fits at the reference size.
    wide = page({"north_description": text * 4}, booklet_layout="portrait")
    assert north(wide)["size"] == 9.6
    # A long length is set smaller on its line; an impossible one leaves the page.
    length = page({"north_length": "1,032.55 م"})
    assert 7.0 <= length["boundaries"]["lengths"][0]["size"] <= 10.06
    assert page({"north_length": "م" * 80})["separate_boundaries"]
    # The author may put them on their own page though they fit.
    chosen = page({"north_description": "شارع"}, include_boundaries_page=True)
    assert chosen["separate_boundaries"] and not chosen["auto"]["boundaries"]


def test_boundaries_are_printed_inside_their_column_on_both_layouts():
    """However they are set the boundaries stay between the page edge and
    their labels."""
    boundaries = {
        "north_description": "يحدها من الشمال ارض فضاء",
        "south_description": "شارع الملك سعود بعرض 60م ثم ممر مشاة " * 2,
        "east_description": "قطعة رقم 161 وقطعة رقم 162",
        "west_description": "شارع بعرض 30م",
        "north_length": "107,032م",
        "south_length": "108,468م",
    }
    from app.generation.booklet.boundaries import GEOMETRY

    for layout in ("landscape", "portrait"):
        right, width = GEOMETRY[layout]["value"], GEOMETRY[layout]["width"]
        item = {
            **item_with(
                property_type="عمارة", boundaries=boundaries, booklet_layout=layout
            ),
            "title": "عقار",
        }
        booklet, _, pdf = exported(project_with("physical"), [item])
        n = [p["kind"] for p in booklet["pages"]].index("property")
        plan = booklet["pages"][n]
        assert len(plan["boundaries"]["rows"][1]["lines"]) >= 2
        text = pdf[n].get_text()
        for word in ("فضاء", "مشاة", "162", "107,032"):
            assert word in text, (layout, word)
        # The south boundary's lines: all inside the value column.
        found = [
            (x0, x1)
            for x0, _, x1, _, word, *_ in pdf[n].get_text("words")
            if word in ("مشاة", "سعود", "الملك")
        ]
        assert found, layout
        for x0, x1 in found:
            assert right - width - 1 <= x0 and x1 <= right + 1, (layout, x0, x1)


def test_announcement_grows_then_shrinks_to_keep_the_court_decision_whole():
    """Guide p.13 sets three lines. A longer court decision keeps the same
    setting and pushes the schedule down; a very long text is set smaller in
    that space, and only what still cannot fit continues on a later page."""
    from app.generation.booklet.composer import (
        ANNOUNCEMENT_LINE,
        ANNOUNCEMENT_LINES,
        announcement_fit,
    )

    legal = "تعلن الشركة عن البيع بالمزاد العلني\nوبإشراف مركز الإسناد والتصفية «إنفاذ»"

    def auction(court):
        project = project_with(
            "physical", legal_announcement_text=legal, court_decision_text=court
        )
        pages = compose(project, [])["pages"]
        return next(p for p in pages if p["kind"] == "auction"), pages

    short, _ = auction("وبقرار من محكمة التنفيذ")
    assert short["announcement_size"] == 19 and short["shift"] == 0
    assert len(short["announcement_lines"]) == 3
    court = "وبقرار من محكمة التنفيذ ومحكمة الأحوال الشخصية بالرياض رقم 4471234567"
    longer, pages = auction(court)
    assert longer["announcement_size"] == 19
    assert len(longer["announcement_lines"]) in (4, 5)
    assert longer["shift"] == (len(longer["announcement_lines"]) - 3) * 29
    assert "".join(longer["announcement_lines"]).replace(" ", "") == (
        legal + court
    ).replace("\n", "").replace(" ", "")
    assert not [p for p in pages if p["kind"] == "information"]
    # The longest texts the forms accept (220 and 120 characters) stay whole.
    size, height, lines, rest = announcement_fit(
        ("إعلان نظامي طويل " * 20)[:220] + "\n" + ("وبقرار من المحكمة " * 10)[:120]
    )
    assert size < 19 and not rest
    assert len(lines) * height <= ANNOUNCEMENT_LINES * ANNOUNCEMENT_LINE + 0.01
    # Beyond that the remainder continues on an information page, as before.
    _, pages = auction("وبقرار من محكمة التنفيذ " * 60)
    assert [p for p in pages if p["kind"] == "information"]


def test_schedule_moves_down_with_a_longer_announcement():
    court = "وبقرار من محكمة التنفيذ ومحكمة الأحوال الشخصية بالرياض رقم 4471234567"

    def top(court_text):
        project = project_with(
            "physical",
            auction_name="مزاد",
            auction_date="2026-07-27",
            start_time="10:00",
            physical_location="LOCATION_MARK",
            legal_announcement_text="تعلن الشركة عن البيع\nوبإشراف مركز الإسناد",
            court_decision_text=court_text,
        )
        booklet, _, pdf = exported(project, [])
        n = [p["kind"] for p in booklet["pages"]].index("auction")
        word = next(w for w in pdf[n].get_text("words") if w[4] == "LOCATION_MARK")
        return booklet["pages"][n]["shift"], word[1]

    (plain_shift, plain), (long_shift, moved) = top("وبقرار من المحكمة"), top(court)
    assert plain_shift == 0 and long_shift >= 29
    assert abs((moved - plain) - long_shift) < 0.5


def test_a_property_prints_up_to_eight_deeds_under_one_label():
    """The first deed and up to seven more: one "deed number" label, the
    numbers two to a line beside it (the facts beneath move down), and all in
    the summary's deed cell."""
    import pydantic

    numbers = [f"{n}4760347179{n}" for n in range(1, 9)]
    with pytest.raises(pydantic.ValidationError):
        PropertyData.model_validate({"extra_deed_numbers": numbers})  # eight more
    kept = PropertyData.model_validate({"extra_deed_numbers": ["", " 12 ", ""]})
    assert kept.extra_deed_numbers == ["12"]
    for layout in ("landscape", "portrait"):

        def base(count, key):
            item = {
                **item_with(
                    property_type="عمارة",
                    deed_number=numbers[0],
                    extra_deed_numbers=numbers[1:count],
                    plan_number="PLAN_MARK",
                    execution_request_number="EXEC_MARK",
                    booklet_layout=layout,
                ),
                "title": "عقار",
            }
            booklet, _, pdf = exported(project_with("physical"), [item])
            kinds = [p["kind"] for p in booklet["pages"]]
            page = pdf[kinds.index("property")]
            text = page.get_text()
            assert all(n in text for n in numbers[:count]), (layout, count)
            assert not any(n in text for n in numbers[count:])
            # One label for them all: the deeds are not named one by one.
            from app.generation.booklet.labels import label

            for n in range(2, 9):
                assert label(f"deed_number_{n}", "ar").split()[-1] not in text
            summary = booklet["pages"][kinds.index("summary")]
            assert summary["lines"][0]["deed_number"] == numbers[:count]
            facts = booklet["pages"][kinds.index("property")]["facts"]
            row = next(r for c in facts for r in c["rows"] if r["key"] == "deed_number")
            return next(w[1] for w in page.get_text("words") if w[4] == key), row

        plan_1, row_1 = base(1, "PLAN_MARK")
        plan_8, row_8 = base(8, "PLAN_MARK")
        assert len(row_1["lines"]) == 1
        # The facts beneath the deeds move down, and stay inside the column.
        assert plan_8 > plan_1
        assert len(row_8["lines"]) in (4, 8)  # two to a line where two fit


def test_deeds_with_their_own_boundaries_each_have_a_box():
    """Several deeds whose boundaries differ: the property page leaves the
    boundaries out and each deed has its framed box, its number on the tab;
    a deed too long for what is left of the page starts on the next one, and
    one longer than a page goes on in a box of its own there."""
    numbers = ["320111010760", "947603471790", "310115041563"]
    long = "ملك جار ابتداء من الزاوية الجنوبية باتجاه الشرق بطول 173 متر " * 40
    item = {
        **item_with(
            property_type="عمارة",
            deed_number=numbers[0],
            extra_deed_numbers=numbers[1:],
            deeds_differ=True,
            boundaries={
                "north_description": "شارع عرض 25 م",
                "north_length": "19.70 م",
            },
            deed_boundaries=[
                {"north_description": "أرض جار", "north_length": "625 م"},
                {"north_description": long[:3000], "south_description": long[:3000]},
            ],
            booklet_layout="portrait",
        ),
        "title": "عقار",
    }
    booklet, _, pdf = exported(project_with("physical"), [item])
    kinds = [p["kind"] for p in booklet["pages"]]
    assert booklet["pages"][kinds.index("property")]["boundaries"] is None
    pages = [p for p in booklet["pages"] if p["kind"] == "boundaries"]
    titles = [b["title"] for p in pages for b in p["boxes"]]
    assert [t.split()[-1] for t in titles][:2] == numbers[:2]
    assert titles.count(titles[-1]) >= 2  # the long deed goes on
    for page in pages:
        for box in page["boxes"]:
            assert 36 <= box["tab"] < box["top"] < box["bottom"] <= 747.5
            for row in box["rows"]:
                assert all(box["top"] < x["base"] < box["bottom"] for x in row["lines"])
    first = pdf[kinds.index("boundaries")].get_text()
    assert numbers[0] in first and "625" in first and "19.70" in first
    # Not differing (or a single deed): the first deed's boundaries, as before.
    item["property_data"]["deeds_differ"] = False
    booklet = compose(project_with("physical"), [item])
    assert not any(p["kind"] == "boundaries" for p in booklet["pages"])


def test_an_empty_deed_takes_its_boundaries_with_it():
    prop = PropertyData.model_validate(
        {
            "extra_deed_numbers": ["", "12"],
            "deed_boundaries": [{"north_description": "a"}, {"north_description": "b"}],
        }
    )
    assert prop.extra_deed_numbers == ["12"]
    assert [b.north_description for b in prop.deed_boundaries] == ["b"]


def test_long_plan_and_plot_numbers_take_a_second_line():
    """A plan or plot number too long for its line goes on, smaller if need
    be, on further lines in its column; the facts beneath move down and the
    column stays above what follows it."""
    from app.generation.booklet.facts import COLUMNS, property_facts

    prop = PropertyData.model_validate(
        {
            "plot_number": "1609 - 1608 - 1610 - 1607 - 1605 - 1606",
            "plan_number": "1433/234/ع/17/8899001122/4455",
            "deed_number": "320111010769",
            "extra_deed_numbers": ["320111010768", "320111010770", "320111010767"],
            "execution_request_number": "403094700065084400",
        }
    ).model_dump(mode="json")
    for layout in ("portrait", "landscape"):
        columns = property_facts(prop, layout)
        rows = {r["key"]: r for c in columns for r in c["rows"]}
        printed = " ".join(line["text"] for line in rows["plot_number"]["lines"])
        # Every number is printed (a line break replaces a separator).
        assert all(n in printed for n in prop["plot_number"].split(" - "))
        assert len(rows["plot_number"]["lines"]) >= 2
        assert not any(
            line["text"].endswith("-") or line["text"].startswith("-")
            for line in rows["plot_number"]["lines"]
        )
        for column, spec in zip(columns, COLUMNS[layout]):
            bottom = column["rows"][-1]["lines"][-1]["base"]
            assert bottom <= spec["limit"] + 0.01, (layout, bottom)
            bases = [line["base"] for r in column["rows"] for line in r["lines"]]
            assert bases == sorted(bases)  # nothing drawn over another line


def test_a_further_deed_too_long_for_its_box_is_reported_with_the_property():
    from app.generation.booklet.fit import booklet_issues

    item = {
        **item_with(deed_number="1", extra_deed_numbers=["2", "9" * 60]),
        "title": "عقار",
    }
    issues = booklet_issues({}, {}, [item])
    assert [(i["field"], i["item"]) for i in issues] == [("deed_number", "عقار")]


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
    assert f.number("1130.4510") == "1130.451"
    # Areas, like amounts: thousands separated, decimals after a point.
    assert f.number("92566.88", "ar", True) == "92,566.88"


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
            {"auction_name": "مزاد درة البحر", "selected_cover_template_id": cover}
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
    # The agent's logo is set one and a half times its reference box
    # (AGENT_LOGO_SCALE), from the box's outer edge and its middle.
    from app.generation.booklet.art import AGENT_LOGO_SCALE as S

    x0, y0, x1, y1 = agent_box
    middle, w, h = (y0 + y1) / 2, (x1 - x0) * S, (y1 - y0) * S
    outer_right = cover in ("infath-4", "infath-5")
    agent_box = (
        x1 - w if outer_right else x0,
        middle - h / 2,
        x1 if outer_right else x0 + w,
        middle + h / 2,
    )
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
        for top, bottom, texts in zip(tops, page["bottoms"], page["lines"]):
            # The long district wraps; the columns are fitted to the values,
            # so a short city keeps its one line.
            assert len(texts["district"]) >= 2 and len(texts["city"]) == 1
            # Nothing is dropped: the lines are the value itself.
            assert " ".join(texts["district"]) == long["property_data"]["district"]
            needed = max(len(text) for text in texts.values()) * SUMMARY_LINE + 6
            assert bottom - top >= max(SUMMARY_MIN_ROW, needed) - 0.01
    assert short["property_data"]["district"] == "العزيزية"


def test_the_property_type_never_moves_another_column():
    """Review: a long property type widened its cell and pushed the others. The
    type's column keeps the guide's width, as the deed number's keeps its own:
    a long type wraps inside its cell and its row grows, and every other
    column edge stays where it was."""
    from app.generation.booklet.composer import (
        SUMMARY_COLS,
        SUMMARY_LINE,
        SUMMARY_MIN_ROW,
        SUMMARY_TOP,
    )

    def summary(kind):
        items = [item_with(property_type=kind), item_with(property_type="فيلا")]
        booklet = compose(project_with("physical"), items)
        return next(p for p in booklet["pages"] if p["kind"] == "summary")

    short, word, long = (
        summary(kind)
        for kind in ["ع", "فيلا", "عمارة استثمارية سكنية تجارية مع محلات ومستودعات"]
    )
    assert short["cols"] == word["cols"] == long["cols"]
    assert long["cols"][0] - long["cols"][1] == SUMMARY_COLS[0] - SUMMARY_COLS[1]
    assert short["lines"][0]["property_type"] == ["ع"]
    wrapped = long["lines"][0]["property_type"]
    assert len(wrapped) >= 3
    assert " ".join(wrapped) == "عمارة استثمارية سكنية تجارية مع محلات ومستودعات"
    assert (
        long["bottoms"][0] - SUMMARY_TOP
        >= max(SUMMARY_MIN_ROW, len(wrapped) * SUMMARY_LINE + 6) - 0.01
    )


@pytest.mark.parametrize(
    "count, pages", [(20, [20]), (21, [20, 1]), (45, [20, 20, 5]), (3, [3])]
)
def test_summary_page_holds_at_most_twenty_properties(count, pages):
    """Twenty properties to a summary page; the next ones open a new page and
    keep their numbers."""
    items = [item_with(property_type="فيلا", city="الرياض") for _ in range(count)]
    booklet = compose(project_with("physical"), items)
    tables = [p for p in booklet["pages"] if p["kind"] == "summary"]
    assert [len(p["rows"]) for p in tables] == pages
    numbers = [row["number"] for p in tables for row in p["rows"]]
    assert numbers == list(range(1, count + 1))


def test_a_value_wider_than_its_cell_is_split_into_lines_that_fit():
    """A long deed number cannot wrap at a space: it is split evenly, whole."""
    from app.generation.booklet.composer import (
        SUMMARY_COLS,
        SUMMARY_FIELDS,
        cell_text,
        cell_width,
    )

    column = SUMMARY_FIELDS.index("deed_number")
    width = SUMMARY_COLS[column] - SUMMARY_COLS[column + 1] - 4
    assert cell_text("310115041563", width) == ["310115041563"]
    assert cell_text("9476034717900000", width) == ["94760347", "17900000"]
    for value in ["9" * 40, "مخطط لطيفة بنت سلطان 1433/234/ع/17", "", "A" * 25 + " B"]:
        lines = cell_text(value, width)
        assert all(cell_width(line) <= width for line in lines), lines
        assert "".join(lines).replace(" ", "") == (value or "-").replace(" ", "")


def cell_characters(page, top, bottom, right):
    """Characters printed in a table's body: (x0, y0, x1, y1, character)."""
    return [
        (*char["bbox"], char["c"])
        for block in page.get_text("rawdict")["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
        for char in span["chars"]
        if char["c"].strip()
        and top < (char["bbox"][1] + char["bbox"][3]) / 2 < bottom
        and char["bbox"][0] < right
    ]


def test_every_summary_value_is_printed_inside_its_own_cell():
    """Review: a long deed number ran over the next column. In the exported
    page every value, however long, lies between its column's rules and inside
    its row."""
    from app.generation.booklet.composer import (
        SUMMARY_FIELDS,
        SUMMARY_TOP,
        summary_value,
    )

    long = item_with(
        property_type="ارض مقام عليها هناجر ومستودعات",
        city="خميس مشيط الجديدة",
        district="مخطط لطيفة بنت سلطان بن عبدالعزيز",
        area="123456789.75",
        plan_number="1433/234/ع/17/8899001122",
        plot_number="12345678901234",
        deed_number="9476034717900000",
        participation_amount="1250000000",
    )
    plain = item_with(property_type="عمارة", city="الرياض", deed_number="310115041563")
    items = [long, plain, long]
    booklet, _, pdf = exported(project_with("physical"), items)
    n = [p["kind"] for p in booklet["pages"]].index("summary")
    plan = booklet["pages"][n]
    # The columns are fitted to the values: the page's own edges.
    cols = plan["cols"]
    characters = cell_characters(pdf[n], SUMMARY_TOP, plan["bottoms"][-1], cols[0])
    rows = list(zip([SUMMARY_TOP] + plan["bottoms"][:-1], plan["bottoms"]))
    cells = {}
    for x0, y0, x1, y1, character in characters:
        # No ink on or beside a column rule: each character is in one column.
        column = next(
            i
            for i in range(len(SUMMARY_FIELDS))
            if cols[i + 1] + 1 <= x0 and x1 <= cols[i] - 1
        )
        row = next(i for i, (a, b) in enumerate(rows) if a <= y0 + 1 and y1 - 1 <= b)
        cells.setdefault((row, column), []).append(character)
    # Each cell holds its own value, whole: compared by its figures.
    for row, item in enumerate(items):
        for column, key in enumerate(SUMMARY_FIELDS):
            expected = sorted(c for c in summary_value(item, key) if c.isdigit())
            found = sorted(c for c in cells.get((row, column), []) if c.isdigit())
            assert found == expected, (row, key)
        assert len(cells[(row, 0)]) > 3  # the property type is there too


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
    # (The cover shows the auction's logo once its name is entered.)
    project = project_with(
        "hybrid",
        auction_name="درة البحر",
        auction_start_date="2026-07-27",
        start_time="10:00",
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


def photograph(colour=(200, 40, 30), size=(1200, 800)):
    """An uploaded picture, as the snapshot hands it to the templates."""
    import base64
    from io import BytesIO

    from PIL import Image

    data = BytesIO()
    Image.new("RGB", size, colour).save(data, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(data.getvalue()).decode()


def rendered(page):
    import pymupdf
    from PIL import Image

    pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1))
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


@pytest.mark.parametrize("cover", [1, 6])
def test_photographic_covers_take_the_authors_photograph(cover):
    """Covers 1 and 6 show the author's photograph in place of their own;
    everything else on the cover is the original artwork, where it was."""
    from PIL import ImageChops

    project = project_with(
        "physical", selected_cover_template_id=f"infath-{cover}", auction_name="مزاد"
    )
    plain = exported(dict(project), [])[2][0]
    own = exported({**project, "cover_image": photograph()}, [])[2][0]
    # One picture on the cover in both: the photograph, now the author's (red).
    assert len(own.get_images()) == len(plain.get_images()) == 1
    assert own.get_images()[0][2:4] != plain.get_images()[0][2:4]
    before, after = rendered(plain), rendered(own)
    red, green, blue = after.getpixel((300, 300))
    assert red > green + 60 and red > blue + 60, (red, green, blue)
    assert before.getpixel((300, 300)) != (red, green, blue)
    # The cover's own shapes are untouched: same paths, and the area outside
    # the photograph (the navy ground of cover 6) is the same picture.
    assert len(own.get_drawings()) == len(plain.get_drawings())
    if cover == 6:
        ground = (0, 600, 595, 842)
        assert not ImageChops.difference(
            before.crop(ground), after.crop(ground)
        ).getbbox()

    # The Infath logo is still drawn over the photograph (white, top right).
    def white(image):
        return sum(min(p) > 245 for p in image.crop((495, 20, 580, 85)).getdata())

    assert white(before) > 100 and abs(white(after) - white(before)) < 30


def test_other_covers_and_unreadable_pictures_keep_the_cover_as_designed():
    from PIL import ImageChops

    # A cover without a photograph ignores an uploaded one.
    plain = project_with("physical", auction_name="مزاد")
    pdf = exported({**plain, "cover_image": photograph()}, [])[2]
    assert pdf[0].get_images() == []
    # A picture that cannot be read leaves the photographic cover as it is.
    photo = project_with(
        "physical", selected_cover_template_id="infath-6", auction_name="مزاد"
    )
    before = rendered(exported(dict(photo), [])[2][0])
    broken = {**photo, "cover_image": "data:image/jpeg;base64,AAAA"}
    after = rendered(exported(broken, [])[2][0])
    assert not ImageChops.difference(before, after).getbbox()


def test_cover_photograph_fills_its_window_without_distortion():
    """A picture of any shape is centred and trimmed to the window, never
    stretched; small pictures are not enlarged."""
    import base64
    from io import BytesIO

    from app.generation.booklet.art import COVER_PHOTO, cover_photo
    from PIL import Image

    for size in [(4000, 1000), (600, 2400), (5000, 5000)]:
        for window in COVER_PHOTO.values():
            cut = Image.open(BytesIO(cover_photo(photograph(size=size), window)))
            ratio = (window[2] - window[0]) / (window[3] - window[1])
            assert abs(cut.width / cut.height - ratio) < 0.01
            assert cut.width <= min(1800, size[0])
    # Transparent pictures stand on white.
    data = BytesIO()
    Image.new("RGBA", (800, 1200), (0, 0, 0, 0)).save(data, "PNG")
    src = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
    cut = Image.open(BytesIO(cover_photo(src, COVER_PHOTO[1])))
    assert min(cut.getpixel((10, 10))) > 240


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
    assert all(len(texts["unit_number"]) >= 2 for texts in page["lines"])
    assert page["bottoms"][0] - 152.8 > 26.3  # the row grew for its wrapped cells
    note = next(b for b in boxes[n] if b[0] == "rentals-note")
    assert abs(note[2] - (page["bottoms"][-1] + 12)) < 0.2


def photos(count):
    return [{"src": f"photo-{n}", "orientation": "landscape"} for n in range(count)]


def kinds_of(booklet):
    return [p["kind"] for p in booklet["pages"] if "item" in p]


def test_features_and_two_more_photos_get_the_guide_features_page():
    """Guide p.17: the page after a property's first page holds its main
    photograph, two additional ones and the features as numbered points; the
    features are no longer inside the first page's box."""
    features = ["قريب من الخدمات", "واجهة على شارع رئيسي", "موقع مميز"]
    item = {**item_with(features=features), "image_assets": photos(5)}
    booklet = compose(project_with(), [item])
    assert kinds_of(booklet)[:3] == ["property", "features", "images"]
    page = next(p for p in booklet["pages"] if p["kind"] == "features")
    assert [i["src"] for i in page["images"]] == ["photo-0", "photo-1", "photo-2"]
    assert [e["text"] for e in page["entries"]] == features
    assert [e["number"] for e in page["entries"]] == [1, 2, 3]
    first = property_pages(booklet)[0]
    assert not any(e.get("heading") == "features" for e in first["info"])
    assert not any(e.get("text") in features for e in first["info"])
    # The two photographs left follow on a photographs page, none repeated.
    rest = [p for p in booklet["pages"] if p["kind"] == "images"]
    assert [[i["src"] for i in p["images"]] for p in rest] == [["photo-3", "photo-4"]]


def test_features_always_have_their_own_page_never_the_info_box():
    """Notes p.12: the additional information stays on the property's page,
    the features go on their optional page, whatever the photographs."""
    features = ["قريب من الخدمات"]
    one_photo = compose(
        project_with(), [{**item_with(features=features), "image_assets": photos(2)}]
    )
    assert "features" in kinds_of(one_photo)
    first = property_pages(one_photo)[0]
    assert not any(e.get("text") == features[0] for e in first["info"])
    page = next(p for p in one_photo["pages"] if p["kind"] == "features")
    assert [i["src"] for i in page["images"]] == ["photo-0", "photo-1"]
    assert "images" not in kinds_of(one_photo)  # its one photo is used there
    no_features = compose(project_with(), [{**item_with(), "image_assets": photos(4)}])
    assert "features" not in kinds_of(no_features)
    assert [p["kind"] for p in no_features["pages"]].count("images") == 1
    # The photographs page switched off: the features keep theirs.
    hidden = compose(
        project_with(),
        [
            {
                **item_with(features=features, include_images_page=False),
                "image_assets": photos(4),
            }
        ],
    )
    assert "features" in kinds_of(hidden) and "images" not in kinds_of(hidden)
    # The features page switched off: the features are not printed.
    off = compose(
        project_with(),
        [
            {
                **item_with(features=features, include_features_page=False),
                "image_assets": photos(4),
            }
        ],
    )
    assert "features" not in kinds_of(off)
    assert not any(
        e.get("text") == features[0] for p in property_pages(off) for e in p["info"]
    )


def test_the_features_page_shows_the_features_own_photographs():
    features = ["قريب من الخدمات"]
    assets = photos(3) + [
        {"src": f"feature-{n}", "orientation": "landscape", "category": "features"}
        for n in range(3)
    ]
    booklet = compose(
        project_with(), [{**item_with(features=features), "image_assets": assets}]
    )
    page = next(p for p in booklet["pages"] if p["kind"] == "features")
    assert [i["src"] for i in page["images"]] == ["feature-0", "feature-1", "feature-2"]
    # The additional photographs keep their page, the features' are not repeated.
    images = [p for p in booklet["pages"] if p["kind"] == "images"]
    assert [[i["src"] for i in p["images"]] for p in images] == [["photo-1", "photo-2"]]


def test_the_optional_pages_follow_the_authors_order():
    item = {
        **item_with(
            features=["قريب من الخدمات"],
            boundaries={"north_description": "شارع " * 400},
            rental_contracts=[{"unit_number": "1", "annual_rent_value": "1000"}],
        ),
        "image_assets": photos(6),
    }

    def groups(booklet):  # a group may run on several pages
        kinds = kinds_of(booklet)
        return [k for n, k in enumerate(kinds) if not n or kinds[n - 1] != k]

    guide = groups(compose(project_with(), [item]))
    assert guide == ["property", "features", "boundaries", "images", "rentals"]
    item["property_data"]["page_order"] = ["rentals", "images", "boundaries"]
    chosen = groups(compose(project_with(), [item]))
    assert chosen == ["property", "rentals", "images", "boundaries", "features"]


def test_long_features_continue_on_a_features_page_without_loss():
    features = [f"ميزة رقم {n} " + " ".join(["تفصيل"] * 30) for n in range(1, 25)]
    booklet = compose(
        project_with(), [{**item_with(features=features), "image_assets": photos(3)}]
    )
    page = next(p for p in booklet["pages"] if p["kind"] == "features")
    more = [
        p
        for p in booklet["pages"]
        if p["kind"] == "information" and p["heading"] == "features"
    ]
    assert more, "the features that do not fit continue on another page"
    printed = page["entries"] + [e for p in more for e in p["entries"]]
    assert [e["text"] for e in printed] == features
    assert [e["number"] for e in printed] == list(range(1, 25))
    # They come straight after the features page.
    order = [p["kind"] for p in booklet["pages"]]
    at = order.index("features")
    assert order[at + 1 : at + 1 + len(more)] == ["information"] * len(more)


def test_properties_close_one_after_another_unless_given_their_own_time():
    """Electronic bidding closes on the first property at its time, on the
    auction's last day, and on each next one the interval later; a property's
    own date or time overrides its share."""
    from app.generation.booklet.composer import closing

    auction = {
        "auction_end_date": "2026-11-14",
        "first_close_time": "18:00",
        "close_interval_minutes": 2,
    }
    assert closing(auction, {}, 0) == ("2026-11-14", "18:00")
    assert closing(auction, {}, 3) == ("2026-11-14", "18:06")
    own = {"auction_close_time": "20:30"}
    assert closing(auction, own, 3) == ("2026-11-14", "20:30")
    assert closing(auction, {"auction_close_date": "2026-11-20"}, 1) == (
        "2026-11-20",
        "18:02",
    )
    # Past midnight the closing moves to the next day.
    late = {**auction, "first_close_time": "23:58"}
    assert closing(late, {}, 2) == ("2026-11-15", "00:02")
    # Without a schedule, only the auction's last day.
    assert closing({"auction_end_date": "2026-11-14"}, {}, 4) == ("2026-11-14", "")
    booklet = compose(
        project_with(
            "electronic",
            auction_end_date="2026-11-14",
            first_close_time="18:00",
            close_interval_minutes=5,
        ),
        [item_with(), item_with(), item_with(auction_close_time="21:00")],
    )
    pages = property_pages(booklet)
    assert [(p["close_date"], p["close_time"]) for p in pages] == [
        ("2026-11-14", "18:00"),
        ("2026-11-14", "18:05"),
        ("2026-11-14", "21:00"),
    ]
    assert all(p["variant"].endswith("-close") for p in pages)
    # Physical auctions have no closing schedule.
    physical = compose(
        project_with("physical", first_close_time="18:00"), [item_with()]
    )
    assert not property_pages(physical)[0]["variant"].endswith("-close")


def test_the_project_gives_each_property_its_scheduled_closing(admin):
    p = create_auction(admin)
    first = add(admin, p, property_input(1))
    second = add(admin, p, property_input(2))
    project = admin.get(f"/api/projects/{p}").json()["project"]
    project["auction"].update(
        auction_end_date="2026-10-12",
        first_close_time="17:00",
        close_interval_minutes=3,
    )
    assert admin.put(f"/api/projects/{p}", json=project).status_code == 200
    closings = admin.get(f"/api/projects/{p}").json()["closings"]
    assert closings["items"][first] == ["2026-10-12", "17:00"]
    assert closings["items"][second] == ["2026-10-12", "17:03"]
    assert closings["next"] == ["2026-10-12", "17:06"]


def test_summary_columns_follow_their_values():
    """A column is as wide as its values need: the participation amount gives
    its room to the columns with more text, and the table keeps its edges."""
    from app.generation.booklet.composer import (
        SUMMARY_COLS,
        SUMMARY_FIELDS,
        summary_columns,
    )

    items = [
        item_with(
            property_type="أرض سكني تجاري",
            city="جدة",
            district="أبحر الشمالية",
            plot_number="التنزيلات الشمالي من قطعة رقم 116",
            participation_amount="150000",
        )
    ]
    cols = summary_columns(items)
    widths = dict(
        zip(SUMMARY_FIELDS, [cols[i] - cols[i + 1] for i in range(len(SUMMARY_FIELDS))])
    )
    assert cols[0] == SUMMARY_COLS[0] and cols[-1] == SUMMARY_COLS[-1]
    guide = dict(
        zip(
            SUMMARY_FIELDS,
            [SUMMARY_COLS[i] - SUMMARY_COLS[i + 1] for i in range(len(SUMMARY_FIELDS))],
        )
    )
    assert widths["participation_amount"] < guide["participation_amount"]
    assert widths["plot_number"] > guide["plot_number"]
    page = summary_pages = compose(project_with("physical"), items)["pages"][4]
    assert page["kind"] == "summary" and page["cols"] == cols
    # Short values keep one line; the long plot text wraps in its cell, and so
    # does a type longer than its column (which keeps the guide's width).
    lines = summary_pages["lines"][0]
    assert all(len(lines[k]) == 1 for k in ("city", "district"))
    assert widths["property_type"] == guide["property_type"]
    assert " ".join(lines["property_type"]) == "أرض سكني تجاري"
