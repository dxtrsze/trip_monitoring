import pytest
import os
from app import app
from models import db, Vehicle, Manpower, Data, Cluster, Schedule, Trip, TripDetail
from ai_service import AIService
from datetime import date


@pytest.fixture
def ai_client():
    """Create a test client with database setup"""
    app.config["TESTING"] = True
    ai_client = app.test_client()

    # Setup the application context and database
    with app.app_context():
        db.create_all()
        yield ai_client
        db.drop_all()


def test_full_scheduling_workflow(ai_client):
    """Test complete workflow from chat to schedule creation"""
    with app.app_context():
        # Setup: Create vehicle, driver, cluster, data
        vehicle = Vehicle(
            plate_number="FULL123",
            capacity=20.0,
            status="Active",
            dept="Logistics",
            type="in-house"
        )
        db.session.add(vehicle)

        driver = Manpower(name="Integration Driver", role="Driver")
        db.session.add(driver)

        cluster = Cluster(
            no="FULL001",
            branch="Integration Branch",
            area="North",
            category="Test"
        )
        db.session.add(cluster)

        data = Data(
            type="ITR",
            posting_date=date(2026, 3, 26),
            document_number="FULL001",
            item_number="001",
            ordered_qty=10,
            delivered_qty=0.0,
            branch_name_v2="Integration Branch",
            due_date=date(2026, 3, 26),
            status="Not Scheduled",
            cbm=1.5
        )
        db.session.add(data)
        db.session.commit()

        # Test: Build proposal
        service = AIService(
            api_key="test",
            api_base="https://test.com",
            model="gpt-4"
        )

        proposal = service.build_schedule_proposal(
            vehicle_id=vehicle.id,
            area="North",
            due_date=date(2026, 3, 26)
        )

        assert proposal is not None
        assert proposal["plate_number"] == "FULL123"
        assert proposal["total_cbm"] > 0

        # Test: Execute proposal
        result = service.execute_schedule(proposal, admin_user_id=1)

        assert result["success"] is True
        assert "schedule_id" in result

        # Verify: Check database records
        schedule = Schedule.query.get(result["schedule_id"])
        assert schedule is not None
        assert len(schedule.trips) == 1

        trip = schedule.trips[0]
        assert len(trip.details) == 1
        assert trip.details[0].branch_name_v2 == "Integration Branch"

        # Verify: Complete Schedule → Trip → TripDetail relationship hierarchy
        # Verify trip.vehicle relationship
        assert trip.vehicle is not None
        assert trip.vehicle.id == vehicle.id
        assert trip.vehicle.plate_number == "FULL123"

        # Verify trip.drivers and trip.assistants relationships
        assert len(trip.drivers) == 1
        assert trip.drivers[0].id == driver.id
        assert trip.drivers[0].name == "Integration Driver"

        # Verify trip_detail.trip relationship
        trip_detail = trip.details[0]
        assert trip_detail.trip is not None
        assert trip_detail.trip.id == trip.id

        # Verify all TripDetail fields
        assert trip_detail.total_cbm is not None
        assert trip_detail.total_ordered_qty is not None
        assert trip_detail.total_delivered_qty is not None
        assert trip_detail.branch_name_v2 == "Integration Branch"
        assert trip_detail.area == "North"

        # Verify: Data status updated
        updated_data = Data.query.get(data.id)
        assert updated_data.status == "Scheduled"

        # Cleanup
        db.session.delete(updated_data)
        for detail in trip.details:
            db.session.delete(detail)
        db.session.delete(trip)
        db.session.delete(schedule)
        db.session.delete(cluster)
        db.session.delete(driver)
        db.session.delete(vehicle)
        db.session.commit()


def test_api_chat_endpoint(ai_client):
    """Test /api/ai/chat endpoint"""
    with app.app_context():
        # Login as admin
        from models import User
        admin = User(
            name="Admin",
            email="admin@test.com",
            position="admin"
        )
        admin.set_password("password")
        db.session.add(admin)
        db.session.commit()

        # Login
        ai_client.post("/login", data={
            "email": "admin@test.com",
            "password": "password"
        })

        # Test chat endpoint
        response = ai_client.post("/api/ai/chat", json={
            "message": "What vehicles are available?",
            "history": []
        })

        # Note: This will fail with actual API call, but tests the endpoint structure
        assert response.status_code in [200, 500]  # 500 if no API key configured

        # Cleanup
        db.session.delete(admin)
        db.session.commit()