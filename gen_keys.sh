#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/keys_only" "$ROOT/frontend/static/keys"
openssl genrsa -out "$ROOT/keys_only/private_demo.pem" 2048
openssl rsa -in "$ROOT/keys_only/private_demo.pem" -pubout -out "$ROOT/frontend/static/keys/public.pem"
echo "Generated keys_only/private_demo.pem and frontend/static/keys/public.pem"
