# mazad

A working administrator workspace for entering or importing project data, generating eight deliverables, reviewing drafts, approving them, and downloading final files. Next.js/React/TypeScript/Tailwind frontend; FastAPI/Pydantic/SQLAlchemy backend; PostgreSQL with JSONB metadata. No developer-owned cloud service is required.

## Auction authoring workspaces

Booklets and banners have separate navigation, campaign data and generation flows. See the [approved Excel template](docs/approved-excel-template.md) and [banner workflow, sizes and rendered examples](docs/banner-workspace.md).

## Quick start with Docker

Requires Docker Engine/Desktop with Compose v2.

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD`, `JWT_SECRET` and `ADMIN_PASSWORD`. Use a URL-safe database password (hex is convenient). Set `ADMIN_EMAIL`.
3. Start:

```sh
docker compose up --build -d
```

Open **http://localhost:8080** and sign in using the administrator credentials in `.env`. Interactive API docs: **http://localhost:8080/docs**. Migrations and an idempotent administrator/template bootstrap run when the backend starts. Database and generated files persist in named volumes. `docker compose down` preserves data; adding `-v` deletes it.

```sh
docker compose logs -f backend
docker compose exec backend alembic current
```

The configured administrator password is used only when the administrator is first created. Changing `.env` alone does not reset an existing account; see `docs/deployment.md`.

## Local development

Requires Python 3.12+, Node 22+, PostgreSQL 14+ and the native Pango libraries used by WeasyPrint.

```sh
# macOS native PDF dependencies
brew install pango
# Debian/Ubuntu equivalent
# apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core fonts-noto-core

python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
cp .env.example .env
```

Set `.env` credentials and `DATABASE_URL` to an existing local PostgreSQL database. Root `.env` is loaded regardless of working directory. Environment variables take precedence.

```sh
cd backend
# On macOS, if native library discovery needs it:
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
.venv/bin/alembic upgrade head
.venv/bin/python -m app.bootstrap
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```sh
cd frontend
npm run dev
```

Open **http://localhost:3000**. Next.js proxies `/api` to `http://127.0.0.1:8000`; set `API_INTERNAL_URL` before building if needed. The browser uses same-origin HttpOnly session cookies, never localStorage tokens.

For a local production build:

```sh
npm --prefix frontend run build
npm --prefix frontend run start
```

The start script prepares Next.js standalone static assets and binds to loopback. Set `BIND_HOST=0.0.0.0` only when remote access is intended. Docker uses its own standalone entry point.

## End-to-end demo

With the backend running and root `.env` configured:

```sh
backend/.venv/bin/python backend/demo.py
# Through Compose's public endpoint:
backend/.venv/bin/python backend/demo.py --base-url http://localhost:8080
```

The script uses the actual authenticated HTTP API. It creates one Arabic demo project, manually enters an item, previews/imports `samples/demo-assets.xlsx`, uploads `samples/demo-generator.jpg`, generates all eight drafts, previews each file, approves every output, and exports PDF/PNG/TXT files to `output/demo/`. It sets the demo document language to Arabic in Settings. A repeated run leaves the existing demo untouched; use `--code DEMO-002` for another run.

To do it yourself in the UI:

1. Create a project; add an item under **Items**.
2. Open **Excel Import**, upload the sample, preview its three normalized rows, and import them.
3. Upload the sample photograph under **Images**, attaching it to an item.
4. Under **Generate**, select all eight types and generate drafts. AI is optional.
5. Open each output; review the PDF/image and edit its narrative where needed.
6. Save edits, approve, then download. Editing an approved output returns it to Draft.
7. Edit any source item: related outputs become **Needs Regeneration** and final exports are blocked until regeneration and approval.

## Outputs

| Generator | Export | Demo behavior |
|---|---|---|
| Asset study | PDF | Per-item financial, technical and specification summary; optional AI narrative; images |
| Project booklet | PDF | Cover, contents and expandable item sections; no fixed page count |
| Banners | PDF + PNG per page | Fixed layout per item, real asset image when supplied |
| Regulatory form | PDF | Formal development form, inventory and signature area |
| Closing form | PDF | Completion inventory, notes and signature area |
| Social content | TXT + PDF | Editable publication copy; no publishing integration |
| Final output report | PDF | Project inventory and output register as of generation time |
| Booklet study report | PDF | Data-completeness observations plus supporting asset information |

Generic-project templates are explicitly marked **DEVELOPMENT TEMPLATE**; the Infath auction paths described below use the supplied official references. Regulatory and completion forms are examples, not client-approved official documents. Regenerate the final output report after other approvals to refresh its output register.

