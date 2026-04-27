"""Test validation in record_arrival endpoint."""

import pytest
from app import app
from models import db, Trip, TripDetail, Schedule, User
import json


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.test_client() as client:
        with app.app_context():
            db.create_all()

            # Create test user
            user = User(id=1, username="test_user", email="test@example.com")
            db.session.add(user)

            # Create test schedule
            schedule = Schedule(id=1, schedule_date="2026-04-27")
            db.session.add(schedule)

            # Create test trip
            trip = Trip(id=1, schedule_id=1, trip_number=1)
            db.session.add(trip)

            # Create test trip detail
            trip_detail = TripDetail(
                id=1,
                trip_id=1,
                branch_name_v2="Test Branch"
            )
            db.session.add(trip_detail)
            db.session.commit()

        yield client

        with app.app_context():
            db.drop_all()


def test_record_arrival_invalid_coordinates(client):
    """Test that invalid coordinates return 400 error."""
    response = client.post(
        '/record_arrival',
        data=json.dumps({
            'branch_name_v2': 'Test Branch',
            'schedule_id': 1,
            'trip_number': 1,
            'latitude': 'invalid',
            'longitude': 'also_invalid'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert data['message'] == 'Invalid coordinates provided'


def test_record_arrival_valid_coordinates(client):
    """Test that valid coordinates work correctly."""
    response = client.post(
        '/record_arrival',
        data=json.dumps({
            'branch_name_v2': 'Test Branch',
            'schedule_id': 1,
            'trip_number': 1,
            'latitude': 25.0340,
            'longitude': 121.5644
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'arrive_time' in data


def test_record_arrival_no_coordinates(client):
    """Test that missing coordinates are handled correctly."""
    response = client.post(
        '/record_arrival',
        data=json.dumps({
            'branch_name_v2': 'Test Branch',
            'schedule_id': 1,
            'trip_number': 1
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
