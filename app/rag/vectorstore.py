"""
Vector store using ChromaDB + FastEmbed embeddings.
FastEmbed loads in 2-3 seconds (vs 5+ minutes for sentence-transformers).
No PyTorch required — uses ONNX runtime which is tiny and fast.
"""
import threading
from pathlib import Path
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_chroma import Chroma
from app.core.config import get_settings

settings     = get_settings()
_lock        = threading.Lock()
_embeddings  = None
_vectorstore = None

# ChromaDB stores vectors here — persists across restarts
CHROMA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "chroma_db")

# FastEmbed model — 384 dimensions, loads in ~3 seconds, no PyTorch
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                _embeddings = FastEmbedEmbeddings(model_name=EMBED_MODEL)
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
    return get_vectorstore().add_documents(chunks)
