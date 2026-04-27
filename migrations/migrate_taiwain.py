#!/usr/bin/env python3
"""
Migration script to add 'type' column to Schedule table.
This script adds a new field to track whether a schedule is for 'in-house' or '3pl' vehicles.
"""

import sys
import os
from sqlalchemy import text, inspect
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Add the parent directory to the path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def migrate_schedule_type():
    """Add type column to schedule table if it doesn't exist."""

    print("Starting migration: Adding 'type' column to schedule table...")
    print("=" * 60)

    with app.app_context():
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('schedule')]

        if 'type' in columns:
            print("✓ Column 'type' already exists in schedule table.")
            print("Migration not needed.")
            return True

        try:
            # Add the type column
            print("Adding 'type' column to schedule table...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE schedule ADD COLUMN type VARCHAR(50)"))
                conn.commit()

            print("✓ Successfully added 'type' column to schedule table")

            # Verify the column was added
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('schedule')]

            if 'type' in columns:
                print("✓ Verification successful: 'type' column exists")
                print("\nMigration completed successfully!")
                return True
            else:
                print("✗ Verification failed: 'type' column not found")
                return False

        except Exception as e:
            print(f"✗ Error during migration: {str(e)}")
            return False

if __name__ == '__main__':
    success = migrate_schedule_type()
    sys.exit(0 if success else 1)
