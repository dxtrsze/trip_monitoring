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
from sqlalchemy.exc import IntegrityError


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
                try:
                    daily_count = DailyVehicleCount(date=today, qty=active_count)
                    db.session.add(daily_count)
                    db.session.commit()
                    print(f"[{datetime.now()}] Created daily vehicle count for {today}: {active_count} active vehicles")
                except IntegrityError:
                    # Race condition: record created by another process
                    db.session.rollback()
                    existing_count = DailyVehicleCount.query.filter_by(date=today).first()
                    if existing_count:
                        existing_count.qty = active_count
                        db.session.commit()
                        print(f"[{datetime.now()}] Updated daily vehicle count for {today} (race condition recovery): {active_count} active vehicles")

            return True

        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now()}] Error counting daily vehicles: {str(e)}", file=sys.stderr)
            return False


if __name__ == '__main__':
    success = count_daily_active_vehicles()
    sys.exit(0 if success else 1)
