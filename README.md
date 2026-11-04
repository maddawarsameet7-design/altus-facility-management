# Altus: Enterprise Facility Management Marketplace

Altus is a production-ready service marketplace connecting organizations (Hospitals, Societies, Offices) with a verified facility management workforce (Housekeeping, Security, Maintenance).

## 🚀 Quality & Tech Stack
- **Backend**: Django REST Framework + PostgreSQL (Scalable, RBAC-native)
- **Frontend**: React.js + Modern Vanilla CSS (Premium, Minimalist UI)
- **Mobile Concept**: React Native-ready Attendance & Job screens
- **Deployment**: Dockerized services for AWS/Cloud consistency

## 📂 Project Structure
- `/backend`: Core API, JWT Auth, Pricing Engine, and RBAC logic.
- `/frontend-web`: Unified dashboard for Clients and Admins with dynamic routing.
- `/mobile-app`: Mobile-first Worker experience screens.
- `docker-compose.yml`: Local orchestrator for DB, Backend, and Frontend.

## ✨ Core Features
1. **Client Control**: Manage properties, book multi-worker services, and track status.
2. **Worker Logistics**: GPS-aware attendance, job acceptance/decline, and earnings tracking.
3. **Admin Power**: Document verification pipeline, platform analytics, and pricing management.
4. **Automated Business Logic**: Automated invoicing and price estimation based on worker-hours.

## 🛠️ Getting Started
### Using Docker (Highly Recommended)
```bash
docker-compose up --build
```
The application will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/

### Development Setup
1. **Backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```
2. **Frontend**:
   ```bash
   cd frontend-web
   npm install
   npm run dev
   ```

## ⏱️ Scheduled Automations & Management Commands
- **Staffing Roster Generation**: `python manage.py generate_roster [--date YYYY-MM-DD] [--days N]` (Runs daily before shift start)
- **Attendance Absent Shifts**: `python manage.py mark_absent_shifts` (Runs periodically after grace window to mark unclocked slots ABSENT and trigger replacements)
- **Replacement Auto-Offering**: `python manage.py process_replacements` (Auto-offers unfilled/absent/leave slots and escalates nearing shifts)
- **Housekeeping Daily Tasks**: `python manage.py generate_daily_tasks [--date YYYY-MM-DD] [--days N]` (Generates daily/weekly/monthly task instances from active templates)
- **Mark Missed Tasks**: `python manage.py mark_missed_tasks` (Marks overdue PENDING, IN_PROGRESS, or AWAITING_EVIDENCE tasks as MISSED with alerts)
- **Private Photo Retention Cleanup**: `python manage.py cleanup_expired_photos [--dry-run]` (Prunes sanitized photos older than `photo_retention_days`)
- **Worker Password Decommission**: `python manage.py decommission_worker_passwords` (Decommissions legacy passwords to enforce passwordless OTP authentication)

## 📈 Scalability Guide
For a larger production rollout:
- Use **AWS RDS** for PostgreSQL with **PostGIS** for location matching.
- Deploy via **AWS ECS** with an Application Load Balancer.
- Use **Redis** for asynchronous tasks (e.g., mass notifications and invoice generation).
