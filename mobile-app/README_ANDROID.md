# Altsan Worker Android Build & Keystore Documentation

This document describes how to generate debug APKs and signed release AABs for **Altsan Worker** (`com.altsan.worker`).

---

## 1. Security & Hardening Checklist
- **Cleartext Traffic:** Disabled (`android:usesCleartextTraffic="false"`). All network communications must use HTTPS.
- **WebView Debugging:** Disabled in production release builds (`WebView.setWebContentsDebuggingEnabled(false)`).
- **Auto-Backup:** Disabled (`android:allowBackup="false"`, `android:fullBackupContent="false"`). Tokens and queue data are never backed up to Google Drive.
- **Permissions:** Strictly foreground-only permissions (`CAMERA`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`). No background location.
- **Min SDK:** 26 (Android 8.0+ Oreo) with hardware-backed Keystore support.
- **Build Guard:** The Vite web build fails immediately if `VITE_API_URL` is missing or is not an `https://` URL.

---

## 2. Generating a Release Keystore (Local/CI)
To generate an upload key for Google Play or ad-hoc pilot distribution, run:

```bash
keytool -genkeypair -v -keystore altsan-worker-release.keystore \
  -alias altsan-worker -keyalg RSA -keysize 2048 -validity 10000
```

> **NEVER commit `altsan-worker-release.keystore` or its passwords to Git.**

---

## 3. Building the Release AAB (Android App Bundle)

Supply keystore credentials through environment variables:

```bash
# Set environment variables (PowerShell)
$env:KEYSTORE_PATH="C:\path\to\altsan-worker-release.keystore"
$env:KEYSTORE_ALIAS="altsan-worker"
$env:KEYSTORE_PASSWORD="YourSecretKeystorePassword"
$env:VITE_API_URL="https://api.altsan.com/api"

# 1. Build the hardened web bundle
npm run build

# 2. Sync to Android native project
npx cap sync android

# 3. Compile signed release bundle
cd android
./gradlew bundleRelease
```

The output bundle will be located at:
`android/app/build/outputs/bundle/release/app-release.aab`

---

## 4. Building the Debug / Preview APK for Internal Field Pilot

For testing on real pilot devices without Google Play:

```bash
# 1. Build web bundle with staging API
$env:VITE_API_URL="https://api.altsan.com/api"
npm run build

# 2. Sync native project
npx cap sync android

# 3. Assemble debug APK
cd android
./gradlew assembleDebug
```

The debug APK will be located at:
`android/app/build/outputs/apk/debug/app-debug.apk`
