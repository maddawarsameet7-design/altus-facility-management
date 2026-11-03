#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput

# Run database migrations with fallback to SQLite if PostgreSQL fails
python manage.py migrate || {
    echo "Primary database migration failed; falling back to SQLite..."
    export DATABASE_URL=""
    python manage.py migrate
}

# Bootstrap initial production accounts and standard categories
python manage.py bootstrap_prod_user || true

if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ] || [ "$DEBUG" = "1" ]; then
    python manage.py seed_data || true
fi
