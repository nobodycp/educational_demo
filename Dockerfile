FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-native.txt ./
RUN pip install --no-cache-dir -r requirements-native.txt

COPY . .

RUN adduser --disabled-password --gecos "" --uid 1000 app \
    && mkdir -p /app/data /app/keys_only /app/frontend/static/keys \
    && chown -R app:app /app

USER app
EXPOSE 5000

# If keys are missing, the app still starts; /api/demo/register will return bad_encrypted_pii
# until keys_only/private_demo.pem is provided (or generated with ./gen_keys.sh pair).
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "2", "--timeout", "120"]
