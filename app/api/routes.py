from pathlib import Path
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.rag.workflow import ask
from app.rag.vectorstore import add_documents
from app.services.ingestion import load_file, chunk_documents, SUPPORTED
from app.services.audit import write_audit

router   = APIRouter(prefix="/api")
settings = get_settings()
logger   = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/chat")
async def chat(payload: ChatRequest):
    try:
        # Run synchronous LangGraph pipeline in a thread pool
        # so the async event loop stays free and uvicorn stays responsive
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, ask, payload.question)

        try:
            write_audit(payload.question, result["source_used"], result.get("trace", []))
        except Exception:
            logger.warning("Audit write failed", exc_info=True)

        return {
            "answer":          result.get("answer", ""),
            "source_used":     result.get("source_used", ""),
            "trace":           result.get("trace", []),
            "citations":       result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
        }
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    x_admin_key: str = Header(default=""),
):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED))}",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename).name
    dest.write_bytes(await file.read())

    docs   = load_file(dest)
    chunks = chunk_documents(docs)
    ids    = add_documents(chunks)

    return {
        "message":     "Document indexed successfully",
        "file":        dest.name,
        "chunks":      len(chunks),
        "ids_created": len(ids),
    }
