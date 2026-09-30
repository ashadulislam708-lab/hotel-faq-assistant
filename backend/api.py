"""REST API exposing the Hotel FAQ question-answering pipeline."""

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import require_config
from rag import answer_question

logger = logging.getLogger(__name__)

require_config("OPENAI_API_KEY", "DATABASE_URL")

app = FastAPI(title="Hotel FAQ Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class Source(BaseModel):
    text: str
    question: str | None
    category: str | None
    similarity: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Plain `def` so FastAPI runs the blocking DB/OpenAI calls in its threadpool.
@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest):
    try:
        return answer_question(request.question)
    except Exception:
        logger.exception("Failed to answer question")
        raise HTTPException(status_code=500, detail="Failed to answer the question.")
