#!/bin/sh
set -eu

python -m alembic upgrade head
exec python -m uvicorn everstory.api.main:app --host 0.0.0.0 --port "${PORT:-8123}"
