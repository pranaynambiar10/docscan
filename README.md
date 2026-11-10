
# DocScan — AI-Powered Document OCR & Q&A

> **Full-stack document intelligence app** — upload PDFs, bills, invoices, and images; extract text with OCR; ask questions using a local LLM powered by Ollama. All processing stays **on your company server** — no data leaves your network.

**Developers:** Pranay Nambiar (CUSAT) · Noor Muhammad KP (CUSAT)

---

## ✨ Features

- 📄 Upload **PDF, DOCX, TXT, JPG, PNG** documents
- ⚡ Fast text extraction — **PyMuPDF** (5–10× faster than PyPDF2) + **PaddleOCR** for scanned images
- 🧠 **RAG pipeline** — semantic vector search retrieves only the most relevant chunks before querying the LLM (handles 100+ page bills accurately)
- 💬 Ask natural-language questions: *"What is the total amount?"*, *"Who is the vendor?"*
- 🔒 **100% local** — Ollama runs the LLM on your server; no API keys, no cloud
- 🐳 **Docker Compose** — one command to run everything
- 📦 **Duplicate detection** — MD5 hash cache skips re-processing identical files

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| **Backend** | Python 3.10, Flask, Gunicorn + Gevent (production server) |
| **OCR** | PyMuPDF (PDFs), PaddleOCR (images/scanned docs) |
| **RAG** | sentence-transformers (`all-MiniLM-L6-v2`), ChromaDB (local vector store) |
| **LLM** | Ollama — `qwen2.5:3b` (default) — fully local, free |
| **Database** | SQLite with WAL mode |
| **Container** | Docker Compose |

---

## 🧠 LLM — Which Model & Why

The app uses **`qwen2.5:3b`** by default via [Ollama](https://ollama.com/):

| Model | Size | RAM | Speed | Quality | Use When |
|---|---|---|---|---|---|
| `qwen2.5:1.5b` | 1.5B | ~2 GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | Low-RAM server |
| **`qwen2.5:3b`** ✅ | 3B | ~4 GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | **Default — best balance** |
| `qwen2.5:7b` | 7B | ~8 GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | GPU server, max accuracy |
| `llama3.2:3b` | 3B | ~4 GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Alternative |
| `mistral:7b` | 7B | ~8 GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Accuracy-first |

Switch model by editing `.env`:
```bash
OLLAMA_MODEL=qwen2.5:3b   # change this line — no code edit needed
```

---

## 🔍 RAG Pipeline — How It Works

Traditional approach (slow, inaccurate for large docs):
```
100-page PDF → 50,000 tokens → LLM context overflows → bad answers
```

DocScan's RAG approach:
```
100-page PDF → chunk into 500-char pieces → embed as vectors → ChromaDB
Question     → embed question → cosine similarity search → top 5 chunks → LLM → accurate answer
```

**Verified retrieval accuracy:** `"What is the invoice total?"` → Score **0.803** match to `"Invoice Total: Rs. 45,230.00"` — with zero keyword overlap.

---

## 🚀 Quick Start (Docker — Recommended)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/)
- 4 GB free RAM minimum (8 GB recommended)

### 1. Clone & Configure
```bash
git clone https://github.com/pranaynambiar10/docscan.git
cd docscan
cp .env .env.local   # optional: customize model, workers, etc.
```

### 2. Start Everything
```bash
docker compose up --build
```

This automatically:
- Starts **Ollama** and pulls `qwen2.5:3b` (~2 GB, one-time download)
- Builds the **backend** with Gunicorn + RAG pipeline
- Builds the **React frontend**
- Wires everything together

### 3. Open the App
```
http://localhost:5173
```

---

## 🖥️ Manual Setup (Linux Server without Docker)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Use the deploy script (does everything automatically)
bash deploy.sh
```

The deploy script:
1. Installs/starts Ollama
2. Pulls `qwen2.5:3b`
3. Installs Python dependencies
4. Pre-caches the embedding model (`all-MiniLM-L6-v2`)
5. Runs smoke test (verifies RAG pipeline)
6. Starts Gunicorn with 4 workers

### Manual Steps (if you prefer)
```bash
# Backend
cd backend
pip install -r requirements.txt

# Pre-cache embedding model (one-time)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Start Ollama + pull model
ollama serve &
ollama pull qwen2.5:3b

# Run backend (production)
gunicorn -w 4 -k gevent --worker-connections 100 --timeout 120 -b 0.0.0.0:5000 app:app

# Frontend (separate terminal)
cd ../frontend
npm install
npm run dev
```

---

## 📁 Project Structure

```
docscan/
├── backend/
│   ├── app.py              # Flask routes (/upload, /chat, /health, /documents)
│   ├── file_processor.py   # PyMuPDF + PaddleOCR + hash dedup cache
│   ├── AI_service.py       # Ollama LLM client — RAG-aware prompting
│   ├── rag_engine.py       # ChromaDB + sentence-transformers RAG engine ✨ NEW
│   ├── requirements.txt    # Python dependencies
│   ├── test_rag.py         # RAG smoke test
│   ├── uploads/            # Uploaded documents
│   ├── chroma_db/          # Vector index (auto-created, persisted)
│   └── documents.db        # SQLite metadata
├── frontend/
│   └── src/
│       ├── pages/Index.tsx
│       └── components/
├── deploy.sh               # Linux server deploy script ✨ NEW
├── docker-compose.yml      # Ollama + Backend + Frontend
├── Dockerfile.backend      # Gunicorn + RAG deps + pre-cached model
├── Dockerfile.frontend
└── .env                    # Configuration (model, workers, RAG tuning)
```

---

## ⚙️ Configuration (`.env`)

```bash
# LLM
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_URL=http://ollama:11434/api/generate

# Server
GUNICORN_WORKERS=4          # 2 × CPU cores + 1 (e.g. 9 for 4-core server)

# RAG Tuning
EMBED_MODEL=all-MiniLM-L6-v2
CHROMA_DB_PATH=./chroma_db
RAG_CHUNK_SIZE=500           # Smaller (300) = more precise bill line items
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=5                  # Chunks sent to LLM per question
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload & process document (OCR + RAG index) |
| `POST` | `/chat` | Ask a question about a document |
| `GET` | `/health` | Health check (returns model name + RAG status) |
| `GET` | `/documents` | List all indexed documents |

### Chat Request Example
```json
POST /chat
{
  "message": "What is the total invoice amount?",
  "filename": "invoice_nov2026.pdf"
}
```
```json
Response:
{
  "response": "The invoice total is Rs. 45,230.00 including GST.",
  "chunks_used": 5,
  "rag_enabled": true
}
```

---

## 🐳 GPU Support (Nvidia)

Uncomment in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Then in `backend/.env`:
```bash
OLLAMA_MODEL=qwen2.5:7b    # Upgrade to 7B with GPU
```

---

## 📄 License

MIT
