-- Run inside PostgreSQL after `docker compose up -d`:
-- docker compose exec postgres psql -U fintech -d fintech_ocr -f /dev/stdin < backend/init_pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;
-- NOTE: invoice_embeddings.vector_data is JSON in the runnable starter for SQLite compatibility.
-- After selecting a specific embedding model and dimension, migrate to vector(N) using Alembic.
