# Automatic deployment on the educational server

Repository: `mohammad-alajlouni/mazad`. Deployment branch: `main`.
Application: http://148.230.111.160

## GitHub Actions

The active deployment path is `.github/workflows/deploy.yml`. Every push to `main`
starts **Deploy Kutayyib** in the repository Actions tab. Manual runs are supported
through **Run workflow** on `main`. The production environment links to the live site.
Build output, backup/activation messages, health checks and failures appear in the run.

Actions connects over SSH using `MAZAD_DEPLOY_SSH_KEY` and the pinned host key in
`MAZAD_DEPLOY_KNOWN_HOSTS` (repository Actions secrets). The dedicated SSH key is
restricted in the server's `authorized_keys` to the deployment script with a 30-minute
time limit; it cannot open an interactive shell, forward ports or execute other commands.
The server password is not stored in GitHub. To rotate access, replace this dedicated
public key on the server and update the private-key secret.

Actions serializes production jobs without cancelling a deployment in progress. The
server also takes a deployment lock and fetches the latest `main`; queued runs converge
to current main. The log reports the actual deployed SHA, which can be newer than the
commit that triggered a queued run. An already-deployed SHA is a successful no-op.

The previous direct GitHub webhook (ID `681048495`) is disabled, and its systemd
receiver/worker are stopped and disabled to avoid duplicate triggers. Their source is
retained for reference. Historical webhook deployments do not appear as Actions runs.
`last-deployment.json` is a legacy webhook record; Actions is the current run history,
and `/var/lib/mazad-deploy/current` identifies the active release.

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
cat /var/lib/mazad-deploy/current
# Retry or deploy latest main manually (uses the same deployment lock):
/usr/local/lib/mazad-deploy/deploy.sh
```

Release source lives in `/var/lib/mazad-deploy/releases/<sha>`; `/opt/mazad/.env` is the
shared application configuration. Compose project remains `mazad`. Server override and
Nginx configuration are under `/etc/mazad`. Do not run the old Compose override to update
this installation: use Actions or the deployment script. Host integration scripts are installed
under `/usr/local/lib/mazad-deploy`; repository changes to these scripts require an explicit
operator installation via `deploy/webhook/install.sh` and service restart.

Monitor disk usage: release images and backups are retained for rollback and are not
automatically deleted. Backups are on the same host; off-host backup is not configured.
GitHub repository is currently public, so the server fetches without a personal token.
If changed to private, configure a read-only deploy key before further deployments.

Receiver checks: `python3 -m unittest discover -s deploy/webhook -p 'test_*.py'`.
