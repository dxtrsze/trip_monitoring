import pytest
from app import app, db
from models import User, Trip, TripDetail, Schedule, Vehicle, Odo
from datetime import date, datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Create test admin user
            admin = User(email='admin@test.com', name='Admin', position='admin', status='active')
            admin.set_password('password')
            db.session.add(admin)
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()

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
