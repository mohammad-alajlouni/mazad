"""Prepare the official auction request form (REGA) for the platform.

The authority's form is a fillable PDF of six pages. The platform fills it
itself: each page is kept as it is (its vector drawing, without the fields),
and each field's box is named, so the filled text and ticks stand exactly
where the authority's form has them. Run once on the official file:

    python scripts/extract_request_form.py

It writes, in templates/infath/assets/forms:
- request-N.pdf: page N, vectors only (placed under the text on export);
- request-N.png: page N for the live preview;
- request-fields.json: {"pages": [{"size": [w, h], "fields": {name: [x0,
  y0, x1, y1]}}], "tables": {...}} in points.
"""

import hashlib
import json
from pathlib import Path

import pymupdf

FORMS = Path(__file__).resolve().parents[1] / "app/templates/infath/assets/forms"
SOURCE = FORMS / "rega-request-source.pdf"

# The fields of each page, in the order the official file lists them
# (None: a box the platform does not fill).
NAMES = {
    1: [
        "date",
        "org_name",
        "cr_number",
        "unified_number",
        "fal_license",
        "manager_name",
        "manager_id",
        "manager_mobile",
        "manager_email",
        "crier_name",
        "crier_id",
        "crier_mobile",
        "crier_email",
    ],
    2: [
        "date",
        "units_count",
        "properties_count",
        "auction_name",
        "method_all",
        "method_physical",
        "method_electronic",
        "city",
        "platform_name",
        "venue",
        "stream_link",
        "end_year",
        "end_month",
        "end_day",
        "start_year",
        "start_month",
        "start_day",
        "start_time",
        "receive_other",
        "receive_cheque",
        "receive_transfer",
        "receive_other_text",
        "keeping",
        None,
        "receive_days",
        "refund_other",
        "refund_cheque",
        "refund_transfer",
        "refund_other_text",
        None,
        "refund_days",
        "entry_none",
        "entry_refundable",
        "entry_advance",
        "entry_deposit",
        "award_minutes",
        "disposal_lease",
        "disposal_sale",
    ],
    3: [
        "date",
        "owner",
        "deed",
        "agent_name",
        "agency_number",
        "age",
        "area",
        "usage",
        "property_type",
        "usage_other",
        "status_other",
        "status_seized",
        "status_other_text",
        "status_stopped",
        "status_mortgaged",
        "status_free",
        "min_price",
        "entry_amount",
        "rulings_other_text",
        "rulings_deposit_sale",
        "rulings_condition",
        "rulings_session",
        "rulings_preemption",
        "rulings_none",
        "rulings_other",
        "ownership_other",
        "ownership_full",
        "ownership_other_text",
        "rights_text",
        "rights_yes",
        "rights_no",
        "dispute_text",
        "dispute_yes",
        "dispute_no",
        "value_text",
        "value_yes",
        "value_no",
        "offplan_text",
        "offplan_yes",
        "offplan_no",
        "contribution_text",
        "contribution_yes",
        "contribution_no",
    ],
    5: ["date"],
    6: ["date", "declarant", "unified_number", "org_name"],
}
# The statement tables: columns right to left.
TABLES = {
    4: [
        "number",
        "owner",
        "deed",
        "contract",
        "area",
        "property_type",
        "usage",
        "age",
        "city",
        "disclosure",
        "min_price",
        "entry_amount",
        "estimated_value",
    ],
    5: ["number", "owner", "deed", "agent_name", "agency_number"],
}


def box(rect):
    return [round(v, 2) for v in (rect.x0, rect.y0, rect.x1, rect.y1)]


source = pymupdf.open(SOURCE)
pages, tables = [], {}
for n, page in enumerate(source, 1):
    widgets = list(page.widgets())
    named = [w for w in widgets if not w.field_name.startswith("Text Field")]
    fields = {}
    for name, widget in zip(NAMES.get(n, []), named, strict=False):
        if name:
            fields[name] = box(widget.rect)
    if n in NAMES and len(named) < len(NAMES[n]):
        raise SystemExit(f"page {n}: {len(named)} fields, {len(NAMES[n])} names")
    if n in TABLES:
        cells = [w for w in widgets if w.field_name.startswith("Text Field")]
        rows = {}
        for w in cells:
            rows.setdefault(round(w.rect.y0 / 4), []).append(w)
        tables[str(n)] = [
            {
                column: box(w.rect)
                for column, w in zip(
                    TABLES[n], sorted(row, key=lambda w: -w.rect.x0), strict=True
                )
            }
            for _, row in sorted(rows.items())
        ]
    pages.append(
        {
            "size": [round(page.rect.width, 3), round(page.rect.height, 3)],
            "fields": fields,
        }
    )
    # The page without its fields: what the authority's form draws.
    single = pymupdf.open()
    single.insert_pdf(source, from_page=n - 1, to_page=n - 1, annots=False)
    for widget in list(single[0].widgets()):
        single[0].delete_widget(widget)
    single.save(FORMS / f"request-{n}.pdf", garbage=4, deflate=True)
    zoom = 1240 / page.rect.width
    single[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), annots=False).save(
        FORMS / f"request-{n}.png"
    )

(FORMS / "request-fields.json").write_text(
    json.dumps({"pages": pages, "tables": tables}, ensure_ascii=False, indent=1) + "\n"
)
(FORMS / "manifest.json").write_text(
    json.dumps(
        {
            "source": {
                SOURCE.name: hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            },
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(FORMS.glob("request-*"))
            },
        },
        ensure_ascii=False,
        indent=1,
    )
    + "\n"
)
print(len(pages), "pages;", {k: len(v) for k, v in tables.items()}, "table rows")
