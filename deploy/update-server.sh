#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

before="$(git rev-parse HEAD)"
git fetch origin new-design
git merge --ff-only origin/new-design
after="$(git rev-parse HEAD)"

services=()
if [[ "$before" != "$after" ]]; then
  changed="$(git diff --name-only "$before" "$after")"
  if grep -qE '^(backend/|compose\.yml$)' <<<"$changed"; then
    services+=(backend)
  fi
  if grep -qE '^(frontend/|compose\.yml$)' <<<"$changed"; then
    services+=(frontend)
  fi
  if grep -qE '^(deploy/Caddyfile|compose\.yml$)' <<<"$changed"; then
    services+=(caddy)
  fi
fi

if ((${#services[@]})); then
  docker compose up -d --build "${services[@]}"
else
  echo "کد تازه‌ای برای ساخت وجود ندارد."
fi

docker compose exec -T backend python - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8080/api/health", timeout=10) as response:
    health = json.load(response)
if health != {"ok": True}:
    raise SystemExit(f"health check failed: {health!r}")
print("سلامت بک‌اند تأیید شد.")
PY

docker compose ps
printf 'نسخهٔ فعال: %s\n' "$after"
