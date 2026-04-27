#!/usr/bin/env python3
"""
Debug script to show actual truck utilization computation from database.
Run this to see how the 237% utilization was calculated.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Schedule, Trip, Vehicle, TripDetail
from sqlalchemy import func as sql_func

def debug_truck_utilization(start_date=None, end_date=None):
    """
    Show the actual truck utilization computation with database data.
    """

    # Default to last 7 days if no dates provided
    if not end_date:
        end_date = datetime.now().date()
    if not start_date:
        start_date = end_date - timedelta(days=6)

    print(f"\n{'='*80}")
    print(f"TRUCK UTILIZATION DEBUG REPORT")
    print(f"{'='*80}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Schedule Type: in-house only")
    print(f"{'='*80}\n")

    # Get all utilization records with actual data
    print("STEP 1: Get all vehicle utilization records")
    print("-" * 80)

    utilization_records = (
        db.session.query(
            Trip.vehicle_id,
            Vehicle.plate_number,
            Vehicle.capacity,
            sql_func.sum(Trip.total_cbm).label("total_loaded_cbm"),
            sql_func.count(Trip.id).label("trip_count"),
        )
        .join(Vehicle)
        .join(Schedule)
        .filter(
            Schedule.delivery_schedule.between(start_date, end_date),
            Schedule.type == "in-house",
            Vehicle.capacity.isnot(None),
            Vehicle.capacity > 0,
        )
        .group_by(Trip.vehicle_id, Vehicle.plate_number, Vehicle.capacity)
        .all()
    )

    if not utilization_records:
        print("No utilization records found!")
        return

    # Display each vehicle's data
    print(f"{'Vehicle':<15} {'Capacity':<12} {'Trips':<8} {'Total CBM':<12} {'Util %':<10} {'Weighted':<12}")
    print("-" * 80)

    total_weighted_util = 0
    total_trips = 0
    utilization_percentages = []

    for r in utilization_records:
        util_percent = (r.total_loaded_cbm / r.capacity * 100)
        weighted = util_percent * r.trip_count

        print(f"{r.plate_number:<15} {r.capacity:<12.2f} {r.trip_count:<8} "
              f"{r.total_loaded_cbm:<12.2f} {util_percent:<10.1f} {weighted:<12.1f}")

        total_weighted_util += weighted
        total_trips += r.trip_count
        utilization_percentages.append(util_percent)

    print("-" * 80)

    # OLD (WRONG) calculation - weighted by trip count
    old_utilization = (total_weighted_util / total_trips) if total_trips > 0 else 0

    # NEW (CORRECT) calculation - simple average
    new_utilization = (
        (sum(utilization_percentages) / len(utilization_percentages))
        if utilization_percentages
        else 0
    )

    print(f"\n{'='*80}")
    print(f"COMPARISON OF CALCULATIONS")
    print(f"{'='*80}\n")

    print(f"OLD CALCULATION (Weighted by trip count):")
    print(f"  Total Weighted Utilization: {total_weighted_util:.2f}")
    print(f"  Total Trips: {total_trips}")
    print(f"  Result: {total_weighted_util} / {total_trips} = {old_utilization:.1f}%")
    print(f"  ⚠️  This is WRONG because it weights by trip count\n")

    print(f"NEW CALCULATION (Simple average per vehicle):")
    print(f"  Vehicle Count: {len(utilization_percentages)}")
    print(f"  Utilization Percentages: {[f'{u:.1f}%' for u in utilization_percentages]}")
    print(f"  Sum: {sum(utilization_percentages):.2f}")
    print(f"  Result: {sum(utilization_percentages):.2f} / {len(utilization_percentages)} = {new_utilization:.1f}%")
    print(f"  ✅ This is CORRECT - average of vehicle utilizations\n")

    # Show detailed breakdown
    print(f"{'='*80}")
    print(f"DETAILED BREAKDOWN BY VEHICLE")
    print(f"{'='*80}\n")

    for r in utilization_records:
        print(f"Vehicle: {r.plate_number}")
        print(f"  Capacity: {r.capacity:.2f} CBM")
        print(f"  Total Loaded: {r.total_loaded_cbm:.2f} CBM")
        print(f"  Number of Trips: {r.trip_count}")
        print(f"  Utilization: ({r.total_loaded_cbm} / {r.capacity}) × 100 = {(r.total_loaded_cbm / r.capacity * 100):.1f}%")
        print(f"  Weighted contribution (old method): {(r.total_loaded_cbm / r.capacity * 100) * r.trip_count:.1f}")
        print()

    # Get the actual trip details for reference
    print(f"{'='*80}")
    print(f"ACTUAL TRIP DETAILS")
    print(f"{'='*80}\n")

    trips = (
        db.session.query(
            Schedule.delivery_schedule,
            Vehicle.plate_number,
            Trip.id.label('trip_id'),
            Trip.trip_number,
            Trip.total_cbm,
            Vehicle.capacity,
        )
        .join(Vehicle)
        .join(Schedule)
        .filter(
            Schedule.delivery_schedule.between(start_date, end_date),
            Schedule.type == "in-house",
            Vehicle.capacity.isnot(None),
            Vehicle.capacity > 0,
        )
        .order_by(Schedule.delivery_schedule, Vehicle.plate_number, Trip.trip_number)
        .all()
    )

    print(f"{'Date':<12} {'Vehicle':<15} {'Trip #':<8} {'CBM':<10} {'Capacity':<10} {'Trip Util %':<12}")
    print("-" * 80)

    for trip in trips:
        trip_util = (trip.total_cbm / trip.capacity * 100) if trip.capacity > 0 else 0
        print(f"{trip.delivery_schedule:<12} {trip.plate_number:<15} {trip.trip_number:<8} "
              f"{trip.total_cbm:<10.2f} {trip.capacity:<10.2f} {trip_util:<12.1f}%")

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Old method (weighted by trips): {old_utilization:.1f}%")
    print(f"New method (average per vehicle): {new_utilization:.1f}%")
    print(f"Difference: {old_utilization - new_utilization:.1f} percentage points")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    with app.app_context():
        # You can pass custom dates as arguments
        import argparse
        parser = argparse.ArgumentParser(description='Debug truck utilization calculation')
        parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
        parser.add_argument('--end', help='End date (YYYY-MM-DD)')
        args = parser.parse_args()

        start_date = datetime.strptime(args.start, '%Y-%m-%d').date() if args.start else None
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else None

        debug_truck_utilization(start_date, end_date)
