#!/bin/bash
# ============================================================
# DocScan — Linux Server Deploy Script
# Usage: bash deploy.sh
# ============================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════╗"
echo "║   DocScan — Linux Server Deploy      ║"
echo "║   RAG + Gunicorn + Ollama (qwen2.5)  ║"
echo "╚══════════════════════════════════════╝"
echo -e "${RESET}"

# ── 0. Detect OS ──────────────────────────────────────────────────────────────
OS=$(uname -s)
if [ "$OS" != "Linux" ]; then
  echo "Warning: This script is designed for Linux. Detected: $OS"
fi

# ── 1. Install Ollama (if not present) ───────────────────────────────────────
echo -e "${BOLD}[1/6] Checking Ollama...${RESET}"
if ! command -v ollama &> /dev/null; then
  echo "  Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo -e "  ${GREEN}Ollama already installed: $(ollama --version)${RESET}"
fi

# ── 2. Start Ollama service ───────────────────────────────────────────────────
echo -e "${BOLD}[2/6] Starting Ollama service...${RESET}"
if ! pgrep -x ollama > /dev/null; then
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  sleep 4  # Wait for Ollama to initialize
  echo -e "  ${GREEN}Ollama started (PID: $(pgrep ollama))${RESET}"
else
  echo -e "  ${GREEN}Ollama already running${RESET}"
fi

# ── 3. Pull LLM model ─────────────────────────────────────────────────────────
MODEL=${OLLAMA_MODEL:-qwen2.5:3b}
echo -e "${BOLD}[3/6] Pulling model: ${MODEL}...${RESET}"
echo "  (This may take a few minutes on first run)"
ollama pull "$MODEL"
echo -e "  ${GREEN}Model ready: ${MODEL}${RESET}"

# ── 4. Install Python dependencies ────────────────────────────────────────────
echo -e "${BOLD}[4/6] Installing Python dependencies...${RESET}"
cd "$(dirname "$0")/backend"
pip install -r requirements.txt --quiet
echo -e "  ${GREEN}Dependencies installed${RESET}"

# ── 5. Pre-cache embedding model ──────────────────────────────────────────────
echo -e "${BOLD}[5/6] Pre-caching embedding model (all-MiniLM-L6-v2)...${RESET}"
EMBED_MODEL=${EMBED_MODEL:-all-MiniLM-L6-v2}
python -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('$EMBED_MODEL')
print(f'  Cached: $EMBED_MODEL ({m.get_embedding_dimension()}d vectors)')
"
echo -e "  ${GREEN}Embedding model cached${RESET}"

# ── 6. Run smoke test ─────────────────────────────────────────────────────────
echo -e "${BOLD}[6/6] Running RAG smoke test...${RESET}"
python test_rag.py
echo -e "  ${GREEN}Smoke test passed!${RESET}"

# ── Start the backend ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ All checks passed! Starting DocScan backend...${RESET}"
echo ""

WORKERS=${GUNICORN_WORKERS:-4}
echo -e "${CYAN}  Gunicorn: ${WORKERS} workers (gevent async)"
echo -e "  Listening: http://0.0.0.0:5000"
echo -e "  LLM: ${MODEL}"
echo -e "  RAG: ChromaDB + ${EMBED_MODEL}${RESET}"
echo ""

# Initialize DB then start Gunicorn
python -c "
from app import init_database
init_database()
print('Database initialized')
"

exec gunicorn \
  -w "$WORKERS" \
  -k gevent \
  --worker-connections 100 \
  --timeout 120 \
  --bind 0.0.0.0:5000 \
  --access-logfile - \
  --error-logfile - \
  app:app
