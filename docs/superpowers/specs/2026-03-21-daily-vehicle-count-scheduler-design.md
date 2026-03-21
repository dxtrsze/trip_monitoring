# Daily Vehicle Count Scheduler - Systemd Timer Implementation

**Date:** 2026-03-21
**Status:** Design
**Author:** Claude Code
**Issue:** BackgroundScheduler embedded in Flask app fails to run reliably when Gunicorn restarts workers

## Problem Statement

The current daily vehicle count scheduler uses APScheduler's `BackgroundScheduler` running within the Flask application process. This approach fails in production because:

1. **Gunicorn worker restarts** kill the scheduler process
2. **No persistence** across application deployments or restarts
3. **Tight coupling** between scheduling logic and Flask application lifecycle
4. **Single point of failure** - if Flask process dies, scheduling stops

Current behavior: Vehicle counts are not consistently recorded at 5:00 AM Manila time.

**Note on Scheduled Time Inconsistency:**
The codebase has an inconsistency: `app.py` (line 6348) correctly schedules for 5:00 AM, but the standalone `scheduler.py` (line 62) schedules for 8:00 AM. This design uses 5:00 AM as the target, matching the production configuration in `app.py`.

## Requirements

- **Functional:** Record daily active vehicle count once per day
- **Timing:** Target 5:00 AM Manila time (flexible window acceptable)
- **Reliability:** Survive Gunicorn worker restarts and application deployments
- **Monitoring:** Manual verification via admin panel sufficient
- **Environment:** Traditional VPS/dedicated server with systemd
- **Complexity:** Minimal operational overhead

## Proposed Solution

