# Daily Vehicle Count Scheduler - Systemd Timer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace unreliable embedded APScheduler with production-grade systemd timer service for daily vehicle counts at 5:00 AM Manila time.

**Architecture:** Standalone Python script executed by systemd timer service, decoupled from Flask/Gunicorn process lifecycle. Script uses Flask app context to access database, runs once per execution, exits cleanly.

**Tech Stack:** Python 3, Flask, SQLAlchemy, systemd (timer + service units), SQLite

**Design Spec:** `docs/superpowers/specs/2026-03-21-daily-vehicle-count-scheduler-design.md`

---

## File Structure

```
trip_monitoring/
├── bin/
│   └── run_daily_vehicle_count.py          # NEW: Standalone execution script
├── systemd/
│   ├── trip-monitoring-vehicle-count.service  # NEW: Systemd service unit
│   └── trip-monitoring-vehicle-count.timer     # NEW: Systemd timer unit
├── app.py                                   # MODIFY: Remove embedded scheduler
├── scheduler.py                             # DEPRECATED: Can remove
└── docs/superpowers/plans/
    └── 2026-03-21-daily-vehicle-count-scheduler-implementation.md  # This file
```

**Component Responsibilities:**
- `bin/run_daily_vehicle_count.py` - Imports Flask app, creates app context, executes vehicle count, exits
- `systemd/*.service` - Defines execution environment (user, working directory, paths)
- `systemd/*.timer` - Schedules service to run daily at 5:00 AM Manila time with persistence
- `app.py` - Remove `scheduler = init_scheduler()` call (line ~6373)

---

## Task 1: Create Directory Structure

**Files:**
- Create: `bin/` directory
- Create: `systemd/` directory

- [ ] **Step 1: Create bin directory**

Run: `mkdir -p bin`
Expected: Directory created, no errors

- [ ] **Step 2: Create systemd directory**

Run: `mkdir -p systemd`
Expected: Directory created, no errors

- [ ] **Step 3: Verify directories**

Run: `ls -la | grep -E 'bin|systemd'`
Expected: Output shows both directories

---

## Task 2: Create Standalone Execution Script

**Files:**
- Create: `bin/run_daily_vehicle_count.py`

- [ ] **Step 1: Create execution script with shebang and imports**

```bash
cat > bin/run_daily_vehicle_count.py << 'EOF'
#!/usr/bin/env python3
"""
Standalone script to run daily vehicle count.
Designed to be executed by systemd timer service.

Usage:
    python3 bin/run_daily_vehicle_count.py

Exit codes:
    0 - Success
    1 - Failure (exception occurred)
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

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
EOF
```

Expected: File created with 57 lines

- [ ] **Step 2: Make script executable**

Run: `chmod +x bin/run_daily_vehicle_count.py`
Expected: No errors, permissions updated

- [ ] **Step 3: Verify script syntax**

Run: `python3 -m py_compile bin/run_daily_vehicle_count.py`
Expected: No syntax errors

- [ ] **Step 4: Commit**

```bash
git add bin/run_daily_vehicle_count.py
git commit -m "feat: add standalone vehicle count execution script

Add standalone Python script for daily vehicle count that can be
executed by systemd timer. Script uses Flask app context to access
database and exits cleanly after execution.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Test Execution Script Manually

**Files:**
- Test: `bin/run_daily_vehicle_count.py`
- Test: Database `instance/trip_monitoring.db`

- [ ] **Step 1: Run script manually**

Run: `python3 bin/run_daily_vehicle_count.py`
Expected: Output like `[2026-03-21 ...] Created/Updated daily vehicle count for 2026-03-21: N active vehicles`

- [ ] **Step 2: Verify exit code**

Run: `echo $?`
Expected: `0` (success)

- [ ] **Step 3: Verify database record**

Run: `sqlite3 instance/trip_monitoring.db "SELECT date, qty FROM daily_vehicle_count ORDER BY date DESC LIMIT 1;"`
Expected: Shows today's date with vehicle count

- [ ] **Step 4: Test idempotency (run again)**

Run: `python3 bin/run_daily_vehicle_count.py`
Expected: Output shows "Updated" not "Created" (record already exists)

- [ ] **Step 5: Verify database has only one record for today**

Run: `sqlite3 instance/trip_monitoring.db "SELECT COUNT(*) FROM daily_vehicle_count WHERE date = date('now');"`
Expected: `1` (only one record per day)

---

## Task 4: Create Systemd Service Unit

**Files:**
- Create: `systemd/trip-monitoring-vehicle-count.service`

- [ ] **Step 1: Determine deployment configuration**

First, identify your deployment paths. Run these commands and note the values:

```bash
# Find Python interpreter
which python3
# Example output: /usr/bin/python3 or /home/user/venv/bin/python3

