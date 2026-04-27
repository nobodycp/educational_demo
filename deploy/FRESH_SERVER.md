# Fresh server install (from zero)

This is the same stack as [install.sh](../install.sh) in the repo. Most “extra” work on a busy VPS comes from **another panel** (e.g. aaPanel) already binding **:80 / :443**, or from **Cloudflare** / **reverse proxy** — not from “Docker” itself.

## Before you start

1. **One** DNS **A** record: `yourdomain.com` → **new server public IPv4** (and `www` if you use it). Wait until it resolves.
2. **Cloudflare** API token: **Zone → DNS → Edit** for the zone of your domain.
3. **One directory only** for the app (e.g. `/root/educational_demo` or `/opt/educational_demo`). **Do not** `git clone` inside an existing clone.
4. Decide: **(A)** this server is **dedicated** to the lab (simplest: nothing else on 80/443), or **(B)** **aaPanel** (or another Nginx) already uses 80/443 — then you will use **HTTP_PUBLISH=8080** and **HTTPS_PUBLISH=8443** and a **reverse proxy** from the domain to `127.0.0.1:8443` with the correct **Host** header.

## One command (new server, non-interactive)

**Before:** A record: `yourdomain` → this server. Cloudflare **Zone.DNS:Edit** token.

**On the server (root, Ubuntu/Debian):** set variables, then pipe `bootstrap` (it clones/updates, runs `install.sh` with `INSTALL_NONINTERACTIVE=1`, runs `gen_keys` if needed, `docker compose build`, TLS, Nginx). **Do not** put the token in the `curl` line in shared environments; use a root shell, export, then `curl`.

```bash
export DOMAIN=lab.example.com
export EMAIL_LE=admin@you.com
export CF_TOKEN=YourCloudflareAPIToken
curl -fsSL https://raw.githubusercontent.com/nobodycp/educational_demo/main/deploy/bootstrap.sh | bash
```

- Optional: `EDU_DEMO_DIR=/opt/edu-demo` to choose install path; default: `$HOME/educational_demo`.
- If 80/443 are busy, `install.sh` will pick 8080/8443; then set reverse proxy in your panel to `https://127.0.0.1:8443` with correct **Host** (see top of this file).

**Interactive** (prompts) instead: `git clone … && ./install.sh` (no `INSTALL_NONINTERACTIVE`).

## Clean install (manual / step by step)

```bash
# 1) OS packages (Debian/Ubuntu)
apt-get update && apt-get install -y git curl ca-certificates

# 2) Clone once
cd /root
git clone https://github.com/nobodycp/educational_demo.git
cd educational_demo
chmod +x install.sh update.sh deploy/render-nginx.sh deploy/teardown.sh gen_keys.sh

# 3) install.sh (interactive) or non-interactive exports + ./install.sh; keys: install runs gen_keys if missing
./install.sh

# 4) If you ran gen_keys after first build, rebuild flask so public.pem is in the image
docker compose build --no-cache flask
docker compose up -d
```

## After `install.sh`

- **HTTPS:** `https://YOURDOMAIN/`
- **Django:** `https://YOURDOMAIN/d/`
- If Nginx is on **8080/8443** (aaPanel on 80/443): in the panel, create the site and set **reverse proxy** target to `https://127.0.0.1:8443`, **Sent domain** = `$host` or your FQDN. Enable `proxy_ssl_verify` off / SNI to upstream if the panel offers it, when proxying to HTTPS on localhost.
- **Do not** point the site vhost at **wwwroot** PHP only — all paths (`/`, `/api/...`, `/static/...`) must reach the app unless you have split locations by design (advanced).

## Ongoing updates

```bash
cd /path/to/educational_demo
git pull
./update.sh
```

## Full reset (this project’s Docker data only)

```bash
cd /path/to/educational_demo
./deploy/teardown.sh
# then re-run ./install.sh or bring stack back after fixing .env
```

## If you “reset” only Docker but keep the clone

- Reinstall engine: `curl -fsSL https://get.docker.com | sh`
- In the repo: `docker compose build && docker compose up -d`
- **Keys:** `private_demo.pem` on disk must still match the **public** baked into the **flask** image; if you re-run `gen_keys.sh`, always **`docker compose build flask`** and **`up`**.

## Checklist to avoid the usual pain

| Issue | Avoid |
|--------|--------|
| Nested folders `educational_demo/educational_demo` | **One** `git clone` in an empty parent directory |
| Port 80 in use | **HTTP_PUBLISH/HTTPS_PUBLISH** in `.env` or `install` detection; reverse-proxy to those ports |
| 502 to Flask after `compose restart` | **Pulled** image after `7bfcb88` (Nginx re-resolves Docker DNS) or **restart nginx** after flask restarts on older configs |
| “decode envelope” / PII errors | **Same** `gen_keys` run for **both** files; then **`docker compose build flask`** |
| `Unexpected token '<'` in browser | **API** returns **HTML** (404/502 page). Ensure **/api** hits Flask (one reverse proxy for the whole site) |
| `curl` to `https://127.0.0.1:8443` with SSL error | Use **`curl -k`** or `--resolve FQDN:8443:127.0.0.1` and `https://FQDN:8443/...` — cert is for the **domain name**, not for `127.0.0.1` |
