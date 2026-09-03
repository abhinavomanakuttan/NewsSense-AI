#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h postgres -U smartfeed; do
  sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Seeding database..."
python /app/scripts/seed.py

echo "Database initialization complete!"
