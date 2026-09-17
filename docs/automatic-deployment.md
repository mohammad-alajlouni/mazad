# Automatic deployment on the educational server

Repository: `mohammad-alajlouni/mazad`. Deployment branch: `main`.
Application: http://148.230.111.160
Webhook: `http://148.230.111.160/hooks/github` (GitHub push event).

Push to `main` to deploy. Other branches and branch deletion are ignored.
The receiver verifies GitHub's HMAC-SHA256 signature and repository before queueing work.
It runs as an unprivileged account without Docker access. Port 9000 binds only to
the Docker host bridge; Nginx exposes the signed endpoint on port 80.
The secret is stored outside Git in `/etc/mazad/webhook.env` with mode 600.
This server currently uses HTTP; configure trusted TLS when a domain is available.

A separate systemd worker serializes deployments. Each deployment fetches the latest
`main`, so overlapping or late push events converge to current main instead of deploying
an older commit. Duplicate delivery IDs are ignored. Pending work survives restart.
The receiver returns 202 immediately; this means accepted, not deployment completed.

Images are tagged with the full commit SHA and built before switching the live application.
The existing database and generated-file volumes are retained. Database and file snapshots
are created in `/var/backups/mazad` before activation. API and homepage health checks run
after startup; failed activation restores previous application images. Database migrations
are **not** reversed automatically: a breaking migration may require restoring the backup.
Building or backing up unsuccessfully leaves the previous version running. A failed job
is recorded; use a new push or the manual command below to retry. Updates can cause a brief
interruption; this is a single-host deployment, not a zero-downtime cluster.

## Operations (SSH on server)

```sh
systemctl status mazad-webhook mazad-deploy
journalctl -u mazad-deploy -n 100 --no-pager
cat /var/lib/mazad-deploy/current
cat /var/lib/mazad-deploy/last-deployment.json
# Retry or deploy latest main manually (uses the same deployment lock):
/usr/local/lib/mazad-deploy/deploy.sh
```

Release source lives in `/var/lib/mazad-deploy/releases/<sha>`; `/opt/mazad/.env` is the
shared application configuration. Compose project remains `mazad`. Server override and
Nginx configuration are under `/etc/mazad`. Do not run the old Compose override to update
this installation: use the worker or deployment script. Host integration scripts are installed
under `/usr/local/lib/mazad-deploy`; repository changes to these scripts require an explicit
operator installation via `deploy/webhook/install.sh` and service restart.

Monitor disk usage: release images and backups are retained for rollback and are not
automatically deleted. Backups are on the same host; off-host backup is not configured.
GitHub repository is currently public, so the server fetches without a personal token.
If changed to private, configure a read-only deploy key before further deployments.

Receiver checks: `python3 -m unittest discover -s deploy/webhook -p 'test_*.py'`.
