#!/usr/bin/env bash
set -o errexit

# Ensure the database schema is up-to-date on every deploy/start.
python manage.py migrate --no-input

# Render sets PORT. Default to 8000 for local runs.
PORT="${PORT:-8000}"

# Start the web server.
exec daphne -b 0.0.0.0 -p "${PORT}" todo_project.asgi:application
