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

## 4. Building the Staging / Preview APK for Internal Field Pilot

> [!IMPORTANT]
> **PREVIEW BUILDS MUST ALWAYS USE STAGING AND NEVER THE PRODUCTION API.**
> Building a preview or test APK against the production API risks corrupting live customer staffing rosters and submitting invalid attendance records.

### Prerequisites Before the Staging APK Can Work
Before deploying the preview APK to test phones, verify:
1. **Live Reachable Staging Backend:** A running Django staging backend with an active HTTPS endpoint reachable from mobile cell data (e.g. `https://staging-api.yourdomain.com/api`).
2. **Valid SSL/TLS Certificate:** Android enforces strict HTTPS (`android:usesCleartextTraffic="false"`). Self-signed or expired certs will be rejected by Android's network security config.
3. **Staging Environment File:** Set `VITE_API_URL` in `mobile-app/.env.staging` (or export `$env:VITE_API_URL`). Never commit secrets or production credentials.
4. **Seeded Test Workers & Roster:** Ensure active workers exist with verified phones (`+91...`) and scheduled roster entries for today.

```bash
# 1. Build web bundle using the dedicated staging profile
npm run build:staging

# 2. Sync web assets & native plugins
npx cap sync android

# 3. Assemble debug/preview APK
cd android
./gradlew assembleDebug
```

The debug APK will be located at:
`android/app/build/outputs/apk/debug/app-debug.apk`

When launched, the app renders a high-visibility amber banner at the top:
`🟡 STAGING ENVIRONMENT — DO NOT USE REAL DATA`

---

## 5. Storage Architecture & Manual Testing Guide (Amendment 5)

### Storage Separation
- **Photo Evidence:** Stored on the local Android filesystem via `@capacitor/filesystem` in `Directory.Data` (`/data/data/com.altsan.worker/files/`). Photos are captured, compressed to 85% JPEG, and written to disk before network dispatch.
- **Offline Mutation Queue:** Stored in IndexedDB (`idb`) in Chromium's sandboxed LevelDB directory.
- **Tokens & Credentials:** Stored securely in Android Keystore / `EncryptedSharedPreferences` via `capacitor-secure-storage-plugin`.
- **Operating System Persistence:** The app requests persistent storage on boot via `navigator.storage.persist()`. The result is logged to console (`[Storage] navigator.storage.persist() granted: true/false`).
- **Main Screen Indicators:** The Attendance screen displays `Last Synced: {time}` and a live badge of pending offline items (`⏳ {count} unconfirmed`).

### Manual Checklist for Storage Clearing & Edge Cases
1. **Device Storage Clearing (Android Settings):**
   - Open **Settings > Apps > Altsan Worker > Storage**.
   - Tap **Clear Cache**: Open app &rarr; Verify queue items, logged-in session, and un-synced photos remain intact.
   - Tap **Clear Storage / Data**: Open app &rarr; Verify app returns cleanly to the Phone OTP sign-in screen without crashing.
2. **Chrome Remote DevTools Inspection:**
   - Connect phone via USB debugging.
   - Open `chrome://inspect/#devices` on your desktop browser.
   - Click **Inspect** under Altsan Worker.
   - Under **Application > Storage > IndexedDB**, inspect `altsan_offline_queue`. Verify records transition from `PENDING` &rarr; `CONFIRMED`.
3. **Airplane Mode / Underground Basement:**
   - Enable Airplane Mode &rarr; Clock in &rarr; Snap task photo &rarr; Complete task.
   - Verify amber "saved locally" banners appear.
   - Disable Airplane Mode &rarr; Tap "Sync Now" &rarr; Verify queue flushes in strict DAG order.

---

## 6. Backend Field Name Inconsistencies & Mapping Reference (Amendment 8)

The mobile app includes a centralized request builder (`requestBuilders.js`) to map disparate field names across Django endpoints:

| Action / Entity | Endpoint | UUID Key | Timestamp Key | GPS Accuracy Key | Coordinates Keys | File Multipart Key |
|---|---|---|---|---|---|
| **Roster Clock-In** | `POST /api/roster/clock-in/` | `clock_in_uuid` | `client_timestamp` | `accuracy` | `lat`, `lng` | `selfie` |
| **Roster Clock-Out** | `POST /api/roster/clock-out/` | `clock_out_uuid` | `client_timestamp` | N/A | N/A | N/A |
| **Task Claim** | `POST /api/housekeeping/tasks/{id}/claim/` | N/A | `action_timestamp` | N/A | N/A | N/A |
| **Task Photo** | `POST /api/housekeeping/tasks/{id}/photos/` | `client_uuid` | `captured_at` | `gps_accuracy_m` | `lat`, `lng` | `file` |
| **Task Complete** | `POST /api/housekeeping/tasks/{id}/complete/` | N/A | `action_timestamp` | N/A | N/A | `expected_photo_uuids` (list) |

*Note on Mock Location:* Standard mobile WebView / `@capacitor/geolocation` does not reliably expose provider flags across low-end Android OEM skins (MIUI, ColorOS). The app intentionally omits `is_mock` and `is_mock_location` so the server stores unflagged/unknown. Location integrity relies on shutter-time selfie capture and strict geofence radius checks.
