from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    app_name: str = "Enterprise IT Support Agentic RAG Copilot"
    app_env: str = "development"

    # LLM
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # Web search
    tavily_api_key: str = ""

    # Embeddings — using FastEmbed BAAI/bge-small-en-v1.5 (hardcoded in vectorstore.py)

    # Retrieval
    top_k: int = 4
    max_retries: int = 1

    # Security
    admin_api_key: str = "change-me"

    # Paths
    audit_db_path: str = str(BASE_DIR / "data" / "audit.db")
    upload_dir: str    = str(BASE_DIR / "uploads")
    sample_kb_dir: str = str(BASE_DIR / "data" / "sample_kb")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
