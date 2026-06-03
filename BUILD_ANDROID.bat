@echo off
TITLE Altus - Android Build Tool
SETLOCAL

SET FRONTEND_DIR=frontend-web

echo ======================================================
echo          ALTUS ANDROID BUILD SYSTEM
echo ======================================================
echo.

echo [1/3] Syncing latest code with Android...
cd %FRONTEND_DIR%
call npm run build
call npx cap sync android

echo.
echo [2/3] Opening Android Studio...
call npx cap open android

echo.
echo [3/3] DONE!
echo.
echo ======================================================
echo IN ANDROID STUDIO:
echo 1. Wait for "Gradle Sync" to finish.
echo 2. Connect your Android phone via USB.
echo 3. Click the GREEN PLAY button at the top.
echo ======================================================
echo.
pause
