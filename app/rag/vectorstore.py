"""
Vector store using FAISS + HashEmbeddings.
FAISS = Facebook AI Similarity Search — fast, lightweight, no server needed.
Vectors saved to disk, loaded instantly on restart.
No heavy downloads, no external API.
"""
import hashlib
import math
import threading
import logging
import pickle
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from app.core.config import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)

_lock        = threading.Lock()
_embeddings  = None
_vectorstore = None

FAISS_DIR  = Path(__file__).resolve().parents[2] / "data" / "faiss_index"
EMBED_DIM  = 384


class HashEmbeddings(Embeddings):
    """
    Zero-download embeddings using character trigram + word hashing.
    Deterministic — same text always gives same 384-dim vector.
    No model files, no downloads, instant startup.
    """

    def _embed(self, text: str) -> list[float]:
        vec  = [0.0] * EMBED_DIM
        text = text.lower().strip()
        for i in range(max(1, len(text) - 2)):
            gram = text[i:i+3]
            h    = int(hashlib.sha256(gram.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0
        for word in text.split():
            h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            vec[h % EMBED_DIM] += 2.0
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
                logger.info("HashEmbeddings ready — zero download")
    return _embeddings


def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        with _lock:
            if _vectorstore is None:
                if FAISS_DIR.exists():
                    # Load existing index from disk
                    logger.info(f"Loading FAISS index from {FAISS_DIR}")
                    _vectorstore = FAISS.load_local(
                        str(FAISS_DIR),
                        get_embeddings(),
                        allow_dangerous_deserialization=True,
                    )
                    logger.info("FAISS index loaded")
                else:
                    logger.info("No FAISS index found — will be created on first ingest")
                    _vectorstore = None
    return _vectorstore


def get_retriever():
    vs = get_vectorstore()
    if vs is None:
        raise RuntimeError(
            "Knowledge base is empty. Run: python ingest_sample_kb.py"
        )
    return vs.as_retriever(search_kwargs={"k": settings.top_k})


def add_documents(chunks: list[Document]) -> list[str]:
    global _vectorstore
    emb = get_embeddings()
    FAISS_DIR.mkdir(parents=True, exist_ok=True)

    with _lock:
        if _vectorstore is None:
            # Create new FAISS index
            _vectorstore = FAISS.from_documents(chunks, emb)
        else:
            # Add to existing index
            _vectorstore.add_documents(chunks)

        # Save to disk
        _vectorstore.save_local(str(FAISS_DIR))
        logger.info(f"FAISS index saved to {FAISS_DIR}")

    return [str(i) for i in range(len(chunks))]
