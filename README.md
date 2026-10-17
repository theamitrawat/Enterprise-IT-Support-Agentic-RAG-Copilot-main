# Enterprise IT Support Agentic RAG Copilot

A web-based IT support assistant built with FastAPI, LangGraph, Groq, and ChromaDB. It searches the local company knowledge base first, grades the retrieved evidence, and uses Groq to produce a grounded answer. If the private knowledge base is insufficient, it can optionally search the web with Tavily.

## Features

- Chat UI, JSON API, and document-upload endpoint.
- Persistent ChromaDB vector storage with local, deterministic embeddings; no embedding model download or embedding API key is required.
- Automatic first-start indexing of the bundled sample IT documents.
- PDF, TXT, Markdown, and DOCX document ingestion.
- Optional Tavily web-search fallback.
- Render Blueprint and Docker deployment configuration.
- Health endpoint: `GET /api/health`.

## Requirements

- Python 3.10+ for local development, or Docker.
- A [Groq API key](https://console.groq.com/) for generated answers.
- Optional [Tavily API key](https://tavily.com/) for external web search.
- A Render account to deploy to Render. The included Render Blueprint uses a paid web-service plan and persistent disk so ChromaDB, uploaded documents, and the audit database survive restarts and deploys.

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/theamitrawat/Enterprise-IT-Support-Agentic-RAG-Copilot-main.git
cd Enterprise-IT-Support-Agentic-RAG-Copilot-main
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env`, then edit the values:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

# Optional. Without this, the copilot answers from the private knowledge base only.
TAVILY_API_KEY=

# Change this if you will use the document upload endpoint.
ADMIN_API_KEY=replace-with-a-long-random-secret
APP_ENV=development
```

Keep `.env` private; it is ignored by Git.

### 5. Start the application

```bash
python run.py
```

Open <http://127.0.0.1:8080>. The first startup automatically indexes supported files in `data/sample_kb/` and `uploads/` if the Chroma collection is empty. You can also run `python ingest_sample_kb.py` to index/update the bundled sample documents manually.

For a quick readiness check, open <http://127.0.0.1:8080/api/health>. The response includes the indexed chunk count and whether Groq and web search are configured.

## Deploy to Render

This repository includes a root-level [`render.yaml`](./render.yaml) Blueprint. It builds the included Dockerfile, exposes the health-check endpoint, creates a persistent disk mounted at `/var/data`, and configures ChromaDB, uploads, and SQLite audit data to use that disk.

> **Plan and storage note:** Render persistent disks are available on paid web services. The included Blueprint uses the `starter` plan and a 1 GB disk. A free Render instance has an ephemeral filesystem; its Chroma index and uploaded files can be lost when the service restarts or deploys. Do not remove the disk configuration for a production knowledge base.

### Deploy with the Blueprint

1. Push this project to a GitHub repository that you own.
2. In the [Render Dashboard](https://dashboard.render.com/), select **New** → **Blueprint** and connect that repository.
3. Render will read `render.yaml`. Enter your `GROQ_API_KEY` when prompted and create the Blueprint.
4. Wait for the first build and deploy to complete. The app indexes the sample knowledge base on startup.
5. Open the service URL shown in Render. Confirm `https://<your-service>.onrender.com/api/health` returns `"status": "ok"` and a positive `knowledge_base_chunks` count.
6. Add `TAVILY_API_KEY` in the service's **Environment** settings if you want web fallback. It is optional; save the change and redeploy.
7. The Blueprint generates an `ADMIN_API_KEY` automatically. View it in the service's **Environment** settings and use it as the `X-Admin-Key` header when uploading documents. Keep this value secret.

Render automatically redeploys when changes are pushed to the connected branch. Review the service logs in Render if the build or health check fails. Because ChromaDB is a local database, keep this service to one instance; the attached persistent disk cannot be shared across multiple instances.

### Deploy manually (without a Blueprint)

Create a Render **Web Service** from the repository and set:

| Setting | Value |
|---|---|
| Runtime | Docker |
| Dockerfile path | `./Dockerfile` |
| Health check path | `/api/health` |

Add these environment variables in Render:

| Key | Value |
|---|---|
| `APP_ENV` | `production` |
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `ADMIN_API_KEY` | A long, random secret |
| `CHROMA_DB_PATH` | `/var/data/chroma_db` |
| `AUDIT_DB_PATH` | `/var/data/audit.db` |
| `UPLOAD_DIR` | `/var/data/uploads` |
| `TAVILY_API_KEY` | Optional Tavily API key |

Attach a persistent disk mounted at `/var/data` before relying on the deployment to preserve data. Use one instance.

## API

### `GET /api/health`

Returns service status, indexed document chunk count, and provider configuration status.

### `POST /api/chat`

Request:

```json
{
  "question": "How do I reset my company password?"
}
```

Returns an answer, its source, workflow trace, and citations.

### `POST /api/ingest`

Upload a `.pdf`, `.txt`, `.md`, or `.docx` file as multipart form data with field name `file`. Include the configured admin key in the `X-Admin-Key` header.

Example:

```bash
curl -X POST "https://<your-service>.onrender.com/api/ingest" \
  -H "X-Admin-Key: <your-admin-api-key>" \
  -F "file=@company-policy.pdf"
```

## Docker (local)

Build and run with persistent local Docker storage:

```bash
docker build -t it-support-copilot .
docker run --rm -p 8080:8080 --env-file .env \
  -e CHROMA_DB_PATH=/var/data/chroma_db \
  -e AUDIT_DB_PATH=/var/data/audit.db \
  -e UPLOAD_DIR=/var/data/uploads \
  -v it-support-copilot-data:/var/data \
  it-support-copilot
```

Open <http://127.0.0.1:8080>. To stop the container, press Ctrl+C. The named Docker volume preserves indexed data across container replacements.

## Tests

Run the focused RAG and ChromaDB tests:

```bash
python -m unittest discover -s tests -v
```

## Project layout

```text
app/
  api/routes.py          Chat, health, and document-ingestion endpoints
  core/config.py         Environment-based application settings
  rag/state.py           LangGraph state and evidence schema
  rag/vectorstore.py     Persistent ChromaDB and local embeddings
  rag/workflow.py        Retrieval, evidence grading, and answer workflow
  services/audit.py      SQLite audit log
  services/ingestion.py  PDF/TXT/MD/DOCX loading and chunking
  main.py                FastAPI app and startup indexing
data/sample_kb/          Bundled example knowledge base
static/                  Browser JavaScript and styles
templates/               Chat UI template
tests/                   Focused unit tests
Dockerfile               Container build and startup
docker-entrypoint.sh     Persistent-volume ownership and privilege drop
render.yaml              Render Blueprint
```

`Agentic-RAG-demo/` contains a standalone exploratory notebook and is not part of the FastAPI application or Render deployment. Deploy the repository root using the root `requirements.txt` and `Dockerfile`.

The old `data/faiss_index/` directory is not used by the current application. Re-ingest the original source documents if they are not already present under `data/sample_kb/` or `uploads/`.
