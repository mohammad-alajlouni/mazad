#!/usr/bin/env bash
# Install from this folder on the existing Mazad host as root.
set -Eeuo pipefail
cd "$(dirname "$0")"
id mazad-hook >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin mazad-hook
install -d -m 700 /etc/mazad /var/lib/mazad-deploy /var/lib/mazad-deploy/releases /var/backups/mazad
install -d -m 700 -o mazad-hook -g mazad-hook /var/lib/mazad-webhook /var/lib/mazad-webhook/seen
install -d -m 755 /usr/local/lib/mazad-deploy
install -m 755 deploy.sh /usr/local/lib/mazad-deploy/deploy.sh
install -m 644 receiver.py worker.py /usr/local/lib/mazad-deploy/
install -m 644 mazad-webhook.service mazad-deploy.service /etc/systemd/system/
install -m 600 compose.server.yaml /etc/mazad/compose.server.yaml
if [[ ! -f /etc/mazad/webhook.env ]]; then
    python3 - <<'PY'
import secrets
from pathlib import Path
p = Path('/etc/mazad/webhook.env')
p.write_text('WEBHOOK_SECRET=' + secrets.token_hex(32) + '\nWEBHOOK_REPOSITORY=mohammad-alajlouni/mazad\nWEBHOOK_BIND=172.17.0.1\nWEBHOOK_SPOOL=/var/lib/mazad-webhook\n')
p.chmod(0o600)
PY
fi
python3 - <<'PY'
from pathlib import Path
s = Path('/opt/mazad/deploy/nginx.conf').read_text()
hook = '''    location = /hooks/github {
        limit_req zone=github_webhook burst=20 nodelay;
        limit_req_status 429;
        client_max_body_size 25m;
        proxy_pass http://host.docker.internal:9000;
        proxy_set_header Host $host;
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }
'''
s = 'limit_req_zone $binary_remote_addr zone=github_webhook:1m rate=10r/m;\n' + s.replace('    location /api/ {', hook + '    location /api/ {')
Path('/etc/mazad/nginx.conf').write_text(s)
PY
if [[ ! -d /var/lib/mazad-deploy/repository ]]; then
    git clone --no-checkout https://github.com/mohammad-alajlouni/mazad.git /var/lib/mazad-deploy/repository
fi
if [[ ! -f /var/lib/mazad-deploy/current ]]; then
    docker tag mazad-backend:latest mazad-backend:initial
    docker tag mazad-frontend:latest mazad-frontend:initial
    printf 'initial\n' > /var/lib/mazad-deploy/current
fi
systemctl daemon-reload
systemctl enable --now mazad-webhook.service mazad-deploy.service
tag=$(cat /var/lib/mazad-deploy/current)
directory=/var/lib/mazad-deploy/releases/$tag
if [[ "$tag" == initial ]]; then directory=/opt/mazad; fi
MAZAD_RELEASE="$tag" docker compose --project-directory "$directory" --env-file /opt/mazad/.env \
    -p mazad -f "$directory/compose.yaml" -f /etc/mazad/compose.server.yaml up -d --no-build --wait
docker exec mazad-nginx-1 nginx -t
docker exec mazad-nginx-1 nginx -s reload
