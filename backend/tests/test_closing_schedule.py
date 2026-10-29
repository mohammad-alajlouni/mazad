"""Every output closes a property's bidding when the booklet does: its own
date and time, else the auction's closing schedule at its place."""

import unicodedata

import pymupdf
from test_auctions import add, pdf, property_input
from test_banners import campaign
from test_workflow import image_data

from app.generation.booklet.composer import closing
from app.generation.marketing.compose import hours, layout, page


def schedule_project(admin):
    p, first = campaign(admin, "electronic", workspace="project")
    # The sample property closes at its own time: this one follows the schedule.
    item = admin.get(f"/api/projects/{p}").json()["items"][0]
    data = {
        **item["property_data"],
        "auction_close_date": None,
        "auction_close_time": None,
    }
    data.pop("rental_contracts", None)
    r = admin.put(
        f"/api/projects/{p}/items/{first}",
        json={"title": item["title"], "property_data": data},
    )
    assert r.status_code == 200, r.text
    items = [first]
    for n in (2, 3):
        body = property_input(n)
        body["property_data"].update(
            {
                "usage": "سكني",
                "execution_request_number": f"55{n}",
                "auction_close_date": None,
                "auction_close_time": None,
            }
        )
        if n == 3:
            # Its own closing, as its form allows.
            body["property_data"].update(
                {"auction_close_date": "2026-10-13", "auction_close_time": "20:30"}
            )
        items.append(add(admin, p, body))
    detail = admin.get(f"/api/projects/{p}").json()["project"]
    auction = {
        **detail["auction"],
        "first_close_time": "16:00",
        "close_interval_minutes": 15,
        "electronic_platform_url": "https://example.com/platform",
    }
    assert (
        admin.put(f"/api/projects/{p}", json={**detail, "auction": auction}).status_code
        == 200
    )
    admin.post(
        f"/api/projects/{p}/images",
        files={"file": ("photo.png", image_data())},
        data={"category": "cover"},
    )
    for item in items:
        admin.post(
            f"/api/projects/{p}/images",
            files={"file": ("photo.png", image_data())},
            data={"category": "main", "item_id": item},
        )
    review = admin.get(f"/api/projects/{p}/review").json()
    assert review["valid"], review
    return p, items, auction


def text_of(page):
    return unicodedata.normalize("NFKC", page.get_text())


def test_boards_close_each_property_as_the_booklet_does(admin):
    p, items, auction = schedule_project(admin)
    details = admin.get(f"/api/projects/{p}").json()["items"]
    expected = [closing(auction, i["property_data"], n) for n, i in enumerate(details)]
    # 16:00, 16:15 on the last day; the third its own 2026-10-13 20:30.
    assert expected == [
        ("2026-10-12", "16:00"),
        ("2026-10-12", "16:15"),
        ("2026-10-13", "20:30"),
    ]
    clock = [hours(t, True, True).split()[0] for _, t in expected]  # 04:00 …

    booklet = admin.post(
        f"/api/projects/{p}/generate", json={"types": ["project_booklet"]}
    )
    assert booklet.status_code == 200, booklet.text
    pages = [
        text_of(x)
        for x in pymupdf.open(stream=pdf(admin, booklet.json()[0]), filetype="pdf")
    ]
    for item, (day, _), time in zip(details, expected, clock, strict=True):
        own = [
            t for t in pages if item["property_data"]["deed_number"] in t and time in t
        ]
        assert own, (item["title"], time)
        assert day.replace("-", " / ") in "".join(own) or day.replace(
            "-", "/"
        ) in "".join(own)

    for size in ("10x3", "4x2", "2x2"):
        admin.put(
            f"/api/projects/{p}/banner-config", json={"auto_size": False, "size": size}
        )
        r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
        assert r.status_code == 200, r.text
        boards = [
            text_of(x)
            for x in pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf")
        ]
        for board, (day, _), time in zip(boards, expected, clock, strict=True):
            assert f"{time} م" in board and day.replace("-", "/") in board, (
                size,
                time,
                board,
            )
    # A board for one property alone keeps that property's place in the booklet.
    admin.put(
        f"/api/projects/{p}/banner-config",
        json={"auto_size": False, "size": "4x2", "property_ids": [items[1]]},
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    (board,) = [
        text_of(x) for x in pymupdf.open(stream=pdf(admin, r.json()[0]), filetype="pdf")
    ]
    ends = board.split("ينتهي")[1]  # (it starts at 04:00 too)
    assert "04:15 م" in ends and "04:00 م" not in ends


def test_property_posts_close_each_property_and_the_announcement_the_auction():
    auction = {
        "auction_type": "electronic",
        "auction_start_date": "2026-11-01",
        "auction_end_date": "2026-11-04",
        "start_time": "10:00",
        "end_time": "18:00",
        "first_close_time": "16:00",
        "close_interval_minutes": 15,
    }
    from app.generation.marketing.compose import values

    second = values({"auction": auction}, {"position": 1, "property_data": {}}, 2, {})
    assert second["time_line"].endswith("04:15 مساء")
    announcement = values({"auction": auction}, None, 2, {})
    assert announcement["time_line"].endswith("06:00 مساء")


def test_the_place_icon_follows_the_auction_type():
    """Guide p.13: the location pin for a hall, the platform for an electronic
    auction, both for a hybrid one (and the line moves aside for the second)."""
    for name in layout():
        slot = next(s for s in layout()[name]["slots"] if s["kind"] == "place_icon")
        pin, screen = len(slot["location"]["parts"]), len(slot["platform"]["parts"])
        aw, ah = layout()[name]["size"]
        for kind, count in (
            ("physical", pin),
            ("electronic", screen),
            ("hybrid", pin + screen),
        ):
            out = page(
                name,
                (aw, ah),
                {"auction_type": kind, "place": "قاعة", "place_line": "المكان/ قاعة"},
                {},
            )
            assert len(out["icons"]) == count, (name, kind)
        hall = page(
            name,
            (aw, ah),
            {"auction_type": "physical", "place": "قاعة", "place_line": "المكان/ قاعة"},
            {},
        )
        both = page(
            name,
            (aw, ah),
            {"auction_type": "hybrid", "place": "قاعة", "place_line": "المكان/ قاعة"},
            {},
        )
        line = lambda o: next(
            t for t in o["texts"] if t["key"] in ("place", "place_line")
        )  # noqa: E731
        if slot["beside"]:
            assert line(both)["x"] < line(hall)["x"]
            # The screen stands clear of the line and of the pin.
            screens = [
                i
                for i in both["icons"]
                if i in [dict(p, dx=i["dx"]) for p in slot["platform"]["parts"]]
            ]
            assert screens
