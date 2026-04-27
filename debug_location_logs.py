"""
Script to investigate and fix orphaned location_log records.
Run: python debug_location_logs.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.venv/lib/python3.12/site-packages')))

from app import app, db
from models import LocationLog, TripDetail

def investigate():
    """Check what orphaned records exist."""
    with app.app_context():
        print("=" * 60)
        print("LOCATION LOG INVESTIGATION")
        print("=" * 60)

        # Get all location logs
        all_logs = LocationLog.query.all()
        print(f"\nTotal location_log records: {len(all_logs)}")

        # Check each one
        orphaned = []
        valid = []

        for log in all_logs:
            if log is None:
                print(f"✗ None value found in results")
                continue

            trip_detail = TripDetail.query.get(log.trip_detail_id)
            if trip_detail:
                valid.append(log)
                print(f"✓ Log {log.id}: trip_detail exists (ID: {log.trip_detail_id})")
            else:
                orphaned.append(log)
                print(f"✗ Log {log.id}: trip_detail MISSING (ID: {log.trip_detail_id})")
                print(f"  - Action: {log.action_type}")
                print(f"  - User ID: {log.user_id}")
                print(f"  - Created: {log.created_at}")

        print("\n" + "=" * 60)
        print(f"Summary: {len(valid)} valid, {len(orphaned)} orphaned")
        print("=" * 60)

        return orphaned, valid

def cleanup_orphans(orphaned):
    """Delete orphaned location_log records."""
    if not orphaned:
        print("\nNo orphaned records to clean up.")
        return

    print(f"\nDeleting {len(orphaned)} orphaned records...")

    with app.app_context():
        for log in orphaned:
            print(f"  Deleting log {log.id}...")
            db.session.delete(log)

        db.session.commit()
        print("Cleanup complete!")

def show_all_option():
    """Show how to modify query to show all records."""
    print("\n" + "=" * 60)
    print("OPTION: Show ALL location logs (including orphans)")
    print("=" * 60)
    print("\nTo show all location logs even without trip_detail:")
    print("\n1. Remove this line from app.py (around line 3250):")
    print("   query = query.filter(TripDetail.id.isnot(None))")
    print("\n2. Update template to handle missing trip_detail:")
    print("   Line 77 already has: {{ log.trip_detail.branch_name_v2 if log.trip_detail else 'N/A' }}")
    print("\nThis will show all location logs with 'N/A' for missing trip details.")

if __name__ == "__main__":
    orphaned, valid = investigate()

    print("\n" + "=" * 60)
    print("OPTIONS:")
    print("=" * 60)
    print("1. Clean up orphaned records (recommended)")
    print("2. Show all records including orphans")
    print("3. Do nothing and investigate manually")
    print("=" * 60)

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == '1':
        confirm = input(f"Delete {len(orphaned)} orphaned records? (yes/no): ").strip().lower()
        if confirm == 'yes':
            cleanup_orphans(orphaned)
    elif choice == '2':
        show_all_option()
    else:
        print("No changes made.")
