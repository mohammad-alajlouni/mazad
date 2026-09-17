# Deployment and operations

## First deployment

1. Provision a Linux host with Docker/Compose, sufficient disk, and persistent backups. Start with a small single-instance deployment and measure generation memory/time with actual client workbooks.
2. Copy the repository and configure `.env`. Generate random secrets with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep `.env` readable only by the operator.
3. Set `CORS_ORIGINS` to the exact HTTPS application origin and `COOKIE_SECURE=true`.
4. Configure TLS termination using an existing ingress/reverse proxy or modify `deploy/nginx.conf` for your certificate. The supplied port 8080 HTTP endpoint is for local validation, not a finished public TLS configuration.
5. Run `docker compose up --build -d`. Confirm `docker compose ps`, `/api/health`, login, a real import and a complete generation/approval/download flow.
6. Insert client-approved templates, fonts, brand assets and mapping. Regulatory forms must receive client validation before real use.

Only Nginx exposes a host port. PostgreSQL and the backend stay on the Compose network. Backend/frontend containers run as non-root users. Private storage is outside the frontend document root. Database and generated-file volumes must both be backed up.

## Updates and migrations

Take a backup, review migrations, build the updated images and run Compose. Backend startup runs `alembic upgrade head` before accepting traffic. Use a coordinated maintenance window for schema changes; do not launch competing initializers across replicas. For a future larger deployment, move migration/bootstrap to a one-shot release job.

```sh
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

Never run destructive test fixtures against production. Downgrades can delete data; inspect migration code before use. The initial migration can create/drop the complete schema and is primarily a development rollback.

## Administrator password rotation

Update `ADMIN_PASSWORD` in `.env`, then recreate the backend so it sees the new value:

```sh
docker compose up -d --force-recreate backend
docker compose exec backend python -m app.manage reset-admin-password
```

The command reads the new password from the environment, hashes it, and revokes existing sessions. It does not print credentials. Changing `JWT_SECRET` also invalidates all sessions. AI credentials are similarly environment-only; restart after changes.

## Backups

```sh
# Run on the deployment host, protecting backup file permissions.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > database.sql
```

Use a volume-aware backup tool for `generated_storage` at the same time. Store encrypted backups off-host and test restores into a separate environment. Do not include credentials in logs or version control. Old unreferenced generated files currently require retention cleanup; do not delete keys still referenced by project images, settings or generated files.

## Monitoring

Health: `/api/health` includes a database query. Backend logs contain authentication failure notices, import/generation/approval activity and sanitized failure types. Application audit records are visible on the dashboard. Watch disk usage, generation duration, memory, 5xx rates and AI timeouts. Set proxy timeouts and upload limits to match the actual deployment.

## Client handover

Obtain representative Excel files (including edge cases), all eight final templates, official form wording, field mappings, brand assets and licensed fonts, real images and rights, optional AI API credentials/model, and hosting/TLS requirements. Test Arabic/RTL, long text, tables, image-heavy projects, financial units and decimal conventions with these actual assets before a public release.

Out of scope: advanced RBAC, multi-tenancy, freelancer management, social publishing, browser extensions, billing, vector search and custom model training.
