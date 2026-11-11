@echo off
TITLE Altsan - Android APK Build Pipeline
SETLOCAL ENABLEDELAYEDEXPANSION

SET FRONTEND_DIR=mobile-app

echo ======================================================
echo          ALTSAN NATIVE ANDROID BUILD SYSTEM
echo ======================================================
echo.

if not defined JAVA_HOME (
    if exist "C:\Program Files\Android\Android Studio\jbr" (
        set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
        set "PATH=!JAVA_HOME!\bin;!PATH!"
        echo [INFO] Detected Android Studio JDK at !JAVA_HOME!
    )
)

echo [1/4] Building web application (Staging Profile)...
cd %FRONTEND_DIR%
call npm run build:staging
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Web build failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/4] Syncing assets and native plugins to Android...
call npx cap sync android
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Capacitor sync failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/4] Compiling native Android APK via Gradle...
cd android
call gradlew.bat assembleDebug
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Gradle compilation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [4/4] Packaging APK to root release folder...
cd ..\..
if not exist "bin" mkdir "bin"
copy /Y "mobile-app\android\app\build\outputs\apk\debug\app-debug.apk" "bin\Altsan-Worker-Debug.apk" >nul

echo.
echo ======================================================
echo  BUILD SUCCESSFUL!
echo  APK: bin\Altsan-Worker-Debug.apk
echo ======================================================
echo.
echo You can transfer "Altsan-Worker-Debug.apk" to your phone
echo via USB, WhatsApp, or Google Drive to install and test.
echo.
pause
