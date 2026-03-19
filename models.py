from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Active')  # 'Active' or 'Inactive'
    capacity = db.Column(db.Float, nullable=True)  # Vehicle capacity in CBM
    dept = db.Column(db.String(50), nullable=True)  # 'Logistics', 'Executive', 'Service'

    def __repr__(self):
        return f'<Vehicle {self.plate_number}>'

class Manpower(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # "Driver", "Assistant"
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Optional link to User
    user = db.relationship('User', backref=db.backref('manpower', uselist=False, lazy=True))

    def __repr__(self):
        return f'<Manpower {self.name} - {self.role}>'

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # "ITR", "SO"
    posting_date = db.Column(db.Date, nullable=False)
    document_number = db.Column(db.String(100), nullable=False)
    item_number = db.Column(db.String(100), nullable=False)
    ordered_qty = db.Column(db.Integer, nullable=False)
    delivered_qty = db.Column(db.Float, nullable=False)
    remaining_open_qty = db.Column(db.Float)
    from_whse_code = db.Column(db.String(50))
    to_whse = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    special_instructions = db.Column(db.Text)
    branch_name = db.Column(db.String(100))
    branch_name_v2 = db.Column(db.String(100))
    document_status = db.Column(db.String(50))  # "O", "C"
    original_due_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    user_code = db.Column(db.String(50))
    po_number = db.Column(db.String(100))
    isms_so_number = db.Column(db.String(100))
    cbm = db.Column(db.Float)
    total_cbm = db.Column(db.Float, default=0.0)  # should be computed (cbm * ordered_qty)
    customer_vendor_code = db.Column(db.String(50))
    customer_vendor_name = db.Column(db.String(100))
    status = db.Column(db.String(50)) # "Not Scheduled", "Scheduled", "Cancelled", "Deleted"
    delivery_type = db.Column(db.String(100), nullable=True)  # Delivery type
    delete_remarks = db.Column(db.String(255), nullable=True)  # Reason for deletion
    detailed_remarks = db.Column(db.Text, nullable=True)  # Detailed remarks for deletion (long text)

    def __repr__(self):
        return f'<Data {self.document_number}>'

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_schedule = db.Column(db.Date, nullable=False)
    plate_number = db.Column(db.String(50), nullable=True)
    capacity = db.Column(db.Float, nullable=True)
    actual = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<Schedule {self.id} - {self.delivery_schedule}>'

# Association tables for many-to-many relationships
trip_driver = db.Table('trip_driver',
    db.Column('trip_id', db.Integer, db.ForeignKey('trip.id'), primary_key=True),
    db.Column('manpower_id', db.Integer, db.ForeignKey('manpower.id'), primary_key=True)
)

trip_assistant = db.Table('trip_assistant',
    db.Column('trip_id', db.Integer, db.ForeignKey('trip.id'), primary_key=True),
    db.Column('manpower_id', db.Integer, db.ForeignKey('manpower.id'), primary_key=True)
)

class Trip(db.Model):
    __tablename__ = 'trip'
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    schedule = db.relationship('Schedule', backref=db.backref('trips', lazy=True))

    trip_number = db.Column(db.Integer, nullable=False) # e.g., Trip 1, Trip 2 on same day
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    vehicle = db.relationship('Vehicle')

    # ✅ Keep ONLY the many-to-many relationships
    drivers = db.relationship('Manpower', secondary=trip_driver, 
                              backref=db.backref('trips_as_driver', lazy='dynamic'))
    assistants = db.relationship('Manpower', secondary=trip_assistant,
                                backref=db.backref('trips_as_assistant', lazy='dynamic'))

    total_cbm = db.Column(db.Float, default=0.0)  # Optional: can be computed
    completed = db.Column(db.Boolean, default=False)  # Track if trip is marked as complete

class TripDetail(db.Model):
    __tablename__ = 'trip_detail'
    id = db.Column(db.Integer, primary_key=True)
    document_number = db.Column(db.String(100), nullable=True)  # Store document number (optional, for reference)
    branch_name_v2 = db.Column(db.String(100), nullable=False)  # Store branch name for grouping
    data_ids = db.Column(db.Text)  # Store comma-separated list of data IDs for this branch
    area = db.Column(db.String(100))

    # Aggregated values
    total_cbm = db.Column(db.Float, nullable=False, default=0.0)  # Sum of all CBM for this document
    total_ordered_qty = db.Column(db.Integer, nullable=False, default=0)  # Sum of ordered quantities
    total_delivered_qty = db.Column(db.Integer, nullable=False, default=0)  # Sum of delivered quantities
    backload_qty = db.Column(db.Integer, nullable=True, default=0)  # Quantity that was backloaded/returned

    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    trip = db.relationship('Trip', backref=db.backref('details', lazy=True))

    status = db.Column(db.String(50))  # "Delivered", "Cancelled" default "Delivered"
    cancel_reason = db.Column(db.String(255))  # Reason for cancellation if status is "Cancelled"
    cause_department = db.Column(db.String(255))  # Department responsible for the cause

    # Arrival and departure tracking
    arrive = db.Column(db.DateTime)  # Arrival date and time
    departure = db.Column(db.DateTime)  # Departure date and time
    reason = db.Column(db.Text)  # Reason for arrival/departure notes

    delivery_type = db.Column(db.String(100), nullable=True)  # Delivery type
    delivery_order = db.Column(db.Integer, nullable=True)  # Delivery sequence (1, 2, 3...)
    original_due_date = db.Column(db.Date, nullable=True)  # Original due date from Data

    def __repr__(self):
        return f'<TripDetail {self.id} - Branch {self.branch_name_v2} - Trip {self.trip_id}>'

class Cluster(db.Model):
    __tablename__ = 'cluster'
    id = db.Column(db.Integer, primary_key=True)
    no = db.Column(db.String(50), nullable=False)  # Cluster number/name
    weekly_schedule = db.Column(db.String(100))  # Weekly schedule
    delivered_by = db.Column(db.String(100))  # Who delivers
    location = db.Column(db.String(100))  # Location
    category = db.Column(db.String(100))  # Category
    area = db.Column(db.String(100))  # Area
    branch = db.Column(db.String(100))  # Branch
    frequency = db.Column(db.String(100))  # Frequency
    frequency_count = db.Column(db.String(50))  # Frequency count
    tl = db.Column(db.String(100))  # TL (Team Lead?)
    delivery_mode = db.Column(db.String(100))  # Delivery mode
    active_branches = db.Column(db.Text)  # Active branches (can be long)

    def __repr__(self):
        return f'<Cluster {self.no} - {self.branch}>'

class Odo(db.Model):
    __tablename__ = 'odo'
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(50), db.ForeignKey('vehicle.plate_number'), nullable=False)
    vehicle = db.relationship('Vehicle', backref=db.backref('odo_readings', lazy=True))
    odometer_reading = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'start odo', 'refill odo', 'end odo'
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.now)
    created_by = db.Column(db.String(100), nullable=False)  # User who created the record
    litters = db.Column(db.Float, nullable=True)  # Fuel litters for refill
    amount = db.Column(db.Float, nullable=True)  # Cost amount for refill
    price_per_litter = db.Column(db.Float, nullable=True)  # Computed: amount / litters

    def __repr__(self):
        return f'<Odo {self.id} - {self.plate_number} - {self.status}>'

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(50), nullable=False, default='user')  # 'admin' or 'user'
    status = db.Column(db.String(50), nullable=False, default='active')  # 'active' or 'inactive'
    daily_rate = db.Column(db.Float, nullable=True)  # Daily rate for payroll
    sched_start = db.Column(db.String(10), nullable=True)  # Schedule start time (e.g., "08:00")
    sched_end = db.Column(db.String(10), nullable=True)  # Schedule end time (e.g., "17:00")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email} - {self.position}>'

