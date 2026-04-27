#!/usr/bin/env bash
#
# One-command bootstrap: Docker, clone (optional), .env, Cloudflare DNS-01 TLS, compose up.
# Target OS: Ubuntu 20.04 / 22.04 (root or sudo for Docker).
#
set -euo pipefail

REPO_NAME_HINT="bango-lab"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf "\033[0;32m[install]\033[0m %s\n" "$*"; }
err() { printf "\033[0;31m[error]\033[0m %s\n" "$*" >&2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "missing: $1"
    exit 1
  fi
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi
  log "Docker not found — installing (official convenience script)…"
  require_cmd curl
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
  log "Add your user to group docker: sudo usermod -aG docker \"\$USER\" (then re-login)"
}

ensure_docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    return 0
  fi
  err "docker compose v2 is required. Install Docker Engine from get.docker.com"
  exit 1
}

install_gettext() {
  if ! command -v envsubst >/dev/null 2>&1; then
    log "installing gettext-base (envsubst)…"
    if command -v apt-get >/dev/null 2>&1; then
      if [ "$(id -u)" -eq 0 ]; then
        apt-get update -y && apt-get install -y gettext-base
      else
        sudo apt-get update -y && sudo apt-get install -y gettext-base
      fi
    else
      err "Please install envsubst (gettext) manually."
      exit 1
    fi
  fi
}

prompt() {
  local var="$1" prompt="$2" default="${3-}"
  local val
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default]: " val || true
    val="${val:-$default}"
  else
    read -r -p "$prompt: " val || true
  fi
  printf %s "$val"
}

# If something already listens on 80/443 (aaPanel, Apache, host Nginx), use alternate host ports.
suggest_nginx_host_ports() {
  local pub_http=80 pub_https=443
  if ! command -v ss >/dev/null 2>&1; then
    printf %s "%s" "$pub_http $pub_https"
    return
  fi
  # Match listeners ending in :80 or :443 (IPv4/IPv6)
  if ss -tln 2>/dev/null | awk 'NR>1 {print $4}' | grep -qE ':80$'; then
    pub_http=8080
  fi
  if ss -tln 2>/dev/null | awk 'NR>1 {print $4}' | grep -qE ':443$'; then
    pub_https=8443
  fi
  printf %s "%s" "$pub_http $pub_https"
}

# --- main flow ---
[ -f "$SCRIPT_DIR/docker-compose.yml" ] || { err "Run from repository root (docker-compose.yml missing)."; exit 1; }

install_docker
ensure_docker_compose
install_gettext
require_cmd git
require_cmd openssl
require_cmd curl

if [ -d "$SCRIPT_DIR/.git" ]; then
  log "Repository already present at $SCRIPT_DIR (skip clone)"
  REPO_ROOT="$SCRIPT_DIR"
else
  GITHUB_URL="$(prompt GITHUB "GitHub repository URL (https://github.com/… .git)" "")"
  if [ -z "$GITHUB_URL" ]; then
    err "Clone required: no .git in $SCRIPT_DIR"
    exit 1
  fi
  PARENT="$(dirname "$SCRIPT_DIR")"
  log "Cloning into $PARENT/$REPO_NAME_HINT …"
  git clone "$GITHUB_URL" "$PARENT/$REPO_NAME_HINT"
  REPO_ROOT="$PARENT/$REPO_NAME_HINT"
  err "Re-run install.sh from the cloned path: $REPO_ROOT/install.sh"
  exit 0
fi

cd "$REPO_ROOT"

# Non-interactive: export INSTALL_NONINTERACTIVE=1, DOMAIN, EMAIL_LE (or LETSENCRYPT_EMAIL), CF_TOKEN (or CLOUDFLARE_API_TOKEN)
OW=0
if [ -n "${INSTALL_NONINTERACTIVE:-}" ] && [ "$INSTALL_NONINTERACTIVE" != "0" ]; then
  CF_TOKEN="${CF_TOKEN:-${CLOUDFLARE_API_TOKEN:-}}"
  if [ -z "$CF_TOKEN" ]; then
    err "Non-interactive: set CF_TOKEN or CLOUDFLARE_API_TOKEN (Cloudflare DNS-01)"
    exit 1
  fi
  if [ -f .env ] && [ "${REGENERATE_ENV:-0}" != "1" ]; then
    set -a && source .env && set +a
    [ -n "${DOMAIN:-}" ] && [ -n "${EMAIL_LE:-}" ] || { err ".env is missing DOMAIN or EMAIL_LE; set REGENERATE_ENV=1 to recreate"; exit 1; }
    log "Non-interactive: reusing .env; refreshing secrets/cf.ini only"
  else
    DOMAIN="${DOMAIN:-}"
    EMAIL_LE="${EMAIL_LE:-${LETSENCRYPT_EMAIL:-}}"
    if [ -z "$DOMAIN" ] || [ -z "$EMAIL_LE" ]; then
      err "Non-interactive: set DOMAIN, EMAIL_LE (or LETSENCRYPT_EMAIL) when creating .env, or use existing .env (omit REGENERATE_ENV)"
      exit 1
    fi
    OW=1
  fi
else
  if [ -f .env ]; then
    read -r -p "Regenerate .env and database passwords? [y/N] " ow_ans || true
    case "${ow_ans:-n}" in y|Y) OW=1 ;; esac
  fi
  if [ ! -f .env ] || [ "$OW" = 1 ]; then
    export DOMAIN
    DOMAIN="$(prompt DOMAIN "Full domain (API token must manage DNS for this name)" "lab.example.com")"
    EMAIL_LE="$(prompt EMAIL "Email for Let's Encrypt" "admin@example.com")"
  else
    # shellcheck disable=SC1091
    set -a && source .env && set +a
    log "Using DOMAIN and Email from existing .env"
  fi
  CF_TOKEN="$(prompt CF "Cloudflare API token (Zone.DNS:Edit)" "")"
  if [ -z "$CF_TOKEN" ]; then
    err "Cloudflare token is required for DNS-01."
    exit 1
  fi
