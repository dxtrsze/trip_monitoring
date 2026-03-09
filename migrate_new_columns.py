#!/usr/bin/env python3
"""
Migration script to add new columns:
- vehicle table: status (default 'Active'), capacity (float)
- data table: delivery_type (text)
- trip_detail table: delivery_type (text)
Run this script to update your existing database.
"""

import sqlite3
import os

def migrate():
    # Get the database path
    db_path = os.path.join('instance', 'trip_monitoring.db')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False

    print(f"Migrating database: {db_path}")

    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ===== MIGRATE VEHICLE TABLE =====
        print("\n--- Migrating vehicle table ---")
        cursor.execute("PRAGMA table_info(vehicle)")
        vehicle_columns = [col[1] for col in cursor.fetchall()]

        # Add status column if it doesn't exist
        if 'status' not in vehicle_columns:
            print("Adding 'status' column to vehicle table...")
            cursor.execute("ALTER TABLE vehicle ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")
            # Update existing records to have 'Active' status
            cursor.execute("UPDATE vehicle SET status = 'Active' WHERE status IS NULL")
            print("✓ Added 'status' column (default: 'Active')")
        else:
            print("✓ 'status' column already exists in vehicle table")

        # Add capacity column if it doesn't exist
        if 'capacity' not in vehicle_columns:
            print("Adding 'capacity' column to vehicle table...")
            cursor.execute("ALTER TABLE vehicle ADD COLUMN capacity FLOAT")
            print("✓ Added 'capacity' column")
        else:
            print("✓ 'capacity' column already exists in vehicle table")

        # ===== MIGRATE DATA TABLE =====
        print("\n--- Migrating data table ---")
        cursor.execute("PRAGMA table_info(data)")
        data_columns = [col[1] for col in cursor.fetchall()]

        # Add delivery_type column if it doesn't exist
        if 'delivery_type' not in data_columns:
            print("Adding 'delivery_type' column to data table...")
            cursor.execute("ALTER TABLE data ADD COLUMN delivery_type VARCHAR(100)")
            print("✓ Added 'delivery_type' column")
        else:
            print("✓ 'delivery_type' column already exists in data table")

        # ===== MIGRATE TRIP_DETAIL TABLE =====
        print("\n--- Migrating trip_detail table ---")
        cursor.execute("PRAGMA table_info(trip_detail)")
        trip_detail_columns = [col[1] for col in cursor.fetchall()]

        # Add delivery_type column if it doesn't exist
        if 'delivery_type' not in trip_detail_columns:
            print("Adding 'delivery_type' column to trip_detail table...")
            cursor.execute("ALTER TABLE trip_detail ADD COLUMN delivery_type VARCHAR(100)")
            print("✓ Added 'delivery_type' column")
        else:
            print("✓ 'delivery_type' column already exists in trip_detail table")

        # ===== MIGRATE ODO TABLE =====
        print("\n--- Migrating odo table ---")
        cursor.execute("PRAGMA table_info(odo)")
        odo_columns = [col[1] for col in cursor.fetchall()]

        # Add litters column if it doesn't exist
        if 'litters' not in odo_columns:
            print("Adding 'litters' column to odo table...")
            cursor.execute("ALTER TABLE odo ADD COLUMN litters FLOAT")
            print("✓ Added 'litters' column")
        else:
            print("✓ 'litters' column already exists in odo table")

        # Add amount column if it doesn't exist
        if 'amount' not in odo_columns:
            print("Adding 'amount' column to odo table...")
            cursor.execute("ALTER TABLE odo ADD COLUMN amount FLOAT")
            print("✓ Added 'amount' column")
        else:
            print("✓ 'amount' column already exists in odo table")

        # Add price_per_litter column if it doesn't exist
        if 'price_per_litter' not in odo_columns:
            print("Adding 'price_per_litter' column to odo table...")
            cursor.execute("ALTER TABLE odo ADD COLUMN price_per_litter FLOAT")
            print("✓ Added 'price_per_litter' column")
        else:
            print("✓ 'price_per_litter' column already exists in odo table")

        # Commit changes
        conn.commit()
        print("\n✅ All migrations completed successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Error migrating database: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    migrate()
