# Fresh server install (from zero)

This is the same stack as [install.sh](../install.sh) in the repo. Most “extra” work on a busy VPS comes from **another panel** (e.g. aaPanel) already binding **:80 / :443**, or from **Cloudflare** / **reverse proxy** — not from “Docker” itself.

## Before you start

1. **One** DNS **A** record: `yourdomain.com` → **new server public IPv4** (and `www` if you use it). Wait until it resolves.
2. **Cloudflare** API token: **Zone → DNS → Edit** for the zone of your domain.
3. **One directory only** for the app (e.g. `/root/educational_demo` or `/opt/educational_demo`). **Do not** `git clone` inside an existing clone.
4. Decide: **(A)** this server is **dedicated** to the lab (simplest: nothing else on 80/443), or **(B)** **aaPanel** (or another Nginx) already uses 80/443 — then you will use **HTTP_PUBLISH=8080** and **HTTPS_PUBLISH=8443** and a **reverse proxy** from the domain to `127.0.0.1:8443` with the correct **Host** header.

## Clean install (recommended order)

```bash
# 1) OS packages (Debian/Ubuntu)
apt-get update && apt-get install -y git curl ca-certificates

# 2) Clone once
cd /root   # or /opt
git clone https://github.com/nobodycp/educational_demo.git
cd educational_demo
chmod +x install.sh update.sh deploy/render-nginx.sh deploy/teardown.sh

# 3) RSA keys (one run — private never goes to git)
./gen_keys.sh
# This writes keys_only/private_demo.pem and frontend/static/keys/public.pem (pair).

# 4) First-time install (Docker, .env, Cloudflare DNS-01, compose up)
./install.sh
# Answer DOMAIN = your FQDN, email, API token. If 80/443 are busy, install.sh may set 8080/8443 in .env.

# 5) Rebuild the Flask image so the NEW public.pem is inside the image
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