class TimeLog(db.Model):
    __tablename__ = 'time_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('time_logs', lazy=True))
    time_in = db.Column(db.DateTime, nullable=False)  # Time in
    time_out = db.Column(db.DateTime, nullable=True)  # Time out
    hrs_rendered = db.Column(db.Float, nullable=True)  # Hours rendered
    daily_rate = db.Column(db.Float, nullable=True)  # Daily rate
    over_time = db.Column(db.Float, nullable=True, default=0.0)  # Overtime hours
    pay = db.Column(db.Float, nullable=True)  # Regular pay
    ot_pay = db.Column(db.Float, nullable=True, default=0.0)  # Overtime pay
    sched_start = db.Column(db.String(10), nullable=True)  # Schedule start (e.g., "08:00")
    sched_end = db.Column(db.String(10), nullable=True)  # Schedule end (e.g., "17:00")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)  # Record creation timestamp

    def __repr__(self):
        return f'<TimeLog {self.id} - User {self.user_id} - {self.time_in}>'

class DailyVehicleCount(db.Model):
    __tablename__ = 'daily_vehicle_count'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    qty = db.Column(db.Integer, nullable=False, default=0)  # Count of active vehicles
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f'<DailyVehicleCount {self.date} - {self.qty} vehicles>'

class Backload(db.Model):
    __tablename__ = 'backload'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # "ITR", "SO"
    posting_date = db.Column(db.Date, nullable=False)
    document_number = db.Column(db.String(100), nullable=False)
    item_number = db.Column(db.String(100), nullable=False)
    ordered_qty = db.Column(db.Integer, nullable=False)
    delivered_qty = db.Column(db.Float, nullable=False)
    remaining_open_qty = db.Column(db.Float)
    from_whse_code = db.Column(db.String(50))
    to_whse = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    special_instructions = db.Column(db.Text)
    branch_name = db.Column(db.String(100))
    branch_name_v2 = db.Column(db.String(100))
    document_status = db.Column(db.String(50))  # "O", "C"
    original_due_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    user_code = db.Column(db.String(50))
    po_number = db.Column(db.String(100))
    isms_so_number = db.Column(db.String(100))
    cbm = db.Column(db.Float)
    total_cbm = db.Column(db.Float, default=0.0)
    customer_vendor_code = db.Column(db.String(50))
    customer_vendor_name = db.Column(db.String(100))
    status = db.Column(db.String(50))  # "Not Scheduled", "Scheduled", "Cancelled"
    delivery_type = db.Column(db.String(100), nullable=True)
    backload_qty = db.Column(db.Integer, nullable=False, default=0)  # Additional column for backload quantity
    backload_remarks = db.Column(db.String(255), nullable=True)  # Reason for backload
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)  # Track when backload was created

    def __repr__(self):
        return f'<Backload {self.document_number} - {self.item_number} - Qty: {self.backload_qty}>' 

