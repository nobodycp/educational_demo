#!/usr/bin/env bash
#
# One-liner (after exports): installs Docker deps, shallow-clone, runs install.sh in non-interactive mode.
# Must run on a clean Ubuntu/Debian as root (or with sudo for apt).
#
#   export DOMAIN=lab.example.com
#   export EMAIL_LE=you@example.com
#   export CF_TOKEN=...   # Cloudflare: Zone.DNS:Edit
#   curl -fsSL https://raw.githubusercontent.com/nobodycp/educational_demo/main/deploy/bootstrap.sh | bash
#
# Do not pass secrets in the same line as curl on multi-user systems (visible in ps); use a file or env from shell profile.
# DNS A record for DOMAIN must point to this server before certbot.
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/nobodycp/educational_demo.git}"
REPO_DIR="${EDU_DEMO_DIR:-$HOME/educational_demo}"
export DEBIAN_FRONTEND=noninteractive

if [ "$(id -u)" -eq 0 ]; then
  APT="apt-get"
else
  command -v sudo >/dev/null 2>&1 || { echo "Run as root or install sudo" >&2; exit 1; }
  APT="sudo apt-get"
fi

$APT update -y
$APT install -y git curl ca-certificates

if [ -d "$REPO_DIR/.git" ]; then
  echo "[bootstrap] updating $REPO_DIR"
  git -C "$REPO_DIR" pull --ff-only
else
  echo "[bootstrap] cloning into $REPO_DIR"
  git clone --depth=1 "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
chmod +x install.sh update.sh deploy/render-nginx.sh gen_keys.sh deploy/teardown.sh 2>/dev/null || true

export INSTALL_NONINTERACTIVE=1
exec ./install.sh
