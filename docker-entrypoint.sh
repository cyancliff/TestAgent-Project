#!/bin/bash
set -e

export PYTHONPATH="/app"
echo "=== TestAgent backend startup ==="

echo "Waiting for database..."
for i in $(seq 1 30); do
    python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('database ok')
" 2>/dev/null && break
    echo "  retrying... ($i/30)"
    sleep 2
done

echo "Initializing database tables..."
python -c "from app.models import init_db; init_db()"

echo "Running database compatibility migrations..."
python scripts/migrate_database.py

echo "Checking question bank..."
NEED_IMPORT=$(python -c "
from app.core.database import SessionLocal
from app.models.assessment import Question
db = SessionLocal()
count = db.query(Question).count()
db.close()
print(count)
")

if [ "$NEED_IMPORT" = "0" ]; then
    echo "Question bank is empty, importing data..."
    python scripts/import_data.py
else
    echo "Question bank already has $NEED_IMPORT items, skipping import"
fi

echo "=== Starting FastAPI ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
