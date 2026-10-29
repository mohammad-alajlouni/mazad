"""Several board sizes chosen together are issued together: one output each,
saved once, without going back for every size."""

import pymupdf
import pytest
from test_auctions import pdf
from test_banners import campaign

from app.services.banners import SIZES


def page_size(admin, output):
    with pymupdf.open(stream=pdf(admin, output), filetype="pdf") as doc:
        return round(doc[0].rect.width), round(doc[0].rect.height)


def mm(size):
    return (
        round(SIZES[size]["width_mm"] * 72 / 25.4),
        round(SIZES[size]["height_mm"] * 72 / 25.4),
    )


def test_every_chosen_size_is_issued_in_one_step(admin):
    p, _ = campaign(admin)
    chosen = ["10x3", "4x2", "2x2"]
    r = admin.put(
        f"/api/projects/{p}/banner-config",
        json={"auto_size": False, "size": "4x2", "sizes": chosen},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sizes"] == chosen and r.json()["size"] == "4x2"
    review = admin.get(f"/api/projects/{p}/banner-review").json()
    assert review["valid"], review
    assert list(review["templates"]) == chosen

    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text
    outputs = r.json()
    assert [o["banner"]["size"] for o in outputs] == chosen
    for o in outputs:
        assert page_size(admin, o) == mm(o["banner"]["size"])
    detail = admin.get(f"/api/projects/{p}").json()
    issued = [o for o in detail["outputs"] if o["output_type"] == "banners"]
    assert sorted(o["banner"]["size"] for o in issued) == sorted(chosen)

    # Issued again, each board keeps its own size (approved ones too).
    square = next(o for o in outputs if o["banner"]["size"] == "2x2")
    assert admin.post(f"/api/outputs/{square['id']}/approve").status_code == 200
    again = admin.post(f"/api/outputs/{square['id']}/regenerate")
    assert again.status_code == 200, again.text
    assert again.json()["id"] != square["id"]
    assert again.json()["banner"]["size"] == "2x2"
    assert page_size(admin, again.json()) == mm("2x2")
    wide = next(o for o in outputs if o["banner"]["size"] == "10x3")
    again = admin.post(f"/api/outputs/{wide['id']}/regenerate").json()
    assert again["banner"]["size"] == "10x3" and page_size(admin, again) == mm("10x3")


def test_a_campaign_saved_with_one_size_keeps_working(admin):
    p, _ = campaign(admin)
    r = admin.put(
        f"/api/projects/{p}/banner-config", json={"auto_size": False, "size": "6x3"}
    )
    assert r.status_code == 200 and r.json()["sizes"] == ["6x3"]
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert [o["banner"]["size"] for o in r.json()] == ["6x3"]


@pytest.mark.parametrize(
    "body, sizes, size",
    [
        ({"size": "4x2", "sizes": ["2x2", "10x5"]}, ["2x2", "10x5"], "2x2"),
        ({"sizes": ["15x5", "15x5", "4x2"]}, ["15x5", "4x2"], "4x2"),
    ],
)
def test_the_previewed_size_is_one_of_the_chosen(admin, body, sizes, size):
    p, _ = campaign(admin)
    r = admin.put(f"/api/projects/{p}/banner-config", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["sizes"] == sizes and r.json()["size"] == size


def test_unknown_or_too_many_sizes_are_refused(admin):
    p, _ = campaign(admin)
    for sizes in [["9x9"], list(SIZES) + ["4x2"]]:
        r = admin.put(
            f"/api/projects/{p}/banner-config",
            json={"auto_size": False, "sizes": sizes},
        )
        assert r.status_code == 422, sizes


def test_usage_is_needed_when_any_chosen_board_shows_it(admin):
    p, i = campaign(admin)
    # The panoramic boards have no usage line: a property may leave it empty.
    admin.put(
        f"/api/projects/{p}/banner-config",
        json={"auto_size": False, "sizes": ["10x3", "15x5"]},
    )
    detail = admin.get(f"/api/projects/{p}").json()
    item = next(x for x in detail["items"] if x["id"] == i)
    item["property_data"]["usage"] = ""
    body = {
        k: v for k, v in item.items() if k not in ("id", "project_id", "created_at")
    }
    r = admin.put(f"/api/projects/{p}/items/{i}", json=body)
    assert r.status_code == 200, r.text
    assert admin.get(f"/api/projects/{p}/banner-review").json()["valid"]
    admin.put(
        f"/api/projects/{p}/banner-config",
        json={"auto_size": False, "sizes": ["10x3", "4x2"]},
    )
    review = admin.get(f"/api/projects/{p}/banner-review").json()
    assert not review["valid"]
    assert {"field": "usage", "section": "items", "item": item["title"]} in review[
        "missing"
    ]
