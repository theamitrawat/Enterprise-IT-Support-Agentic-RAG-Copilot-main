# IT Support Agentic RAG Copilot

A full-stack AI-powered IT support assistant built with **LangGraph**, **FastAPI**, **Pinecone**, **Groq**, and **Tavily**. The system uses an Agentic RAG (Retrieval-Augmented Generation) workflow that searches a private company knowledge base first, grades the evidence, falls back to web search if needed, rewrites weak queries and retries — then generates a grounded, cited answer.

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
  → Retrieve from Private KB
  → Grade Evidence (good enough to answer?)
  → Web Search fallback if weak
  → Grade Web Evidence
  → Rewrite Query and Retry if still weak
  → Generate Grounded Answer
```

The agent controls **what to do next** based on the quality of evidence — not just blindly generating from whatever was retrieved.

---

## Demo Screenshots

> Run the project and open `http://127.0.0.1:8080`

The UI includes:
- **Welcome screen** with 8 example questions covering all KB topics
- **Streaming responses** — answer appears word by word like Gemini
- **Agent Trace drawer** — shows every decision the agent made (route, grade, fallback)
- **Dark / Light theme** toggle
- **Document upload** — add new company docs to the KB at runtime

---

## Architecture

```
Employee (Browser)
        │
        ▼
  FastAPI Backend
        │
        ▼
  LangGraph Workflow
   ┌────┴─────┐
   │          │
Pinecone    Tavily
Private KB  Web Search
   └────┬─────┘
        │
      Groq LLM
  (Route / Grade / Generate)
        │
        ▼
  Grounded Answer + Trace
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Workflow | LangGraph |
| LLM | Groq (`openai/gpt-oss-20b`) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` (local, no API cost) |
| Vector DB | Pinecone |
| Web Search | Tavily |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Audit Log | SQLite |
| Containerization | Docker |

---

## Project Structure

```
it-support-rag-copilot/
│
├── app/
│   ├── api/routes.py          # /chat, /chat/stream, /ingest, /health
│   ├── core/config.py         # Centralized pydantic-settings config
│   ├── core/logging.py        # Logging setup
│   ├── rag/state.py           # LangGraph TypedDict state
│   ├── rag/vectorstore.py     # Pinecone + HuggingFace embeddings
│   ├── rag/workflow.py        # Full 10-node Agentic RAG graph + streaming
│   ├── services/audit.py      # SQLite audit log
│   ├── services/ingestion.py  # PDF/TXT/MD/DOCX loader + chunker
│   └── main.py                # FastAPI app factory
│
├── data/sample_kb/            # Sample company IT documents
│   ├── company_it_handbook.md
│   └── service_desk_runbook.md
│
├── static/
│   ├── css/style.css          # Gemini-style UI with dark/light theme
│   └── js/app.js              # SSE streaming + markdown rendering
│
├── templates/index.html       # Main UI
├── Agentic-RAG-demo/          # Jupyter notebook prototype
├── docs/                      # Project documentation PDFs
├── .env.example               # Environment variable template
├── Dockerfile                 # Container deployment
├── ingest_sample_kb.py        # One-shot KB ingestion script
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project metadata
└── run.py                     # Dev server entry point
```

---

## Setup & Run

### Prerequisites
- Python 3.10+
- Accounts with free tiers: [Groq](https://console.groq.com), [Pinecone](https://www.pinecone.io), [Tavily](https://tavily.com)

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

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
PINECONE_API_KEY=your_pinecone_api_key

PINECONE_INDEX_NAME=it-support-rag
PINECONE_NAMESPACE=company-kb
EMBEDDING_MODEL=all-MiniLM-L6-v2
GROQ_MODEL=openai/gpt-oss-20b

ADMIN_API_KEY=your-secure-admin-key
APP_ENV=development
```

### Step 4 — Load the sample knowledge base

```bash
python ingest_sample_kb.py
```

This chunks the two sample IT documents and uploads their vectors to Pinecone. Only needed once.

### Step 5 — Start the server

```bash
python run.py
```

Open **http://127.0.0.1:8080** in your browser.

---

## API Reference

### `GET /api/health`
Returns server status.

### `GET /api/chat/stream?question=...`
Server-Sent Events endpoint. Streams trace steps and answer tokens in real time.

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
Body: multipart form with a `.pdf`, `.txt`, `.md`, or `.docx` file.

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

---

## License

MIT License — see [LICENSE](LICENSE)
