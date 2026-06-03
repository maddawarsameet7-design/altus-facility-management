@echo off
TITLE Altus Central Core - Unified Launcher
echo ====================================================
echo   Altus: Enterprise Facility Management Platform
echo ====================================================
echo.

:: Check for Docker
echo [1/3] Checking Docker status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker is not running. Attempting to start containers anyway...
)

:: Start Backend
echo [2/3] Orchestrating Backend Services (Docker)...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose failed. Please ensure Docker Desktop is running.
    pause
    exit /b
)

:: Start Frontend Desktop App
echo [3/3] Launching Altus Desktop Terminal...
cd frontend-web
echo Starting Electron Window...
npm run electron:dev

echo.
echo ====================================================
echo   Altus is now running in its own window.
echo   - API: http://localhost:8000
echo   - GUI: Desktop Window
echo ====================================================
pause
