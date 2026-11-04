# Altus: Enterprise Managed Staffing & Facility Management Platform

Altus is a production-ready, multitenant managed staffing platform connecting client organizations (Societies, Hospitals, Offices) with an employed, verified facility workforce (Housekeeping, Security, Maintenance).

## 🚀 Quality & Tech Stack
- **Backend**: Django REST Framework + PostgreSQL (Strict multitenancy, SocietyScopedMixin, RBAC-native)
- **Frontend**: React.js + Modern Vanilla CSS (Client, Supervisor, and Director Dashboards)
- **Mobile**: React Native Worker Experience (Geofenced attendance, photo tasks, relievers, offline sync)
- **Security & Storage**: Private object storage with signed URLs, sanitized image pipeline, EXIF stripping
- **Authentication**: Passwordless phone OTP for workers, HMAC-SHA256 digests, multi-device approval tracking

## 📂 Project Structure
- `/backend`: Core API, staffing engine, housekeeping SLA quality engine, OTP auth, and management commands.
- `/frontend-web`: Unified client and supervisor management portal.
- `/mobile-app`: Mobile worker application with geofenced clock-in and photo evidence capture.
- `render.yaml`: Production infrastructure definition with web service and automated background cron jobs.
- `docker-compose.yml`: Local multi-service orchestrator (PostgreSQL, Redis, Backend, Frontend).

## 🔒 Production Environment Variables & Deployment Blockers
In production (`DEBUG=False`), the system executes strict startup verification checks (`core.security_checks.validate_production_settings`). If any required variable is missing or insecure, startup aborts with `ImproperlyConfigured`:

| Environment Variable | Requirement | Failure Consequence If Missing or Invalid |
|---|---|---|
| `DEBUG` | Must default to `False`. | If `True`, debug traces expose stacks, security validations bypass, and rate throttles relax. |
| `SECRET_KEY` | Min 32 cryptographically secure characters. | Startup aborts with `ImproperlyConfigured` if missing, short (<32 chars), or using known defaults. |
| `ALLOWED_HOSTS` | Comma-separated domain names (e.g. `api.altsan.com`). | Startup aborts if empty or wildcard `[*]`. Unlisted hosts receive HTTP 400 Bad Request. |
| `CORS_ALLOWED_ORIGINS` | Exact frontend origins (e.g. `https://altsan.com`). | Startup aborts if empty. Client web and mobile browsers are blocked by CORS policy. |
| `DATABASE_URL` | PostgreSQL connection string (`postgres://...`). | Startup aborts if missing or if engine is not PostgreSQL. SQLite fallback is strictly blocked. |
| `REDIS_URL` | Redis URL (`redis://...`). | Startup aborts if missing. Required for WebSocket channels, coordination, and distributed cache. |
| `OTP_HMAC_SECRET` | Dedicated secret key (min 16 chars). | Startup aborts if missing or identical to `SECRET_KEY`. Fallback to `SECRET_KEY` is strictly prohibited. |
| `PRIVATE_STORAGE_BUCKET` | S3 / Cloud private bucket name. | Startup aborts if missing. Task photos, KYC, and selfies must never use guessable public links. |
| `SMS_PROVIDER` | `TWILIO` or `AWS_SNS`. | Startup aborts if missing or configured to `ConsoleSMSBackend`. |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Twilio credentials (if `SMS_PROVIDER=TWILIO`). | Startup aborts if any Twilio credential is missing. Workers cannot receive login OTP codes. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS credentials (if `SMS_PROVIDER=AWS_SNS` or S3). | Startup aborts if missing. SMS or private object storage dispatches fail. |
| `SMS_DAILY_GLOBAL_CAP` | Global daily SMS cap (default 500). | In-app warning to Directors at 80%; hard cutoff at 100% to protect SMS provider budget. |

## ⏱️ Scheduled Automations & Cron Jobs (`render.yaml`)
Automated staffing and housekeeping maintenance jobs are codified in `render.yaml`:
1. **Daily Staffing Roster (`generate_roster`)**: Runs daily at `00:00 UTC` (`0 0 * * *`) to generate `DailyRoster` slots for upcoming shifts.
2. **Mark Absent Shifts (`mark_absent_shifts`)**: Runs every 5 minutes (`*/5 * * * *`) to mark unclocked slots `ABSENT` past grace period and auto-open `ReplacementRequest`.
3. **Process Replacements (`process_replacements`)**: Runs every minute (`* * * * *`) to auto-offer open slots to eligible relievers and escalate nearing shifts.
4. **Daily Housekeeping Tasks (`generate_daily_tasks`)**: Runs daily at `00:00 UTC` (`0 0 * * *`) to generate daily, weekly, and monthly `TaskInstance` items from templates.
5. **Mark Missed Tasks (`mark_missed_tasks`)**: Runs every 10 minutes (`*/10 * * * *`) to mark overdue incomplete tasks `MISSED` and alert supervisors.
6. **Private Photo Retention Cleanup (`cleanup_expired_photos`)**: Runs weekly on Sundays at `02:00 UTC` (`0 2 * * 0`) with `--dry-run` default to prune expired photos while preserving complaints, shared inspections, and locked quality snapshots.

## 🛠️ Getting Started & Local Development
```bash
# 1. Clone repository
git clone https://github.com/organization/facility-marketplace.git
cd facility-marketplace

# 2. Start PostgreSQL & Redis services via Docker
docker-compose up -d db redis

# 3. Setup backend environment
cd backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# 4. Run test suite
pytest
```
