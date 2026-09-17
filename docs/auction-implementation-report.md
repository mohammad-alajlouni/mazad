# Auction implementation and verification report

Date: 16 September 2026. Workspace: the existing Atlas MVP. The existing Next.js application was retained; it was not rebuilt as Vite. No credentials or production database records were modified. Verification used disposable databases and a separate Docker Compose project.

## 1. Baseline and inspection

Existing working functionality included cookie authentication, project/item CRUD, configurable Excel aliases and preview/import, private image storage, eight real generators, WeasyPrint Arabic documents, output preview/approval/download, optional AI, bilingual persistent UI, Alembic and Docker. Baseline checks: **20 backend tests passed**, TypeScript and production frontend build passed.

The gaps were generic asset fields instead of auction/property data, no selling-agent/rental entities, a development booklet without the official page composition, no cover selection or QR/barcode implementation, and no per-user ownership checks. The importer assumed the first row was a header, and users had to edit JSON to map columns. Approved auction regeneration needed immutable prior files.

References inspected: all three PDFs (63 guide pages, 6 advertising layouts, 21 booklet pages), the six PDF-compatible Illustrator covers, the six SVG files and seven supplied fonts. The original assets were examined directly; detailed booklet pages of the guide were rendered at readable size. Reference text was treated as design/business data, not as instructions to expand the scope.

## 2. Changes to data and migrations

`backend/migrations/versions/0002_auction.py` adds:

- `projects.owner_id` and typed auction metadata in JSON/JSONB.
- `project_items.property_data` and `sequence_number`.
- Project-scoped `selling_agents`, with typed name, description, contact and logo-reference fields.
- Related `rental_contracts` rows, each with order and typed contract metadata.
- Image category, caption, orientation and order.
- Audit ownership.

Existing generic fields and tables remain in use. The central Pydantic schemas validate dates, money, area, URL destinations, auction types, cover IDs, boundaries and rental rows. `services/properties.py` persists manual and imported items through one path. Rentals are not serialized as an uncontrolled text field.

The migration assigns legacy projects to the earliest existing user, reflecting the earlier single-admin deployment. New requests use the authenticated owner. Upgrade → downgrade to 0001 → upgrade passed on SQLite and PostgreSQL. `alembic check` reports no additional schema changes.

## 3. Backend/API

