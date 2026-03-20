import pytest
from app import app, db
from models import User, Trip, TripDetail, Schedule, Vehicle, Odo
from datetime import date, datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            # Create test admin user if doesn't exist
            admin = db.session.query(User).filter_by(email='admin@test.com').first()
            if not admin:
                admin = User(email='admin@test.com', name='Admin', position='admin', status='active')
                admin.set_password('password')
                db.session.add(admin)
                db.session.commit()
        yield client

@pytest.fixture
def auth_headers(client):
    # Login and get session cookie
    response = client.post('/login', data={
        'email': 'admin@test.com',
        'password': 'password'
    }, follow_redirects=True)
    # Session is now stored in client's cookie jar
    return {}

def test_kpis_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/kpis')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

def test_kpis_contains_all_required_fields(client, auth_headers):
    response = client.get('/api/dashboard/kpis')
    data = response.get_json()
    required_fields = [
        'on_time_delivery_rate', 'in_full_delivery_rate', 'difot_score',
        'truck_utilization', 'fuel_efficiency', 'fuel_cost_per_km',
        'data_completeness', 'period'
    ]
    for field in required_fields:
        assert field in data

def test_kpis_period_info_present(client, auth_headers):
    response = client.get('/api/dashboard/kpis')
    data = response.get_json()
    assert 'period' in data
    assert 'start_date' in data['period']
    assert 'end_date' in data['period']

def test_trends_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/trends')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

def test_trends_contains_required_data(client, auth_headers):
    response = client.get('/api/dashboard/trends')
    data = response.get_json()
    required_keys = ['daily_deliveries', 'fuel_efficiency', 'truck_utilization']
    for key in required_keys:
        assert key in data
        assert isinstance(data[key], list)

def test_comparisons_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/comparisons')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

def test_comparisons_contains_rankings(client, auth_headers):
    response = client.get('/api/dashboard/comparisons')
    data = response.get_json()
    required_keys = ['vehicle_utilization', 'branch_frequency', 'driver_performance']
    for key in required_keys:
        assert key in data
        assert isinstance(data[key], list)

def test_gauges_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/gauges')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

def test_gauges_contains_all_required_fields(client, auth_headers):
    response = client.get('/api/dashboard/gauges')
    data = response.get_json()
    required_fields = ['on_time_rate', 'utilization', 'data_completeness']
    for field in required_fields:
        assert field in data

def test_gauges_respects_date_parameters(client, auth_headers):
    response = client.get('/api/dashboard/gauges?start_date=2026-03-15&end_date=2026-03-17')
    assert response.status_code == 200
    data = response.get_json()
    assert 'on_time_rate' in data
    assert 'utilization' in data
    assert 'data_completeness' in data

def test_gauges_requires_admin_access(client):
    # Create non-admin user if doesn't exist
    from models import User
    with app.app_context():
        non_admin = db.session.query(User).filter_by(email='user@test.com').first()
        if not non_admin:
            non_admin = User(email='user@test.com', name='User', position='operations', status='active')
            non_admin.set_password('password')
            db.session.add(non_admin)
            db.session.commit()

    # Login as non-admin
    response = client.post('/login', data={
        'email': 'user@test.com',
        'password': 'password'
    }, follow_redirects=True)

    # Try to access gauges endpoint
    response = client.get('/api/dashboard/gauges')
    assert response.status_code == 403
