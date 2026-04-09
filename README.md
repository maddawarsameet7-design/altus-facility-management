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

## 📈 Scalability Guide
For a larger production rollout:
- Use **AWS RDS** for PostgreSQL with **PostGIS** for location matching.
- Deploy via **AWS ECS** with an Application Load Balancer.
- Use **Redis** for asynchronous tasks (e.g., mass notifications and invoice generation).