# Find project directory (absolute path)
pwd
# Example output: /home/user/trip_monitoring

# Find Flask app user (check how Gunicorn runs)
ps aux | grep gunicorn | grep -v grep | head -1 | awk '{print $1}'
# Example output: www-data or ubuntu or your username
```

Note these values for the next step.

- [ ] **Step 2: Create systemd service unit with placeholders**

```bash
cat > systemd/trip-monitoring-vehicle-count.service << 'EOF'
[Unit]
Description=Trip Monitoring Daily Vehicle Count
After=network.target

[Service]
Type=oneshot
User=__USER__
Group=__GROUP__
WorkingDirectory=__PROJECT_ROOT__
Environment="PATH=__PYTHON_BIN__:/usr/local/bin:/usr/bin:/bin"
ExecStart=__PYTHON_BIN__ __PROJECT_ROOT__/bin/run_daily_vehicle_count.py
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
```

Expected: File created with placeholders

- [ ] **Step 3: Replace placeholders with actual values**

Edit `systemd/trip-monitoring-vehicle-count.service` and replace:
- `__USER__` with Flask app user (e.g., `www-data`, `ubuntu`, or your username)
- `__GROUP__` with Flask app group (often same as user)
- `__PROJECT_ROOT__` with absolute path from `pwd` (e.g., `/home/user/trip_monitoring`)
- `__PYTHON_BIN__` with directory from `which python3` (e.g., `/usr/bin` or `/home/user/venv/bin`)

Example final file:
```ini
[Unit]
Description=Trip Monitoring Daily Vehicle Count
After=network.target

