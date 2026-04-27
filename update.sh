#!/usr/bin/env bash
# Pull, rebuild, Django migrate + collectstatic, restart stack (run from repo root after install.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ ! -f .env ]; then
  echo "Missing .env — run ./install.sh first" >&2
  exit 1
fi
# shellcheck disable=SC1091
set -a && source .env && set +a

if [ -d .git ] && [ "${SKIP_GIT_PULL:-0}" != "1" ]; then
  echo "[update] git pull"
  git pull --ff-only origin "${GIT_BRANCH:-main}" 2>/dev/null || git pull --ff-only || true
fi

echo "[update] docker compose build"
docker compose build

echo "[update] up -d (rolling)"
docker compose up -d

if docker compose ps -q django >/dev/null 2>&1; then
  echo "[update] Django migrate + collectstatic"
  docker compose exec -T django python /srv/django/manage.py migrate --noinput
  docker compose exec -T django python /srv/django/manage.py collectstatic --noinput 2>/dev/null || true
fi

echo "[update] done."
docker compose ps
