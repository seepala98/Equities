#!/bin/sh
set -e

# Wait for DB to be ready (simple loop)
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for database at $POSTGRES_HOST:$POSTGRES_PORT..."
  while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
    echo "Postgres is unavailable - sleeping"
    sleep 1
  done
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput || true

# Start Django development server
exec python manage.py runserver 0.0.0.0:8000
