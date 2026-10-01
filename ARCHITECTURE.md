# Architecture — Hotel FAQ Assistant

A Retrieval-Augmented Generation (RAG) assistant that answers guest questions about *Harborview Inn & Suites* using only the hotel's FAQ documents.

| Layer | Technology |
|---|---|
| Frontend | React + Vite (`frontend/`) |
| Backend API | FastAPI + Uvicorn (`backend/api.py`) |
| Vector store | PostgreSQL 16 + pgvector (HNSW index, cosine distance) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) |
| Answer generation | OpenAI `gpt-4o-mini` |

The system has two independent flows that share one database:

1. **Ingestion (offline, run on demand)** — FAQ markdown → chunks → embeddings → pgvector.
2. **Ask (online, per request)** — question → embedding → similarity search → LLM answer.

---

## 1. System diagram

```
                         INGESTION  (python ingest.py)
 ┌────────────────────┐   ┌───────────┐   ┌────────────┐   ┌───────────────┐
 │ data/policies/*.md │──►│ chunking  │──►│ embeddings │──►│ db (pgvector) │
 │ 10 FAQ files       │   │ 1 Q&A =   │   │ OpenAI     │   │ faq_chunks    │
 └────────────────────┘   │ 1 chunk   │   │ batch=128  │   │ ingestion_    │
                          └───────────┘   └────────────┘   │ state         │
                                                           └───────┬───────┘
                                                                   │
                            ASK  (POST /api/ask)                   │ similarity
 ┌─────────┐  JSON   ┌────────┐   ┌───────────┐   ┌────────────┐   │ search
 │ React   │────────►│ api.py │──►│  rag.py   │──►│ retrieval  │───┘
 │ browser │◄────────│FastAPI │◄──│answer_    │   │ .py        │──► embed_query (OpenAI)
 └─────────┘ answer  └────────┘   │question   │   └────────────┘
             +sources             │           │──► generation.py ──► gpt-4o-mini (OpenAI)
                                  └───────────┘    (only if relevant chunks were found)
```

---

## 2. Repository layout

| Path | Responsibility |
|---|---|
| `backend/data/policies/*.md` | Source FAQ content (10 files: booking, check-in, cancellation, dining, amenities, parking, pets, Wi-Fi, accessibility, local area). |
| `backend/config.py` | Loads `.env`; exposes `OPENAI_API_KEY`, `DATABASE_URL`, `SIMILARITY_THRESHOLD`, `TOP_K`; `require_config()` fails fast on missing values. |
| `backend/chunking.py` | `load_faq_files()` reads the markdown files; `chunk_faq_content()` splits each into Q&A chunks. |
| `backend/embeddings.py` | OpenAI embedding calls with batching and retry: `embed_documents()` (ingest) and `embed_query()` (ask). |
| `backend/db.py` | Connection, schema creation, bulk replace, content-hash state, and `search_similar()`. |
| `backend/ingest.py` | CLI orchestrating the whole ingestion pipeline. |
| `backend/retrieval.py` | `retrieve_top_k()`: embed the question, search, filter by threshold. |
| `backend/generation.py` | System prompt, prompt assembly, `gpt-4o-mini` call. |
| `backend/rag.py` | `answer_question()`: the end-to-end ask pipeline and the fallback message. |
| `backend/api.py` | FastAPI app: `GET /api/health`, `POST /api/ask`, CORS, startup `init_schema()`. |
| `backend/ask.py` | CLI to ask a single question without the web UI. |
| `backend/docker-compose.yml` | Services `db`, `ingest`, `api`. |
| `backend/docker/initdb/01-vector.sql` | Runs `CREATE EXTENSION IF NOT EXISTS vector;` on first DB start. |
| `frontend/src/App.jsx`, `api.js` | Chat UI and the `fetch` call to `/api/ask`. |

---

## 3. Data source format

Each file in `backend/data/policies/` follows this structure:

```markdown
# Dining Policy — Harborview Inn & Suites        ← category (line 1, "# ")

## Is room service available?                    ← question ("## ")

Room service is available daily from 6:30 AM…    ← answer (everything until next "## ")

## Can dietary restrictions be accommodated?
...
```

The chunker depends on this convention: line 1 is the category, every `## ` heading is a question, and the text beneath it is the answer.

---

## 4. Flow 1 — Ingestion

Command:

```bash
python ingest.py              # normal run (skips if content unchanged)
python ingest.py --force      # re-ingest even if content unchanged
python ingest.py --dry-run    # load, chunk and embed; do NOT touch the database
```

