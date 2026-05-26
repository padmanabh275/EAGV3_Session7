"""FastAPI app for the India shopping RAG frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shopping_rag import service

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="S7 Shopping RAG", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    use_index: bool = True
    top_k: int = Field(6, ge=1, le=20)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(6, ge=1, le=20)


class IndexAnswerRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    answer: str = Field(..., min_length=10, max_length=50000)
    title: str | None = Field(None, max_length=200)


@app.get("/")
def index_page():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def api_health():
    return service.health()


@app.get("/api/samples")
def api_samples():
    return service.sample_queries()


@app.post("/api/search")
def api_search(body: SearchRequest):
    try:
        return {"query": body.query, "results": service.search(body.query, top_k=body.top_k)}
    except Exception as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/ask")
def api_ask(body: AskRequest):
    try:
        result = service.ask(body.query, use_index=body.use_index, top_k=body.top_k)
        return {"query": body.query, **result}
    except Exception as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/index-answer")
def api_index_answer(body: IndexAnswerRequest):
    """Index a query+answer pair (e.g. from without-RAG) into the FAISS catalog."""
    try:
        return service.index_qa_pair(body.query, body.answer, title=body.title)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(503, str(e)) from e


app.mount("/static", StaticFiles(directory=STATIC), name="static")
