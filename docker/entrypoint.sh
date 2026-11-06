#!/bin/bash
set -e

echo "⏳ Waiting for database..."
until python manage.py check --database default > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Database is ready."

echo "🔄 Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

if [ "${SEED_DEMO:-true}" = "true" ]; then
    echo "🌱 Seeding demo data..."
    python manage.py seed_demo
fi

echo "🚀 Starting server on 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000
