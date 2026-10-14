"""
Vector store using ChromaDB — runs locally on disk, no API keys,
no cold starts, no timeouts. Replaces Pinecone.
"""
import threading
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from app.core.config import get_settings

settings  = get_settings()
_lock     = threading.Lock()
_embeddings  = None
_vectorstore = None

# ChromaDB stores data here — persists across restarts
CHROMA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "chroma_db")


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                _embeddings = HuggingFaceEmbeddings(
                    model_name=settings.embedding_model
                )
    return _embeddings


def get_vectorstore():
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
    store = get_vectorstore()
    ids   = store.add_documents(chunks)
    return ids