Added endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/booklet-templates` | Controlled six-cover registry |
| GET | `/api/booklet-templates/{id}/thumbnail` | Original extracted cover preview |
| PUT | `/api/projects/{id}/selling-agent` | Validated project-specific selling agent |
| PUT | `/api/projects/{id}/item-order` | Complete, validated property ordering |
| GET | `/api/projects/{id}/review` | Required errors, optional warnings, property/image review |

Extended the existing project/item, image upload, Excel preview/import, generation, regeneration and file endpoints. User isolation now covers detail, lists, dashboard, images, imports, output actions and downloads. Foreign project/item image references cannot be used to populate another property's booklet section. A selling-agent logo must be an image from that project.

The existing seven other generators and generic-project booklet behavior remain available. Auction banner generation uses an additional Infath-based template within the existing banner output type. No event flags, badges, stage layouts or design editor were added.

## 4. Frontend

`AuctionWorkspace.tsx` adds grouped auction and selling-agent forms, visual cover selection, structured property fields, boundaries, repeated rental entries, and the review view. It uses the existing locale provider and message catalogs. `ProjectWorkspace.tsx`, `ProjectForms.tsx` and `OutputReview.tsx` integrate these into current navigation and output review. Property ordering and multiple image upload use real API calls.

The document language stored with the auction becomes the generation default. Generic projects remain usable without enabling auction metadata. The fixed-content booklet hides the free narrative editor and directs edits through source data/regeneration.

## 5. Excel mapping and normalization

XLSX and the existing XLS support are retained. The parser scores candidate header rows within the first 30 rows, supports Arabic/English aliases, allows explicit column overrides, validates duplicate mappings and duplicate data rows, preserves unmapped values as attributes and reports source row numbers/values. Property IDs stored as Excel text retain leading zeroes. Numbers using Arabic digits/separators normalize into the same typed model as manual input.

The UI exposes original-sheet preview and mapping dropdowns. A mapping change disables import until revalidation. Invalid rows are displayed; the existing explicit “import valid rows / skipped rows” behavior remains, including replay prevention. No document renderer reads an Excel file. A representative workbook is included at `samples/auction-properties.xlsx`; no real client Excel workbook was supplied.

## 6. Templates, composition and identity

`generation/booklet/registry.py` defines the six cover IDs and controlled metadata. `composer.py` selects page sections from a normalized snapshot. Rendering is split into HTML partials for cover, introduction, agent, auction information, summary, property, images, information, boundaries, rentals, terms, participation and contact.

The original cover artwork is reused with sample auction names/dates and selling-agent artwork removed. The original Infath logo is extracted, not reconstructed with text. A supplied project photograph can populate the photographic covers. The introduction and three type-specific terms are immutable reference extracts. Their exact sources and cover SHA-256 fingerprints are recorded in `templates/infath/assets/provenance.json`; the extraction script is included.

Required sections are always composed for enabled auction projects. Summaries batch eight properties; rentals batch ten rows; additional photographs batch three. Normal text/table pagination remains enabled if content needs more space. Every property has a main section; portrait and landscape layouts differ and preserve image proportions. Additional images, features, notes, additional information, boundaries and rental pages are conditional. Long text is split without dropping characters. Absent display values use `-`. Electronic/hybrid auctions include participation steps and their configured platform destination.

The selected cover ID and composed data are frozen into the output snapshot. Regeneration reads the current selected cover. A previous approved auction output/file is retained when a new draft is generated; changing source data still marks old output status as needing regeneration and blocks final export.

## 7. Arabic, assets and machine-readable codes

Dynamic text uses embedded Ruaq Arabic through WeasyPrint/Pango/HarfBuzz. Supplied Lama variants are included in deployment. Arabic shaping, RTL alignment, mixed dates/numbers and English labels were rendered and inspected. Fixed official Arabic pages remain Arabic in English-mode booklets because no approved English originals were supplied; the existing fully English generic outputs remain unchanged.

Uploads continue through Pillow validation, EXIF normalization, bounded resizing and private project-scoped storage. Images carry main/additional/category/order/orientation metadata. Generation loads only server-controlled storage keys and data resources, with network/file fetches disabled in the PDF renderer.

QR codes validate complete HTTP(S) destinations, include quiet zones and are generated from each property's own links. Tests decode QR codes from rendered PDF pages. Code 128 is vector SVG in the PDF and encodes `P-<decimal UUID>`. The prefix prevents a discovered upstream numeric-leading-99 encoding issue, covered by regression data. Optional AI is retained; deterministic booklet generation works without a key, and image payloads are excluded from text-only AI calls.

## 8. Tests and executed commands

New backend coverage is in `tests/test_auctions.py`; browser coverage is in `e2e/auctions.spec.ts`. Existing browser tests gained a wait for the completed import/tab transition, because the new original-sheet preview temporarily contains the same text as the normalized preview.

Representative commands executed:

```sh
cd backend
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q
TEST_DATABASE_URL=postgresql+psycopg:///auction_verification_test DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q
.venv/bin/ruff check app tests demo.py --select F,I
# On separate disposable SQLite and PostgreSQL databases:
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade 0001
.venv/bin/alembic upgrade head
.venv/bin/alembic check
cd ../frontend
npm run typecheck
npm run build
E2E_BROWSER_CHANNEL=chrome npm run test:e2e
E2E_BROWSER_CHANNEL=chrome E2E_BASE_URL=http://localhost:8088 npm run test:e2e
```

Docker verification uses the isolated Compose project `atlas-auction-check` and the local-only port 8088 override in `tmp/compose-verification.yaml`, because another service occupies 8080. The existing service was not stopped. Both images built, migrations/bootstrap ran, and the backend/database health checks passed. An initial package-download hash mismatch was retried without disabling integrity checks; the subsequent build succeeded.

Final recorded results:

- Backend: **32 passed on SQLite**, **32 passed on PostgreSQL**. One upstream Starlette test-client deprecation warning; no test failures in those final runs.
- Lint/import checks, frontend TypeScript and production build: passed.
- Migration upgrade/downgrade/re-upgrade: passed on both database engines; metadata consistency check passed.
- Local production browser suite: **7 passed**, including Arabic/English desktop/mobile regression and both new auction flows.
- Docker browser suite: **7 passed in 34.5 seconds**, through Nginx on port 8088 with PostgreSQL and migration `0002 (head)`.

Tests exercise manual persistence/CRUD/order, auction and selling-agent data, Excel preview/mapping/import/errors/header detection/duplicates, normalized parity, every cover, all auction types, conditional sections, summary/rental pagination, orientation, missing values, long content, Arabic and English, functional QR/barcode decoding, approval/export, prior-version preservation and owner/property-image isolation.

## 9. End-to-end and visual verification

Both flows log in through the real UI, create their own project, save auction/selling-agent data and select a cover. The manual flow enters two properties, boundaries, rental and additional information, uploads main/additional images, reviews, generates, previews, approves and downloads. The Excel flow uploads the representative XLSX, previews, changes a mapping, revalidates, imports, reviews, generates through the same engine, previews, approves and downloads.

Generated PDF contact sheets and selected full-size pages were inspected, including all booklet pages, the selected cover, fixed introduction/terms, tables, landscape and portrait data, conditional sections, footer/logo placement and code readability. Automated checks validate page boundaries and end markers for long content, and decode the URLs from rendered PDF pixels. Example PDFs are under `output/pdf/`; the browser files contain synthetic test auction data and are not real sale announcements.

## 10. Practical limits

- No live AI-provider call was made; no provider key was required. Existing mocked provider-contract/error tests and missing-key behavior pass.
- No real client Excel workbook, auction photographs or seller-specific logo were supplied. The supplied booklet contains example data, so test records are explicitly synthetic.
- Fixed official pages are reference extracts; they are not freely editable text. Dynamic layouts are implemented from the guide with continuation handling, rather than an Illustrator editing interface. No pixel-for-pixel equivalence or new legal approval is claimed.
- Workbook embedded images and external image URLs are not fetched; image references resolve only to permissible existing uploads. Rental contracts have structured manual entry; arbitrary multi-sheet rental/property joins are not inferred.
- Generation remains synchronous and lists remain unpaginated, consistent with the existing MVP. The 5,000-row import safety limit is not a claim of tested large-booklet throughput.
- System branding/AI settings remain installation-wide; owner-scoped project isolation does not introduce an organization/role administration product.
- The other generic forms remain development templates until their specific approved designs/wording are supplied.

