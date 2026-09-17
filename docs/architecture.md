# Architecture and integrity

## Application boundaries

One modular FastAPI application and one Next.js application, backed by PostgreSQL. There are no microservices, queues, vector stores, publishing integrations or unavailable hosted services. Nginx is the public reverse proxy in Compose.

The browser only calls same-origin `/api` endpoints. Next.js rewrites those requests during local development; Nginx proxies them directly in Compose. Credentials remain in a Secure (production), HttpOnly, SameSite=Strict cookie. Dashboard content is rendered only after `/auth/me` succeeds; every business API and file endpoint independently verifies authentication.

## Data model

- `users`: administrator email, Argon2 password hash and token version.
- `projects`: business metadata, workflow status and monotonically increasing source revision.
- `project_items`: normalized structured fields, Decimal quantities/financial values, flexible JSONB attributes.
- `project_images`: project/item association and private storage key.
- `excel_imports`, `excel_import_rows`: staged workbook imports, normalized rows and validation errors.
- `templates`: output type, replaceable template filename and demo/version configuration.
- `generated_outputs`: project/template associations, status, source revision, content snapshot and approval timestamps.
- `generated_files`: private storage keys and MIME types for each output's current files.
- `ai_generations`: purpose, provider result status and draft text.
- `system_settings`: organization branding and output language.
- `audit_logs`: project creation, import, generation, review and approval events.

Foreign keys connect records. Unique project references and template types are enforced in the database. PostgreSQL uses JSONB; a JSON variant exists only to allow lightweight SQLite tests. Financial values are Decimal-backed numeric columns; line and project totals are calculated with Decimal. Values are unit values, and totals multiply by quantity. No currency conversion or valuation model is implied.

## Normalization and ingestion

Manual requests are validated with `ItemInput` and pass through the same `normalize()` function used for Excel rows. Both write `ProjectItem` records. Generators cannot see sheet names, row numbers or column positions.

Excel reads all sheets, taking row 1 as headers. Alias mappings are case-insensitive and configurable in JSON or per-upload. Unknown columns go into attributes. Required title, positive quantity, nonnegative finite financial value and decimal precision constraints apply to both paths. Blank rows are skipped; invalid rows remain in the preview with sheet/row-specific errors. Commit imports only valid rows. A project lock plus import-status check prevents duplicate commit and cross-project use of an import ID.

Uploads are bounded to 10 MB by default. XLSX compressed contents are checked against a 50 MB expansion limit before parsing; preview is capped at 5,000 rows. Production Nginx imposes an overall request-body limit. There is no execution of workbook formulas or macros.

## Generation and approval

The registry contains eight independent `BaseOutputGenerator` implementations. Each receives the same project-scoped snapshot and emits data for a Jinja HTML template. WeasyPrint renders PDFs; PyMuPDF rasterizes banner pages to PNG. Social text also has a UTF-8 TXT export.

WeasyPrint was chosen for Pango/HarfBuzz Arabic shaping, CSS RTL, custom font embedding, reusable HTML/CSS, real images, repeated table headers and natural pagination. Noto Sans Arabic regular/bold fonts and their SIL OFL license are bundled. The system does not force a fixed page count. Banner and booklet layouts use item sections but allow content to overflow onto additional pages when necessary.

Jinja autoescapes data. Rendered images/fonts are embedded from validated local assets as data URLs. The PDF URL fetcher rejects external URLs and arbitrary filesystem paths. Uploaded image filenames are UUIDs; Pillow verifies JPEG/PNG/WebP, limits pixel dimensions, applies EXIF orientation, strips original metadata by re-encoding, and resizes images. Excel image references can resolve only to records belonging to the same project. Images are never served as public static files.

Every generation produces a Draft. Approval re-renders the artifact with its approved status and timestamp. Narrative edits reset approval. Source edits increment the project revision and mark existing outputs Needs Regeneration. Regeneration captures current data, replaces the narrative/files and resets approval. Downloads marked as final require Approved; draft previews remain viewable and inherently saveable by browsers.

Database writes and generation metadata commit transactionally. Project locks serialize ingestion and generation. Output mutations acquire the project lock before the output lock, keeping lock order consistent. Export is a read of committed state. An already-downloaded file cannot be recalled after a later source edit.

Snapshots include images and branding to preserve generated content even when settings change. This trades storage volume for predictable output. Branding changes apply on future generation, not retroactively. The final report's register is explicitly a generation-time snapshot.

## AI and files

`AIProvider` is a protocol; `OpenAICompatibleProvider` handles the HTTP contract and `AIService` supplies use-case methods plus graceful failure. Missing credentials, malformed responses and provider errors do not block non-AI generation. Prompts treat project content as data and request factual text, but administrator review is always required. API keys are never returned to the frontend or recorded in audit messages.

`FileStorage` describes `put()` and `read()`; `LocalStorage` is the development implementation. Storage keys, rather than filesystem paths, are stored in the database. Replace service construction with an S3/R2/MinIO adapter at the storage boundary. Image normalization belongs to the upload service; the adapter stores validated bytes. No generator depends on a local public URL.

Current regeneration removes old database file associations but retains unreferenced disk bytes. Add a reference-aware retention/garbage-collection command before sustained production usage. Failed generation can similarly leave orphaned files; committed output metadata remains consistent.

## Extending the MVP

Add a generator class, register it, provide an HTML template and insert template metadata through a migration/bootstrap update. The frontend obtains available output types from the API. Add new input connectors by mapping them to `ItemInput`; do not add Excel assumptions to generators. Future roles can extend the authenticated-user dependency. None of these future modules is implemented here.

## Operational limits

One administrator and synchronous generation are deliberate MVP choices. Login throttling is in-process; a multi-worker or multi-instance deployment needs shared throttling. Logout increments the user's token version and revokes all active sessions for that administrator. Lists are currently unpaginated. Large image-heavy projects require capacity testing and eventually a worker queue. Template/configuration changes are trusted server administration, not an end-user editor.

PyMuPDF is distributed under AGPL/commercial terms; assess your distribution model before commercial closed-source deployment, or replace the banner rasterizer with a compatible PDFium adapter. The renderer is isolated in `generation/engine.py`. Other third-party notices are included with their assets.