class LCLSummary(db.Model):
    __tablename__ = 'lcl_summary'
    id = db.Column(db.Integer, primary_key=True)
    posting_date = db.Column(db.Date, nullable=False)
    company = db.Column(db.String(100), nullable=False, default='FINDEN')
    dept = db.Column(db.String(100), nullable=False, default='LOGISTICS')
    branch_name = db.Column(db.String(100), nullable=False)
    tot_qty = db.Column(db.Integer, nullable=False, default=0)
    tot_cbm = db.Column(db.Float, nullable=False, default=0.0)

    # Additional tracking fields
    prep_date = db.Column(db.Date, nullable=True)
    waybill_no = db.Column(db.String(100), nullable=True)
    pl_3pl = db.Column('3pl', db.String(100), nullable=True)  # Maps to DB column '3pl'
    ref_docs = db.Column(db.String(200), nullable=True)
    freight_category = db.Column(db.String(100), nullable=True)
    shipping_line = db.Column(db.String(100), nullable=True)
    container_no = db.Column(db.String(100), nullable=True)
    seal_no = db.Column(db.String(100), nullable=True)
    tot_boxes = db.Column(db.Integer, nullable=True)
    declared_value = db.Column(db.Float, nullable=True)
    freight_charge = db.Column(db.Float, nullable=True)
    length_width_height = db.Column(db.String(100), nullable=True)  # Renamed from 'lenght_width_height'
    total_kg = db.Column(db.Float, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    port_of_destination = db.Column(db.String(100), nullable=True)
    order_date = db.Column(db.Date, nullable=True)
    booked_date = db.Column(db.Date, nullable=True)
    actual_pickup_date = db.Column(db.Date, nullable=True)
    etd = db.Column(db.Date, nullable=True)  # Estimated Time of Departure
    atd = db.Column(db.Date, nullable=True)  # Actual Time of Departure
    eta = db.Column(db.Date, nullable=True)  # Estimated Time of Arrival
    ata = db.Column(db.Date, nullable=True)  # Actual Time of Arrival
    actual_delivered_date = db.Column(db.Date, nullable=True)
    received_by = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    detailed_remarks = db.Column(db.Text, nullable=True)
    actual_delivery_leadtime = db.Column(db.Integer, nullable=True)  # In days
    received_date_to_pick_up_date = db.Column(db.Integer, nullable=True)  # In days
    year = db.Column(db.Integer, nullable=True)
    pick_up_month = db.Column(db.String(20), nullable=True)
    total_freight_charge = db.Column(db.Float, nullable=True)
    billing_date = db.Column(db.Date, nullable=True)
    billing_no = db.Column(db.String(100), nullable=True)
    billing_status = db.Column(db.String(50), nullable=True)
    team_lead = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)  # For visibility control

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # Unique constraint to prevent duplicate summaries
    __table_args__ = (
        db.UniqueConstraint('posting_date', 'branch_name', name='uix_lcl_summary_date_branch'),
    )

    def __repr__(self):
        return f'<LCLSummary {self.posting_date} - {self.branch_name} - Qty: {self.tot_qty}>'

