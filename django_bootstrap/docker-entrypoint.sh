#!/bin/sh
set -e
cd /srv/django
export DJANGO_SETTINGS_MODULE=portal.settings
export PYTHONPATH="/srv/django"
python manage.py migrate --noinput
python manage.py collectstatic --noinput 2>/dev/null || true
exec "$@"
