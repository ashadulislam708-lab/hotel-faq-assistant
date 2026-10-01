# Hotel FAQ Assistant

A Retrieval-Augmented Generation (RAG) system that answers natural-language questions about a hotel — check-in/check-out, amenities, policies, wifi, parking, pets, cancellations, and more — using grounded retrieval over a curated FAQ knowledge base.

## Overview

The assistant answers guest and staff questions by retrieving the most relevant entries from the hotel's FAQ content and generating a response strictly grounded in that content. If a question isn't covered by the knowledge base, the assistant says so rather than fabricating an answer.

## Features

- Natural-language Q&A over hotel FAQ content
- Answers grounded in retrieved source content — no hallucinated policies or facts
- Explicit fallback response when a question isn't covered by the knowledge base
- Chat-style web interface

## Architecture

The pipeline is implemented directly (no third-party RAG orchestration framework), with each stage explicit:

```
User question
   │
   ▼
Embed query (OpenAI)
   │
   ▼
Vector similarity search (Postgres + pgvector)
   │
   ▼
Top-k FAQ chunks  ──► Prompt assembly (context + question + instructions)
   │
   ▼
OpenAI API (generation)
   │
   ▼
Answer shown in Streamlit chat UI
```

FAQ content is chunked (one chunk per Q&A pair), embedded with the OpenAI embeddings API, and stored in PostgreSQL via the `pgvector` extension. At query time, the user's question is embedded and matched against stored chunks via vector similarity search; the top matches are assembled into a prompt and sent to the OpenAI API to generate the final answer.

See [PRD.md](PRD.md) for full product requirements, scope, and architecture details.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python |
| Vector store | PostgreSQL + `pgvector` extension |
| Embeddings | OpenAI API |
| Generation (LLM) | OpenAI API |
| UI | Streamlit |
| DB access | psycopg2 or SQLAlchemy |

## Prerequisites

- Python 3.10+
- PostgreSQL with the `pgvector` extension installed
- An OpenAI API key

## Getting Started

```bash
# Clone the repository
git clone <repository-url>
cd RAG/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# then edit .env with your API keys and database URL

# Enable pgvector on your Postgres database
psql -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Populate the knowledge base
python ingest.py
```

Ask a question from the command line:

```bash
python ask.py "What time is check-in?"
```

## Running with Docker

Backend and frontend have separate compose files. Run backend commands from `backend/` and frontend commands from `frontend/`.

```bash
# Backend (from backend/)

# 1. Ingest data (load FAQ content into pgvector)
docker compose run --rm ingest

# 2. Run the API only (http://localhost:8000)
docker compose up api

# 3. Run the database only
docker compose up db

# 4. Run the database and API together
docker compose up db api

# Frontend (from frontend/)

# 5. Run the React chat UI (http://localhost:5173)
docker compose up --build
```

API: `POST /api/ask` with `{"question": "..."}` returns `{"answer": "...", "sources": [...]}`; `GET /api/health` for liveness.

## Project Structure

```
RAG/
├── backend/
│   ├── data/               # Hotel FAQ source content
│   │   └── policies/
│   ├── config.py           # Environment/config loading
│   ├── db.py                # Postgres/pgvector connection and schema
│   ├── chunking.py          # FAQ markdown loading and chunking
│   ├── embeddings.py        # OpenAI embedding calls
│   ├── ingest.py            # Chunking, embedding, and storage pipeline
│   ├── retrieval.py         # Query embedding and similarity search
│   ├── generation.py        # Prompt assembly and OpenAI API integration
│   ├── rag.py               # Query pipeline: retrieve, then generate
│   ├── api.py               # FastAPI REST API
│   ├── ask.py               # CLI for a single question
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React (Vite) chat UI
├── PRD.md
└── README.md
```

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for OpenAI (embeddings and answer generation) |
| `DATABASE_URL` | PostgreSQL connection string (pgvector-enabled database) |
| `SIMILARITY_THRESHOLD` | Minimum cosine similarity for a chunk to be used (default `0.3`) |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API (default `http://localhost:5173`) |
| `TOP_K` | Max chunks retrieved per question (default `5`) |

## Status

In active development, following the milestones defined in [PRD.md](PRD.md).

## Documentation

Full product requirements, scope, and design decisions are documented in [PRD.md](PRD.md).
