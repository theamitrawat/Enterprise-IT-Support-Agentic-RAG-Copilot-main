from pathlib import Path
import logging
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.rag.workflow import ask, ask_stream
from app.rag.vectorstore import add_documents
from app.services.ingestion import load_file, chunk_documents, SUPPORTED
from app.services.audit import write_audit

router = APIRouter(prefix="/api")
settings = get_settings()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        result = ask(payload.question)
        write_audit(payload.question, result["source_used"], result.get("trace", []))
        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "trace": result.get("trace", []),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
        }
    except Exception as exc:
        logger.exception("Chat request failed")
        message = str(exc) or exc.__class__.__name__
        if "Connection error" in message:
            message = (
                "Could not connect to the LLM service. Check your internet connection, "
                "GROQ_API_KEY, and GROQ_MODEL in .env."
            )
        raise HTTPException(status_code=500, detail=message) from exc


@router.get("/chat/stream")
async def chat_stream(question: str):
    """Server-Sent Events streaming endpoint for real-time token delivery."""
    if not question or len(question.strip()) < 2:
        raise HTTPException(status_code=422, detail="Question too short")

    async def event_generator():
        try:
            async for event in ask_stream(question):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ingest")
async def ingest(file: UploadFile = File(...), x_admin_key: str = Header(default="")):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Supported: {', '.join(sorted(SUPPORTED))}")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename).name
    dest.write_bytes(await file.read())
    docs = load_file(dest)
    chunks = chunk_documents(docs)
    ids = add_documents(chunks)
    return {"message": "Document indexed", "file": dest.name, "chunks": len(chunks), "ids_created": len(ids)}
