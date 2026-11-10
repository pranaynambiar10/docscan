@echo off
title DocScan 1-Click Launcher
echo ========================================================
echo        DocScan - All-in-One Local App Launcher
echo ========================================================
echo.

:: 1. Check Ollama
echo [1/3] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Ollama is already running.
) else (
    echo Starting Ollama...
    start /B "" ollama serve
    timeout /t 3 /nobreak >nul
)

:: 2. Start Backend
echo.
echo [2/3] Starting DocScan Backend (Flask + RAG + ChromaDB)...
cd /d "%~dp0backend"
start "DocScan Backend" cmd /k "python app.py"

:: 3. Start Frontend
echo.
echo [3/3] Starting DocScan Frontend (React + Vite)...
cd /d "%~dp0frontend"
start "DocScan Frontend" cmd /k "npm run dev"

:: Wait 3 seconds then open browser
timeout /t 3 /nobreak >nul
echo.
echo ========================================================
echo  All services started!
echo  Opening DocScan in browser: http://localhost:8080
echo ========================================================
start http://localhost:8080