## Architecture

```text
Manual entry ─┐
              ├─ Pydantic normalization ─ PostgreSQL project/items/JSONB
Excel parser ─┘                                │
                                   project-scoped snapshot
                                               │
                                  generator registry (8 types)
                                               │
                          Jinja templates + optional AI provider
                                               │
                                   Draft PDFs / PNGs / text
                                               │
                              Review → Approve → Final export
```

- `backend/app/api/`: authentication-protected project, ingestion, output and settings routes.
- `backend/app/schemas.py`: validated central inputs; `services/ingestion.py`: shared normalizer and configurable Excel mapping.
- `backend/app/generation/`: pure output-specific builders, registry and document rendering engine.
- `backend/app/templates/`: replaceable HTML/CSS, Excel header mapping and embedded Arabic fonts.
- `backend/app/services/`: AI provider interface and local file storage boundary.
- `backend/app/models.py`: relational entities, JSONB snapshots and audit records.
- `backend/migrations/`: frozen initial Alembic migration.
- `frontend/components/`: authentication, dashboard, project data forms, outputs, review and settings.

See `docs/architecture.md` for data integrity, security, locking, storage and extension points.

## Tests and checks

```sh
cd backend
# Quick disposable SQLite test run; not the production database.
.venv/bin/python -m pytest -q
# Required production-engine integration run (create an empty disposable database first):
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/automation_test .venv/bin/python -m pytest -q
.venv/bin/ruff check app tests demo.py --select F,I
```

The test runner refuses a PostgreSQL test database whose name does not end in `_test`. It **recreates its test tables**. Never point it at real data. Tests cover login/logout/revocation/throttling, validation, project creation, manual input, Excel mapping/preview/import/replay, all eight generated outputs, approvals/exports, stale data, images, Arabic text, 20+ page booklets, project isolation, AI failure and provider contracts.

```sh
cd frontend
npm run typecheck
npm run build
npx playwright install chromium
# Keep frontend and API running; use root .env credentials or environment variables.
npm run test:e2e
# Use installed Google Chrome instead:
E2E_BROWSER_CHANNEL=chrome npm run test:e2e
```

The browser test creates its own labeled demo project and covers login, data entry, Excel preview/import, upload, generation, narrative editing, approval, download, mobile width and logout. It leaves demo records for inspection. See `docs/implementation-report.md` for the checks actually run in this workspace.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL; required locally; Compose sets the internal host |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose database initialization; use a URL-safe password |
| `JWT_SECRET` | Required, 32+ random characters |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Initial administrator; password must have 12+ characters |
| `STORAGE_DIR` | Private upload/generated file directory; relative to backend working directory locally |
| `CORS_ORIGINS` | Comma-separated exact trusted browser origins; also used for mutation-origin checks |
| `COOKIE_SECURE` | Set `true` behind production HTTPS; `false` only for local HTTP |
| `AI_API_KEY` | Optional server-only API credential |
| `AI_BASE_URL` | OpenAI-compatible API base URL ending in `/v1` |
| `AI_MODEL` | Provider model identifier; must exist for your account |
| `MAX_UPLOAD_MB` | Per-file upload limit, default 10; adjust Nginx limit with it |
| `API_INTERNAL_URL` | Next.js build-time API rewrite target; Compose uses `http://backend:8000` |

Never commit `.env`. No secret is returned from `/api/settings`. Provider/model configuration is managed in the server environment; branding and document language are editable in Settings.

## AI behavior

`AIService` wraps an `AIProvider` protocol and `OpenAICompatibleProvider`. Summary, description, social text and analysis helpers are available. Missing credentials return **UNAVAILABLE**. Provider timeouts, invalid responses and HTTP errors return **ERROR** without breaking deterministic generation. Requests and draft text are stored for review. No approval is performed by AI.

The live provider cannot be validated without a client API key. Automated tests cover request shape, all four helpers, missing configuration and provider failure. Fixed demo model defaults are configurable; select a model supported by the chosen provider.

## Templates and client assets

Replace files in `backend/app/templates/`; each output type has its own HTML template inheriting `base.html`. The `templates` table maps types to filenames and records demo/version metadata. This metadata can be maintained through migrations/configuration; there is no visual editor. Generators use normalized fields and never read Excel columns.

