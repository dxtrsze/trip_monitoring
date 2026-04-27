#!/usr/bin/env python3
"""
Script to delete all data from trip_monitoring database
Preserves: user, vehicle, cluster, manpower tables
Deletes: all other table data

Database-agnostic version using SQLAlchemy ORM
Compatible with SQLite, PostgreSQL, and other databases
"""

import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    TripDetail, Trip, Schedule, Data, Backload,
    Odo, DailyVehicleCount, User, Vehicle, Cluster, Manpower,
    LCLSummary, LCLDetail, TimeLog, ArchiveLog
)

def get_model_class(table_name):
    """Map table name to SQLAlchemy model class"""
    model_map = {
        'trip_detail': TripDetail,
        'trip': Trip,
        'schedule': Schedule,
        'data': Data,
        'backload': Backload,
        'odo': Odo,
        'daily_vehicle_count': DailyVehicleCount,
        'user': User,
        'vehicle': Vehicle,
        'cluster': Cluster,
        'manpower': Manpower,
        'lcl_summary': LCLSummary,
        'lcl_detail': LCLDetail,
        'time_log': TimeLog,
        'archive_log': ArchiveLog,
    }
    return model_map.get(table_name)

def clear_database():
    """Clear database data using SQLAlchemy ORM"""
    print(f"Starting database cleanup: {datetime.now()}")
    print(f"Database: SQLAlchemy ORM (Database-Agnostic)")

    with app.app_context():
        try:
            # Define table processing order (respecting foreign key dependencies)
            # Tables to preserve (not to be deleted)
            preserve_tables = {'user', 'vehicle', 'cluster', 'manpower'}

            # Tables to clear, in dependency order (children first)
            tables_to_clear = [
                ('trip_driver', 'Association table: trip_driver'),
                ('trip_assistant', 'Association table: trip_assistant'),
                ('trip_detail', 'TripDetail'),
                ('trip', 'Trip'),
                ('schedule', 'Schedule'),
                ('data', 'Data'),
                ('backload', 'Backload'),
                ('odo', 'Odo'),
                ('daily_vehicle_count', 'DailyVehicleCount'),
                ('lcl_detail', 'LCLDetail'),
                ('lcl_summary', 'LCLSummary'),
                ('time_log', 'TimeLog'),
                ('archive_log', 'ArchiveLog'),
            ]

            print(f"\nTables to preserve: {', '.join(sorted(preserve_tables))}")
            print(f"Tables to clear: {', '.join([t[0] for t in tables_to_clear])}")

            # Count rows before deletion
            total_rows = 0
            print(f"\nRows before deletion:")
            for table_name, description in tables_to_clear:
                model_class = get_model_class(table_name)
                if model_class:
                    count = db.session.query(model_class).count()
                    total_rows += count
                    print(f"  {table_name}: {count:,} rows ({description})")
                else:
                    # For association tables without model classes, use raw SQL
                    result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()
                    total_rows += count
                    print(f"  {table_name}: {count:,} rows ({description})")

            print(f"\nTotal rows to delete: {total_rows:,}")

            # Delete data in order
            print(f"\nDeleting data:")

            for table_name, description in tables_to_clear:
                try:
                    model_class = get_model_class(table_name)

                    if model_class:
                        # Use SQLAlchemy ORM for models
                        deleted_count = db.session.query(model_class).delete()
                        db.session.flush()  # Flush to execute without committing yet
                        print(f"✓ Cleared {table_name}: {deleted_count:,} rows deleted")
                    else:
                        # Use raw SQL for association tables
                        result = db.session.execute(db.text(f"DELETE FROM {table_name}"))
                        deleted_count = result.rowcount
                        db.session.flush()
                        print(f"✓ Cleared {table_name}: {deleted_count:,} rows deleted")

                except Exception as e:
                    print(f"✗ Error clearing {table_name}: {e}")
                    raise

            # Verify preserved tables still have data
            print(f"\nVerifying preserved tables:")
            preserved_models = [
                ('user', User),
                ('vehicle', Vehicle),
                ('cluster', Cluster),
                ('manpower', Manpower),
            ]

            for table_name, model_class in preserved_models:
                count = db.session.query(model_class).count()
                status = "✓" if count > 0 else "⚠"
                print(f"  {table_name}: {count:,} rows {status}")

            # Verify cleared tables are empty
            print(f"\nVerifying cleared tables are empty:")
            all_empty = True
            for table_name, description in tables_to_clear:
                model_class = get_model_class(table_name)
                if model_class:
                    count = db.session.query(model_class).count()
                else:
                    result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()

                status = "✓" if count == 0 else "✗"
                print(f"  {table_name}: {count:,} rows {status}")
                if count > 0:
                    all_empty = False

            # Commit the changes
            db.session.commit()

            if all_empty:
                print("\n✓ Database cleanup completed successfully!")
                print(f"✓ Preserved data in: {', '.join(sorted(preserve_tables))}")
                return True
            else:
                print("\n⚠ Some tables still contain data")
                return False

        except Exception as e:
            db.session.rollback()
            print(f"Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE CLEANUP SCRIPT (SQLAlchemy ORM)")
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
