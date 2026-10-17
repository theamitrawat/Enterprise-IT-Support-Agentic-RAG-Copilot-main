import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.config import get_settings, BASE_DIR
from app.core.logging import configure_logging
from app.services.audit import init_db
from app.services.ingestion import SUPPORTED, ingest_paths

configure_logging()
settings = get_settings()
init_db()

logger = logging.getLogger(__name__)


def prepare_knowledge_base() -> None:
    from app.rag.vectorstore import get_document_count

    count = get_document_count()
    if count:
        logger.info("Chroma knowledge base already contains %d chunks", count)
        return

    sample_dir = Path(settings.sample_kb_dir)
    upload_dir = Path(settings.upload_dir)
    source_files = []
    for directory in (sample_dir, upload_dir):
        if directory.is_dir():
            source_files.extend(
                path for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED
            )
    source_files.sort()
    if not source_files:
        logger.warning("No documents found to initialize the Chroma knowledge base")
        return

    documents, chunks, identifiers = ingest_paths(source_files)
    logger.info(
        "Initialized Chroma knowledge base with %d documents and %d chunks",
        len(documents),
        len(identifiers),
    )
    if not chunks:
        logger.warning("Knowledge base source files contained no indexable text")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Preparing persistent Chroma knowledge base...")
    await asyncio.to_thread(prepare_knowledge_base)
    logger.info("Chroma knowledge base ready")

    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY is not set — chat will fail")
    if not settings.tavily_api_key:
        logger.info("TAVILY_API_KEY is not set — web search fallback is disabled")
    if settings.admin_api_key == "change-me":
        logger.warning("ADMIN_API_KEY is still default — change it before use")
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.include_router(router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name}
    )
