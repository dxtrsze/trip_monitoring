#!/usr/bin/env python3
"""
Background scheduler for daily tasks.
Run this script separately or integrate with app.py.
Usage: python scheduler.py
"""

import sys
import os
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
                print(f"[{datetime.now()}] Updated daily vehicle count for {today}: {active_count} active vehicles")
            else:
                # Create new record
                daily_count = DailyVehicleCount(date=today, qty=active_count)
                db.session.add(daily_count)
                print(f"[{datetime.now()}] Created daily vehicle count for {today}: {active_count} active vehicles")

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now()}] Error counting daily vehicles: {str(e)}")
            return False


def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()

    # Schedule job to run every day at 5:00 AM
    scheduler.add_job(
        func=count_daily_active_vehicles,
        trigger=CronTrigger(hour=5, minute=0),
        id='daily_vehicle_count',
        name='Count daily active vehicles',
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()
    print(f"[{datetime.now()}] Scheduler started. Daily vehicle count will run at 5:00 AM daily.")

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    return scheduler


if __name__ == '__main__':
    # Run the count once immediately (for testing)
    print("Running daily vehicle count now...")
    count_daily_active_vehicles()

    # Start the scheduler
    scheduler = start_scheduler()

    print("Scheduler is running. Press Ctrl+C to exit.")

    try:
        # Keep the script running
        import time
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down scheduler...")
        scheduler.shutdown()
        print("Scheduler shut down successfully.")
