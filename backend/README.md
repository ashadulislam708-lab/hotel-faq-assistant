# Hotel FAQ Assistant — Backend

FastAPI service that answers hotel FAQ questions using retrieval-augmented generation. FAQ content is chunked, embedded with OpenAI, and stored in Postgres with the pgvector extension.

## Setup

```bash
cp .env.example .env
# set OPENAI_API_KEY, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT
```

## Run with Docker

```bash
docker compose up -d db api
docker compose run --rm ingest
```

### `docker compose up -d db api`

Starts the database and the API in the background (`-d`). The `ingest` service is not started.

- **db** — Postgres with pgvector. On the first boot it enables the `vector` extension. Data is kept in the `pgdata` Docker volume, so it survives restarts.
- **api** — FastAPI served by uvicorn on http://localhost:8000. It waits for the database to be healthy and creates the tables on startup. It only reads data; it never ingests.

### `docker compose run --rm ingest`

Runs the ingestion job once, then removes its container (`--rm`).

1. Loads the FAQ files from `data/policies/` and hashes their content.
2. Skips the rest if the content is unchanged since the last ingestion.
3. Splits the content into chunks and creates embeddings with OpenAI.
4. Replaces the contents of `faq_chunks` in a single transaction, so a failure leaves the previous data intact.

The API uses the new data immediately; no restart is needed. To re-ingest even when nothing changed:

```bash
docker compose run --rm ingest python ingest.py --force
```

### When to run what

- **First time, or after the FAQ files change:** run both commands.
- **Every other time:** only `docker compose up -d db api`.
- `docker compose up` (without service names) starts db, ingest and api together; ingest skips itself when content is unchanged.

## Try it

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What time is check-in?"}'
```