fi
if [ ! -f .env ] || [ "$OW" = 1 ]; then
  POSTGRES_PASSWORD="$(openssl rand -base64 32 | tr -d '\n')"
  DJANGO_SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n')"
  read -r HTTP_PUBLISH HTTPS_PUBLISH <<<"$(suggest_nginx_host_ports)"
  if [ "$HTTP_PUBLISH" != 80 ] || [ "$HTTPS_PUBLISH" != 443 ]; then
    log "Host ports 80/443 look busy; using HTTP_PUBLISH=$HTTP_PUBLISH HTTPS_PUBLISH=$HTTPS_PUBLISH (set reverse proxy to 127.0.0.1:$HTTP_PUBLISH and :$HTTPS_PUBLISH or only HTTPS)."
  fi
  cat > .env <<EOF
DOMAIN=$DOMAIN
POSTGRES_USER=lab
POSTGRES_DB=lab
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1
EMAIL_LE=$EMAIL_LE
# Host ports for Nginx (80/443 if free; else 8080/8443 with aaPanel or similar on 80/443)
HTTP_PUBLISH=$HTTP_PUBLISH
HTTPS_PUBLISH=$HTTPS_PUBLISH
EOF
  chmod 600 .env
  log "Wrote .env (secrets inside — keep private)"
fi
# shellcheck disable=SC1091
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
DOMAIN="${DOMAIN:-}"
[ -n "$DOMAIN" ] || { err "DOMAIN missing in .env"; exit 1; }
[ -n "${EMAIL_LE:-}" ] || { err "EMAIL_LE missing in .env (Let's Encrypt contact)"; exit 1; }

mkdir -p secrets keys_only
umask 077
printf 'dns_cloudflare_api_token = %s\n' "$CF_TOKEN" > secrets/cf.ini
printf '# generated\n' > secrets/.gitkeep 2>/dev/null || true
log "Wrote secrets/cf.ini (mode 600 recommended)"

# Bango: browser uses public.pem baked into the flask image; server uses private_demo.pem (mount). Generate if missing.
if [ ! -f "$REPO_ROOT/keys_only/private_demo.pem" ] || [ ! -f "$REPO_ROOT/frontend/static/keys/public.pem" ]; then
  if [ -x "$REPO_ROOT/gen_keys.sh" ]; then
    log "Generating Bango RSA keypair (./gen_keys.sh)…"
    (cd "$REPO_ROOT" && ./gen_keys.sh)
  else
    err "Run chmod +x gen_keys.sh; keys for encrypted PII are required before build."
    exit 1
  fi
fi

# --- build app images first ---
log "docker compose build…"
docker compose build

# --- data stack (no Nginx until certs exist) ---
log "Starting postgres, redis, flask, django…"
docker compose up -d postgres redis
sleep 2
docker compose up -d flask django

# --- Let's Encrypt (DNS-01) ---
log "Requesting certificate for $DOMAIN (Cloudflare DNS)…"
if ! docker compose run --rm \
  certbot certonly \
  --non-interactive --agree-tos \
  -m "$EMAIL_LE" \
  --dns-cloudflare --dns-cloudflare-credentials /run/secrets/cf.ini \
  -d "$DOMAIN"; then
  err "Certbot failed. Check: token scopes, API DNS edit for zone, DOMAIN matches zone."
  err "Nginx with TLS was not started."
  exit 1
fi

# --- Nginx (needs certs on shared volume) ---
export DOMAIN
chmod +x "$REPO_ROOT/deploy/render-nginx.sh" 2>/dev/null || true
bash "$REPO_ROOT/deploy/render-nginx.sh"

if ! docker compose up -d nginx; then
  err "Nginx failed. If you see 'address already in use' on :80 or :443, set alternate host ports, then start Nginx again:"
  err "  sed -i.bak 's/^HTTP_PUBLISH=.*/HTTP_PUBLISH=8080/;s/^HTTPS_PUBLISH=.*/HTTPS_PUBLISH=8443/' .env && docker compose up -d nginx"
  err "  Then point the panel (aaPanel) reverse proxy to 127.0.0.1:8080 and 127.0.0.1:8443 (or HTTPS only)."
  err "If TLS path errors, verify /etc/letsencrypt on the certbot volume."
  exit 1
fi

log "Done."
log "  • HTTPS: https://$DOMAIN/"
log "  • Django: https://$DOMAIN/d/"
log "  • Cloudflare: use Full (strict) — origin has a valid cert now."
log "  • Renew: add cron: docker compose -f $REPO_ROOT/docker-compose.yml run --rm certbot renew"
log "  • Update: ./update.sh"
