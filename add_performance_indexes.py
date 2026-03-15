#!/usr/bin/env python3
"""
Performance Index Migration Script
Adds indexes to frequently queried columns for better query performance.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text, inspect

def index_exists(inspector, table_name, index_name):
    """Check if an index already exists"""
    existing_indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in existing_indexes)

def add_indexes():
    """Add performance indexes to the database"""
    indexes_to_add = [
        # Data table indexes
        ('data', 'idx_data_status', 'CREATE INDEX IF NOT EXISTS idx_data_status ON data(status)'),
        ('data', 'idx_data_due_date', 'CREATE INDEX IF NOT EXISTS idx_data_due_date ON data(due_date)'),
        ('data', 'idx_data_document_number', 'CREATE INDEX IF NOT EXISTS idx_data_document_number ON data(document_number)'),
        ('data', 'idx_data_status_due_date', 'CREATE INDEX IF NOT EXISTS idx_data_status_due_date ON data(status, due_date)'),

        # Schedule table indexes
        ('schedule', 'idx_schedule_delivery_schedule', 'CREATE INDEX IF NOT EXISTS idx_schedule_delivery_schedule ON schedule(delivery_schedule)'),

        # TripDetail table indexes
        ('trip_detail', 'idx_trip_detail_departure', 'CREATE INDEX IF NOT EXISTS idx_trip_detail_departure ON trip_detail(departure)'),

        # Odo table indexes
        ('odo', 'idx_odo_datetime', 'CREATE INDEX IF NOT EXISTS idx_odo_datetime ON odo(datetime)'),
        ('odo', 'idx_odo_plate_number', 'CREATE INDEX IF NOT EXISTS idx_odo_plate_number ON odo(plate_number)'),
        ('odo', 'idx_odo_status', 'CREATE INDEX IF NOT EXISTS idx_odo_status ON odo(status)'),
    ]

    with app.app_context():
        inspector = inspect(db.engine)
        added_count = 0
        skipped_count = 0

        print("Checking and adding performance indexes...\n")

        for table_name, index_name, create_sql in indexes_to_add:
            try:
                if index_exists(inspector, table_name, index_name):
                    print(f"✓ Index {index_name} already exists on {table_name}")
                    skipped_count += 1
                else:
                    # Execute the CREATE INDEX statement
                    db.session.execute(text(create_sql))
                    db.session.commit()
                    print(f"✓ Added index {index_name} to {table_name}")
                    added_count += 1
            except Exception as e:
                print(f"✗ Error adding index {index_name}: {str(e)}")
                db.session.rollback()

        print(f"\n{'='*60}")
        print(f"Index creation complete!")
        print(f"Added: {added_count} indexes")
        print(f"Skipped: {skipped_count} indexes (already exist)")
        print(f"{'='*60}")

        # Verify indexes were created
        print("\nVerifying indexes...")
        for table_name, index_name, _ in indexes_to_add:
            if index_exists(inspector, table_name, index_name):
                print(f"  ✓ {index_name} exists on {table_name}")

if __name__ == '__main__':
    add_indexes()
