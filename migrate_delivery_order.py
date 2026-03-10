#!/usr/bin/env python3
"""
Migration script for delivery order tracking feature

Changes:
- Add delivery_order column to trip_detail table
"""

import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = 'instance/trip_monitoring.db'

    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return False

    print(f"Starting migration: {datetime.now()}")
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if delivery_order column already exists
        cursor.execute("PRAGMA table_info(trip_detail)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'delivery_order' in columns:
            print("Column 'delivery_order' already exists in trip_detail table. Skipping...")
        else:
            # Add delivery_order column to trip_detail table
            print("Adding 'delivery_order' column to trip_detail table...")
            cursor.execute("""
                ALTER TABLE trip_detail
                ADD COLUMN delivery_order INTEGER
            """)
            print("✓ Added delivery_order column")

        # Commit the changes
        conn.commit()
        print("\nMigration completed successfully!")
        return True

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        return False

    finally:
        conn.close()

if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)
