"""
Vector store using ChromaDB + character n-gram hashing embeddings.

WHY: All local embedding models (sentence-transformers, FastEmbed) require
downloading 90-400MB model files which is too slow on slow connections.

This implementation uses deterministic character n-gram hashing to convert
text to 384-dimensional vectors — zero downloads, instant startup, works
offline. Quality is sufficient for a small KB (< 1000 documents).

For production with large KBs, replace GroqEmbeddings with FastEmbedEmbeddings
once the model has been downloaded and cached.
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
    Zero-download embeddings using character trigram hashing.
    - No model files to download
    - Instant startup
    - Deterministic — same text always gives same vector
    - Good enough for small knowledge bases
    """

    def _embed(self, text: str) -> list[float]:
        vec  = [0.0] * EMBED_DIM
        text = text.lower().strip()
        # Character trigrams
        for i in range(max(1, len(text) - 2)):
            gram = text[i:i+3]
            h    = int(hashlib.sha256(gram.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0
        # Word unigrams (boost word-level similarity)
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
                logger.info("HashEmbeddings ready — no download needed")
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