Entry point: `main()` in `backend/ingest.py`.

### Step by step

**1. Validate configuration.**
`require_config("OPENAI_API_KEY", "DATABASE_URL")`. A dry run only needs `OPENAI_API_KEY` since it never writes to the database. Missing values raise a clear error before any work is done.

**2. Load the FAQ files** — `chunking.load_faq_files()`.
Globs `backend/data/policies/*.md`, **sorted** so the order is deterministic, and returns each file's raw text as a list of strings.

**3. Compute a content hash** — `ingest._content_hash()`.
SHA-256 over all documents joined with `\x00` (a separator that prevents `["ab","c"]` and `["a","bc"]` from colliding). The hash identifies "the exact FAQ content that was ingested".

**4. Prepare the schema** — `db.init_schema()` *(skipped on dry run)*.
- Opens a plain connection and runs `CREATE EXTENSION IF NOT EXISTS vector;` (it must exist before `register_vector()` can work).
- Creates `faq_chunks` and `ingestion_state` if missing, plus an HNSW index.
- Verifies the stored vector width equals `EMBEDDING_DIM` (1536); otherwise raises an error telling you to drop the table and re-ingest.

**5. Skip if nothing changed** *(not on dry run)*.
`db.get_content_hash()` returns the hash saved by the last successful ingestion. If it equals the new hash and `--force` was not given, the run logs "unchanged; skipping" and returns. No OpenAI calls, no writes. This saves both time and embedding cost.

**6. Chunk** — `chunking.chunk_faq_content(doc)` per document.
- `category` = first line without the leading `#` (only if it starts with `# `).
- Body split with `re.split(r"(?m)^## +", body)`; `sections[0]` (text before the first `##`) is dropped.
- In each section, the first line is the **question** and the rest is the **answer**.
- One chunk per Q&A pair:

```python
{
  "text":     "Q: <question>\nA: <answer>",   # this is what gets embedded
  "question": "<question>",
  "answer":   "<answer>",
  "category": "<category>",
}
```

`text` contains both question and answer so the resulting vector captures both meanings; a guest question can match either side.

**7. Embed** — `embeddings.embed_documents([chunk["text"], ...])`.
- Texts are sent to OpenAI in **batches of 128** (`BATCH_SIZE`).
- Each batch goes through `_embed_with_retry()`: up to **3 attempts**, waiting 2 s then 4 s between failures (linear backoff). After the third failure the exception propagates and ingestion exits with status 1.
- Output order equals input order, so embeddings are paired back to chunks with `zip`.
- Every embedding is a list of 1536 floats; semantically similar texts produce nearby vectors.

**8. Attach embeddings.**
`chunk["embedding"] = embedding` for each chunk.

**9. Dry run stops here.** It logs "skipping database write".

**10. Store atomically** — `db.replace_all_chunks(chunks, content_hash)`.
Everything happens in **one transaction**:

1. Build rows `(text, vector, question, category)`; `_to_vector()` checks length == 1536 and converts to a `float32` numpy array (so pgvector receives its native `[x,y,…]` format rather than a `numeric[]`).
2. `TRUNCATE TABLE faq_chunks;`
3. `execute_values` bulk-inserts all rows in a single statement.
4. Upsert the new `content_hash` into `ingestion_state` (`ON CONFLICT (id) DO UPDATE`).
5. `COMMIT`.

If any step fails nothing is committed: the previous chunks *and* the previous hash remain, so data and hash can never drift out of sync, and the table is never left empty or half-filled.

### Database schema

```sql
CREATE TABLE faq_chunks (
    id         SERIAL PRIMARY KEY,
    text       TEXT NOT NULL,              -- "Q: …\nA: …"  → shown to the LLM
    embedding  VECTOR(1536) NOT NULL,      -- meaning of text → used for search
    question   TEXT,                       -- metadata for display / filtering
    category   TEXT,                       -- metadata for display / filtering
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX faq_chunks_embedding_idx
  ON faq_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE ingestion_state (             -- exactly one row (CHECK id = 1)
    id           SMALLINT PRIMARY KEY DEFAULT 1,
    content_hash TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (id = 1)
);
```

**Why store both `text` and `embedding`?**
The embedding is used to *find* chunks but cannot be turned back into words (embedding is one-way). The text is what the LLM actually reads to write the answer. Without `embedding` there is no semantic search; without `text` there is nothing to show the LLM. `question` and `category` are extra metadata for displaying sources and for possible filtering.

