"""
Vector store using ChromaDB + HashEmbeddings.
Zero downloads, instant startup, no external dependencies.
Uses character n-gram + word hashing to generate 384-dim vectors.
Sufficient quality for small knowledge bases (< 1000 documents).
"""
import hashlib
import math
import threading
import logging
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from app.core.config import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)

_lock        = threading.Lock()
_embeddings  = None
_vectorstore = None

CHROMA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "chroma_db")
EMBED_DIM  = 384


class HashEmbeddings(Embeddings):
    """
    Deterministic embeddings using character trigram + word hashing.
    - No model files to download
    - Instant startup
    - Works offline
    - Same text always gives same vector
    """

    def _embed(self, text: str) -> list[float]:
        vec  = [0.0] * EMBED_DIM
        text = text.lower().strip()
        # Character trigrams for sub-word similarity
        for i in range(max(1, len(text) - 2)):
            gram = text[i:i+3]
            h    = int(hashlib.sha256(gram.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0
        # Word unigrams for word-level similarity (weighted higher)
        for word in text.split():
            h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 2.0
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings() -> HashEmbeddings:
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                _embeddings = HashEmbeddings()
                logger.info("HashEmbeddings initialized — no download needed")
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        with _lock:
            if _vectorstore is None:
                _vectorstore = Chroma(
                    collection_name="company-kb",
                    embedding_function=get_embeddings(),
                    persist_directory=CHROMA_DIR,
                )
    return _vectorstore


def get_retriever():
    return get_vectorstore().as_retriever(
        search_kwargs={"k": settings.top_k}
    )


def add_documents(chunks):
    return get_vectorstore().add_documents(chunks)
