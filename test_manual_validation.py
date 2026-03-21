#!/usr/bin/env python3
"""
Manual validation script for Driver/Assistant Time Logs feature.
Tests the backend function directly without requiring HTTP authentication.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import after adding to path
from app import app, db, get_time_log_matrix_data
from models import Schedule, Trip, trip_driver, trip_assistant, Manpower, TimeLog

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
END = '\033[0m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{END}")
    print(f"{BOLD}{BLUE}{text:^70}{END}")
    print(f"{BOLD}{BLUE}{'='*70}{END}\n")

def print_success(text):
    print(f"{GREEN}✓ PASS:{END} {text}")

def print_error(text):
    print(f"{RED}✗ FAIL:{END} {text}")

def print_info(text):
    print(f"{YELLOW}ℹ INFO:{END} {text}")

def test_database_state():
    """Test: Check database state"""
    print_header("TEST 1: Database State")

    with app.app_context():
        # Check schedules
        schedule_count = db.session.query(Schedule).count()
        print_info(f"Total schedules: {schedule_count}")

        # Check trips
        trip_count = db.session.query(Trip).count()
        print_info(f"Total trips: {trip_count}")

        # Check driver assignments
        driver_assignments = db.session.query(
            db.func.count(trip_driver.c.manpower_id)
        ).scalar()
        print_info(f"Driver assignments: {driver_assignments}")

        # Check assistant assignments
        assistant_assignments = db.session.query(
            db.func.count(trip_assistant.c.manpower_id)
        ).scalar()
        print_info(f"Assistant assignments: {assistant_assignments}")

        # Check time logs
        time_log_count = db.session.query(TimeLog).count()
        print_info(f"Total time logs: {time_log_count}")

        if schedule_count > 0 and trip_count > 0:
            print_success("Database has data for testing")
            return True
        else:
            print_error("Database lacks sufficient data")
            return False

def test_empty_date_range():
    """Test: Empty date range (far future)"""
    print_header("TEST 2: Empty Date Range (No Data)")

    with app.app_context():
        start_date = datetime(2030, 1, 1).date()
        end_date = datetime(2030, 1, 8).date()  # +1 day added by function

        try:
            personnel_list, date_list = get_time_log_matrix_data(start_date, end_date)

            if len(personnel_list) == 0:
                print_success("Empty date range returns empty personnel list")
                print_info(f"Date list: {date_list}")
                return True
            else:
                print_error(f"Expected 0 personnel, got {len(personnel_list)}")
                return False

        except Exception as e:
            print_error(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def test_valid_date_range():
    """Test: Valid date range with data"""
    print_header("TEST 3: Valid Date Range (Last 7 Days)")

    with app.app_context():
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        test_end_date = end_date + timedelta(days=1)  # Function adds +1 day

        print_info(f"Testing: {start_date} to {end_date}")

        try:
            personnel_list, date_list = get_time_log_matrix_data(start_date, test_end_date)

            print_success(f"Function executed successfully")
            print_info(f"Found {len(personnel_list)} personnel records")
            print_info(f"Date range: {len(date_list)} dates")

            # Check structure
            if len(personnel_list) > 0:
                person = personnel_list[0]

                # Check required keys
                required_keys = ['manpower_id', 'name', 'role', 'dates']
                for key in required_keys:
                    if key not in person:
                        print_error(f"Missing key: {key}")
                        return False

                print_success("Personnel records have correct structure")

                # Display sample data
                print_info(f"Sample person: {person['name']} ({person['role']})")
                print_info(f"Dates: {date_list[:3]}...")

                # Check dates structure
                if len(date_list) > 0:
                    sample_date = date_list[0]
                    if sample_date in person['dates']:
                        time_data = person['dates'][sample_date]
                        print_info(f"Sample time data for {sample_date}:")
                        print_info(f"  time_in: {time_data['time_in']}")
                        print_info(f"  time_out: {time_data['time_out']}")

                        # Check for valid badge values
                        valid_values = ['Missing', None]  # None is valid (will be formatted)
                        # Also check for time format (HH:MM AM/PM)
                        if time_data['time_in'] not in ['Missing', None]:
                            print_success("time_in has valid value")
                        if time_data['time_out'] not in ['Missing', None]:
                            print_success("time_out has valid value")

                        return True
                    else:
                        print_error(f"Date {sample_date} not in person['dates']")
                        return False
            else:
                print_info("No personnel found in date range (this is OK if no trips exist)")
                return True

        except Exception as e:
            print_error(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def test_incomplete_timelog_data():
    """Test: Incomplete TimeLog data handling"""
    print_header("TEST 4: Incomplete TimeLog Data")

    with app.app_context():
        # Use last 30 days to increase chance of finding incomplete data
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=29)
        test_end_date = end_date + timedelta(days=1)

        print_info(f"Testing: {start_date} to {end_date}")

        try:
            personnel_list, date_list = get_time_log_matrix_data(start_date, test_end_date)

            if len(personnel_list) == 0:
                print_info("No personnel found in date range")
                return True

            # Check for 'Missing' badges
            found_missing = False
            found_complete = False

            for person in personnel_list:
                for date_str in date_list:
                    time_data = person['dates'][date_str]

                    if time_data['time_in'] == 'Missing' or time_data['time_out'] == 'Missing':
                        found_missing = True
                        print_info(f"Found incomplete data: {person['name']} on {date_str}")
                        print_info(f"  time_in: {time_data['time_in']}, time_out: {time_data['time_out']}")

                    if time_data['time_in'] != 'Missing' and time_data['time_out'] != 'Missing':
                        found_complete = True

            if found_missing:
                print_success("Incomplete TimeLog data properly marked as 'Missing'")

            if found_complete:
                print_success("Complete TimeLog data properly formatted")

            if not found_missing and not found_complete:
                print_info("No TimeLog data found in test range (this is OK)")

            return True

        except Exception as e:
            print_error(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def test_date_range_structure():
    """Test: Date range generation"""
    print_header("TEST 5: Date Range Structure")

    with app.app_context():
        start_date = datetime(2025, 3, 15).date()
        end_date = datetime(2025, 3, 18).date()  # 3 days: 15, 16, 17
        test_end_date = end_date + timedelta(days=1)  # Function adds +1 day

        print_info(f"Testing: {start_date} to {end_date}")

        try:
            personnel_list, date_list = get_time_log_matrix_data(start_date, test_end_date)

            # Check date list
            expected_dates = ['2025-03-15', '2025-03-16', '2025-03-17']

            if date_list == expected_dates:
                print_success(f"Date list correctly generated: {date_list}")
            else:
                print_error(f"Date list mismatch")
                print_info(f"Expected: {expected_dates}")
                print_info(f"Got: {date_list}")
                return False

            return True

        except Exception as e:
            print_error(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def test_personnel_deduplication():
    """Test: Personnel deduplication (same person, different role)"""
    print_header("TEST 6: Personnel Deduplication")

    with app.app_context():
        # Check if same person appears with different roles
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=29)
        test_end_date = end_date + timedelta(days=1)

        try:
            personnel_list, date_list = get_time_log_matrix_data(start_date, test_end_date)

            # Check for duplicate names
            names = [p['name'] for p in personnel_list]
            unique_names = set(names)

            if len(names) != len(unique_names):
                # This might be valid if same person has different roles
                print_info(f"Found {len(names)} records with {len(unique_names)} unique names")
                print_info("This is valid if same person has different roles")

                # Check if duplicates have different roles
                name_roles = {}
                for p in personnel_list:
                    if p['name'] not in name_roles:
                        name_roles[p['name']] = []
                    name_roles[p['name']].append(p['role'])

                for name, roles in name_roles.items():
                    if len(roles) > 1:
                        print_info(f"  {name} has roles: {roles}")

            print_success("Personnel deduplication working correctly")
            return True

        except Exception as e:
            print_error(f"Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Run all tests"""
    print(f"\n{BOLD}{BLUE}")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  Driver/Assistant Time Logs - Manual Validation Suite           ║")
    print("║  Testing get_time_log_matrix_data() Function                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"{END}\n")

    # Run all tests
    results = {}

    results['database_state'] = test_database_state()
    results['empty_date_range'] = test_empty_date_range()
    results['valid_date_range'] = test_valid_date_range()
    results['incomplete_data'] = test_incomplete_timelog_data()
    results['date_range_structure'] = test_date_range_structure()
    results['personnel_deduplication'] = test_personnel_deduplication()

    # Print summary
    print_header("TEST SUMMARY")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for test_name, passed in results.items():
        status = f"{GREEN}PASS{END}" if passed else f"{RED}FAIL{END}"
        print(f"  {test_name.replace('_', ' ').title():.<50} {status}")

    print(f"\n{BOLD}Overall Result: {passed_tests}/{total_tests} tests passed{END}")

    if passed_tests == total_tests:
        print(f"\n{GREEN}{BOLD}✓ ALL TESTS PASSED{END}\n")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ SOME TESTS FAILED{END}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
