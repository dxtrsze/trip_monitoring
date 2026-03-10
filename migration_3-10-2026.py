#!/usr/bin/env python3
"""
Migration script for database changes made on March 10, 2026

Changes:
- Add backload_remarks column to backload table
- Add delete_remarks column to data table
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
        # Check if backload_remarks column already exists
        cursor.execute("PRAGMA table_info(backload)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'backload_remarks' in columns:
            print("Column 'backload_remarks' already exists in backload table. Skipping...")
        else:
            # Add backload_remarks column to backload table
            print("Adding 'backload_remarks' column to backload table...")
            cursor.execute("""
                ALTER TABLE backload
                ADD COLUMN backload_remarks VARCHAR(255)
            """)
            print("✓ Added backload_remarks column")

        # Check if delete_remarks column already exists in data table
        cursor.execute("PRAGMA table_info(data)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'delete_remarks' in columns:
            print("Column 'delete_remarks' already exists in data table. Skipping...")
        else:
            # Add delete_remarks column to data table
            print("Adding 'delete_remarks' column to data table...")
            cursor.execute("""
                ALTER TABLE data
                ADD COLUMN delete_remarks VARCHAR(255)
            """)
            print("✓ Added delete_remarks column")

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
