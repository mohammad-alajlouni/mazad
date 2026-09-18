import pytest
from fastapi import HTTPException
from weasyprint import HTML
from app.generation.preflight import check_layout, inspect_pdf


def test_rejects_incorrect_page_dimensions():
    pdf = HTML(string="<style>@page{size:A5}</style><p>Wrong size</p>").write_pdf()
    with pytest.raises(HTTPException, match="preflight"):
        inspect_pdf(pdf, {"booklet": {"pages": []}})


def test_rejects_text_clipping_in_fixed_region():
    doc = HTML(
        string='<div data-fit="headline" style="width:100px;height:10px;font-size:40px">Headline</div>'
    ).render()
    with pytest.raises(HTTPException, match="preflight"):
        check_layout(doc, {})
