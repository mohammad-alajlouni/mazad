# Approved booklet Excel import

The author workflow uses `GET /api/booklet-import-template` to download a blank
copy of the supplied Hail workbook layout, then
`POST /api/projects/{id}/imports/approved/preview` to validate the populated file.
The download preserves Arabic RTL, labels, merged cells, styles and five blank
property sheets; it contains no original property values. Users can duplicate or
remove property sheets. Intact empty sheets are ignored. The original generic
row-based preview API remains available for existing integrations, but is no longer
shown in the author UI.

Each worksheet is one property. The parser validates the fixed labels before reading
input cells. It never guesses a column mapping for this layout. Unexpected populated
cells are errors. Limits: 10 MB upload (configured application limit), 50 MB expanded
workbook, 100 sheets, 200 rows and 30 columns per sheet. Only `.xlsx` is accepted.

| Cells | Meaning |
| --- | --- |
| D3 / E3 | Closing date (DD/MM/YYYY or native Excel date) / time |
| D5 / D7 / F7 | Description / property type / area |
| D8 / D9 / D10 | Deed / plan / plot identifiers |
| F8 / F9 / F10 | Usage / district / participation amount |
| C13 | Additional information |
| I8:I11 | North, south, east, west boundary descriptions |
| I14:I17 | North, south, east, west lengths |
| I20 / I21 / I22 | Survey / additional images / location URLs |

Links can alternatively be attached to their corresponding labels H20:H22.
Remote URLs are stored, not fetched. Embedded photos are not imported; the user
uploads photos in the images step. Formulas are rejected instead of executing them
or accepting potentially stale cached results. Numeric identifiers should be stored
as text; leading zeros in supported zero-only Excel number formats are preserved.

Description, type, positive area and deed number are required. Placeholder amounts
such as `****` and districts such as `/` stay blank with warnings. Dates differing
across properties are retained and flagged. City is absent from the template; an
optional common-city form field fills it explicitly, otherwise the user must complete
it in each property form. Warnings require acknowledgement in the UI.

The preview reports sheet names, exact input cells, localized errors/warnings and
original values. Changing the file or common city clears the old preview. There are
no writes to project properties during preview. The server rejects the entire commit
if any sheet has errors. Duplicate deed + plan + plot combinations are checked both
inside the workbook and against current project data, including again under the
project lock during commit. Commit is transactional, ordered by worksheet order,
and cannot be replayed. Existing user ownership checks apply to both endpoints.

Tests: `backend/tests/test_approved_excel.py`, `frontend/e2e/approved-import.spec.ts`.
Synthetic examples: `samples/approved-properties.xlsx` and the intentionally invalid
`approved-properties-invalid.xlsx`. The supplied source file is not published.
