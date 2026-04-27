#!/usr/bin/env python3
"""
Migration script to create location_log table
Run this script to update existing databases: python migrations/add_location_log.py
"""

import sys
import os
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import inspect, text


def migrate_location_log():
    """Create location_log table with proper indexes if it doesn't exist"""

    with app.app_context():
        print("=" * 60)
        print("Location Log Table: Creating Table and Indexes")
        print("=" * 60)

        # Check if table already exists
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if 'location_log' in existing_tables:
            print("✓ Table 'location_log' already exists")
            print("  Skipping table creation.")
        else:
            print("Creating 'location_log' table...")

            try:
                # Create the table using raw SQL
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        CREATE TABLE location_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            trip_detail_id INTEGER NOT NULL REFERENCES trip_detail(id),
                            action_type VARCHAR(20) NOT NULL,
                            latitude FLOAT NOT NULL,
                            longitude FLOAT NOT NULL,
                            captured_at TIMESTAMP NOT NULL,
                            user_id INTEGER NOT NULL REFERENCES user(id),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """))
                    conn.commit()

                print("✓ Successfully created 'location_log' table")

                # Verify the table was created
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()

                if 'location_log' in tables:
                    print("✓ Verification successful: 'location_log' table exists")
                    print(f"  Total tables in database: {len(tables)}")
                else:
                    print("✗ Verification failed: 'location_log' table not found")
                    return False

            except Exception as e:
                print(f"✗ Error creating table: {e}")
                return False

        # Create indexes (these are idempotent with IF NOT EXISTS)
        print("\n" + "=" * 60)
        print("Creating Indexes")
        print("=" * 60)

        indexes_created = 0

        # Index on trip_detail_id
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    'CREATE INDEX IF NOT EXISTS idx_location_log_trip_detail '
                    'ON location_log(trip_detail_id)'
                ))
                conn.commit()
            print("✓ Created index idx_location_log_trip_detail on trip_detail_id")
            indexes_created += 1
        except Exception as e:
            print(f"✗ Failed to create idx_location_log_trip_detail: {e}")

        # Index on user_id
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    'CREATE INDEX IF NOT EXISTS idx_location_log_user '
                    'ON location_log(user_id)'
                ))
                conn.commit()
            print("✓ Created index idx_location_log_user on user_id")
            indexes_created += 1
        except Exception as e:
            print(f"✗ Failed to create idx_location_log_user: {e}")

        # Index on created_at
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    'CREATE INDEX IF NOT EXISTS idx_location_log_created '
                    'ON location_log(created_at)'
                ))
                conn.commit()
            print("✓ Created index idx_location_log_created on created_at")
            indexes_created += 1
        except Exception as e:
            print(f"✗ Failed to create idx_location_log_created: {e}")

        if indexes_created == 3:
            print(f"\n✓ All {indexes_created} indexes created successfully")
        else:
            print(f"\n⚠ Created {indexes_created} out of 3 indexes")

        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        return True


if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration Script")
    print("Creating location_log table with indexes")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = migrate_location_log()

    print()
    print("=" * 60)
    if success:
        print("Migration completed successfully!")
        sys.exit(0)
    else:
        print("Migration failed!")
        sys.exit(1)