- Brand name, color, language and uploaded logo: **Settings**.
- Fonts: replace the bundled regular/bold TTF files in `templates/fonts/` with appropriately licensed client fonts; update `base.html` and the renderer if font filenames change.
- Excel aliases: `templates/excel_mapping.json`, or per-upload JSON mapping in the Excel Import screen. Unknown columns become `attributes`.
- Real asset images: upload to the project or a specific item. Excel image references may resolve only to already-uploaded images in that same project; external URLs are not fetched.

Remaining client-specific inputs: real project data and photographs, a real Excel workbook where applicable, approved designs for the other generic outputs, optional AI credentials and hosting credentials. Infath auction reference files and fonts are now packaged as described below.

## Migrations and deployment

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic revision --autogenerate -m "describe schema change"
# Review generated code before running it.
```

Do not edit the released initial migration to change the schema. Add a new migration. See `docs/deployment.md` for HTTPS, backups, operations and configuration; `docs/api.md` for endpoints.

## MVP limitations

Administrator bootstrap; bilingual Arabic/English workspace with persistent RTL/LTR selection and owner-scoped project access; no advanced role management. Generation runs synchronously, so large projects or many images need capacity testing; the 5,000-row import limit is a safety limit, not a generation-performance guarantee. Lists are not paginated. Image URLs are intentionally not fetched. Excel formulas require saved cached values; embedded workbook images are not extracted. Regeneration replaces the current files and narrative, while audit records preserve events; full version history and unreferenced-file cleanup are future work. Draft preview files can be saved by a browser; approval gates official exports, not DRM. Demo templates and configuration are technical files; there is no template editor.

## Infath auction booklets (September 2026)

The existing Next.js/FastAPI application now includes an **Auction setup** tab. This is an extension of the current project/item workflow, not a replacement application.

1. Create a project, open **Auction setup**, enter the auction type, schedule, location/platform and legal announcement, choose one of six supplied covers, and save.
2. Save the selling agent in the second form. Upload its real logo under **Images**, attached to the project; select that upload in the selling-agent form. Upload an auction logo or cover photograph with the matching category if needed.
3. Under **Items**, add each property. Expand the structured property, links, features, boundaries and rental sections. Description/notes continue to use the existing item fields. Use **Move up** to reorder properties.
4. Alternatively upload `samples/auction-properties.xlsx`, inspect the original and normalized rows, correct column mappings using dropdowns, validate again, and import. Mapping changes disable import until revalidated. Store identifiers with leading zeroes as Excel text.
5. Upload one main image and additional photographs per property. Multiple additional files can be uploaded together; upload order is retained. Portrait/landscape orientation is detected after EXIF normalization.
6. Open **Generate**, review blocking errors and optional-data warnings, select Project Booklet, and generate. The document begins as Draft. Preview, approve and download use the existing output screen. Official wording cannot be edited through the narrative editor.

Manual and Excel input use `ItemInput` / `PropertyData` and the same save service and generation snapshot. The renderer does not read workbooks. Structured rental rows have their own relational table. Project/auction data and property metadata use validated JSON/JSONB extensions to the existing tables; selling agents are project-scoped related records.

The page composer selects the supplied cover, preserves the reference introduction and type-specific terms, repeats summaries and rental tables, creates orientation-specific property sections, and adds image, boundary, feature and information pages only when populated. Missing values remain `-`. Ruaq Arabic is embedded; supplied Lama fonts are also included. Fixed official Arabic pages remain Arabic even when dynamic document labels are English, because no approved English versions were supplied. QR links are real, validated HTTP(S) destinations; Code 128 identifies the project as `P-<decimal UUID>`.

Auction booklets use the Infath reference assets and layouts; the auction banner path also uses the supplied identity. Other generic-project outputs keep their existing development templates. Their presence is not a claim of regulatory approval. The provided commercial booklet is a template/example, not live auction data.

Run migration `0002` before starting the updated backend. Existing projects are assigned to the earliest existing administrator (the previous installation was single-admin); subsequent project access is owner-scoped. Existing user sessions/authentication are preserved. System branding settings remain installation-wide, not tenant-specific. Review existing account provisioning before using the installation for a multi-organization service.

For auction booklets, regenerating an approved version creates a new Draft and retains the earlier PDF and snapshot. A later project change marks previous outputs as needing regeneration and blocks final export until the current version is approved. Generic-output regeneration retains its original behavior.

See [auction implementation and verification report](docs/auction-implementation-report.md) for the reference provenance, endpoints, schema, executed checks and remaining limits. Supplied assets are packaged under `backend/app/templates/infath/assets`; deployment does not depend on Downloads. `backend/scripts/extract_infath_assets.py` documents how those assets were extracted, and `provenance.json` records source fingerprints.
