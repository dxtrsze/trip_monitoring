# Flask Trip Monitoring Application

## Tech Stack
- Backend: Flask 3.1.3 + Flask-SQLAlchemy 3.1.1 + Flask-Login 0.6.3
- Database: SQLite (dev) / PostgreSQL (production planned)
- Scheduler: APScheduler 3.11.2+ with pytz timezone support
- Frontend: Vanilla HTML/CSS/JS, Bootstrap for modals

## Configuration
- Main DB: `instance/trip_monitoring.db` (SQLite)
- Archive DB: Uses SQLAlchemy binds: `app.config['SQLALCHEMY_BINDS'] = {'archive': archive_db_url}`
- SECRET_KEY should use environment variables (currently hardcoded in app.py:23)

## Database Models
Core models: Vehicle, Manpower, Data, Schedule, Trip, TripDetail, Cluster, User, Odo, DailyVehicleCount, Backload, TimeLog, LCLSummary, LCLDetail, ArchiveLog

## Code Patterns
- Use SQLAlchemy ORM only (no raw SQL in app code; clear_database_data.py is exception)
- Soft delete: `delete_remarks` (dropdown) + `detailed_remarks` (textarea)
- Flask-Login for authentication and role-based access control
- CSV upload validation: posting_date, document_number, duplicates
- In-memory cache for static reference data (SimpleCache, 5-minute TTL)

## Features
- LCL (Less than Container Load) for partial shipments
- Multi-level approval workflows
- Daily vehicle count scheduler (5:00 AM Manila time)
- Archive system with separate database

## Dashboard
- Admin-only operational dashboard at route `/`
- 6 KPIs: On-Time Rate, In-Full Rate, DIFOT Score, Truck Utilization, Fuel Efficiency, Data Completeness
- 3 trend charts: Daily Delivery Counts, Fuel Efficiency, Truck Utilization
- 3 comparison charts: Vehicle Ranking, Branch Frequency, Driver Performance
- 3 gauge charts: On-Time Rate, Utilization, Data Completeness
- Powered by Apache ECharts 5.x
- Auto-refresh with "Last updated" timestamp
- Default 7-day view, supports custom date ranges (max 90 days)