### Ingestion flow diagram

```
*.md files
   │  load_faq_files()                       sorted, UTF-8
   ▼
raw texts ───────────► _content_hash() ─────────────────┐
   │                                                    │
   │ (non-dry-run) init_schema()                        ▼
   │                       get_content_hash() == hash and not --force ?
   │                                     │ yes → log "unchanged" → exit
   ▼                                     │ no
chunk_faq_content()  (one Q&A = one chunk)
   ▼
embed_documents()    (batches of 128, retry ×3 → OpenAI)
   ▼
chunk["embedding"] = vector[1536]
   │ dry-run? → stop
   ▼
replace_all_chunks()   TRUNCATE → bulk INSERT → upsert hash → COMMIT
```

---

## 5. Flow 2 — Asking a question

Endpoint: `POST /api/ask` with body `{"question": "..."}` (1–1000 characters, validated by Pydantic). The same pipeline is available from the CLI: `python ask.py "your question"`.

### Step by step

**1. Frontend** — `frontend/src/api.js` → `askQuestion()`.
`fetch(`${VITE_API_URL ?? "http://localhost:8000"}/api/ask`, { method: "POST", body: JSON.stringify({ question }) })`. `App.jsx` appends the user message, shows "Searching FAQ…", then renders the answer and a collapsible **Sources** list (category, question, similarity score, text).

**2. API layer** — `api.py: ask()`.
Pydantic rejects empty or >1000-character questions (HTTP 422). The handler is a plain `def`, so FastAPI runs the blocking OpenAI and database calls in its thread pool. Any exception is logged and returned as HTTP 500 `"Failed to answer the question."`. CORS allows the origins in `CORS_ORIGINS` (default `http://localhost:5173`).

**3. Pipeline entry** — `rag.py: answer_question()`.
The question is stripped. If it is empty, return the fallback message immediately, with no OpenAI or database calls.

**4. Retrieval** — `retrieval.py: retrieve_top_k(question, k=TOP_K, min_similarity=SIMILARITY_THRESHOLD)`.

   a. **Embed the question** — `embeddings.embed_query()`.
   Same model (`text-embedding-3-small`) and same retry logic as ingestion → a 1536-dim vector. The same model is required: vectors from different models are not comparable.

   b. **Similarity search** — `db.search_similar(vector, k)`:

   ```sql
   SELECT text, question, category,
          1 - (embedding <=> %s::vector) AS similarity
   FROM faq_chunks
   ORDER BY embedding <=> %s::vector
   LIMIT %s;                         -- k = TOP_K
   ```
   - `<=>` is pgvector's **cosine distance**. 0 = same direction (same meaning).
   - `similarity = 1 - distance`, so **1 is the closest** and lower is less related.
   - `ORDER BY … LIMIT k` returns the k nearest chunks; the **HNSW index** makes this an approximate nearest-neighbour lookup instead of a full table scan.

   c. **Threshold filter**:

   ```python
   [chunk for chunk in results if chunk["similarity"] >= min_similarity]
   ```

**5. Fallback if nothing is relevant.**
If the filtered list is empty, `answer_question` returns `FALLBACK_MESSAGE` ("I'm sorry, I don't have information on that topic. Please contact the hotel front desk for help.") with `sources: []`. **The LLM is not called**, which saves cost and prevents the model from inventing an answer to an off-topic question.

**6. Generate the answer** — `generation.generate_answer(question, chunks)`.
- `build_prompt`: the `text` of each chunk joined by blank lines, then the question:

  ```
  Context:
  Q: …
  A: …

  Q: …
  A: …

  Question: <user question>
  ```
- Chat completion with model `gpt-4o-mini`, a **system prompt** instructing it to answer *only* from the provided context and to say it has no information rather than guess, and the prompt above as the user message.

**7. Response.**

```json
{
  "answer": "<LLM-generated answer based on the retrieved chunks>",
  "sources": [
    { "text": "Q: …\nA: …", "question": "…", "category": "…", "similarity": 0.71 }
  ]
}
```

### TOP_K and SIMILARITY_THRESHOLD

Both are read from the environment in `config.py` (defaults shown):

| Setting | Default | Meaning |
|---|---|---|
| `TOP_K` | `5` | **Count limit.** The maximum number of chunks fetched from the database. |
| `SIMILARITY_THRESHOLD` | `0.3` | **Quality limit.** Minimum cosine similarity for a chunk to be used. |

