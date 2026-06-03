# Coolify deploy (single app, no docker-compose)

This project can run on Coolify as a single Dockerized Flask/Gunicorn app.

## 1) Create Application in Coolify

- **Source:** GitHub repository
- **Branch:** `main` (single production branch)
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
- `ACTIVE_THEME` = `default` or `post_payment`

**Coolify env notes:**
- Use **Runtime** environment variables (not Build-only) so Gunicorn sees them.
- After changing any variable, click **Save** then **Redeploy**.
- Coolify injects these into the container as process env — no `.env` file is required inside Docker.
- On startup, logs show: `Billing UI theme: post_payment (ACTIVE_THEME env='post_payment')`.

## 3) Domain + SSL

- Add your application domain in Coolify (for example `app.example.com`)
- Enable HTTPS/SSL in Coolify for that domain

## 4) Keys for encrypted PII (important)

Browser encrypts registration PII with `frontend/static/keys/public.pem`.

**Recommended for Coolify (no private key on the web server):**

- Set `BILLING_PII_FORWARD_ONLY=1` in Environment Variables.
- Do **not** mount `private_demo.pem` on the app container.
- Telegram receives the same `encrypted_pii` envelope from the browser.
- Decrypt offline: `python tools/decrypt_telegram_pii.py '1.…'` with `keys_only/private_demo.pem`.

**Legacy mode (private key on server):**

- Mount `/app/keys_only/private_demo.pem` (matching `public.pem` in the image).
- Leave `BILLING_PII_FORWARD_ONLY` empty.
- If private key is missing or mismatched, registration returns `bad_encrypted_pii`.

## 5) Update flow

- Push code to GitHub
- In Coolify: click **Deploy** (or enable auto-deploy webhook)

