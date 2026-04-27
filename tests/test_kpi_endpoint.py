#!/usr/bin/env python3
"""
Simple test script to verify the /api/dashboard/kpis endpoint
Run this after starting the Flask app
"""

import requests
import json
from datetime import date, timedelta

# Base URL for the Flask app
BASE_URL = 'http://localhost:5000'

def test_kpis_endpoint():
    """Test the KPIs endpoint"""
    print("Testing /api/dashboard/kpis endpoint...")

    try:
        # First, login as admin
        print("\n1. Logging in as admin...")
        session = requests.Session()

        # You'll need to replace these credentials with actual admin credentials
        login_data = {
            'email': 'admin@test.com',  # Replace with actual admin email
            'password': 'password'      # Replace with actual password
        }

        # Try to access the endpoint
        print("\n2. Accessing /api/dashboard/kpis...")
        response = session.get(f'{BASE_URL}/api/dashboard/kpis')

        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")

        if response.status_code == 200:
            print("\n✓ SUCCESS: Endpoint returned 200")
            data = response.json()

            # Check required fields
            required_fields = [
                'on_time_delivery_rate', 'in_full_delivery_rate', 'difot_score',
                'truck_utilization', 'fuel_efficiency', 'fuel_cost_per_km',
                'data_completeness', 'period'
            ]

            print("\n3. Checking required fields...")
            all_present = True
            for field in required_fields:
                if field in data:
                    print(f"   ✓ {field}")
                else:
                    print(f"   ✗ {field} MISSING")
                    all_present = False

            if all_present:
                print("\n✓ All required fields present!")

            # Check period info
            if 'period' in data:
                print("\n4. Checking period info...")
                period = data['period']
                if 'start_date' in period and 'end_date' in period:
                    print(f"   ✓ Period: {period['start_date']} to {period['end_date']}")
                else:
                    print("   ✗ Period info incomplete")

            # Pretty print the response
            print("\n5. Response data:")
            print(json.dumps(data, indent=2))

            return True

        elif response.status_code == 403:
            print("\n✗ ACCESS DENIED: Admin access required")
            print("   Make sure you're logged in as an admin user")
            return False

        elif response.status_code == 404:
            print("\n✗ NOT FOUND: Endpoint doesn't exist")
            return False

        else:
            print(f"\n✗ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("\n✗ CONNECTION ERROR: Cannot connect to Flask app")
        print("   Make sure the Flask app is running on http://localhost:5000")
        return False

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("KPI Endpoint Test")
    print("=" * 60)
    print("\nMake sure the Flask app is running before executing this test:")
    print("  python3 app.py")
    print("\nThen run this script:")
    print("  python3 test_kpi_endpoint.py")
    print("=" * 60)

    success = test_kpis_endpoint()

    print("\n" + "=" * 60)
    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 60)