They are applied in this order: first take the top K from the database, then drop those below the threshold.

```
Nearest 5 from DB:           0.82   0.61   0.34   0.28   0.15
After threshold >= 0.3:      0.82   0.61   0.34            → 3 chunks go to the LLM
All 5 below 0.3:             (empty) → fallback message, LLM not called
```

Tuning:
- Raise `TOP_K` → more context for the LLM (better recall) but more tokens/cost and more irrelevant text.
- Lower `TOP_K` → cheaper and more focused, but may miss needed information.
- Raise `SIMILARITY_THRESHOLD` (e.g. 0.5) → fewer wrong answers, but more "I don't know" for loosely phrased questions.
- Lower `SIMILARITY_THRESHOLD` → more questions get answered, with a higher risk of weakly related context.

### Ask flow diagram

```
Browser  ──POST /api/ask {question}──►  api.py  (validate 1–1000 chars)
                                          │
                                          ▼
                                   rag.answer_question
                                          │ strip; empty → FALLBACK
                                          ▼
                              retrieval.retrieve_top_k
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
     embed_query(question)      search_similar(vec, TOP_K)   keep similarity ≥ THRESHOLD
     OpenAI → vector[1536]      pgvector cosine, HNSW
                                          │
                       empty? ── yes ──► FALLBACK_MESSAGE (no LLM call)
                                          │ no
                                          ▼
                           generation.generate_answer
                           system prompt + context + question → gpt-4o-mini
                                          │
                                          ▼
                       { answer, sources[text, question, category, similarity] }
                                          │
                                          ▼
                       Browser renders answer + collapsible Sources
```

---

## 6. Configuration

Set in `backend/.env` (see `backend/.env.example`) and loaded by `config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — (required) | Embeddings and chat completions. |
| `DATABASE_URL` | — (required) | Postgres connection string. Compose overrides it to point at the `db` service. |
| `SIMILARITY_THRESHOLD` | `0.3` | Minimum cosine similarity for a chunk to be used. |
| `TOP_K` | `5` | Maximum chunks retrieved per question. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins. |
| `API_PORT` | `8000` | Port Uvicorn listens on (compose). |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | — | Database container settings. |
| `FRONTEND_PORT` | — | Frontend container port (`frontend/.env`). |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL the frontend calls. |

Constants in code: embedding model, `BATCH_SIZE=128`, `MAX_RETRIES=3`, backoff 2 s (`embeddings.py`); `EMBEDDING_DIM=1536` (`db.py`); chat model `gpt-4o-mini` and the system prompt (`generation.py`).

---

## 7. Deployment (Docker Compose)

`backend/docker-compose.yml` defines three services:

| Service | Role |
|---|---|
| `db` | `pgvector/pgvector:pg16`, persistent volume `pgdata`, healthcheck via `pg_isready`, runs `initdb/01-vector.sql` on first start. |
| `ingest` | One-shot `python ingest.py`; waits for `db` to be healthy. |
| `api` | `uvicorn api:app` on `API_PORT`; waits for `db` to be healthy. Its startup hook calls `init_schema()`, so the API works even if it starts before ingestion (it simply has no chunks yet and returns the fallback message). |

The frontend has its own `frontend/docker-compose.yml` (Vite dev server on `FRONTEND_PORT`).

Typical first run: start `db` → run `ingest` → start `api` → start `frontend`.

---

## 8. Design decisions and caveats

- **Atomic replace.** Truncate + insert + hash update share one transaction, so a failure never leaves the store empty, partial or inconsistent with its hash.
- **Hash-based skip.** Unchanged content costs zero OpenAI calls. Use `--force` to rebuild anyway (e.g. after changing the chunking logic, which is *not* part of the hash).
- **Same embedding model for documents and queries.** Changing the model or `EMBEDDING_DIM` requires dropping `faq_chunks` and re-ingesting; `init_schema()` detects the mismatch and says so.
- **Grounded answers.** The threshold fallback plus the system prompt keep answers inside the FAQ content; off-topic questions never reach the LLM.
- **Whole-table re-ingest.** Any content change re-embeds every chunk. This is cheap at the current size (10 files) but would need incremental updates for a large corpus.
- **`answer` is not a separate column.** It lives inside `text`; retrieval returns `text`, which already contains both question and answer.
- **`db.insert_chunk()` is unused by ingestion.** It exists for single-chunk inserts; the pipeline uses `replace_all_chunks`.
- **No conversation memory.** Each `/api/ask` call is independent; the UI keeps history only for display.
