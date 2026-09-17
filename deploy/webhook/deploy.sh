#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
exec 9>/var/lib/mazad-deploy/deploy.lock
flock -x 9
export GIT_TERMINAL_PROMPT=0
repo=/var/lib/mazad-deploy/repository
state=/var/lib/mazad-deploy
git -C "$repo" fetch --prune origin '+refs/heads/main:refs/remotes/origin/main'
sha=$(git -C "$repo" rev-parse refs/remotes/origin/main)
previous=$(cat "$state/current")
if [[ "$sha" == "$previous" ]]; then
    echo "Already deployed $sha"
    exit 0
fi
release="$state/releases/$sha"
mkdir -p "$release"
git -C "$repo" archive "$sha" | tar -x -C "$release"
ln -sfn /opt/mazad/.env "$release/.env"
compose() {
    local tag=$1 directory=$2
    shift 2
    MAZAD_RELEASE="$tag" docker compose --project-directory "$directory" --env-file /opt/mazad/.env \
        -p mazad -f "$directory/compose.yaml" -f /etc/mazad/compose.server.yaml "$@"
}
previous_dir="$state/releases/$previous"
if [[ "$previous" == initial ]]; then previous_dir=/opt/mazad; fi
echo "Building $sha"
compose "$sha" "$release" build --pull
backup="/var/backups/mazad/$(date -u +%Y%m%dT%H%M%SZ)-$sha"
mkdir -p "$backup"
docker exec mazad-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup/database.sql.gz"
docker run --rm -v mazad_generated_storage:/data:ro -v "$backup:/backup" alpine:3.22 \
    tar -czf /backup/storage.tar.gz -C /data .
printf '%s\n' "$previous" > "$backup/previous-release"
echo "Activating $sha"
if compose "$sha" "$release" up -d --no-build --wait --wait-timeout 180 && \
   docker exec mazad-nginx-1 nginx -s reload && \
   curl --retry 5 --retry-all-errors --retry-delay 2 --max-time 15 -fsS http://127.0.0.1/api/health && \
   curl --retry 5 --retry-all-errors --retry-delay 2 --max-time 15 -fsS -o /dev/null http://127.0.0.1/; then
    printf '%s\n' "$sha" > "$state/current.new"
    mv "$state/current.new" "$state/current"
    echo "Successfully deployed $sha"
else
    echo "Activation failed; restoring application images for $previous (database migration is not reversed)" >&2
    compose "$previous" "$previous_dir" up -d --no-build --wait --wait-timeout 180
    docker exec mazad-nginx-1 nginx -s reload
    exit 1
fi
