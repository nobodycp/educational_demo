# Coolify deploy (single app, no docker-compose)

This project can run on Coolify as a single Dockerized Flask/Gunicorn app.

## 1) Create Application in Coolify

- **Source:** GitHub repository
- **Branch:** `pre-docker` (or your working branch)
- **Build Pack:** Dockerfile
- **Dockerfile path:** `./Dockerfile`
- **Port:** `5000`

## 2) Environment Variables (minimum)

Set these in Coolify -> Application -> **Environment Variables** (Runtime):

- `FLASK_SECRET_KEY` = long random string
- `HANDOFF_SECRET` = long random string
- `COOKIE_SECURE` = `1`
- `STRICT_ORIGIN` = `1` (recommended when behind single domain)

Optional (if used):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_THREAD_ID`
- `ACTIVE_THEME` = `default` or `post_pyment` (UI theme; spelling must match `config/prebuilt_themes.json`)

**Coolify env notes:**
- Use **Runtime** environment variables (not Build-only) so Gunicorn sees them.
- After changing any variable, click **Save** then **Redeploy**.
- Coolify injects these into the container as process env — no `.env` file is required inside Docker.
- On startup, logs show: `Billing UI theme: post_pyment (ACTIVE_THEME env='post_pyment')`.
- Common mistake: use `post_pyment` (folder name) or `post_payment` (alias).

## 3) Domain + SSL

- Add your application domain in Coolify (for example `app.example.com`)
- Enable HTTPS/SSL in Coolify for that domain

## 4) Keys for encrypted PII (important)

`/api/demo/register` expects a private key at `keys_only/private_demo.pem`.

- Keep `private_demo.pem` out of git.
- In Coolify, mount a persistent volume or file to:
  - `/app/keys_only/private_demo.pem`
- Ensure the matching public key is in repo at:
  - `frontend/static/keys/public.pem`
- Generate matching pair locally with:
  - `./gen_keys.sh`

If private key is missing or mismatched, registration returns:
`bad_encrypted_pii`.

## 5) Update flow

- Push code to GitHub
- In Coolify: click **Deploy** (or enable auto-deploy webhook)

