from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.config import get_settings, BASE_DIR
from app.core.logging import configure_logging
from app.services.audit import init_db
import logging


configure_logging()
settings = get_settings()
init_db()

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")

app.include_router(router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def startup_checks():
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY is not set — chat will fail")
    if not settings.pinecone_api_key:
        logger.warning("PINECONE_API_KEY is not set — KB retrieval will fail")
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY is not set — web search fallback will fail")
    if settings.admin_api_key == "change-me":
        logger.warning("admin_api_key is still the default 'change-me' — change it in .env before use")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})
