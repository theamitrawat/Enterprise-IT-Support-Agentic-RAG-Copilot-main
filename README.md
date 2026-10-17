# IT Support Agentic RAG Copilot

A full-stack AI-powered IT support assistant built with **LangGraph**, **FastAPI**, **ChromaDB**, **Groq**, and **Tavily**. The system uses an Agentic RAG workflow that searches a private company knowledge base first, grades the evidence, falls back to web search if needed, rewrites weak queries and retries — then generates a grounded answer.

---

## What Makes This Different from Normal RAG

Standard RAG does this:
```
Question → Retrieve → Generate
```

This project makes decisions at every step:
```
Question
  → Route (IT question or casual chat?)
  → Retrieve from Private KB (ChromaDB)
  → Grade Evidence (good enough to answer?)
  → Web Search fallback if weak
  → Grade Web Evidence
  → Rewrite Query and Retry if still weak
  → Generate Grounded Answer
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Workflow | LangGraph |
| LLM | Groq (`openai/gpt-oss-20b`) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` (local, no API cost) |
| Vector DB | FAISS (local disk — no API, no downloads, instant) |
| Web Search | Tavily |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Audit Log | SQLite |
| Containerization | Docker |

---

## Project Structure

```
it-support-rag-copilot/
├── app/
│   ├── api/routes.py          # /chat, /ingest, /health
│   ├── core/config.py         # Centralized settings
│   ├── core/logging.py        # Logging setup
│   ├── rag/state.py           # LangGraph TypedDict state
│   ├── rag/vectorstore.py     # ChromaDB + HuggingFace embeddings
│   ├── rag/workflow.py        # 10-node Agentic RAG graph
│   ├── services/audit.py      # SQLite audit log
│   ├── services/ingestion.py  # PDF/TXT/MD/DOCX loader + chunker
│   └── main.py                # FastAPI app factory
├── data/
│   ├── sample_kb/             # Sample company IT documents
│   └── chroma_db/             # ChromaDB vector store (auto-created)
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/index.html
├── Agentic-RAG-demo/          # Jupyter notebook prototype
├── docs/                      # Project documentation PDFs
├── .env.example
├── Dockerfile
├── ingest_sample_kb.py        # One-shot KB ingestion script
├── requirements.txt
└── run.py
```

---

## Setup & Run

### Prerequisites
- Python 3.10+
- Free API accounts: [Groq](https://console.groq.com), [Tavily](https://tavily.com)
- No Pinecone or any other vector DB account needed

### Step 1 — Clone and create virtual environment

```bash
git clone https://github.com/your-username/it-support-rag-copilot.git
cd it-support-rag-copilot

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

> First run downloads the `all-MiniLM-L6-v2` embedding model (~90 MB). Subsequent runs are instant.

### Step 3 — Configure environment

Copy `.env.example` to `.env` and fill in your API keys:

```env
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key

EMBEDDING_MODEL=all-MiniLM-L6-v2
GROQ_MODEL=openai/gpt-oss-20b

ADMIN_API_KEY=your-secure-admin-key
APP_ENV=development
```

### Step 4 — Load the sample knowledge base

```bash
python ingest_sample_kb.py
```

This chunks the two sample IT documents and saves their vectors to ChromaDB locally in `data/chroma_db/`. Only needed once.

### Step 5 — Start the server

```bash
python run.py
```

Open **http://127.0.0.1:8080** in your browser.

---

## API Reference

### `GET /api/health`
Returns server status.

### `POST /api/chat`
```json
{ "question": "How do I reset my company password?" }
```
Returns:
```json
{
  "answer": "...",
  "source_used": "private_kb",
  "trace": ["Router -> KB", "Private KB retrieval -> 4 chunks", "KB evidence grade -> GOOD", "Answer generation -> PRIVATE KB"],
  "citations": []
}
```

### `POST /api/ingest`
Header: `X-Admin-Key: your-admin-key`
Body: multipart form with `.pdf`, `.txt`, `.md`, or `.docx` file.

---

## Example Questions to Try

**Access & Security**
- How do I connect to the company VPN from home?
- My VPN connection keeps failing, what should I check?
- How do I reset my company password using self-service?
- My account got locked after too many failed login attempts. What do I do?

**Hardware & Software**
- My laptop is running very slow. How do I fix it?
- I lost my company laptop. What steps should I take immediately?
- How do I install software not in the Software Portal?
- I cannot send or receive emails. How do I troubleshoot this?

---

## Docker

```bash
docker build -t it-support-copilot .
docker run -p 8080:8080 --env-file .env it-support-copilot
```

> Note: When running in Docker, run `python ingest_sample_kb.py` inside the container after first start to populate ChromaDB.

---

## License

MIT License — see [LICENSE](LICENSE)
