import pytest
import os
from ai_service import AIService
from models import db, Vehicle
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_ai_service_initialization():
    """Test that AIService initializes with OpenAI client"""
    api_key = os.environ.get("ZAI_API_KEY", "test_key")
    api_base = os.environ.get("ZAI_API_BASE", "https://api.z.ai/api/paas/v4")
    model = os.environ.get("ZAI_MODEL", "gpt-4")

    service = AIService(api_key=api_key, api_base=api_base, model=model)

    assert service.client is not None
    assert service.model == model
    assert service.api_base == api_base

def test_query_vehicles(client):
    """Test querying vehicles from database"""
    with app.app_context():
        # Clean up any existing test vehicle
        existing = Vehicle.query.filter_by(plate_number="TEST123").first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        # Create test vehicle
        vehicle = Vehicle(
            plate_number="TEST123",
            capacity=15.5,
            status="Active",
            dept="Logistics",
            type="in-house"
        )
        db.session.add(vehicle)
        db.session.commit()

        service = AIService(
            api_key="test",
            api_base="https://test.com",
            model="gpt-4"
        )

        vehicles = service.query_vehicles()

        assert len(vehicles) > 0
        assert any(v.plate_number == "TEST123" for v in vehicles)

        # Cleanup
        db.session.delete(vehicle)
        db.session.commit()

def test_query_pending_deliveries(client):
    """Test querying pending deliveries by area and due date"""
    with app.app_context():
        from models import Cluster, Data
        from datetime import date

        # Clean up any existing test data
        existing_cluster = Cluster.query.filter_by(no="TEST001").first()
        if existing_cluster:
            db.session.delete(existing_cluster)
            db.session.commit()

        existing_data = Data.query.filter_by(document_number="TEST001").first()
        if existing_data:
            db.session.delete(existing_data)
            db.session.commit()

        # Create test cluster
        cluster = Cluster(
            no="TEST001",
            branch="Test Branch",
            area="North",
            category="Test"
        )
        db.session.add(cluster)
        db.session.flush()

        # Create test data
        data = Data(
            type="ITR",
            posting_date=date(2026, 3, 26),
            document_number="TEST001",
            item_number="001",
            ordered_qty=10,
            delivered_qty=0.0,
            branch_name_v2="Test Branch",
            due_date=date(2026, 3, 26),
            status="Not Scheduled",
            cbm=1.5
        )
        db.session.add(data)
        db.session.commit()

        service = AIService(
            api_key="test",
            api_base="https://test.com",
            model="gpt-4"
        )

        results = service.query_pending_deliveries("North", date(2026, 3, 26))

        assert len(results) > 0

        # Cleanup
        db.session.delete(data)
        db.session.delete(cluster)
        db.session.commit()

def test_query_available_manpower(client):
    """Test querying available drivers and assistants"""
    with app.app_context():
        from models import Manpower

        # Clean up any existing test manpower
        existing_driver = Manpower.query.filter_by(name="Test Driver").first()
        if existing_driver:
            db.session.delete(existing_driver)
            db.session.commit()

        existing_assistant = Manpower.query.filter_by(name="Test Assistant").first()
        if existing_assistant:
            db.session.delete(existing_assistant)
            db.session.commit()

        # Create test manpower
        driver = Manpower(
            name="Test Driver",
            role="Driver"
        )
        assistant = Manpower(
            name="Test Assistant",
            role="Assistant"
        )
        db.session.add(driver)
        db.session.add(assistant)
        db.session.commit()

        service = AIService(
            api_key="test",
            api_base="https://test.com",
            model="gpt-4"
        )

        drivers = service.query_available_manpower(role="Driver")
        assistants = service.query_available_manpower(role="Assistant")

        assert len(drivers) > 0
        assert len(assistants) > 0

        # Cleanup
        db.session.delete(driver)
        db.session.delete(assistant)
        db.session.commit()

def test_build_schedule_proposal(client):
    """Test building a complete schedule proposal"""
    with app.app_context():
        from models import Vehicle, Cluster, Data
        from datetime import date

        # Clean up any existing test data
        existing_vehicle = Vehicle.query.filter_by(plate_number="PROP123").first()
        if existing_vehicle:
            db.session.delete(existing_vehicle)
            db.session.commit()

        existing_cluster = Cluster.query.filter_by(no="PROP001").first()
        if existing_cluster:
            db.session.delete(existing_cluster)
            db.session.commit()

        existing_data = Data.query.filter(Data.document_number.in_(["PROP001", "PROP002"])).all()
        for d in existing_data:
            db.session.delete(d)
        db.session.commit()

        # Create test vehicle
        vehicle = Vehicle(
            plate_number="PROP123",
            capacity=20.0,
            status="Active",
            dept="Logistics",
            type="in-house"
        )
        db.session.add(vehicle)
        db.session.flush()

        # Create test cluster
        cluster = Cluster(
            no="PROP001",
            branch="Proposal Branch",
            area="North",
            category="Test"
        )
        db.session.add(cluster)
        db.session.flush()

        # Create test data items
        data1 = Data(
            type="ITR",
            posting_date=date(2026, 3, 26),
            document_number="PROP001",
            item_number="001",
            ordered_qty=10,
            delivered_qty=0.0,
            branch_name_v2="Proposal Branch",
            due_date=date(2026, 3, 26),
            status="Not Scheduled",
            cbm=1.0
        )
        data2 = Data(
            type="ITR",
            posting_date=date(2026, 3, 26),
            document_number="PROP002",
            item_number="002",
            ordered_qty=5,
            delivered_qty=0.0,
            branch_name_v2="Proposal Branch",
            due_date=date(2026, 3, 26),
            status="Not Scheduled",
            cbm=0.5
        )
        db.session.add(data1)
        db.session.add(data2)
        db.session.commit()

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
        assert proposal["vehicle_id"] == vehicle.id
        assert proposal["plate_number"] == "PROP123"
        assert proposal["total_cbm"] > 0
        assert len(proposal["trips"]) > 0
        assert len(proposal["trips"][0]["details"]) > 0

        # Cleanup
        db.session.delete(data1)
        db.session.delete(data2)
        db.session.delete(cluster)
        db.session.delete(vehicle)
        db.session.commit()

def test_format_proposal_display(client):
    """Test formatting proposal for human-readable display"""
    with app.app_context():
        service = AIService(
            api_key="test",
            api_base="https://test.com",
            model="gpt-4"
        )

        proposal = {
            "delivery_schedule": "2026-03-26",
            "plate_number": "TEST123",
            "capacity": 15.5,
            "total_cbm": 14.2,
            "utilization_pct": 91.6,
            "trips": [
                {
                    "trip_number": 1,
                    "details": [
                        {
                            "branch_name_v2": "Branch A",
                            "total_cbm": 7.1,
                            "total_ordered_qty": 50
                        }
                    ]
                }
            ]
        }

        display = service.format_proposal_display(proposal)

        assert "TEST123" in display
        assert "15.5 CBM" in display
        assert "14.2 CBM" in display
        assert "Branch A" in display
