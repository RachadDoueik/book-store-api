#!/usr/bin/env sh
set -eu

echo "[bootstrap] Waiting for database..."
python /app/scripts/wait_for_db.py

echo "[bootstrap] Running Alembic migrations..."
alembic upgrade head

echo "[bootstrap] Running seed scripts (one-time)..."
python /app/scripts/seed_db.py

echo "[bootstrap] Backfilling books embeddings (one-time)..." 
python /app/scripts/backfill_books_embeddings.py

echo "[bootstrap] Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000