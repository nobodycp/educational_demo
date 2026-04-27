#!/usr/bin/env bash
# Render Nginx vhost: only ${DOMAIN} is replaced (keeps Nginx $variables intact).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DOMAIN
if [ -z "${DOMAIN:-}" ]; then
  echo "set DOMAIN=example.com" >&2
  exit 1
fi
if ! command -v envsubst >/dev/null; then
  echo "install gettext (envsubst), e.g. apt install -y gettext-base" >&2
  exit 1
fi
mkdir -p "$ROOT/nginx/resolved"
# shellcheck disable=SC2016
envsubst '$DOMAIN' < "$ROOT/nginx/default.conf.in" > "$ROOT/nginx/resolved/default.conf"
echo "Wrote $ROOT/nginx/resolved/default.conf (DOMAIN=$DOMAIN)"
