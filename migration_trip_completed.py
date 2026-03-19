#!/usr/bin/env python3
"""
Migration script to add 'completed' column to trip table and 'type' column to vehicle table
Run this script to update existing databases: python migration_trip_completed.py
"""

import sys
import os
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Trip, Vehicle

def migrate_trip_completed():
    """Add completed column to trip table and type column to vehicle table if they don't exist"""

    with app.app_context():
        # ========== TRIP TABLE MIGRATION ==========
        print("=" * 60)
        print("Trip Table: Adding 'completed' Column")
        print("=" * 60)

        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('trip')]

        if 'completed' in columns:
            print("✓ Column 'completed' already exists in trip table")
        else:
            print("Adding 'completed' column to trip table...")

            try:
                # Add the column using raw SQL
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE trip ADD COLUMN completed BOOLEAN DEFAULT 0"))
                    conn.commit()

                print("✓ Successfully added 'completed' column to trip table")

                # Verify the column was added
                inspector = db.inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('trip')]

                if 'completed' in columns:
                    print("✓ Verification successful: 'completed' column exists")
                    print(f"  Total columns in trip table: {len(columns)}")
                else:
                    print("✗ Verification failed: 'completed' column not found")
                    return False

            except Exception as e:
                print(f"✗ Error adding column: {e}")
                return False

            # Set default value for existing trips
            try:
                existing_trips = Trip.query.count()
                print(f"\nUpdating {existing_trips} existing trips...")

                # Update all existing trips to have completed = False
                db.session.query(Trip).update({Trip.completed: False})
                db.session.commit()

                print("✓ All existing trips updated with completed = False")

            except Exception as e:
                print(f"✗ Error updating existing trips: {e}")
                db.session.rollback()
                return False

        # ========== VEHICLE TABLE MIGRATION ==========
        print("\n" + "=" * 60)
        print("Vehicle Table: Adding 'type' Column")
        print("=" * 60)

        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            vehicle_columns = [col['name'] for col in inspector.get_columns('vehicle')]

            if 'type' in vehicle_columns:
                print("✓ Column 'type' already exists in vehicle table")
            else:
                print("Adding 'type' column to vehicle table...")

                # Add the column using raw SQL
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE vehicle ADD COLUMN type VARCHAR(50)"))
                    conn.commit()

                print("✓ Successfully added 'type' column to vehicle table")

                # Verify the column was added
                inspector = db.inspect(db.engine)
                vehicle_columns = [col['name'] for col in inspector.get_columns('vehicle')]

                if 'type' in vehicle_columns:
                    print("✓ Verification successful: 'type' column exists")
                    print(f"  Total columns in vehicle table: {len(vehicle_columns)}")
                else:
                    print("✗ Verification failed: 'type' column not found")
                    return False

                # Set default value for existing vehicles
                existing_vehicles = Vehicle.query.count()
                print(f"\nUpdating {existing_vehicles} existing vehicles...")

                # Update all existing vehicles to have type = 'in-house'
                db.session.query(Vehicle).update({Vehicle.type: 'in-house'})
                db.session.commit()

                print("✓ All existing vehicles updated with type = 'in-house'")

        except Exception as e:
            print(f"✗ Error adding vehicle type column: {e}")
            db.session.rollback()
            return False

    print("\n✓ Migration completed successfully!")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration Script")
    print("Adding 'completed' column to trip table")
    print("Adding 'type' column to vehicle table")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = migrate_trip_completed()

    print()
    print("=" * 60)
    if success:
        print("Migration completed successfully!")
        sys.exit(0)
    else:
        print("Migration failed!")
        sys.exit(1)
