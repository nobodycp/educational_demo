# Flask lab app (Gunicorn)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

# Project tree
COPY wsgi.py app.py ./
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY tools/ ./tools/
# keys_only/ is not in git (private PEM is gitignored). Empty dir; bind-mount ./keys_only at runtime.
# Writable data (SQLite, incidents) — use volume
RUN adduser --disabled-password --gecos "" --uid 1000 app \
    && mkdir -p /app/data /app/keys_only && chown -R app:app /app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:5000/" -o /dev/null || exit 1

CMD ["gunicorn", "wsgi:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
