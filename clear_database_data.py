#!/usr/bin/env python3
"""
Script to delete all data from trip_monitoring.db
Preserves: user, vehicle, cluster, manpower tables
Deletes: all other table data
"""

import sqlite3
import os
from datetime import datetime

def clear_database():
    db_path = 'instance/trip_monitoring.db'

    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return False

    print(f"Starting database cleanup: {datetime.now()}")
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Disable foreign key constraints temporarily for faster deletion
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        all_tables = [row[0] for row in cursor.fetchall()]

        # Tables to preserve
        preserve_tables = {'user', 'vehicle', 'cluster', 'manpower'}

        # Tables to delete (exclude sqlite system tables and preserved tables)
        tables_to_clear = [t for t in all_tables if not t.startswith('sqlite_') and t not in preserve_tables]

        print(f"\nTables to preserve: {', '.join(sorted(preserve_tables))}")
        print(f"Tables to clear: {', '.join(sorted(tables_to_clear))}")

        # Count rows before deletion
        total_rows = 0
        for table in tables_to_clear:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  {table}: {count} rows")

        print(f"\nTotal rows to delete: {total_rows}")

        # Delete data in order (child tables first, then parent tables)
        # Association tables first
        association_tables = ['trip_driver', 'trip_assistant']
        for table in association_tables:
            if table in tables_to_clear:
                cursor.execute(f"DELETE FROM {table}")
                print(f"✓ Cleared {table}")

        # Trip details
        if 'trip_detail' in tables_to_clear:
            cursor.execute("DELETE FROM trip_detail")
            print("✓ Cleared trip_detail")

        # Trips
        if 'trip' in tables_to_clear:
            cursor.execute("DELETE FROM trip")
            print("✓ Cleared trip")

        # Schedules
        if 'schedule' in tables_to_clear:
            cursor.execute("DELETE FROM schedule")
            print("✓ Cleared schedule")

        # Data tables
        data_tables = ['data', 'backload']
        for table in data_tables:
            if table in tables_to_clear:
                cursor.execute(f"DELETE FROM {table}")
                print(f"✓ Cleared {table}")

        # Odo readings
        if 'odo' in tables_to_clear:
            cursor.execute("DELETE FROM odo")
            print("✓ Cleared odo")

        # Daily vehicle counts
        if 'daily_vehicle_count' in tables_to_clear:
            cursor.execute("DELETE FROM daily_vehicle_count")
            print("✓ Cleared daily_vehicle_count")

        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")

        # Verify preserved tables still have data
        print(f"\nVerifying preserved tables:")
        for table in sorted(preserve_tables):
            if table in all_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} rows ✓")

        # Verify cleared tables are empty
        print(f"\nVerifying cleared tables are empty:")
        all_empty = True
        for table in sorted(tables_to_clear):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            status = "✓" if count == 0 else "✗"
            print(f"  {table}: {count} rows {status}")
            if count > 0:
                all_empty = False

        # Commit the changes
        conn.commit()

        if all_empty:
            print("\n✓ Database cleanup completed successfully!")
            print(f"✓ Preserved data in: {', '.join(sorted(preserve_tables))}")
            return True
        else:
            print("\n⚠ Some tables still contain data")
            return False

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during cleanup: {e}")
        return False

    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE CLEANUP SCRIPT")
    print("=" * 60)
    print("\n⚠ WARNING: This will DELETE data from most tables!")
    print("Preserved tables: user, vehicle, cluster, manpower")
    print("\nPress Ctrl+C to cancel, or")
    import time
    for i in range(5, 0, -1):
        print(f"Starting in {i}...", flush=True)
        time.sleep(1)

    print("\nExecuting...\n")
    success = clear_database()
    exit(0 if success else 1)
