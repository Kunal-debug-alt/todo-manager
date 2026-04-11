#!/usr/bin/env bash
set -o errexit

# Ensure the database schema is up-to-date on every deploy/start.
python manage.py migrate --no-input

# Automatically create an admin user on startup since Render Free tier blocks the Shell
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_EMAIL=admin@example.com
export DJANGO_SUPERUSER_PASSWORD=admin123
python manage.py createsuperuser --noinput || true

# Render sets PORT. Default to 8000 for local runs.
PORT="${PORT:-8000}"

# Start the web server.
exec daphne -b 0.0.0.0 -p "${PORT}" todo_project.asgi:application
