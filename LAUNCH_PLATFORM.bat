@echo off
TITLE Altus Facility Management - Launching Platform
SETLOCAL

:: Configuration
SET BACKEND_DIR=backend
SET FRONTEND_DIR=frontend-web

echo ======================================================
echo          ALTUS FACILITY MANAGEMENT PLATFORM           
echo ======================================================
echo.

:: Check for Local IP
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "127.0.0.1"') do set LOCAL_IP=%%a
echo [1/3] Detecting Network... Local IP: %LOCAL_IP%

:: Cleanup existing processes
echo [Cleanup] Killing zombie processes on ports 8000 and 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1

:: Start Backend
echo [2/3] Starting Django Backend...
start /b cmd /c "cd %BACKEND_DIR% && python manage.py runserver 0.0.0.0:8000"

:: Start Frontend
echo [3/3] Starting React Mobile UI...
start /b cmd /c "cd %FRONTEND_DIR% && npm run dev"

echo.
echo ======================================================
echo    PLATFORM LAUNCHED SUCCESSFULLY
echo ======================================================
echo.
echo 💻 ADMIN PANEL: http://localhost:8000/admin
echo 🌐 WEB DASHBOARD: http://localhost:5173
echo.
echo 📱 TO TEST ON IPHONE:
echo    1. Connect iPhone to the same Wi-Fi.
echo    2. Open Safari and go to: http://%LOCAL_IP%:5173
echo.
echo ======================================================
echo KEEP THIS WINDOW OPEN TO STAY CONNECTED
echo ======================================================
pause
