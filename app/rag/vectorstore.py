"""Persistent Chroma vector store with deterministic, local embeddings."""
import hashlib
import logging
import math
import threading
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_lock = threading.RLock()
_embeddings: "HashEmbeddings | None" = None
_vectorstore: Chroma | None = None

CHROMA_DIR = Path(settings.chroma_db_path)
COLLECTION_NAME = settings.chroma_collection_name
EMBED_DIM = 384


class HashEmbeddings(Embeddings):
    """Deterministic, zero-download character-trigram and word embeddings."""

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBED_DIM
        text = text.lower().strip()
        for index in range(max(1, len(text) - 2)):
            trigram = text[index:index + 3]
            digest = int(hashlib.sha256(trigram.encode()).hexdigest(), 16)
            vector[digest % EMBED_DIM] += 1.0
        for word in text.split():
            digest = int(hashlib.sha256(word.encode()).hexdigest(), 16)
            vector[digest % EMBED_DIM] += 2.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings() -> HashEmbeddings:
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                _embeddings = HashEmbeddings()
                logger.info("Local hash embeddings ready")
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        with _lock:
            if _vectorstore is None:
                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
                _vectorstore = Chroma(
                    collection_name=COLLECTION_NAME,
                    embedding_function=get_embeddings(),
                    persist_directory=str(CHROMA_DIR),
                    collection_metadata={"hnsw:space": "cosine"},
                )
                logger.info("Chroma collection ready at %s", CHROMA_DIR)
    return _vectorstore


def get_document_count() -> int:
    return get_vectorstore()._collection.count()


def get_retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": settings.top_k})


def add_documents(chunks: list[Document]) -> list[str]:
    if not chunks:
        return []

    identifiers = [
        hashlib.sha256(
            (
                f"{doc.metadata.get('source', '')}|"
                f"{doc.metadata.get('page', '')}|"
                f"{doc.metadata.get('start_index', '')}|"
                f"{doc.page_content}"
            ).encode("utf-8")
        ).hexdigest()
        for doc in chunks
    ]
    store = get_vectorstore()
    with _lock:
        sources = {
            str(doc.metadata["source"])
            for doc in chunks
            if doc.metadata.get("source")
        }
        existing_ids: set[str] = set()
        for source in sources:
            existing_ids.update(store.get(where={"source": source}, include=[])["ids"])
        store.add_documents(chunks, ids=identifiers)
        stale_ids = existing_ids.difference(identifiers)
        if stale_ids:
            store.delete(ids=list(stale_ids))
    logger.info("Indexed %d chunks in Chroma", len(chunks))
    return identifiers
