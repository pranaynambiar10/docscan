#!/bin/bash
# ==============================================================================
# DocScan — 1-Step Unified Server Launcher (Linux)
# Usage: ./start-server.sh
# ==============================================================================
set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║          🚀 DocScan — All-in-One Server Launcher          ║"
echo "║          Ollama (1.5B/3B) + Flask Backend + Frontend      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Docker is available
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo -e "${GREEN}🐳 Docker & Docker Compose detected!${NC}"
    echo -e "Starting all services in unified containers (Ollama, Backend, Frontend)..."
    docker compose up -d --build
    echo ""
    echo -e "${BOLD}${GREEN}============================================================${NC}"
    echo -e "${BOLD}${GREEN}🎉 DocScan is up and running in 1 step!${NC}"
    echo -e "  🌐 Frontend:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8080"
    echo -e "  ⚙️  Backend:   http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):5000"
    echo -e "  🤖 Ollama:    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):11434"
    echo -e "${BOLD}${GREEN}============================================================${NC}"
    echo -e "To view logs: ${CYAN}docker compose logs -f${NC}"
    echo -e "To stop:      ${YELLOW}docker compose down${NC}"
    exit 0
fi

# Fallback: Native launch without Docker
echo -e "${YELLOW}Docker daemon not active, starting natively...${NC}"

# 1. Start Ollama
echo -e "${BOLD}[1/3] Checking Ollama service...${NC}"
if ! pgrep -x "ollama" > /dev/null; then
    if ! command -v ollama &> /dev/null; then
        echo "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    echo "Starting Ollama in background..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
fi

echo "Ensuring AI models are ready..."
ollama pull qwen2.5:1.5b || true
ollama pull qwen2.5:3b || true
echo -e "  ${GREEN}✅ Ollama running on port 11434${NC}"

# 2. Start Backend
echo -e "${BOLD}[2/3] Starting Flask/Gunicorn Backend...${NC}"
cd "$(dirname "$0")/backend"
pip install -r requirements.txt --quiet || true

if command -v gunicorn &> /dev/null; then
    nohup gunicorn -w 4 -k gevent --worker-connections 100 --timeout 120 --bind 0.0.0.0:5000 app:app > /tmp/docscan_backend.log 2>&1 &
else
    nohup python app.py > /tmp/docscan_backend.log 2>&1 &
fi
echo -e "  ${GREEN}✅ Backend running on port 5000${NC}"

# 3. Start Frontend
echo -e "${BOLD}[3/3] Starting Frontend UI...${NC}"
cd "../frontend"
npm install --silent || true
nohup npm run dev -- --host > /tmp/docscan_frontend.log 2>&1 &
echo -e "  ${GREEN}✅ Frontend running on port 8080${NC}"

echo ""
echo -e "${BOLD}${GREEN}============================================================${NC}"
echo -e "${BOLD}${GREEN}🎉 DocScan is up and running in 1 step!${NC}"
echo -e "  🌐 Frontend:  http://localhost:8080"
echo -e "  ⚙️  Backend:   http://localhost:5000"
echo -e "${BOLD}${GREEN}============================================================${NC}"