class LCLDetail(db.Model):
    __tablename__ = 'lcl_detail'
    id = db.Column(db.Integer, primary_key=True)
    sap_upload_date = db.Column(db.Date, nullable=False)
    isms_upload_date = db.Column(db.Date, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    doc_type = db.Column(db.String(50), nullable=True)
    dr_number = db.Column(db.String(100), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=0)
    fr_whse = db.Column(db.String(100), nullable=True)
    to_whse = db.Column(db.String(100), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    serial_number = db.Column(db.String(100), nullable=False)
    itr_so = db.Column(db.String(100), nullable=True)
    dr_it = db.Column(db.String(100), nullable=True)
    cbm = db.Column(db.Float, nullable=False, default=0.0)
    email = db.Column(db.String(120), nullable=True)  # For visibility control
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # Unique constraint to prevent duplicate uploads
    __table_args__ = (
        db.UniqueConstraint('sap_upload_date', 'customer_name', 'serial_number', name='uix_lcl_detail_unique'),
    )

    def __repr__(self):
        return f'<LCLDetail {self.sap_upload_date} - {self.customer_name} - {self.serial_number}>'

class ArchiveLog(db.Model):
    __tablename__ = 'archive_log'
    id = db.Column(db.Integer, primary_key=True)
    executed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    cutoff_year = db.Column(db.Integer, nullable=False)
    records_archived = db.Column(db.Integer, nullable=False)
    tables_affected = db.Column(db.Text)  # JSON string
    status = db.Column(db.String(50))  # 'success', 'failed', 'partial'
    error_message = db.Column(db.Text)
    execution_time_seconds = db.Column(db.Float)

    def __repr__(self):
        return f'<ArchiveLog {self.executed_at} - Year {self.cutoff_year} - {self.status}>'
