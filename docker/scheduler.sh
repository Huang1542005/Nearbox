#!/bin/bash
set -e

echo "⏳ Waiting for database..."
until python manage.py check --database default > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Scheduler started. Running expire_orders every 60 seconds."

while true; do
    python manage.py expire_orders
    sleep 60
done
