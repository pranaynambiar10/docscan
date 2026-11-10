# ==============================================================================
# DocScan — Windows PowerShell 1-Click Launcher
# Usage: .\start or .\start.ps1
# ==============================================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "        DocScan - All-in-One Local App Launcher         " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Check Ollama
Write-Host "[1/3] Checking Ollama service..." -ForegroundColor Yellow
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollamaProc) {
    Write-Host "  ✅ Ollama is already running." -ForegroundColor Green
} else {
    Write-Host "  Starting Ollama in background..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# 2. Start Backend
Write-Host "[2/3] Starting DocScan Backend (Flask + RAG + ChromaDB)..." -ForegroundColor Yellow
$backendPath = Join-Path $rootDir "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; python app.py"

# 3. Start Frontend
Write-Host "[3/3] Starting DocScan Frontend (React + Vite)..." -ForegroundColor Yellow
$frontendPath = Join-Path $rootDir "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"

# Wait and open browser
Start-Sleep -Seconds 3
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "🎉 All services started!" -ForegroundColor Green
Write-Host "🌐 Opening DocScan in browser: http://localhost:8080" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

Start-Process "http://localhost:8080"
