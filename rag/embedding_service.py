"""Internal multilingual embedding endpoint; never expose this service publicly."""

import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field


MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
app = FastAPI(title="NewsPulse embeddings", docs_url=None, redoc_url=None)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=16)


@lru_cache(maxsize=1)
def model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


@app.on_event("startup")
def warm_model():
    model()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/embed")
def embed(request: EmbedRequest):
    if any(not text.strip() or len(text) > 4000 for text in request.texts):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Texts must be nonempty and at most 4000 characters")
    vectors = model().encode(request.texts, normalize_embeddings=True).tolist()
    return {"vectors": vectors}