Replace embedded `BackgroundScheduler` with **systemd timer service** - a standard Linux approach for scheduled tasks.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Systemd Timer Unit                       │
│  (triggers daily at 5:00 AM Asia/Manila, persistent)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Systemd Service Unit                      │
│  (defines execution context: user, env, working dir)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           Standalone Python Execution Script                │
│  (bin/run_daily_vehicle_count.py - runs once, exits)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask App Context                        │
│  (imports app.py, creates app context for DB access)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           count_daily_active_vehicles()                     │
│  (existing function - queries vehicles, creates record)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              DailyVehicleCount Database Record              │
│  (create or update record for today's date)                 │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Execution Script (`bin/run_daily_vehicle_count.py`)

Lightweight Python script that:
- Imports Flask app using `sys.path` manipulation
- Creates app context to access **both databases** (main + archive via SQLAlchemy binds)
- Calls existing `count_daily_active_vehicles()` function
- Writes output to stdout/stderr (captured by systemd journal)
- Exits with status code: 0 (success) or 1 (failure)

**Key characteristics:**
- Runs once and exits (not long-running)
- No APScheduler dependency
- Minimal code, leverages existing function
- Safe to run multiple times (checks for existing records)
- **Database Access:** Script properly loads Flask app configuration including `SQLALCHEMY_BINDS` for archive database

**Full script implementation:** See Appendix A - Execution Script Code

#### 2. Systemd Service (`trip-monitoring-vehicle-count.service`)

Defines execution environment:

```ini
[Unit]
Description=Trip Monitoring Daily Vehicle Count
After=network.target

[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/path/to/trip_monitoring
Environment="PATH=/path/to/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/path/to/venv/bin/python /path/to/trip_monitoring/bin/run_daily_vehicle_count.py
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

**Key settings:**
- `Type=oneshot`: Service runs once and exits (expected behavior)
- `StandardOutput/Error=journal`: Logs captured by systemd journal
- `Environment`: Full PATH including system binaries
- `Restart=on-failure`: Retries on transient failures with 60s delay
- Service user: Should match Flask app user for database permissions

#### 3. Systemd Timer (`trip-monitoring-vehicle-count.timer`)

Scheduling configuration:

```ini
[Unit]
Description=Run daily vehicle count at 5:00 AM Manila time
Requires=trip-monitoring-vehicle-count.service

[Timer]
OnCalendar=05:00 Asia/Manila
Persistent=true

[Install]
WantedBy=timers.target
```

**Key settings:**
- `OnCalendar=05:00 Asia/Manila`: Runs at 5:00 AM Manila time daily
- `Persistent=true`: If system was off at scheduled time, runs on next startup
- `Requires=service`: Ensures service unit is available

### File Structure

```
trip_monitoring/
├── bin/
│   └── run_daily_vehicle_count.py          # NEW: Execution script
├── systemd/
│   ├── trip-monitoring-vehicle-count.service  # NEW: Service unit
│   └── trip-monitoring-vehicle-count.timer     # NEW: Timer unit
├── app.py                                   # MODIFY: Remove embedded scheduler
├── models.py                                # UNCHANGED
└── scheduler.py                             # DEPRECATED: Can be removed
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Database connection failure | Script exits code 1, error logged to journal, retries next day |
| Database locked (SQLite) | Exception raised, logged to journal, systemd retries after 60s (up to default retry limit) |
| System reboot at 4:59 AM | `Persistent=true` ensures run on startup, no duplicate (code checks existing) |
| Multiple manual triggers | Safe - updates existing record instead of duplicating |
| Gunicorn restart during execution | Not impacted - separate process with own app context |

**Logging:**
- Success output → systemd journal (INFO level)
- Error output → systemd journal (ERR level)
- View logs: `journalctl -u trip-monitoring-vehicle-count.service`
- Follow logs: `journalctl -u trip-monitoring-vehicle-count.service -f`

## Testing Plan

### 1. Script Testing
```bash
# Manual execution test
python bin/run_daily_vehicle_count.py

# Verify exit code
echo $?

# Check database for record
sqlite3 instance/trip_monitoring.db "SELECT * FROM daily_vehicle_count ORDER BY date DESC LIMIT 1"
```

### 2. Service Testing
```bash
# Install and test service
sudo systemctl start trip-monitoring-vehicle-count.service
sudo systemctl status trip-monitoring-vehicle-count.service
sudo journalctl -u trip-monitoring-vehicle-count.service -n 50
```

### 3. Timer Testing
```bash
# Enable and start timer
sudo systemctl enable trip-monitoring-vehicle-count.timer
sudo systemctl start trip-monitoring-vehicle-count.timer

# Verify next run time
systemctl list-timers trip-monitoring-vehicle-count.timer

# Manual trigger for testing
sudo systemctl start trip-monitoring-vehicle-count.service
```

### 4. Verification Checklist
- ✓ Script executes without errors
- ✓ Service status shows "active (exited)"
- ✓ Timer is enabled and shows next run time
- ✓ DailyVehicleCount record created/updated
- ✓ Logs visible in journal
- ✓ Admin panel displays new count

## Deployment Steps

### Phase 1: Preparation
1. Create directory structure: `mkdir -p bin systemd`
2. Write execution script to `bin/run_daily_vehicle_count.py`
3. Make script executable: `chmod +x bin/run_daily_vehicle_count.py`
4. Test script manually from project root

### Phase 2: Pre-Deployment Checklist
Before installing systemd units, verify:
- [ ] Flask app user (e.g., `www-data`) has read access to project directory
- [ ] SQLite database files are writable by Flask app user
- [ ] Virtual environment is accessible to Flask app user
- [ ] Python interpreter path is correct and executable
- [ ] All required dependencies installed in virtual environment

### Phase 3: Systemd Configuration
1. Update paths in `systemd/trip-monitoring-vehicle-count.service`:
   - `User=` and `Group=` (match Flask app user)
   - `WorkingDirectory=` (absolute path to trip_monitoring)
   - `Environment=PATH=` (include venv/bin + system paths)
   - `ExecStart=` (absolute paths to python and script)

2. Validate systemd unit syntax:
   ```bash
   sudo systemd-analyze verify systemd/trip-monitoring-vehicle-count.service
   sudo systemd-analyze verify systemd/trip-monitoring-vehicle-count.timer
   ```

3. Install systemd units:
   ```bash
   sudo cp systemd/trip-monitoring-vehicle-count.service /etc/systemd/system/
   sudo cp systemd/trip-monitoring-vehicle-count.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

### Phase 4: Enable Timer
```bash
sudo systemctl enable trip-monitoring-vehicle-count.timer
sudo systemctl start trip-monitoring-vehicle-count.timer
systemctl list-timers | grep vehicle-count
```

### Phase 5: Cleanup Old Scheduler
1. Comment out `scheduler = init_scheduler()` in `app.py` (line ~6373)
2. Optionally remove `scheduler.py`
3. Restart Gunicorn: `sudo systemctl restart gunicorn` (or your service name)
4. Verify old scheduler is no longer running

### Phase 6: Final Verification
```bash
# Check timer status
sudo systemctl status trip-monitoring-vehicle-count.timer

# Trigger manual test
sudo systemctl start trip-monitoring-vehicle-count.service

# Check logs
sudo journalctl -u trip-monitoring-vehicle-count.service -n 20

# Verify in admin panel
# Navigate to the daily vehicle counts page (route: /daily_vehicle_counts)
# and confirm record created for today's date
```

### Rollback Procedure
If issues arise:
```bash
# Stop and disable timer
sudo systemctl stop trip-monitoring-vehicle-count.timer
sudo systemctl disable trip-monitoring-vehicle-count.timer

# Remove systemd files
sudo rm /etc/systemd/system/trip-monitoring-vehicle-count.*
sudo systemctl daemon-reload

# Restore old scheduler in app.py
# Uncomment: scheduler = init_scheduler()
# Restart Gunicorn
sudo systemctl restart gunicorn
```

## Benefits

1. **Reliability:** Decoupled from Flask process lifecycle
2. **Persistence:** Survives deployments, worker restarts, system reboots
3. **Simplicity:** Standard Linux tools, well-documented
4. **Observability:** Built-in logging via journalctl
5. **Safety:** `Persistent=true` ensures missed runs execute on startup
6. **Maintenance:** Minimal ongoing operational overhead
7. **Testing:** Easy to test manually with `systemctl start`

## Trade-offs

| Aspect | Chosen Approach | Alternatives Considered |
|--------|----------------|------------------------|
| Complexity | Low (standard Linux tools) | Medium (Celery), High (custom solution) |
| Dependencies | None (systemd only) | Redis/RabbitMQ (Celery) |
| Portability | Linux-only | Cron (more portable) |
| Flexibility | Fixed schedule | Dynamic scheduling (APScheduler in code) |
| Monitoring | Manual (journalctl) | Automated alerts (not needed per requirements) |

## Future Considerations

- If multiple scheduled tasks are needed, consider consolidating into a single timer with a script that runs multiple jobs
- For enhanced monitoring, add log aggregation or alerting if task fails
- For timezone flexibility, timer can be modified without code changes

## Success Criteria

- ✓ Vehicle count recorded daily at 5:00 AM Manila time
- ✓ Recording continues across Gunicorn worker restarts
- ✓ Recording continues across Flask application deployments
- ✓ Logs available for troubleshooting
- ✓ Admin panel shows accurate daily counts
- ✓ Manual verification possible via admin panel

---

## Appendix A: Execution Script Code

```python
#!/usr/bin/env python3
"""
Standalone script to run daily vehicle count.
Designed to be executed by systemd timer service.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import DailyVehicleCount, Vehicle


def count_daily_active_vehicles():
    """Count active vehicles and save to DailyVehicleCount table"""
    with app.app_context():
        try:
            today = datetime.now().date()

            # Check if record already exists for today
            existing_count = DailyVehicleCount.query.filter_by(date=today).first()

            # Count active vehicles
            active_count = Vehicle.query.filter_by(status='Active').count()

            if existing_count:
                # Update existing record
                existing_count.qty = active_count
                db.session.commit()
                print(f"[{datetime.now()}] Updated daily vehicle count for {today}: {active_count} active vehicles")
            else:
                # Create new record
                daily_count = DailyVehicleCount(date=today, qty=active_count)
                db.session.add(daily_count)
                db.session.commit()
                print(f"[{datetime.now()}] Created daily vehicle count for {today}: {active_count} active vehicles")

            return True

        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now()}] Error counting daily vehicles: {str(e)}", file=sys.stderr)
            return False


if __name__ == '__main__':
    success = count_daily_active_vehicles()
    sys.exit(0 if success else 1)
```

**Usage:**
```bash
# Direct execution (for testing)
python3 bin/run_daily_vehicle_count.py

# Via systemd
sudo systemctl start trip-monitoring-vehicle-count.service
```

---

## Appendix B: Monitoring and Troubleshooting

### Checking Timer Status
```bash
# List all timers
systemctl list-timers

# Check specific timer
systemctl status trip-monitoring-vehicle-count.timer

# View next scheduled run time
systemctl show trip-monitoring-vehicle-count.timer --property=NextElapseUSecMonotonic
```

### Viewing Logs
```bash
# Recent logs
sudo journalctl -u trip-monitoring-vehicle-count.service -n 50

# Follow logs in real-time
sudo journalctl -u trip-monitoring-vehicle-count.service -f

# Logs from today only
sudo journalctl -u trip-monitoring-vehicle-count.service --since today

# Logs from last run
sudo journalctl -u trip-monitoring-vehicle-count.service --since "1 hour ago"
```

### Expected Log Output

**Success:**
```
Mar 21 05:00:01 hostname python3[12345]: [2026-03-21 05:00:01.123456] Created daily vehicle count for 2026-03-21: 42 active vehicles
```

**Error (database locked):**
```
Mar 21 05:00:01 hostname python3[12345]: [2026-03-21 05:00:01.123456] Error counting daily vehicles: database is locked
```

### Manual Trigger
```bash
# Force immediate execution (useful for testing)
sudo systemctl start trip-monitoring-vehicle-count.service

# Check exit code
sudo systemctl show trip-monitoring-vehicle-count.service --property=ExecMainStatus
```
