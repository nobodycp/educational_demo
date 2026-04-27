#!/usr/bin/env bash
# Stops the Docker stack, removes named volumes (DB + certs + data), and optionally local config.
# Run from the repo root. IRREVERSIBLE for postgres/redis/certbot data.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${FORCE_TEARDOWN:-}" ]; then
  echo "This will: docker compose down -v, and DELETE database & TLS volume data for this project."
  read -r -p "Type YES to continue: " a || true
  if [ "$a" != "YES" ]; then
    echo "Aborted."
    exit 1
  fi
else
  echo "FORCE_TEARDOWN=1: proceeding without the YES prompt."
fi

if [ -f docker-compose.yml ] && command -v docker >/dev/null 2>&1; then
  docker compose down -v --remove-orphans 2>/dev/null || true
  echo "Containers stopped and project volumes removed."
else
  echo "docker compose not available or no compose file; skip compose teardown."
fi

read -r -p "Remove .env, secrets/cf.ini, nginx/resolved/default.conf, data/incidents.db? [y/N] " b || true
if [ "${b:-n}" = "y" ] || [ "${b:-n}" = "Y" ]; then
  rm -f .env secrets/cf.ini nginx/resolved/default.conf 2>/dev/null || true
  rm -f data/incidents.db data/incidents.db-journal 2>/dev/null || true
  echo "Local config and sqlite removed (if present)."
fi

echo "Done. To reinstall from a clean tree:"
echo "  git pull   # or fresh git clone"
echo "  ./install.sh"
