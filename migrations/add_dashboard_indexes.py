"""
Add database indexes to improve dashboard query performance
Run: python migrations/add_dashboard_indexes.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def add_indexes():
    with app.app_context():
        print("Adding dashboard performance indexes...")

        # Index for TripDetail-Schedule joins
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_trip ON trip_detail(trip_id)'))
            db.session.commit()
            print("✓ Added index on trip_detail(trip_id)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail index: {e}")
            db.session.rollback()

        # Index for Schedule.delivery_schedule (frequently queried)
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_schedule_delivery ON schedule(delivery_schedule)'))
            db.session.commit()
            print("✓ Added index on schedule(delivery_schedule)")
        except Exception as e:
            print(f"✗ Failed to add schedule index: {e}")
            db.session.rollback()

        # Index for Odo datetime queries
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_odo_datetime ON odo(datetime)'))
            db.session.commit()
            print("✓ Added index on odo(datetime)")
        except Exception as e:
            print(f"✗ Failed to add odo index: {e}")
            db.session.rollback()

        # Index for Odo status queries
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_odo_status ON odo(status)'))
            db.session.commit()
            print("✓ Added index on odo(status)")
        except Exception as e:
            print(f"✗ Failed to add odo status index: {e}")
            db.session.rollback()

        # Index for TripDetail.arrive (data completeness queries)
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_arrive ON trip_detail(arrive)'))
            db.session.commit()
            print("✓ Added index on trip_detail(arrive)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail arrive index: {e}")
            db.session.rollback()

        # Index for TripDetail.departure
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_departure ON trip_detail(departure)'))
            db.session.commit()
            print("✓ Added index on trip_detail(departure)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail departure index: {e}")
            db.session.rollback()

        print("\n✓ Dashboard indexes added successfully!")

if __name__ == '__main__':
    add_indexes()
