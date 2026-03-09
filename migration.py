#!/usr/bin/env python3
"""
Migration script to add new columns to the schedule table
Run this script: python migration.py
"""

import sqlite3
import os

def migrate_schedule_table():
    """Migrate schedule table - add new columns"""
    db_path = 'instance/trip_monitoring.db'

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(schedule)")
        columns = [column[1] for column in cursor.fetchall()]

        # Columns to add
        new_columns = {
            'plate_number': 'VARCHAR(50)',
            'capacity': 'FLOAT',
            'actual': 'FLOAT'
        }

        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                sql = f"ALTER TABLE schedule ADD COLUMN {column_name} {column_type}"
                print(f"Adding column to schedule: {column_name}")
                cursor.execute(sql)
            else:
                print(f"Column schedule.{column_name} already exists, skipping...")

        conn.commit()
        conn.close()

        print("\n✅ Schedule table migration completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Schedule table migration failed: {str(e)}")
        return False


def create_daily_vehicle_count_table():
    """Create daily_vehicle_count table"""
    db_path = 'instance/trip_monitoring.db'

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_vehicle_count'")
        table_exists = cursor.fetchone()

        if table_exists:
            print("Table daily_vehicle_count already exists, skipping...")
        else:
            # Create the table
            create_table_sql = """
            CREATE TABLE daily_vehicle_count (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                qty INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """

            cursor.execute(create_table_sql)
            conn.commit()
            print("✅ Created daily_vehicle_count table successfully!")

        # Add original_due_date column to trip_detail table if it doesn't exist
        cursor.execute("PRAGMA table_info(trip_detail)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'original_due_date' not in columns:
            cursor.execute("ALTER TABLE trip_detail ADD COLUMN original_due_date DATE")
            conn.commit()
            print("✅ Added original_due_date column to trip_detail table!")
        else:
            print("Column trip_detail.original_due_date already exists, skipping...")

        # Add total_delivered_qty column to trip_detail table if it doesn't exist
        if 'total_delivered_qty' not in columns:
            cursor.execute("ALTER TABLE trip_detail ADD COLUMN total_delivered_qty INTEGER NOT NULL DEFAULT 0")
            # Update existing records to set total_delivered_qty = total_ordered_qty
            cursor.execute("UPDATE trip_detail SET total_delivered_qty = total_ordered_qty")
            conn.commit()
            print("✅ Added total_delivered_qty column to trip_detail table!")
            print("✅ Initialized total_delivered_qty with total_ordered_qty for existing records!")
        else:
            print("Column trip_detail.total_delivered_qty already exists, skipping...")

        conn.close()
        return True

    except Exception as e:
        print(f"\n❌ Failed to create daily_vehicle_count table: {str(e)}")
        return False


def migrate_all():
    """Run all migrations"""
    print("=" * 50)
    print("Starting Database Migration")
    print("=" * 50)

    # Migrate schedule table
    print("\n1. Migrating schedule table...")
    migrate_schedule_table()

    # Create daily_vehicle_count table
    print("\n2. Creating daily_vehicle_count table...")
    create_daily_vehicle_count_table()

    print("\n" + "=" * 50)
    print("All migrations completed!")
    print("=" * 50)


if __name__ == '__main__':
    migrate_all()
