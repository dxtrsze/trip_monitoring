#!/usr/bin/env python3
"""
Migration script to add 'completed' column to trip table
Run this script to update existing databases: python migration_trip_completed.py
"""

import sys
import os
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Trip

def migrate_trip_completed():
    """Add completed column to trip table if it doesn't exist"""

    with app.app_context():
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('trip')]

        if 'completed' in columns:
            print("✓ Column 'completed' already exists in trip table")
            return

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

    print("\n✓ Migration completed successfully!")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Trip Table: Adding 'completed' Column Migration")
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
