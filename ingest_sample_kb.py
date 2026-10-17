from pathlib import Path
from app.core.config import get_settings
from app.services.ingestion import SUPPORTED, ingest_paths
from app.rag.vectorstore import CHROMA_DIR

settings = get_settings()

print("Step 1/4 — Loading settings...")
print(f"  Embeddings : HashEmbeddings (zero-download, instant)")
print(f"  Chroma DB  : {CHROMA_DIR}")
print(f"  KB dir     : {settings.sample_kb_dir}")

folder = Path(settings.sample_kb_dir)
if not folder.is_dir():
    raise FileNotFoundError(f"Knowledge base directory not found: {folder}")
files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
print(f"\nStep 2/4 — Found {len(files)} file(s): {[f.name for f in files]}")
if not files:
    raise RuntimeError(f"No supported documents found in {folder}")

print("\nStep 3/4 — Loading and chunking documents...")
documents, chunks, ids = ingest_paths(files)
print(f"  Loaded {len(documents)} documents and created {len(chunks)} chunks")
print("\nStep 4/4 — Updating Chroma collection...")

print(f"\nDone! Indexed {len(files)} files -> {len(chunks)} chunks -> {len(ids)} vectors")
print(f"Chroma database saved to: {CHROMA_DIR}")
print("Start the server with: python run.py")