[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/home/user/trip_monitoring
Environment="PATH=/home/user/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/user/venv/bin/python /home/user/trip_monitoring/bin/run_daily_vehicle_count.py
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Validate systemd unit syntax**

Run: `sudo systemd-analyze verify systemd/trip-monitoring-vehicle-count.service`
Expected: No output or warnings (success)

- [ ] **Step 5: Commit**

```bash
git add systemd/trip-monitoring-vehicle-count.service
git commit -m "feat: add systemd service unit for daily vehicle count

Add systemd service unit that defines execution environment for
standalone vehicle count script. Includes proper user, working
directory, and environment configuration with retry logic.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Create Systemd Timer Unit

**Files:**
- Create: `systemd/trip-monitoring-vehicle-count.timer`

- [ ] **Step 1: Create systemd timer unit**

```bash
cat > systemd/trip-monitoring-vehicle-count.timer << 'EOF'
[Unit]
Description=Run daily vehicle count at 5:00 AM Manila time
Requires=trip-monitoring-vehicle-count.service

[Timer]
OnCalendar=05:00 Asia/Manila
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

Expected: File created with 12 lines

- [ ] **Step 2: Validate systemd timer syntax**

Run: `sudo systemd-analyze verify systemd/trip-monitoring-vehicle-count.timer`
Expected: No output or warnings (success)

- [ ] **Step 3: Verify timer schedule**

Run: `systemd-analyze calendar "05:00 Asia/Manila"`
Expected: Output showing "Normalized form: ... 05:00" and next occurrences

- [ ] **Step 4: Commit**

```bash
git add systemd/trip-monitoring-vehicle-count.timer
git add systemd/trip-monitoring-vehicle-count.service
git commit -m "feat: add systemd timer for daily 5:00 AM vehicle count

Add systemd timer unit to trigger vehicle count service daily at
5:00 AM Manila time. Persistent=true ensures missed runs execute
on system startup.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Pre-Deployment Verification

**Files:**
- Verify: File permissions
- Verify: Database access
- Verify: Virtual environment

- [ ] **Step 1: Verify project directory permissions**

Run: `ls -ld .`
Expected: Directory is readable by service user (check User= in service file)

If service user is `www-data` and directory is owned by you:
```bash
# Make directory readable by www-data
sudo chmod o+r .
```

- [ ] **Step 2: Verify database file permissions**

Run: `ls -l instance/trip_monitoring.db`
Expected: Database file is writable by service user

If service user needs write access:
```bash
# For SQLite in instance directory
sudo chmod o+w instance/trip_monitoring.db
# Or change ownership
sudo chown www-data:www-data instance/trip_monitoring.db
```

- [ ] **Step 3: Verify virtual environment accessibility**

If using virtual environment, verify service user can access it:

Run: `ls -l venv/bin/python` (or your venv path)
Expected: Python executable is readable/executable by service user

- [ ] **Step 4: Test script execution as service user**

Run: `sudo -u www-data python3 bin/run_daily_vehicle_count.py` (replace www-data with your service user)
Expected: Script executes successfully, creates/updates database record

If this fails with permission errors, fix permissions before proceeding.

---

## Task 7: Install Systemd Units

**Files:**
- Install: `/etc/systemd/system/trip-monitoring-vehicle-count.service`
- Install: `/etc/systemd/system/trip-monitoring-vehicle-count.timer`

- [ ] **Step 1: Copy service unit to systemd directory**

Run: `sudo cp systemd/trip-monitoring-vehicle-count.service /etc/systemd/system/`
Expected: No errors

- [ ] **Step 2: Copy timer unit to systemd directory**

Run: `sudo cp systemd/trip-monitoring-vehicle-count.timer /etc/systemd/system/`
Expected: No errors

- [ ] **Step 3: Reload systemd daemon**

Run: `sudo systemctl daemon-reload`
Expected: No output (success)

- [ ] **Step 4: Verify units are loaded**

Run: `systemctl list-unit-files | grep trip-monitoring`
Expected: Shows both service and timer files (disabled status)

---

## Task 8: Test Manual Service Trigger

**Files:**
- Test: Systemd service execution
- Test: systemd journal logs

- [ ] **Step 1: Start service manually (bypass timer)**

Run: `sudo systemctl start trip-monitoring-vehicle-count.service`
Expected: No output (service runs in background)

- [ ] **Step 2: Check service exit status**

Run: `sudo systemctl status trip-monitoring-vehicle-count.service`
Expected: Status shows "active (exited)" with green "Active: successful" line

- [ ] **Step 3: View service logs**

Run: `sudo journalctl -u trip-monitoring-vehicle-count.service -n 20`
Expected: Shows output like "[2026-03-21 ...] Created/Updated daily vehicle count..."

- [ ] **Step 4: Verify database record created**

Run: `sqlite3 instance/trip_monitoring.db "SELECT date, qty FROM daily_vehicle_count ORDER BY date DESC LIMIT 1;"`
Expected: Shows record with current timestamp (service ran just now)

- [ ] **Step 5: Check for errors in logs**

Run: `sudo journalctl -u trip-monitoring-vehicle-count.service --since '5 minutes ago' | grep -i error`
Expected: No output (no errors)

If errors appear, review logs and fix before proceeding.

---

## Task 9: Enable and Start Timer

**Files:**
- Enable: Systemd timer

- [ ] **Step 1: Enable timer (auto-start on boot)**

Run: `sudo systemctl enable trip-monitoring-vehicle-count.timer`
Expected: Output "Created symlink /etc/systemd/system/timers.target.wants/trip-monitoring-vehicle-count.timer → /etc/systemd/system/trip-monitoring-vehicle-count.timer."

- [ ] **Step 2: Start timer**

Run: `sudo systemctl start trip-monitoring-vehicle-count.timer`
Expected: No output (success)

- [ ] **Step 3: Verify timer is active**

Run: `sudo systemctl status trip-monitoring-vehicle-count.timer`
Expected: Shows "loaded" and "active (active)" with green status

- [ ] **Step 4: Check next scheduled run time**

Run: `systemctl list-timers trip-monitoring-vehicle-count.timer`
Expected: Shows timer with "NEXT" column showing tomorrow 5:00 AM

Alternative command:
```bash
sudo systemctl show trip-monitoring-vehicle-count.timer --property=NextElapseUSecMonotonic
```

- [ ] **Step 5: Verify timer persistence**

Run: `systemctl show trip-monitoring-vehicle-count.timer --property=Persistent`
Expected: `Persistent=yes`

---

## Task 10: Remove Embedded Scheduler from Flask App

**Files:**
- Modify: `app.py:6373` (approximately)

- [ ] **Step 1: Find scheduler initialization line**

Run: `grep -n "scheduler = init_scheduler()" app.py`
Expected: Shows line number (typically around 6373)

Note the exact line number for next step.

- [ ] **Step 2: Comment out scheduler initialization**

Edit `app.py` and comment out the scheduler initialization line:

```python
# OLD (line ~6373):
# scheduler = init_scheduler()

# NEW:
# scheduler = init_scheduler()  # DEPRECATED: Replaced by systemd timer
scheduler = None
```

- [ ] **Step 3: Verify app still runs without errors**

Run: `python3 -c "from app import app; print('App loads successfully')"`
Expected: Output "App loads successfully" with no import errors

- [ ] **Step 4: Test Flask app basic functionality**

Run: `python3 -c "from app import app, db; with app.app_context(): print(f'Database: {db.engine.url}')"`
Expected: Shows database URL without errors

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "refactor: remove embedded scheduler, replaced by systemd timer

Comment out init_scheduler() call in app.py. Scheduler functionality
is now handled by systemd timer service (trip-monitoring-vehicle-count.timer).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Restart Flask Application

**Files:**
- Restart: Gunicorn or Flask application service

- [ ] **Step 1: Identify Flask application service name**

Run: `systemctl | grep -i flask` or `systemctl | grep -i gunicorn` or `ps aux | grep gunicorn`
Expected: Shows service name (e.g., `gunicorn`, `flask-app`, etc.)

- [ ] **Step 2: Restart Flask application service**

Run: `sudo systemctl restart <service-name>` (replace with actual service name)
Expected: Service restarts successfully

Example:
```bash
sudo systemctl restart gunicorn
# or
sudo systemctl restart flask-app
```

- [ ] **Step 3: Verify application is running**

Run: `sudo systemctl status <service-name>`
Expected: Shows "active (running)" with green status

- [ ] **Step 4: Test web application is accessible**

Run: `curl -I http://localhost:8000` (or your app port)
Expected: HTTP response with status 200 or redirect

- [ ] **Step 5: Verify old scheduler is not running**

Run: `ps aux | grep -i scheduler | grep -v grep`
Expected: No output (no standalone scheduler process)

---

## Task 12: End-to-End Verification

**Files:**
- Verify: Complete system functionality

- [ ] **Step 1: Check all systemd units status**

Run:
```bash
echo "=== Timer Status ==="
sudo systemctl status trip-monitoring-vehicle-count.timer --no-pager
echo ""
echo "=== Service Status ==="
sudo systemctl status trip-monitoring-vehicle-count.service --no-pager
echo ""
echo "=== Next Run ==="
systemctl list-timers trip-monitoring-vehicle-count.timer --no-pager
```

Expected: Timer active, service exists, next run scheduled for 5:00 AM

- [ ] **Step 2: Verify admin panel shows vehicle counts**

Open browser: Navigate to `/daily_vehicle_counts` route
Expected: Page loads, shows historical vehicle counts including today

- [ ] **Step 3: Manually trigger service one more time**

Run: `sudo systemctl start trip-monitoring-vehicle-count.service`
Expected: Service starts and exits successfully

- [ ] **Step 4: Verify log shows latest execution**

Run: `sudo journalctl -u trip-monitoring-vehicle-count.service --since '1 minute ago'`
Expected: Shows log entry from manual trigger

- [ ] **Step 5: Check database has latest record**

Run: `sqlite3 instance/trip_monitoring.db "SELECT datetime, date, qty FROM daily_vehicle_count ORDER BY date DESC LIMIT 3;"`
Expected: Shows today's record with recent timestamp

- [ ] **Step 6: Document deployment**

Create deployment notes for your records:
```bash
cat > DEPLOYMENT_NOTES.md << 'EOF'
# Daily Vehicle Count Scheduler Deployment

**Date:** $(date +%Y-%m-%d)
**Deployment:** Systemd timer replacing embedded APScheduler

## Systemd Units
- Service: /etc/systemd/system/trip-monitoring-vehicle-count.service
- Timer: /etc/systemd/system/trip-monitoring-vehicle-count.timer

## Schedule
Daily at 5:00 AM Manila time (Asia/Manila timezone)

## Monitoring
Check status: sudo systemctl status trip-monitoring-vehicle-count.timer
View logs: sudo journalctl -u trip-monitoring-vehicle-count.service -f
Next run: systemctl list-timers trip-monitoring-vehicle-count.timer

## Manual Trigger
sudo systemctl start trip-monitoring-vehicle-count.service

## Rollback
See deployment plan rollback procedure if needed.
EOF
```

---

## Task 13: Clean Up Deprecated Files (Optional)

**Files:**
- Remove: `scheduler.py` (deprecated)

- [ ] **Step 1: Verify scheduler.py is not referenced**

Run: `grep -r "scheduler.py" . --include="*.py" --include="*.md" --exclude-dir=.git`
Expected: Only shows the file itself, no imports or references

- [ ] **Step 2: Remove deprecated scheduler.py**

Run: `git rm scheduler.py`
Expected: File staged for removal

- [ ] **Step 3: Commit cleanup**

```bash
git commit -m "chore: remove deprecated scheduler.py

Replaced by systemd timer service. Standalone script at
bin/run_daily_vehicle_count.py now handles daily execution.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 4: Update documentation (if any references old scheduler)**

Check if README, CLAUDE.md, or other docs mention the old scheduler and update them.

---

## Rollback Procedure

If issues arise after deployment, execute these steps to restore the old scheduler:

- [ ] **Rollback Step 1: Stop and disable timer**

Run: `sudo systemctl stop trip-monitoring-vehicle-count.timer && sudo systemctl disable trip-monitoring-vehicle-count.timer`
Expected: Timer stopped and disabled

- [ ] **Rollback Step 2: Remove systemd units**

Run: `sudo rm /etc/systemd/system/trip-monitoring-vehicle-count.* && sudo systemctl daemon-reload`
Expected: Files removed, daemon reloaded

- [ ] **Rollback Step 3: Restore old scheduler in app.py**

Edit `app.py` and uncomment:
```python
scheduler = init_scheduler()
```

Remove:
```python
scheduler = None
```

- [ ] **Rollback Step 4: Restart Flask application**

Run: `sudo systemctl restart <service-name>` (gunicorn, flask-app, etc.)
Expected: App restarts with embedded scheduler

- [ ] **Rollback Step 5: Verify old scheduler works**

Check logs or wait for scheduled time to confirm embedded scheduler runs.

---

## Testing Checklist

After completing all tasks, verify:

- [ ] Script runs manually: `python3 bin/run_daily_vehicle_count.py`
- [ ] Script creates database record correctly
- [ ] Service unit validates: `systemd-analyze verify`
- [ ] Timer unit validates: `systemd-analyze verify`
- [ ] Service starts manually: `systemctl start ...service`
- [ ] Service logs appear in journal: `journalctl -u ...service`
- [ ] Timer is enabled and active: `systemctl status ...timer`
- [ ] Timer shows next run time: `systemctl list-timers ...timer`
- [ ] Flask app runs without embedded scheduler
- [ ] Admin panel shows vehicle counts
- [ ] Manual trigger works: `systemctl start ...service`
- [ ] No permission errors in logs
- [ ] No Python import errors
- [ ] Database record created/updated correctly
- [ ] Deployment notes documented

---

## Success Criteria

- ✅ Vehicle count recorded daily at 5:00 AM Manila time
- ✅ Recording continues across Gunicorn worker restarts
- ✅ Recording continues across Flask application deployments
- ✅ Logs available via journalctl
- ✅ Admin panel shows accurate daily counts
- ✅ Manual verification possible via `systemctl start` command
- ✅ Systemd timer persists across system reboots
- ✅ No embedded scheduler dependency in Flask app

---

## Completion

All tasks complete! The daily vehicle count scheduler is now running via systemd timer, providing reliable, production-grade scheduling that survives Flask application restarts and Gunicorn worker restarts.

**Next Steps:**
- Monitor logs for first few days to ensure reliability
- Consider adding log aggregation if monitoring at scale
- Document any customizations for your specific environment
