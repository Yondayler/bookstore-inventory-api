#!/usr/bin/env sh
set -e

PORT="${PORT:-8000}"

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "==> Applying database migrations"
  python manage.py migrate --noinput
fi

if [ "${SEED_DATABASE:-false}" = "true" ]; then
  echo "==> Seeding sample books"
  python manage.py seed_books
fi

case "$1" in
  gunicorn)
    echo "==> Starting gunicorn on 0.0.0.0:${PORT}"
    exec gunicorn config.wsgi:application \
      --bind "0.0.0.0:${PORT}" \
      --workers "${WEB_CONCURRENCY:-3}" \
      --threads "${WEB_THREADS:-2}" \
      --timeout "${WEB_TIMEOUT:-60}" \
      --access-logfile - \
      --error-logfile -
    ;;
  runserver)
    echo "==> Starting the Django development server on 0.0.0.0:${PORT}"
    exec python manage.py runserver "0.0.0.0:${PORT}"
    ;;
  *)
    exec "$@"
    ;;
esac
