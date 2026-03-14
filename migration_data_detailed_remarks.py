#!/usr/bin/env python3
"""
Migration script to add detailed_remarks column to Data table
Run this script to update your existing database
Usage: python migration_data_detailed_remarks.py
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Data


def migrate():
    """Add detailed_remarks column to Data table"""
    with app.app_context():
        try:
            print(f"[{datetime.now()}] Starting migration: Add detailed_remarks column to Data table")

            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('data')]

            if 'detailed_remarks' in columns:
                print(f"[{datetime.now()}] Column 'detailed_remarks' already exists in Data table. No migration needed.")
                return True

            # Add the column using raw SQL
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE data ADD COLUMN detailed_remarks TEXT"))
                conn.commit()

            print(f"[{datetime.now()}] Successfully added 'detailed_remarks' column to Data table")

            # Verify the column was added
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('data')]

            if 'detailed_remarks' in columns:
                print(f"[{datetime.now()}] ✓ Migration completed successfully!")
                print(f"[{datetime.now()}] ✓ Column 'detailed_remarks' is now available in Data table")
                return True
            else:
                print(f"[{datetime.now()}] ✗ Migration failed - column not found after ALTER TABLE")
                return False

        except Exception as e:
            print(f"[{datetime.now()}] ✗ Error during migration: {str(e)}")
            return False


if __name__ == '__main__':
    print("=" * 70)
    print("DATABASE MIGRATION: Add detailed_remarks Column")
    print("=" * 70)
    print()

    success = migrate()

    print()
    print("=" * 70)
    if success:
        print("Migration completed successfully!")
        print("You can now use the detailed_remarks field in the Data model.")
    else:
        print("Migration failed. Please check the error messages above.")
    print("=" * 70)

    sys.exit(0 if success else 1)
