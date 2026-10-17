from pathlib import Path
from app.core.config import get_settings
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents, CHROMA_DIR

settings = get_settings()

print("Step 1/4 — Loading settings...")
print(f"  Embeddings : HashEmbeddings (zero-download, instant)")
print(f"  ChromaDB   : {CHROMA_DIR}")
print(f"  KB dir     : {settings.sample_kb_dir}")

folder = Path(settings.sample_kb_dir)
files  = [p for p in folder.iterdir() if p.is_file()]
print(f"\nStep 2/4 — Found {len(files)} file(s): {[f.name for f in files]}")

all_docs = []
for path in files:
    print(f"  Loading {path.name}...")
    all_docs.extend(load_file(path))
print(f"  Loaded {len(all_docs)} document(s)")

print("\nStep 3/4 — Chunking documents...")
chunks = chunk_documents(all_docs)
print(f"  Created {len(chunks)} chunks")

print("\nStep 4/4 — Saving to ChromaDB...")
ids = add_documents(chunks)

print(f"\nDone! Indexed {len(files)} files -> {len(chunks)} chunks -> {len(ids)} vectors")
print("Your KB is ready. Start the server with: python run.py")
