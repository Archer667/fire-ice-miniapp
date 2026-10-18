#!/usr/bin/env bash
set -euo pipefail

# Run from any directory; never read an environment file as executable code.
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
fail() { printf '%s\n' "$*" >&2; exit 1; }

[[ -f backend/web_auth.py && -f compose.yml && -f deploy/Caddyfile ]] || fail 'This is not the Valyria Web App source folder.'
command -v docker >/dev/null || fail 'Docker is missing. Ask your server provider to install Docker Engine and the Docker Compose plugin first.'
docker compose version >/dev/null || fail 'The Docker Compose plugin is missing.'
docker info >/dev/null || fail 'Docker is not running or this account cannot access it.'

if [[ -f .env ]]; then
    HOST=$(sed -n 's/^APP_HOST=//p' .env | tr -d '\r')
    [[ $# -eq 0 || "$1" == "$HOST" ]] || fail 'The existing address differs. No settings were changed. Update the address deliberately before rerunning.'
    grep -qxF 'DB_NAME=valyria_web_app' <(tr -d '\r' < .env) || fail 'Unexpected database name. Review .env before continuing.'
    grep -qxF 'MONGODB_URI=mongodb://mongodb:27017' <(tr -d '\r' < .env) || fail 'Unexpected database connection. Review .env before continuing.'
    grep -qxF 'WEB_COOKIE_SECURE=true' <(tr -d '\r' < .env) || fail 'Secure cookies must remain enabled.'
    grep -qxF "PUBLIC_APP_ORIGIN=https://$HOST" <(tr -d '\r' < .env) || fail 'The public origin does not match the address.'
else
    HOST=${1:-}
    if [[ -z "$HOST" ]]; then
        read -r -p 'Game domain, without https:// (for example play.yourdomain.ir): ' HOST
    fi
fi

[[ ${#HOST} -le 253 && "$HOST" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$ ]] || fail 'Enter a domain or subdomain only, without https://, a port or a path.'
[[ "$HOST" != *example.* && "$HOST" != localhost ]] || fail 'Use your actual public domain.'

if [[ ! -f .env ]]; then
    # Refuse a second installation sharing this Compose project and its database.
    [[ -z "$(docker ps -aq --filter label=com.docker.compose.project=valyria-web-app)" ]] || fail 'A Valyria Web App installation already exists. Locate its original folder; do not create another configuration.'
    [[ -z "$(docker volume ls -q --filter label=com.docker.compose.project=valyria-web-app)" ]] || fail 'Existing Valyria data was found. Locate the original installation before proceeding.'
    (umask 077; set -o noclobber; cat > .env <<EOF
APP_HOST=$HOST
PUBLIC_APP_ORIGIN=https://$HOST
MONGODB_URI=mongodb://mongodb:27017
DB_NAME=valyria_web_app
WEB_COOKIE_SECURE=true
EOF
    )
fi

printf '%s\n' 'Building and starting Valyria Web App. The first build requires access to package and Docker image repositories.'
docker compose config --quiet
docker compose up -d --build

printf '%s\n' 'Checking backend readiness...'
docker compose exec -T backend python - <<'PY'
import time
import urllib.request
for attempt in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3) as response:
            if response.status == 200:
                break
    except Exception:
        pass
    time.sleep(2)
else:
    raise SystemExit('Backend is not ready. Run: docker compose logs --tail=80 backend mongodb')
PY

printf '\n%s\n' "Services are running. Public address: https://$HOST" \
    'DNS must point to this server and TCP ports 80 and 443 must be reachable for the HTTPS certificate.' \
    'For a fresh installation, create the main administrator with:' \
    'docker compose exec backend python -m web_auth bootstrap-admin' \
    'Save the recovery code displayed by that command.' \
    'Before inviting players, open the HTTPS address and check login and notifications.' \
    'Keep database backups outside this server. Do not remove Docker volumes during updates.'
