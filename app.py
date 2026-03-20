import os
import csv
import io
import json
import random
import string
import re
from collections import defaultdict
from dateutil import parser as date_parser
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pandas as pd
from models import db, Vehicle, Manpower, Data, Schedule, Trip, TripDetail, Cluster, User, Odo, DailyVehicleCount, Backload, TimeLog, LCLSummary, LCLDetail, ArchiveLog, trip_driver, trip_assistant
from sqlalchemy import func
from sqlalchemy.orm import joinedload, subqueryload
from functools import wraps
from threading import Lock



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trip_monitoring.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configure archive database bind
archive_db_path = os.path.join(os.path.dirname(__file__), 'instance', 'trip_archive.db')
archive_db_path_abs = os.path.abspath(archive_db_path)
archive_db_url = f'sqlite:///{archive_db_path_abs}'
app.config['SQLALCHEMY_BINDS'] = {'archive': archive_db_url}

db.init_app(app)

# Simple in-memory cache for static reference data
# This cache stores frequently accessed data that doesn't change often
class SimpleCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = Lock()
        self.default_ttl = 300  # 5 minutes default TTL

    def get(self, key):
        with self._lock:
            if key in self._cache:
                timestamp = self._timestamps.get(key)
                if timestamp and datetime.now() - timestamp < timedelta(seconds=self.default_ttl):
                    return self._cache[key]
                else:
                    # Cache expired
                    del self._cache[key]
                    del self._timestamps[key]
            return None

    def set(self, key, value, ttl=None):
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
            if ttl:
                # Store custom TTL (not used in get() but can be extended)
                pass

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def delete(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            if key in self._timestamps:
                del self._timestamps[key]

# Initialize cache
cache = SimpleCache()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Create tables
with app.app_context():
    db.create_all()

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}

# Helper function to parse date
def parse_date_flexible(date_str):
    """Parse common date formats like '10/2/25', '10/02/2025', '2025-10-02'."""
    if not date_str or date_str.strip() == '':
        return None
    try:
        # Parse and ensure it's a date (not datetime)
        parsed = date_parser.parse(date_str.strip(), dayfirst=False)
        return parsed.date()
    except (ValueError, TypeError):
        raise ValueError(f"Unable to parse date: '{date_str}'")

# Decorator to check if user is admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.position != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('view_schedule'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator to check if user is logged in
def login_required_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Cached data helper functions
def get_cached_active_vehicles():
    """Get cached list of active vehicles"""
    cached_data = cache.get('active_vehicles')
    if cached_data is not None:
        return cached_data

    vehicles = Vehicle.query.filter_by(status='Active').order_by(Vehicle.plate_number).all()
    cache.set('active_vehicles', vehicles)
    return vehicles

def get_cached_all_vehicles():
    """Get cached list of all vehicles"""
    cached_data = cache.get('all_vehicles')
    if cached_data is not None:
        return cached_data

    vehicles = Vehicle.query.order_by(Vehicle.plate_number).all()
    cache.set('all_vehicles', vehicles)
    return vehicles

def get_cached_drivers():
    """Get cached list of drivers"""
    cached_data = cache.get('drivers')
    if cached_data is not None:
        return cached_data

    drivers = Manpower.query.filter_by(role='Driver').order_by(Manpower.name).all()
    cache.set('drivers', drivers)
    return drivers

def get_cached_assistants():
    """Get cached list of assistants"""
    cached_data = cache.get('assistants')
    if cached_data is not None:
        return cached_data

    assistants = Manpower.query.filter_by(role='Assistant').order_by(Manpower.name).all()
    cache.set('assistants', assistants)
    return assistants

def get_cached_clusters():
    """Get cached list of clusters"""
    cached_data = cache.get('clusters')
    if cached_data is not None:
        return cached_data

    clusters = Cluster.query.all()
    cache.set('clusters', clusters)
    return clusters

def get_cached_cluster_dict():
    """Get cached cluster dictionary for lookup"""
    cached_data = cache.get('cluster_dict')
    if cached_data is not None:
        return cached_data

    clusters = Cluster.query.all()
    cluster_dict = {}
    for cluster in clusters:
        if cluster.branch:
            cluster_dict[cluster.branch.lower()] = cluster.area or ''
    cache.set('cluster_dict', cluster_dict)
    return cluster_dict

def invalidate_reference_cache():
    """Invalidate all reference data caches (call after modifying vehicles, manpower, or clusters)"""
    cache.delete('active_vehicles')
    cache.delete('all_vehicles')
    cache.delete('drivers')
    cache.delete('assistants')
    cache.delete('clusters')
    cache.delete('cluster_dict')

# Home page
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.position == 'admin':
            return render_template('dashboard.html')
        else:
            # Non-admin users redirect to view_schedule
            return redirect(url_for('view_schedule'))
    else:
        return render_template('login.html')

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please provide both email and password', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.status != 'active':
                flash('Your account is inactive. Please contact the administrator.', 'error')
                return redirect(url_for('login'))

            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')

            # Redirect to the appropriate page based on user position
            if user.position == 'admin':
                return redirect(url_for('index'))
            else:
                return redirect(url_for('view_schedule'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Data management routes
@app.route('/data')
@login_required
def view_data():
   # ✅ Only fetch records with status = 'Not Scheduled' with pagination and search
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 records per page
    search_term = request.args.get('search', '').strip()

    # Build query
    query = Data.query.filter_by(status='Not Scheduled')

    # Apply search filter if provided
    if search_term:
        query = query.filter(Data.document_number.contains(search_term))

    pagination = query.order_by(Data.due_date.desc().nulls_last(), Data.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('view_data.html', data=pagination.items, pagination=pagination, search_term=search_term)

@app.route('/data/scheduled')
@login_required
def view_scheduled_data():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Get search and filter parameters
    search_term = request.args.get('search', '').strip()
    search_type = request.args.get('type', 'document')
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 records per page

    # Build query
    query = Data.query.filter(Data.status == 'Scheduled')

    # Apply filters if search term is provided
    if search_term:
        if search_type == 'document':
            query = query.filter(Data.document_number.contains(search_term))
        elif search_type == 'class':
            query = query.filter(
                db.or_(
                    Data.branch_name.contains(search_term),
                    Data.branch_name_v2.contains(search_term)
                )
            )

    # Order by id descending (newest first) and paginate
    pagination = query.order_by(Data.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('view_scheduled_data.html',
                         data=pagination.items,
                         pagination=pagination,
                         search_term=search_term,
                         search_type=search_type)
 
@app.route('/data/download_template')
def download_csv_template():
    from io import StringIO
    from flask import Response

    # Create an in-memory CSV
    template = StringIO()
    writer = csv.writer(template)

    # Write headers matching Data model fields (in order)
    writer.writerow([
        "Type",
        "Posting Date",
        "Document Number",
        "Item No.",
        "Ordered Quantity",
        "Delivered Quantity",
        "Remaining Open Qty",
        "From Warehouse Code",
        "To Warehouse",
        "Remarks",
        "Special Instruction",
        "Branch Name",
        "Branch Name v2",
        "Document Status",
        "Due Date",
        "User_Code",
        "PO Number",
        "ISMS SO#",
        "CBM",
        "Customer/Vendor Code",
        "Customer/Vendor Name",
        "Delivery Type"
    ])

    # Write one sample row for guidance (based on your data)
    writer.writerow([
    ])

    template.seek(0)

    # Return as downloadable CSV file
    return Response(
        template.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=data_upload_template.csv'}
    )

@app.route('/data/upload', methods=['GET', 'POST'])
def upload_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are allowed', 'error')
            return redirect(request.url)

        try:
            # Read file content
            file_content = file.stream.read()

            # Try multiple encodings
            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            stream = None
            decoded = False

            for encoding in encodings:
                try:
                    stream = file_content.decode(encoding).splitlines()
                    decoded = True
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if not decoded:
                flash("File encoding error. Unable to read the CSV file. Please ensure it's saved as UTF-8, Latin-1, or Windows-1252 encoding.", 'error')
                return redirect(request.url)

            csv_reader = csv.DictReader(stream)

            expected_headers = {
                "Type", "Posting Date", "Document Number", "Item No.",
                "Ordered Quantity", "Delivered Quantity", "Remaining Open Qty",
                "From Warehouse Code", "To Warehouse", "Remarks",
                "Special Instruction", "Branch Name", "Branch Name v2",
                "Document Status", "Due Date", "User_Code", "PO Number",
                "ISMS SO#", "CBM", "Customer/Vendor Code", "Customer/Vendor Name",
                "Delivery Type"
            }

            if set(csv_reader.fieldnames) != expected_headers:
                missing = expected_headers - set(csv_reader.fieldnames)
                extra = set(csv_reader.fieldnames) - expected_headers
                msg = ""
                if missing:
                    msg += f"Missing columns: {', '.join(missing)}. "
                if extra:
                    msg += f"Unexpected columns: {', '.join(extra)}."
                flash(f"Invalid CSV headers. {msg}", 'error')
                return redirect(request.url)

            # ✅ OPTIMIZED: Batch processing for better performance
            # Step 1: Load all CSV rows into memory and validate
            all_rows = list(csv_reader)
            if not all_rows:
                flash("CSV file is empty", 'error')
                return redirect(request.url)

            # Step 2: Validate all rows first (data parsing)
            validated_records = []
            rows_to_insert = []
            records_skipped = 0
            posting_date_errors = []

            for row_num, row in enumerate(all_rows, start=2):
                try:
                    # Parse and validate data
                    posting_date = parse_date_flexible(row["Posting Date"])
                    due_date = parse_date_flexible(row["Due Date"])
                    document_number = row["Document Number"] if row["Document Number"] else None

                    # Validate posting_date - NOT NULL constraint
                    if posting_date is None:
                        if document_number:
                            posting_date_errors.append(f"Row {row_num}: Missing posting_date (Document Number: {document_number})")
                        else:
                            # Skip line entirely if both posting_date and document_number are null
                            records_skipped += 1
                            continue
                        continue

                    # Helper to safely convert numeric fields (handles spaces and empty strings)
                    def safe_float(val, default=0.0):
                        if val is None or val.strip() == '':
                            return default
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return default

                    def safe_int(val, default=0):
                        if val is None or val.strip() == '':
                            return default
                        try:
                            return int(float(val))
                        except (ValueError, TypeError):
                            return default

                    cbm = safe_float(row["CBM"], 0.0)
                    ordered_qty = safe_float(row["Ordered Quantity"], 0.0)
                    ordered_qty_int = safe_int(row["Ordered Quantity"], 0)

                    # Helper to convert empty strings to None
                    def clean(val):
                        return val if val != '' else None

                    # Handle branch name fallback logic
                    branch_name = clean(row["Branch Name"])
                    branch_name_v2 = clean(row["Branch Name v2"])

                    # If branch_name is blank, use branch_name_v2
                    if not branch_name:
                        branch_name = branch_name_v2
                    # If branch_name_v2 is blank, use branch_name
                    elif not branch_name_v2:
                        branch_name_v2 = branch_name

                    # Store validated record
                    validated_records.append({
                        'row_num': row_num,
                        'document_number': document_number,
                        'item_number': row["Item No."],
                        'ordered_qty': ordered_qty_int,
                        'type': row["Type"],
                        'posting_date': posting_date,
                        'due_date': due_date,
                        'cbm': cbm,
                        'ordered_qty_float': ordered_qty,
                        'delivered_qty': safe_float(row["Delivered Quantity"], 0.0),
                        'remaining_open_qty': safe_float(row["Remaining Open Qty"], 0.0),
                        'from_whse_code': clean(row["From Warehouse Code"]),
                        'to_whse': clean(row["To Warehouse"]),
                        'remarks': clean(row["Remarks"]),
                        'special_instructions': clean(row["Special Instruction"]),
                        'branch_name': branch_name,
                        'branch_name_v2': branch_name_v2,
                        'document_status': clean(row["Document Status"]),
                        'user_code': clean(row["User_Code"]),
                        'po_number': clean(row["PO Number"]),
                        'isms_so_number': clean(row["ISMS SO#"]),
                        'customer_vendor_code': clean(row["Customer/Vendor Code"]),
                        'customer_vendor_name': clean(row["Customer/Vendor Name"]),
                        'delivery_type': clean(row["Delivery Type"])
                    })

                except ValueError as ve:
                    flash(f"Row {row_num}: Invalid data format – {str(ve)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)
                except Exception as e:
                    flash(f"Row {row_num}: Unexpected error – {str(e)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)

            # Step 2.5: Check for duplicates within the CSV file itself
            csv_internal_duplicates = {}
            csv_unique_records = []
            csv_internal_skipped = 0

            for record in validated_records:
                key = (record['document_number'], record['item_number'], record['ordered_qty'])
                if key in csv_internal_duplicates:
                    # Track the duplicate
                    if key not in csv_internal_duplicates:
                        csv_internal_duplicates[key] = [record['row_num']]
                    csv_internal_duplicates[key].append(record['row_num'])
                    csv_internal_skipped += 1
                else:
                    csv_internal_duplicates[key] = [record['row_num']]
                    csv_unique_records.append(record)

            # Build error messages for internal duplicates
            csv_dup_warnings = []
            for key, row_nums in csv_internal_duplicates.items():
                if len(row_nums) > 1:
                    doc_num = key[0] if key[0] else "N/A"
                    item_num = key[1] if key[1] else "N/A"
                    ord_qty = key[2]
                    rows_str = ", ".join(map(str, row_nums))
                    csv_dup_warnings.append(
                        f"Duplicate record in CSV: Document '{doc_num}', Item '{item_num}', Qty {ord_qty} found in rows {rows_str}. Keeping first occurrence, skipping duplicates."
                    )

            # Update validated_records to only include unique records from CSV
            validated_records = csv_unique_records

            # Step 3: Batch duplicate check - SINGLE QUERY instead of N queries
            # Build list of all unique (document_number, item_number, ordered_qty) from CSV
            csv_keys = [(r['document_number'], r['item_number'], r['ordered_qty']) for r in validated_records]

            # Query all existing records that match ANY of the CSV keys in one go
            # Use OR clauses for SQLite compatibility
            if csv_keys:
                # Split into batches to avoid SQL query size limits
                batch_size = 500
                existing_records = []

                for i in range(0, len(csv_keys), batch_size):
                    batch = csv_keys[i:i + batch_size]
                    # Build OR conditions for each batch
                    or_conditions = db.or_(
                        *(db.and_(
                            Data.document_number == doc_num,
                            Data.item_number == item_num,
                            Data.ordered_qty == ord_qty
                        ) for doc_num, item_num, ord_qty in batch)
                    )
                    batch_records = Data.query.filter(or_conditions).all()
                    existing_records.extend(batch_records)

                # Build set of existing records for fast lookup
                existing_keys = {(r.document_number, r.item_number, r.ordered_qty) for r in existing_records}
            else:
                existing_keys = set()

            # Step 4: Filter out duplicates and prepare bulk insert
            records_to_insert = []
            for record in validated_records:
                key = (record['document_number'], record['item_number'], record['ordered_qty'])
                if key in existing_keys:
                    records_skipped += 1
                else:
                    records_to_insert.append(record)

            # Step 5: Bulk insert all non-duplicate records at once
            if records_to_insert:
                with db.session.no_autoflush:
                    for record in records_to_insert:
                        data_entry = Data(
                            type=record['type'],
                            posting_date=record['posting_date'],
                            document_number=record['document_number'],
                            item_number=record['item_number'],
                            ordered_qty=record['ordered_qty'],
                            delivered_qty=record['delivered_qty'],
                            remaining_open_qty=record['remaining_open_qty'],
                            from_whse_code=record['from_whse_code'],
                            to_whse=record['to_whse'],
                            remarks=record['remarks'],
                            special_instructions=record['special_instructions'],
                            branch_name=record['branch_name'],
                            branch_name_v2=record['branch_name_v2'],
                            document_status=record['document_status'],
                            original_due_date=record['due_date'],
                            due_date=record['due_date'],
                            user_code=record['user_code'],
                            po_number=record['po_number'],
                            isms_so_number=record['isms_so_number'],
                            cbm=record['cbm'],
                            total_cbm=round(record['cbm'] * record['ordered_qty_float'], 2),
                            customer_vendor_code=record['customer_vendor_code'],
                            customer_vendor_name=record['customer_vendor_name'],
                            delivery_type=record['delivery_type'],
                            status="Not Scheduled"
                        )
                        db.session.add(data_entry)

                db.session.commit()
                records_added = len(records_to_insert)
            else:
                records_added = 0

            # Display CSV internal duplicate warnings first
            if csv_dup_warnings:
                for warning in csv_dup_warnings:
                    flash(warning, 'warning')

            # Display posting_date validation errors
            if posting_date_errors:
                for error in posting_date_errors:
                    flash(error, 'warning')

            message = f"Successfully uploaded {records_added} record(s)!"
            total_skipped = records_skipped + csv_internal_skipped
            if total_skipped > 0:
                if csv_internal_skipped > 0:
                    message += f" Skipped {total_skipped} duplicate record(s) ({csv_internal_skipped} within CSV, {records_skipped} in database)."
                else:
                    message += f" Skipped {total_skipped} duplicate record(s)."
            flash(message, 'success')
            return redirect(url_for('view_data'))

        except Exception as e:
            flash(f"Failed to process file: {str(e)}", 'error')
            db.session.rollback()
            return redirect(request.url)

    return render_template('add_data.html')


@app.route('/data/<int:id>/edit', methods=['GET', 'POST'])
def edit_data(id):
    data = Data.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Helper to safely get form values (empty string → None for optional fields)
            def get_form_value(key, default=None):
                val = request.form.get(key, '').strip()
                return val if val != '' else default

            # Update string fields
            data.type = request.form['type']
            data.document_number = request.form['document_number']
            data.item_number = request.form['item_number']
            data.from_whse_code = get_form_value('from_whse_code')
            data.to_whse = get_form_value('to_whse')
            data.pur_slr_uom_if_base_unit = get_form_value('pur_slr_uom_if_base_unit')
            data.branch_name = get_form_value('branch_name')
            data.branch_name_v2 = get_form_value('branch_name_v2')
            data.document_status = get_form_value('document_status')
            data.po_number = get_form_value('po_number')
            data.isms_so_number = get_form_value('isms_so_number')
            data.customer_vendor_code = get_form_value('customer_vendor_code')
            data.customer_vendor_name = get_form_value('customer_vendor_name')
            data.user_code = get_form_value('user_code')
            data.special_instructions = get_form_value('special_instructions')
            data.remarks = get_form_value('remarks')
            data.status = request.form['status']  # Required (dropdown)

            # Handle dates
            posting_date_str = request.form.get('posting_date')
            data.posting_date = datetime.strptime(posting_date_str, '%Y-%m-%d').date() if posting_date_str else None

            due_date_str = request.form.get('due_date')
            new_due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

            # Check if due_date is being changed
            old_due_date = data.due_date
            due_date_changed = old_due_date != new_due_date

            # Update due_date for the current record
            data.due_date = new_due_date

            # Handle numeric fields
            data.ordered_qty = int(request.form['ordered_qty'])
            data.delivered_qty = float(request.form['delivered_qty'])
            data.remaining_open_qty = float(request.form['remaining_open_qty']) if request.form['remaining_open_qty'] else 0.0
            data.cbm = float(request.form['cbm']) if request.form['cbm'] else 0.0

            # Save to DB
            db.session.commit()

            # If due_date changed, update all records with the same document_number
            updated_count = 0
            if due_date_changed:
                document_number = data.document_number

                # Find all records with the same document_number (excluding the current record)
                related_records = Data.query.filter(
                    Data.document_number == document_number,
                    Data.id != id
                ).all()

                # Update their due_date and original_due_date
                for record in related_records:
                    record.due_date = new_due_date
                    record.original_due_date = new_due_date
                    updated_count += 1

                if updated_count > 0:
                    db.session.commit()

            # Prepare success message
            if updated_count > 0:
                flash(f'Record updated successfully! Also updated due date for {updated_count} other record(s) with document number {data.document_number}', 'success')
            else:
                flash('Record updated successfully!', 'success')
            return redirect(url_for('view_data'))

        except ValueError as ve:
            flash(f'Invalid input: {str(ve)}', 'error')
            db.session.rollback()
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            db.session.rollback()

    # GET request: render edit form
    return render_template('edit_data.html', data=data)


@app.route('/soft_delete_data', methods=['POST'])
@login_required
def soft_delete_data():
    """Soft delete a data record by setting status to 'Deleted'"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        data_id = data.get('data_id')
        delete_remarks = data.get('delete_remarks')
        detailed_remarks = data.get('detailed_remarks')

        if not data_id:
            return jsonify({'success': False, 'message': 'Data ID is required'}), 400

        if not delete_remarks:
            return jsonify({'success': False, 'message': 'Delete remarks are required'}), 400

        # Get the data record
        data_record = Data.query.get_or_404(data_id)

        # Soft delete by updating status
        data_record.status = "Deleted"
        data_record.delete_remarks = delete_remarks
        data_record.detailed_remarks = detailed_remarks

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Record {data_record.document_number} has been marked as deleted'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting record: {str(e)}'}), 500


# Resource management routes
@app.route('/vehicles')
@login_required
def manage_vehicles():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    vehicles = Vehicle.query.order_by(Vehicle.plate_number).all()
    return render_template('manage_vehicles.html', vehicles=vehicles)

@app.route('/vehicles/add', methods=['POST'])
def add_vehicle():
    plate_number = request.form.get('plate_number')
    capacity = request.form.get('capacity')
    dept = request.form.get('dept')
    vehicle_type = request.form.get('type')

    if not plate_number:
        flash('Plate number is required')
        return redirect(url_for('manage_vehicles'))

    if not capacity:
        flash('Capacity is required')
        return redirect(url_for('manage_vehicles'))

    if not dept:
        flash('Department is required')
        return redirect(url_for('manage_vehicles'))

    if not vehicle_type:
        flash('Type is required')
        return redirect(url_for('manage_vehicles'))

    try:
        vehicle = Vehicle(plate_number=plate_number, capacity=float(capacity), dept=dept, type=vehicle_type)
        db.session.add(vehicle)
        db.session.commit()
        invalidate_reference_cache()  # Invalidate vehicle cache
        flash('Vehicle added successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding vehicle: {str(e)}')

    return redirect(url_for('manage_vehicles'))

@app.route('/vehicles/<int:id>/delete', methods=['POST'])
def delete_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    try:
        db.session.delete(vehicle)
        db.session.commit()
        invalidate_reference_cache()  # Invalidate vehicle cache
        flash('Vehicle deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting vehicle: {str(e)}')

    return redirect(url_for('manage_vehicles'))

@app.route('/vehicles/<int:id>/deactivate', methods=['POST'])
def deactivate_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    try:
        vehicle.status = 'Inactive'
        db.session.commit()
        invalidate_reference_cache()  # Invalidate vehicle cache
        flash('Vehicle deactivated successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating vehicle: {str(e)}')

    return redirect(url_for('manage_vehicles'))

@app.route('/vehicles/<int:id>/activate', methods=['POST'])
def activate_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    try:
        vehicle.status = 'Active'
        db.session.commit()
        invalidate_reference_cache()  # Invalidate vehicle cache
        flash('Vehicle activated successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error activating vehicle: {str(e)}')

    return redirect(url_for('manage_vehicles'))

@app.route('/vehicles/<int:id>/edit', methods=['POST'])
def edit_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    plate_number = request.form.get('plate_number')
    capacity = request.form.get('capacity')
    dept = request.form.get('dept')
    vehicle_type = request.form.get('type')

    if not plate_number:
        flash('Plate number is required')
        return redirect(url_for('manage_vehicles'))

    if not capacity:
        flash('Capacity is required')
        return redirect(url_for('manage_vehicles'))

    if not dept:
        flash('Department is required')
        return redirect(url_for('manage_vehicles'))

    if not vehicle_type:
        flash('Type is required')
        return redirect(url_for('manage_vehicles'))

    try:
        vehicle.plate_number = plate_number
        vehicle.capacity = float(capacity)
        vehicle.dept = dept
        vehicle.type = vehicle_type
        db.session.commit()
        invalidate_reference_cache()  # Invalidate vehicle cache
        flash('Vehicle updated successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating vehicle: {str(e)}')

    return redirect(url_for('manage_vehicles'))

@app.route('/manpower')
@login_required
def manage_manpower():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    manpower = Manpower.query.order_by(Manpower.name).all()
    users = User.query.filter_by(position='user').all()
    return render_template('manage_manpower.html', manpower=manpower, users=users)

@app.route('/manpower/add', methods=['POST'])
@login_required
def add_manpower():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('manage_manpower'))

    user_id = request.form.get('user_id')
    name = request.form.get('name')
    role = request.form.get('role')

    if not name or not role:
        flash('Name and role are required')
        return redirect(url_for('manage_manpower'))

    try:
        # If user is selected, use their name (override the provided name)
        if user_id and user_id.strip():
            user = db.session.get(User, int(user_id))
            if user:
                name = user.name

        person = Manpower(name=name, role=role)
        if user_id and user_id.strip():
            person.user_id = int(user_id)

        db.session.add(person)
        db.session.commit()
        invalidate_reference_cache()  # Invalidate manpower cache
        flash('Manpower added successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding manpower: {str(e)}')

    return redirect(url_for('manage_manpower'))

@app.route('/manpower/<int:id>/delete', methods=['POST'])
def delete_manpower(id):
    person = Manpower.query.get_or_404(id)

    try:
        db.session.delete(person)
        db.session.commit()
        invalidate_reference_cache()  # Invalidate manpower cache
        flash('Manpower deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting manpower: {str(e)}')

    return redirect(url_for('manage_manpower'))

# Cluster management routes
@app.route('/clusters')
@login_required
def manage_clusters():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    clusters = Cluster.query.all()
    return render_template('manage_clusters.html', clusters=clusters)

@app.route('/clusters/add', methods=['POST'])
def add_cluster():
    no = request.form.get('no')
    weekly_schedule = request.form.get('weekly_schedule')
    delivered_by = request.form.get('delivered_by')
    location = request.form.get('location')
    category = request.form.get('category')
    area = request.form.get('area')
    branch = request.form.get('branch')
    frequency = request.form.get('frequency')
    frequency_count = request.form.get('frequency_count')
    tl = request.form.get('tl')
    delivery_mode = request.form.get('delivery_mode')
    active_branches = request.form.get('active_branches')

    if not no:
        flash('Cluster number is required')
        return redirect(url_for('manage_clusters'))

    try:
        cluster = Cluster(
            no=no,
            weekly_schedule=weekly_schedule,
            delivered_by=delivered_by,
            location=location,
            category=category,
            area=area,
            branch=branch,
            frequency=frequency,
            frequency_count=frequency_count,
            tl=tl,
            delivery_mode=delivery_mode,
            active_branches=active_branches
        )
        db.session.add(cluster)
        db.session.commit()
        flash('Cluster added successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding cluster: {str(e)}')

    return redirect(url_for('manage_clusters'))

@app.route('/clusters/<int:id>/edit', methods=['GET', 'POST'])
def edit_cluster(id):
    cluster = Cluster.query.get_or_404(id)

    if request.method == 'POST':
        try:
            cluster.no = request.form.get('no')
            cluster.weekly_schedule = request.form.get('weekly_schedule')
            cluster.delivered_by = request.form.get('delivered_by')
            cluster.location = request.form.get('location')
            cluster.category = request.form.get('category')
            cluster.area = request.form.get('area')
            cluster.branch = request.form.get('branch')
            cluster.frequency = request.form.get('frequency')
            cluster.frequency_count = request.form.get('frequency_count')
            cluster.tl = request.form.get('tl')
            cluster.delivery_mode = request.form.get('delivery_mode')
            cluster.active_branches = request.form.get('active_branches')

            db.session.commit()
            flash('Cluster updated successfully!')
            return redirect(url_for('manage_clusters'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating cluster: {str(e)}')

    return render_template('edit_cluster.html', cluster=cluster)

@app.route('/clusters/<int:id>/delete', methods=['POST'])
def delete_cluster(id):
    cluster = Cluster.query.get_or_404(id)

    try:
        db.session.delete(cluster)
        db.session.commit()
        invalidate_reference_cache()  # Invalidate cluster cache
        flash('Cluster deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting cluster: {str(e)}')

    return redirect(url_for('manage_clusters'))

@app.route('/clusters/upload', methods=['GET', 'POST'])
def upload_clusters():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are allowed', 'error')
            return redirect(request.url)

        try:
            # Read file content
            file_content = file.stream.read()

            # Try multiple encodings
            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            stream = None
            decoded = False

            for encoding in encodings:
                try:
                    stream = file_content.decode(encoding).splitlines()
                    decoded = True
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if not decoded:
                flash("File encoding error. Unable to read the CSV file. Please ensure it's saved as UTF-8, Latin-1, or Windows-1252 encoding.", 'error')
                return redirect(request.url)

            csv_reader = csv.DictReader(stream)

            # Expected headers for cluster CSV
            expected_headers = {
                "No.", "Weekly Schedule", "Delivered By", "Location", "Category",
                "Area", "Branch", "Frequency", "Frequency Count", "TL",
                "Delivery Mode", "Active Branches"
            }

            # Check if headers match (allowing extra columns but requiring expected ones)
            csv_headers = set(csv_reader.fieldnames) if csv_reader.fieldnames else set()
            missing = expected_headers - csv_headers

            if missing:
                flash(f"Invalid CSV headers. Missing columns: {', '.join(missing)}", 'error')
                return redirect(request.url)

            # Delete all existing cluster data
            Cluster.query.delete()
            db.session.commit()

            # Upload new data
            records_added = 0
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Helper to convert empty strings to None
                    def clean(val):
                        return val if val and val.strip() != '' else None

                    cluster_entry = Cluster(
                        no=clean(row.get("No.")),
                        weekly_schedule=clean(row.get("Weekly Schedule")),
                        delivered_by=clean(row.get("Delivered By")),
                        location=clean(row.get("Location")),
                        category=clean(row.get("Category")),
                        area=clean(row.get("Area")),
                        branch=clean(row.get("Branch")),
                        frequency=clean(row.get("Frequency")),
                        frequency_count=clean(row.get("Frequency Count")),
                        tl=clean(row.get("TL")),
                        delivery_mode=clean(row.get("Delivery Mode")),
                        active_branches=clean(row.get("Active Branches"))
                    )

                    if cluster_entry.no:  # Only add if 'no' field is present
                        db.session.add(cluster_entry)
                        records_added += 1

                except Exception as e:
                    flash(f"Row {row_num}: Error processing row – {str(e)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)

            db.session.commit()
            invalidate_reference_cache()  # Invalidate cluster cache
            flash(f"Successfully uploaded {records_added} cluster(s)! All previous data was replaced.", 'success')
            return redirect(url_for('manage_clusters'))

        except Exception as e:
            flash(f"Failed to process file: {str(e)}", 'error')
            db.session.rollback()
            return redirect(request.url)

    return render_template('upload_clusters.html')

@app.route('/clusters/download_template')
def download_clusters_template():
    from io import StringIO
    from flask import Response

    # Create an in-memory CSV
    template = StringIO()
    writer = csv.writer(template)

    # Write headers
    writer.writerow([
        "No.", "Weekly Schedule", "Delivered By", "Location", "Category",
        "Area", "Branch", "Frequency", "Frequency Count", "TL",
        "Delivery Mode", "Active Branches"
    ])

    # Write one sample row for guidance
    writer.writerow([
        "CL-001", "Mon, Wed, Fri", "Team A", "North", "Regular",
        "Area 1", "Branch 1", "Weekly", "3", "John Doe",
        "Truck", "Branch 1, Branch 2, Branch 3"
    ])

    template.seek(0)

    # Return as downloadable CSV file
    return Response(
        template.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=clusters_template.csv'}
    )

# User management routes
@app.route('/users')
@login_required
def manage_users():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Show 20 users per page

    # Build query with search filter
    query = User.query
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                User.name.ilike(search_pattern),
                User.email.ilike(search_pattern)
            )
        )

    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('manage_users.html', users=pagination.items, pagination=pagination, search=search)

@app.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    position = request.form.get('position')
    status = request.form.get('status', 'active')
    daily_rate = request.form.get('daily_rate')
    sched_start = request.form.get('sched_start')
    sched_end = request.form.get('sched_end')

    if not name or not email or not password or not position:
        flash('Name, email, password, and position are required', 'error')
        return redirect(url_for('manage_users'))

    try:
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists', 'error')
            return redirect(url_for('manage_users'))

        user = User(
            name=name,
            email=email,
            position=position,
            status=status
        )

        # Set optional payroll fields
        if daily_rate:
            try:
                user.daily_rate = float(daily_rate)
            except ValueError:
                flash('Invalid daily rate format', 'error')
                return redirect(url_for('manage_users'))
        else:
            user.daily_rate = 0.0  # Default to 0.0 if not provided

        if sched_start:
            user.sched_start = sched_start
        else:
            user.sched_start = '08:00'  # Default to 8:00 AM

        if sched_end:
            user.sched_end = sched_end
        else:
            user.sched_end = '18:00'  # Default to 6:00 PM

        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('User added successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding user: {str(e)}', 'error')

    return redirect(url_for('manage_users'))

@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    user = User.query.get_or_404(id)

    if request.method == 'POST':
        try:
            user.name = request.form.get('name')
            user.email = request.form.get('email')
            position = request.form.get('position')
            status = request.form.get('status', 'active')
            password = request.form.get('password')
            daily_rate = request.form.get('daily_rate')
            sched_start = request.form.get('sched_start')
            sched_end = request.form.get('sched_end')

            # Check if email already exists (excluding current user)
            existing_user = User.query.filter(User.email == user.email, User.id != id).first()
            if existing_user:
                flash('Email already exists', 'error')
                return redirect(url_for('manage_users'))

            user.position = position
            user.status = status

            # Update optional payroll fields
            if daily_rate and daily_rate.strip():
                try:
                    user.daily_rate = float(daily_rate)
                except ValueError:
                    flash('Invalid daily rate format', 'error')
                    return redirect(url_for('manage_users'))
            else:
                user.daily_rate = 0.0  # Default to 0.0 if not provided

            if sched_start and sched_start.strip():
                user.sched_start = sched_start
            else:
                user.sched_start = '08:00'  # Default to 08:00 if not provided

            if sched_end and sched_end.strip():
                user.sched_end = sched_end
            else:
                user.sched_end = '18:00'  # Default to 18:00 if not provided

            # Only update password if provided
            if password and password.strip():
                user.set_password(password)

            db.session.commit()
            flash('User updated successfully!')
            return redirect(url_for('manage_users'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')

    return render_template('edit_user.html', user=user)

@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Prevent deleting yourself
    if current_user.id == id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(id)

    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')

    return redirect(url_for('manage_users'))

@app.route('/users/<int:id>/reset_password', methods=['POST'])
@login_required
def reset_user_password(id):
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    user = User.query.get_or_404(id)

    try:
        # Generate password: letter + 6 digits + letter
        first_letter = random.choice(string.ascii_letters)
        six_digits = ''.join(random.choices(string.digits, k=6))
        last_letter = random.choice(string.ascii_letters)
        new_password = f"{first_letter}{six_digits}{last_letter}"
        user.set_password(new_password)
        db.session.commit()
        flash(f'Password for {user.email} has been reset to: {new_password}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}', 'error')

    return redirect(url_for('manage_users'))

@app.route('/users/report/csv')
@login_required
def generate_user_report():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Get all users with position == 'user'
    users = User.query.filter_by(position='user').all()

    # Create CSV data
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Name', 'Email', 'Password'])

    # Generate new random passwords for all users and include in CSV
    try:
        for user in users:
            # Generate password: letter + 6 digits + letter
            first_letter = random.choice(string.ascii_letters)
            six_digits = ''.join(random.choices(string.digits, k=6))
            last_letter = random.choice(string.ascii_letters)
            new_password = f"{first_letter}{six_digits}{last_letter}"
            user.set_password(new_password)
            writer.writerow([user.name, user.email, new_password])

        # Commit the new passwords to database
        db.session.commit()
        flash('All user passwords have been reset. New passwords are included in the CSV report.')
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating report: {str(e)}', 'error')

    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=user_credentials_report.csv'
        }
    )

@app.route('/users/reset_all', methods=['POST'])
@login_required
def reset_all_user_passwords():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Get all users with position == 'user'
    users = User.query.filter_by(position='user').all()

    if not users:
        flash('No users found with position "user"', 'info')
        return redirect(url_for('manage_users'))

    try:
        reset_count = 0
        reset_details = []

        for user in users:
            # Generate password: letter + 6 digits + letter
            first_letter = random.choice(string.ascii_letters)
            six_digits = ''.join(random.choices(string.digits, k=6))
            last_letter = random.choice(string.ascii_letters)
            new_password = f"{first_letter}{six_digits}{last_letter}"
            user.set_password(new_password)
            reset_details.append(f"{user.email}: {new_password}")
            reset_count += 1

        db.session.commit()

        # Show flash message with all new passwords
        flash(f'Successfully reset passwords for {reset_count} user(s):')
        for detail in reset_details:
            flash(detail)
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting passwords: {str(e)}', 'error')

    return redirect(url_for('manage_users'))

# API endpoint to fetch documents with specific status and due date
@app.route('/api/documents', methods=['GET'])
def get_documents():
    status = request.args.get('status')
    due_date = request.args.get('due_date')

    query = Data.query

    if status:
        query = query.filter_by(status=status)

    if due_date:
        try:
            # Parse the date string
            date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
            query = query.filter_by(due_date=date_obj)
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD format.'}), 400

    documents = query.all()
    result = []
    for doc in documents:
        result.append({
            'id': doc.id,
            'document_number': doc.document_number,
            'due_date': doc.due_date.strftime('%Y-%m-%d') if doc.due_date else None,
            'status': doc.status,
            'type': doc.type,
            'branch_name': doc.branch_name,
            'cbm': doc.cbm
        })

    return jsonify(result)

# API endpoint to search scheduled documents and class data
@app.route('/api/search_scheduled', methods=['GET'])
def search_scheduled():
    search_term = request.args.get('search', '').strip()
    search_type = request.args.get('type', 'document')  # 'document' or 'class'

    # Start with all scheduled documents
    query = Data.query.filter(Data.status == 'Scheduled')

    # Apply filters only if search term is provided
    if search_term:
        if search_type == 'document':
            # Search by document number
            query = query.filter(Data.document_number.contains(search_term))
        elif search_type == 'class':
            # Search by class data (branch name)
            query = query.filter(
                db.or_(
                    Data.branch_name.contains(search_term),
                    Data.branch_name_v2.contains(search_term)
                )
            )

    documents = query.all()
    result = []
    for doc in documents:
        result.append({
            'id': doc.id,
            'document_number': doc.document_number,
            'posting_date': doc.posting_date.strftime('%Y-%m-%d') if doc.posting_date else None,
            'item_number': doc.item_number,
            'ordered_qty': doc.ordered_qty,
            'total_cbm': doc.total_cbm,
            'delivered_qty': doc.delivered_qty,
            'branch_name': doc.branch_name or doc.branch_name_v2 or '',
            'status': doc.status,
            'document_status': doc.document_status,
            'due_date': doc.due_date.strftime('%Y-%m-%d') if doc.due_date else None
        })

    return jsonify(result)

@app.route('/schedules')
@login_required
def view_schedule():
    from sqlalchemy import or_

    # Get today's date
    today = datetime.now().date()

    if current_user.position == 'admin':
        # Admins see all schedules (past, today, and future)
        # Use eager loading to prevent N+1 queries
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).joinedload(Trip.vehicle),
            subqueryload(Schedule.trips).subqueryload(Trip.drivers),
            subqueryload(Schedule.trips).subqueryload(Trip.assistants),
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).order_by(Schedule.delivery_schedule.desc()).all()

    else:
        # Regular users only see schedules where they are assigned
        # Get the user's associated manpower entry
        user_manpower = getattr(current_user, 'manpower', None)

        if user_manpower:
            # Today's trips where user is assigned as driver or assistant
            todays_trips = Trip.query.filter(
                db.and_(
                    db.or_(
                        Trip.drivers.any(id=user_manpower.id),
                        Trip.assistants.any(id=user_manpower.id)
                    ),
                    Trip.schedule.has(Schedule.delivery_schedule == today)
                )
            ).all()

            # Incomplete trips from prior days where user is assigned
            prior_incomplete_trips = Trip.query.join(
                Schedule, Trip.schedule_id == Schedule.id
            ).join(
                TripDetail, Trip.id == TripDetail.trip_id
            ).filter(
                db.and_(
                    Schedule.delivery_schedule < today,  # Prior days only
                    TripDetail.departure == None,  # Incomplete trips
                    db.or_(
                        Trip.drivers.any(id=user_manpower.id),
                        Trip.assistants.any(id=user_manpower.id)
                    )
                )
            ).distinct().all()

            # Get all schedule IDs
            all_schedule_ids = list(set([trip.schedule_id for trip in todays_trips] + [trip.schedule_id for trip in prior_incomplete_trips]))
            # Use eager loading to prevent N+1 queries
            schedules = Schedule.query.options(
                subqueryload(Schedule.trips).joinedload(Trip.vehicle),
                subqueryload(Schedule.trips).subqueryload(Trip.drivers),
                subqueryload(Schedule.trips).subqueryload(Trip.assistants),
                subqueryload(Schedule.trips).subqueryload(Trip.details)
            ).filter(Schedule.id.in_(all_schedule_ids)).order_by(Schedule.delivery_schedule.desc()).all()
        else:
            # User has no associated manpower entry - show no schedules
            schedules = []

    # Sort trip details by delivery_order for each trip (NULL values last)
    for schedule in schedules:
        for trip in schedule.trips:
            trip.details = sorted(trip.details, key=lambda d: (d.delivery_order is None, d.delivery_order or 999))

    # Fetch executive vehicles for the refill form
    executive_vehicles = Vehicle.query.filter_by(dept='Executive', status='Active').all()

    # Fetch all vehicles for the edit vehicle modal (filtered in template to show only active Logistics)
    vehicles = get_cached_active_vehicles()

    return render_template('view_schedule.html', schedules=schedules, today=today, executive_vehicles=executive_vehicles, vehicles=vehicles)


@app.route('/schedules/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    if request.method == 'POST':
        try:
            delivery_date = datetime.strptime(request.form['delivery_schedule_from'], '%Y-%m-%d').date()

            # Create Schedule
            schedule = Schedule(delivery_schedule=delivery_date)
            db.session.add(schedule)
            db.session.flush()  # Get schedule.id

            trip_count = int(request.form.get('trip_count', 0))
            for i in range(1, trip_count + 1):
                vehicle_id = request.form.get(f'vehicle_{i}')
                # ✅ NEW CODE (use this)
                driver_ids = request.form.getlist(f'driver_{i}')
                assistant_ids = request.form.getlist(f'assistant_{i}')

                # Validate: at least one driver and a vehicle
                if not vehicle_id or not driver_ids:
                    continue

                # Convert to integers (filter out empty strings)
                driver_ids = [int(d) for d in driver_ids if d.strip()]
                assistant_ids = [int(a) for a in assistant_ids if a.strip()]

                # Create Trip WITHOUT driver_id/assistant_id
                trip = Trip(
                    schedule_id=schedule.id,
                    trip_number=i,
                    vehicle_id=vehicle_id,
                    total_cbm=0.0
                )
                db.session.add(trip)
                db.session.flush()  # Get trip.id

                # ✅ Assign MULTIPLE drivers
                trip.drivers.clear()  # Optional (new trip, so empty anyway)
                for did in driver_ids:
                    driver = db.session.get(Manpower, did)
                    if driver:
                        trip.drivers.append(driver)

                # ✅ Assign MULTIPLE assistants
                trip.assistants.clear()
                for aid in assistant_ids:
                    assistant = db.session.get(Manpower, aid)
                    if assistant:
                        trip.assistants.append(assistant)
                db.session.add(trip)
                db.session.flush()

                # Add all selected drivers and assistants to the trip
                for driver_id in driver_ids:
                    driver = db.session.get(Manpower, driver_id)
                    if driver and driver not in trip.drivers:
                        trip.drivers.append(driver)

                for assistant_id in assistant_ids:
                    assistant = db.session.get(Manpower, assistant_id)
                    if assistant and assistant not in trip.assistants:
                        trip.assistants.append(assistant)

                # Get selected data IDs for this trip
                data_ids_str = request.form.get(f'trip_{i}_data_ids', '')
                # Split the comma-separated string into individual IDs
                data_ids = data_ids_str.split(',') if data_ids_str else []

                # Parse delivery orders from JSON if provided
                import json
                delivery_orders_str = request.form.get(f'trip_{i}_delivery_orders', '{}')
                try:
                    delivery_orders = json.loads(delivery_orders_str) if delivery_orders_str else {}
                except json.JSONDecodeError:
                    delivery_orders = {}

                # Group data by branch_name_v2 to create aggregated TripDetail entries
                branch_groups = {}
                for data_id in data_ids:
                    if not data_id:
                        continue
                    data = db.session.get(Data, data_id)
                    if data:
                        branch_name = data.branch_name_v2 or data.branch_name or 'Unknown'
                        if branch_name not in branch_groups:
                            branch_groups[branch_name] = {
                                'data_ids': [],
                                'document_numbers': [],
                                'total_cbm': 0.0,
                                'total_ordered_qty': 0,
                                'area': data.branch_name or data.branch_name_v2 or '',
                                'original_due_date': data.original_due_date,  # Store original due date
                                'delivery_order': None  # Will be set from first data_id
                            }

                        branch_groups[branch_name]['data_ids'].append(data.id)
                        branch_groups[branch_name]['document_numbers'].append(data.document_number)
                        branch_groups[branch_name]['total_cbm'] += data.cbm * data.ordered_qty or 0.0
                        branch_groups[branch_name]['total_ordered_qty'] += data.ordered_qty or 0

                        # Set delivery_order from first data_id if not already set
                        if branch_groups[branch_name]['delivery_order'] is None and str(data.id) in delivery_orders:
                            branch_groups[branch_name]['delivery_order'] = delivery_orders[str(data.id)]

                        # Mark as Scheduled
                        data.status = "Scheduled"
                        data.delivered_qty = data.ordered_qty or 0.0

                # Create aggregated TripDetail entries grouped by branch
                trip_total_cbm = 0.0
                auto_order = 1
                for branch_name, branch_data in branch_groups.items():
                    # Use provided delivery_order or auto-increment
                    detail_order = branch_data['delivery_order']
                    if detail_order is None:
                        detail_order = auto_order
                        auto_order += 1

                    detail = TripDetail(
                        document_number=branch_data['document_numbers'][0],  # Store first doc number for reference
                        branch_name_v2=branch_name,
                        data_ids=','.join(str(id) for id in branch_data['data_ids']),
                        trip_id=trip.id,
                        area=branch_data['area'],
                        total_cbm=branch_data['total_cbm'],
                        total_ordered_qty=branch_data['total_ordered_qty'],
                        total_delivered_qty=branch_data['total_ordered_qty'],  # Initialize with total_ordered_qty
                        status="Delivered",
                        original_due_date=branch_data['original_due_date'],  # Save original due date
                        delivery_order=detail_order  # Set delivery order
                    )
                    db.session.add(detail)
                    trip_total_cbm += branch_data['total_cbm']

                trip.total_cbm = trip_total_cbm

            # Update schedule with vehicle info and actual total CBM
            # Get the first trip's vehicle information
            if schedule.trips:
                first_trip = schedule.trips[0]
                if first_trip.vehicle:
                    schedule.plate_number = first_trip.vehicle.plate_number
                    schedule.capacity = first_trip.vehicle.capacity

                # Calculate actual total CBM from all trips
                schedule.actual = sum(trip.total_cbm for trip in schedule.trips)

            db.session.commit()
            flash("Schedule created successfully!", "success")
            return redirect(url_for('view_schedule'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
            return redirect(request.url)

    # GET: Load resources for form (use cached data)
    # Filter vehicles to only show active Logistics vehicles
    vehicles = [v for v in get_cached_active_vehicles() if v.dept == 'Logistics']
    drivers = get_cached_drivers()
    assistants = get_cached_assistants()
    return render_template('add_schedule.html',
                         vehicles=vehicles,
                         drivers=drivers,
                         assistants=assistants)


@app.route('/api/not_scheduled')
def api_not_scheduled():
    # Support both old single date parameter and new date range parameters
    due_date_str = request.args.get('due_date')  # Backward compatibility
    due_date_from_str = request.args.get('due_date_from')
    due_date_to_str = request.args.get('due_date_to')

    # Use new parameters if provided, otherwise fall back to old parameter
    if due_date_from_str:
        from_date = datetime.strptime(due_date_from_str, '%Y-%m-%d').date()
        if due_date_to_str:
            # Date range query
            to_date = datetime.strptime(due_date_to_str, '%Y-%m-%d').date()
            subq = Data.query.filter(
                Data.status == 'Not Scheduled',
                Data.due_date >= from_date,
                Data.due_date <= to_date
            ).subquery()
        else:
            # Single date query (using from_date)
            subq = Data.query.filter(
                Data.status == 'Not Scheduled',
                Data.due_date == from_date
            ).subquery()
    elif due_date_str:
        # Backward compatibility with old parameter
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        subq = Data.query.filter(
            Data.status == 'Not Scheduled',
            Data.due_date == due_date
        ).subquery()
    else:
        return jsonify([])

    # Group by document_number and aggregate
    results = db.session.query(
        subq.c.document_number,
        func.sum(subq.c.total_cbm).label('total_cbm'),
        func.sum(subq.c.ordered_qty).label('ordered_qty'),
        func.min(subq.c.branch_name).label('branch_name'),
        func.min(subq.c.branch_name_v2).label('branch_name_v2'),
        func.min(subq.c.due_date).label('due_date'),
        func.min(subq.c.original_due_date).label('original_due_date'),
        func.group_concat(subq.c.id).label('data_ids')  # Collect all IDs for this doc
    ).group_by(subq.c.document_number).all()

    # Get cached cluster dictionary for fast lookup
    cluster_dict = get_cached_cluster_dict()

    documents = []
    for row in results:
        # Determine branch (prefer branch_name, fallback to v2)
        branch = row.branch_name or row.branch_name_v2 or '—'
        # Match cluster.area using branch_name_v2 to match with cluster.branch
        branch_v2 = row.branch_name_v2 or row.branch_name or ''
        area = cluster_dict.get(branch_v2.lower(), '') if branch_v2 else ''

        documents.append({
            'document_number': row.document_number,
            'total_cbm': float(row.total_cbm) if row.total_cbm else 0.0,
            'ordered_qty': int(row.ordered_qty) if row.ordered_qty else 0,
            'branch': branch,
            'area': area,
            'due_date': row.due_date.strftime('%Y-%m-%d') if row.due_date else '',
            'original_due_date': row.original_due_date.strftime('%Y-%m-%d') if row.original_due_date else '',
            'data_ids': row.data_ids.split(',')  # List of all Data.id for this doc
        })

    return jsonify(documents)

@app.route('/api/areas', methods=['GET'])
def get_areas():
    """Get all unique areas from clusters"""
    areas = db.session.query(Cluster.area).filter(Cluster.area.isnot(None)).filter(Cluster.area != '').distinct().order_by(Cluster.area).all()
    return jsonify([area[0] for area in areas])


@app.route('/api/vehicle_schedule_status', methods=['GET'])
def api_vehicle_schedule_status():
    """Check if a vehicle is already scheduled for a given date"""
    vehicle_id = request.args.get('vehicle_id')
    date_str = request.args.get('date')

    if not vehicle_id or not date_str:
        return jsonify({'error': 'vehicle_id and date are required'}), 400

    try:
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404

        delivery_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check if vehicle exists in any trip for this date
        existing_schedules = db.session.query(Schedule, Trip, Vehicle).join(
            Trip, Schedule.id == Trip.schedule_id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).filter(
            Schedule.delivery_schedule == delivery_date,
            Vehicle.plate_number == vehicle.plate_number
        ).all()

        if existing_schedules:
            schedule_info = []
            for schedule, trip, vehicle in existing_schedules:
                schedule_info.append({
                    'schedule_id': schedule.id,
                    'trip_number': trip.trip_number,
                    'plate_number': vehicle.plate_number
                })

            return jsonify({
                'is_scheduled': True,
                'vehicle': vehicle.plate_number,
                'date': date_str,
                'existing_schedules': schedule_info
            })
        else:
            return jsonify({
                'is_scheduled': False,
                'vehicle': vehicle.plate_number,
                'date': date_str
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/available_for_edit')
def api_available_for_edit():
    """Get available shipments for editing a trip (Not Scheduled, not assigned to any trip in the schedule)"""
    delivery_date_str = request.args.get('delivery_date')
    trip_id = request.args.get('trip_id')
    due_date_from_str = request.args.get('due_date_from')
    due_date_to_str = request.args.get('due_date_to')

    if not trip_id:
        return jsonify([])

    trip = db.session.get(Trip, trip_id)
    if not trip:
        return jsonify([])

    schedule_id = trip.schedule_id

    # Get all data_ids already assigned to any trip in this schedule
    existing_trip_details = TripDetail.query.join(Trip).filter(Trip.schedule_id == schedule_id).all()
    assigned_data_ids = set()
    for detail in existing_trip_details:
        if detail.data_ids:
            assigned_data_ids.update(detail.data_ids.split(','))

    # Build the date filter query
    date_filters = [Data.status == 'Not Scheduled']

    # If date range parameters are provided, use them; otherwise use delivery_date for backward compatibility
    if due_date_from_str and due_date_to_str:
        # Use date range
        due_date_from = datetime.strptime(due_date_from_str, '%Y-%m-%d').date()
        due_date_to = datetime.strptime(due_date_to_str, '%Y-%m-%d').date()
        date_filters.append(Data.due_date >= due_date_from)
        date_filters.append(Data.due_date <= due_date_to)
    elif delivery_date_str:
        # Use exact delivery date (backward compatibility)
        delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        date_filters.append(Data.due_date == delivery_date)

    # Get all "Not Scheduled" data with date filter
    subq = Data.query.filter(*date_filters).subquery()

    # Group by document_number and aggregate
    results = db.session.query(
        subq.c.document_number,
        func.sum(subq.c.total_cbm).label('total_cbm'),
        func.sum(subq.c.ordered_qty).label('ordered_qty'),
        func.min(subq.c.branch_name).label('branch_name'),
        func.min(subq.c.branch_name_v2).label('branch_name_v2'),
        func.min(subq.c.due_date).label('due_date'),
        func.min(subq.c.original_due_date).label('original_due_date'),
        func.group_concat(subq.c.id).label('data_ids')
    ).group_by(subq.c.document_number).all()

    # Fetch all clusters for lookup
    clusters = Cluster.query.all()
    cluster_dict = {}
    for cluster in clusters:
        if cluster.branch:
            cluster_dict[cluster.branch.lower()] = cluster.area or ''

    documents = []
    for row in results:
        # Filter out any data_ids that are already assigned
        if row.data_ids:
            data_id_list = row.data_ids.split(',')
            # Check if ANY of the data_ids in this group are already assigned
            if any(data_id in assigned_data_ids for data_id in data_id_list):
                continue

            # Determine branch (prefer branch_name, fallback to v2)
            branch = row.branch_name or row.branch_name_v2 or '—'
            branch_v2 = row.branch_name_v2 or row.branch_name or ''
            area = cluster_dict.get(branch_v2.lower(), '') if branch_v2 else ''

            documents.append({
                'document_number': row.document_number,
                'total_cbm': float(row.total_cbm) if row.total_cbm else 0.0,
                'branch': branch,
                'area': area,
                'due_date': row.due_date.strftime('%Y-%m-%d') if row.due_date else '',
                'original_due_date': row.original_due_date.strftime('%Y-%m-%d') if row.original_due_date else '',
                'data_ids': data_id_list
            })

    return jsonify(documents)


@app.route('/add_shipments_to_trip', methods=['POST'])
@login_required
def add_shipments_to_trip():
    """Add shipments to an existing trip"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = data.get('trip_id')
        schedule_id = data.get('schedule_id')
        data_ids = data.get('data_ids', [])

        if not trip_id or not data_ids:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        # Group data by branch_name_v2 to create aggregated TripDetail entries
        branch_groups = {}
        for data_id in data_ids:
            if not data_id:
                continue
            data_record = db.session.get(Data, data_id)
            if data_record:
                branch_name = data_record.branch_name_v2 or data_record.branch_name or 'Unknown'
                if branch_name not in branch_groups:
                    branch_groups[branch_name] = {
                        'data_ids': [],
                        'document_numbers': [],
                        'total_cbm': 0.0,
                        'total_ordered_qty': 0,
                        'area': data_record.branch_name or data_record.branch_name_v2 or '',
                        'original_due_date': data_record.original_due_date
                    }

                branch_groups[branch_name]['data_ids'].append(data_record.id)
                branch_groups[branch_name]['document_numbers'].append(data_record.document_number)
                branch_groups[branch_name]['total_cbm'] += data_record.cbm * data_record.ordered_qty or 0.0
                branch_groups[branch_name]['total_ordered_qty'] += data_record.ordered_qty or 0

                # Mark as Scheduled
                data_record.status = "Scheduled"
                data_record.delivered_qty = data_record.ordered_qty or 0.0

        # Get the maximum delivery_order for this trip (to append to end)
        max_order_result = db.session.query(db.func.max(TripDetail.delivery_order)).filter_by(trip_id=trip.id).first()
        max_order = max_order_result[0] if max_order_result and max_order_result[0] is not None else 0
        next_order = max_order + 1

        # Create aggregated TripDetail entries grouped by branch
        trip_total_cbm = trip.total_cbm or 0.0
        for branch_name, branch_data in branch_groups.items():
            detail = TripDetail(
                document_number=branch_data['document_numbers'][0],
                branch_name_v2=branch_name,
                data_ids=','.join(str(id) for id in branch_data['data_ids']),
                trip_id=trip.id,
                area=branch_data['area'],
                total_cbm=branch_data['total_cbm'],
                total_ordered_qty=branch_data['total_ordered_qty'],
                total_delivered_qty=branch_data['total_ordered_qty'],
                status="Delivered",
                original_due_date=branch_data['original_due_date'],
                delivery_order=next_order  # Append to end of delivery sequence
            )
            db.session.add(detail)
            trip_total_cbm += branch_data['total_cbm']
            next_order += 1  # Increment for next detail

        trip.total_cbm = trip_total_cbm

        # Update schedule actual total CBM
        schedule = db.session.get(Schedule, schedule_id)
        if schedule:
            schedule.actual = sum(t.total_cbm for t in schedule.trips)

        db.session.commit()
        return jsonify({'success': True, 'message': f'Successfully added {len(data_ids)} shipment(s) to trip'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/get_trip_shipments/<int:trip_id>')
@login_required
def get_trip_shipments(trip_id):
    """Get all shipments currently assigned to a trip"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404

        shipments = []
        for detail in trip.details:
            # Parse data_ids to get individual data records
            if detail.data_ids:
                data_id_list = detail.data_ids.split(',')
                for data_id in data_id_list:
                    data_record = db.session.get(Data, data_id)
                    if data_record:
                        shipments.append({
                            'data_id': data_id,
                            'document_number': data_record.document_number,
                            'branch_name_v2': detail.branch_name_v2,
                            'total_cbm': detail.total_cbm,
                            'due_date': data_record.due_date.strftime('%Y-%m-%d') if data_record.due_date else None,
                            'delivery_order': detail.delivery_order
                        })

        return jsonify({'shipments': shipments})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/remove_shipment_from_trip', methods=['POST'])
@login_required
def remove_shipment_from_trip():
    """Remove a shipment from a trip"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = data.get('trip_id')
        data_id = data.get('data_id')

        if not trip_id or not data_id:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        data_record = db.session.get(Data, data_id)
        if not data_record:
            return jsonify({'success': False, 'message': 'Data record not found'}), 404

        # Find the TripDetail that contains this data_id
        trip_detail = None
        for detail in trip.details:
            if detail.data_ids and data_id in detail.data_ids.split(','):
                trip_detail = detail
                break

        if not trip_detail:
            return jsonify({'success': False, 'message': 'Shipment not found in this trip'}), 404

        # Remove the data_id from the TripDetail
        data_id_list = trip_detail.data_ids.split(',')
        data_id_list.remove(data_id)

        # Calculate the CBM of the removed shipment
        removed_cbm = data_record.cbm * data_record.ordered_qty if data_record.cbm and data_record.ordered_qty else 0.0

        if len(data_id_list) == 0:
            # If this was the only data_id, remove the entire TripDetail
            db.session.delete(trip_detail)
        else:
            # Update the TripDetail with remaining data_ids
            trip_detail.data_ids = ','.join(data_id_list)
            # Recalculate totals
            remaining_data = db.session.query(Data).filter(Data.id.in_(data_id_list)).all()
            trip_detail.total_cbm = sum(d.cbm * d.ordered_qty for d in remaining_data if d.cbm and d.ordered_qty)
            trip_detail.total_ordered_qty = sum(d.ordered_qty for d in remaining_data if d.ordered_qty)
            trip_detail.total_delivered_qty = trip_detail.total_ordered_qty

        # Update trip total CBM
        trip.total_cbm = sum(d.total_cbm for d in trip.details if d.total_cbm)

        # Update schedule actual total CBM
        if trip.schedule:
            trip.schedule.actual = sum(t.total_cbm for t in trip.schedule.trips if t.total_cbm)

        # Mark the data record as Not Scheduled
        data_record.status = "Not Scheduled"
        data_record.delivered_qty = 0

        db.session.commit()
        return jsonify({'success': True, 'message': f'Successfully removed shipment {data_record.document_number} from trip'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/toggle_trip_complete', methods=['POST'])
@login_required
def toggle_trip_complete():
    """Toggle trip completion status"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = data.get('trip_id')

        if not trip_id:
            return jsonify({'success': False, 'message': 'Missing trip_id'}), 400

        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        # Toggle the completed status
        trip.completed = not trip.completed
        db.session.commit()

        status = "completed" if trip.completed else "marked as incomplete"
        return jsonify({'success': True, 'message': f'Trip #{trip.trip_number} {status}', 'completed': trip.completed})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/get_trip_crew/<int:trip_id>')
@login_required
def get_trip_crew(trip_id):
    """Get current crew for a trip and all available drivers/assistants"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    try:
        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404

        # Get current driver and assistant IDs
        current_driver_ids = [d.id for d in trip.drivers]
        current_assistant_ids = [a.id for a in trip.assistants]

        # Get all available drivers and assistants
        all_drivers = Manpower.query.filter_by(role='Driver').order_by(Manpower.name).all()
        all_assistants = Manpower.query.filter_by(role='Assistant').order_by(Manpower.name).all()

        return jsonify({
            'current_drivers': current_driver_ids,
            'current_assistants': current_assistant_ids,
            'all_drivers': [{'id': d.id, 'name': d.name} for d in all_drivers],
            'all_assistants': [{'id': a.id, 'name': a.name} for a in all_assistants]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_trip_details/<int:trip_id>')
@login_required
def get_trip_details(trip_id):
    """Get trip details for reordering delivery stops"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Eager load details to avoid lazy loading issues
        trip = db.session.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404

        # Get all trip details
        details = []
        for detail in trip.details:
            details.append({
                'id': detail.id,
                'branch_name_v2': detail.branch_name_v2,
                'delivery_order': detail.delivery_order,
                'total_cbm': detail.total_cbm,
                'arrive': detail.arrive.strftime('%Y-%m-%dT%H:%M') if detail.arrive else None,
                'departure': detail.departure.strftime('%Y-%m-%dT%H:%M') if detail.departure else None
            })

        print(f"Fetched {len(details)} details for trip {trip_id}")
        return jsonify({'details': details})

    except Exception as e:
        print(f"Error fetching trip details: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/update_delivery_order', methods=['POST'])
@login_required
def update_delivery_order():
    """Update delivery order for trip details"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = int(data.get('trip_id'))  # Ensure trip_id is an integer
        orders = data.get('orders', {})

        if not trip_id:
            return jsonify({'success': False, 'message': 'Trip ID is required'}), 400

        if not orders:
            return jsonify({'success': False, 'message': 'Orders are required'}), 400

        # Verify the trip exists
        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        # Update each trip detail's delivery_order
        updated_count = 0
        for detail_id_str, order in orders.items():
            detail_id = int(detail_id_str)  # Convert detail_id to int
            detail = db.session.get(TripDetail, detail_id)
            if detail and detail.trip_id == trip_id:
                detail.delivery_order = int(order)  # Ensure order is int
                updated_count += 1
            else:
                print(f"Warning: Detail {detail_id} not found or not part of trip {trip_id}")

        db.session.commit()
        print(f"Updated {updated_count} trip details for trip {trip_id}")
        return jsonify({
            'success': True,
            'message': f'Delivery order updated successfully ({updated_count} stops updated)'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error updating delivery order: {str(e)}")
        return jsonify({'success': False, 'message': f'Error updating delivery order: {str(e)}'}), 500


@app.route('/update_trip_crew', methods=['POST'])
@login_required
def update_trip_crew():
    """Update drivers and assistants for a trip"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = data.get('trip_id')
        driver_ids = data.get('driver_ids', [])
        assistant_ids = data.get('assistant_ids', [])

        if not trip_id:
            return jsonify({'success': False, 'message': 'Trip ID is required'}), 400

        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        # Validate that at least one driver is selected
        if not driver_ids:
            return jsonify({'success': False, 'message': 'At least one driver is required'}), 400

        # Clear existing drivers and assistants
        trip.drivers.clear()
        trip.assistants.clear()

        # Add new drivers
        for driver_id in driver_ids:
            driver = db.session.get(Manpower, driver_id)
            if driver:
                trip.drivers.append(driver)

        # Add new assistants
        for assistant_id in assistant_ids:
            assistant = db.session.get(Manpower, assistant_id)
            if assistant:
                trip.assistants.append(assistant)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Crew updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating crew: {str(e)}'}), 500


@app.route('/update_trip_vehicle', methods=['POST'])
@login_required
def update_trip_vehicle():
    """Update vehicle for a trip"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        trip_id = data.get('trip_id')
        vehicle_id = data.get('vehicle_id')

        if not trip_id or not vehicle_id:
            return jsonify({'success': False, 'message': 'Trip ID and Vehicle ID are required'}), 400

        trip = db.session.get(Trip, trip_id)
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            return jsonify({'success': False, 'message': 'Vehicle not found'}), 404

        # Update the vehicle
        trip.vehicle_id = vehicle_id

        # Update schedule vehicle info if this is the first trip
        schedule = trip.schedule
        if schedule and schedule.trips and schedule.trips[0].id == trip.id:
            schedule.plate_number = vehicle.plate_number
            schedule.capacity = vehicle.capacity

        db.session.commit()
        return jsonify({'success': True, 'message': 'Vehicle updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating vehicle: {str(e)}'}), 500


@app.route('/update_trip_times', methods=['POST'])
@login_required
def update_trip_times():
    """Update arrive and departure times for trip details"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    try:
        data = request.get_json()
        updates = data.get('updates', [])

        if not updates:
            return jsonify({'success': False, 'message': 'No updates provided'}), 400

        for update in updates:
            detail_id = update.get('detail_id')
            arrive = update.get('arrive')
            departure = update.get('departure')

            if not detail_id:
                continue

            detail = db.session.get(TripDetail, detail_id)
            if not detail:
                continue

            # Update arrive time
            if arrive:
                try:
                    detail.arrive = datetime.strptime(arrive, '%Y-%m-%dT%H:%M')
                except ValueError:
                    return jsonify({'success': False, 'message': f'Invalid arrive time format for detail {detail_id}'}), 400
            elif arrive is None:
                detail.arrive = None

            # Update departure time
            if departure:
                try:
                    detail.departure = datetime.strptime(departure, '%Y-%m-%dT%H:%M')
                except ValueError:
                    return jsonify({'success': False, 'message': f'Invalid departure time format for detail {detail_id}'}), 400
            elif departure is None:
                detail.departure = None

        db.session.commit()
        return jsonify({'success': True, 'message': 'Times updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating times: {str(e)}'}), 500


# view_schedule.html individual delete button for each trip
@app.route('/cancel_trip_detail', methods=['POST'])
def cancel_trip_detail():
    try:
        data = request.get_json()
        branch_name = data.get('branch_name_v2')
        schedule_id = data.get('schedule_id')
        trip_number = data.get('trip_number')
        cancel_reason = data.get('cancel_reason')
        cancel_department = data.get('cancel_department')

        if not branch_name or not schedule_id or not trip_number:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        # Find the trip detail with the given branch name
        schedule = db.session.get(Schedule, schedule_id)
        if not schedule:
            return jsonify({'success': False, 'message': 'Schedule not found'}), 404

        trip = Trip.query.filter_by(schedule_id=schedule_id, trip_number=trip_number).first()
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        trip_detail = TripDetail.query.filter_by(trip_id=trip.id, branch_name_v2=branch_name).first()
        if not trip_detail:
            return jsonify({'success': False, 'message': 'Trip detail not found'}), 404

        # Update the status in trip_detail
        trip_detail.status = "Cancelled"
        trip_detail.cancel_reason = cancel_reason
        trip_detail.cause_department = cancel_department
        trip_detail.total_delivered_qty = 0

        # Also update the status of all associated Data records
        if trip_detail.data_ids:
            data_ids = trip_detail.data_ids.split(',')
            for data_id in data_ids:
                data_record = db.session.get(Data, data_id)
                if data_record:
                    data_record.status = "Not Scheduled"

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/record_arrival', methods=['POST'])
def record_arrival():
    try:
        data = request.get_json()
        branch_name = data.get('branch_name_v2')
        schedule_id = data.get('schedule_id')
        trip_number = data.get('trip_number')
        reason = data.get('reason', '')

        if not branch_name or not schedule_id or not trip_number:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        # Find the trip detail
        trip = Trip.query.filter_by(schedule_id=schedule_id, trip_number=trip_number).first()
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        trip_detail = TripDetail.query.filter_by(trip_id=trip.id, branch_name_v2=branch_name).first()
        if not trip_detail:
            return jsonify({'success': False, 'message': 'Trip detail not found'}), 404

        # Record arrival time and reason
        trip_detail.arrive = datetime.now()
        trip_detail.reason = reason

        db.session.commit()
        return jsonify({'success': True, 'arrive_time': trip_detail.arrive.strftime('%Y-%m-%d %H:%M:%S')})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/record_departure', methods=['POST'])
def record_departure():
    try:
        data = request.get_json()
        branch_name = data.get('branch_name_v2')
        schedule_id = data.get('schedule_id')
        trip_number = data.get('trip_number')
        reason = data.get('reason', '')

        if not branch_name or not schedule_id or not trip_number:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        # Find the trip detail
        trip = Trip.query.filter_by(schedule_id=schedule_id, trip_number=trip_number).first()
        if not trip:
            return jsonify({'success': False, 'message': 'Trip not found'}), 404

        trip_detail = TripDetail.query.filter_by(trip_id=trip.id, branch_name_v2=branch_name).first()
        if not trip_detail:
            return jsonify({'success': False, 'message': 'Trip detail not found'}), 404

        # Record departure time and reason
        trip_detail.departure = datetime.now()
        if reason:
            trip_detail.reason = reason

        db.session.commit()
        return jsonify({'success': True, 'departure_time': trip_detail.departure.strftime('%Y-%m-%d %H:%M:%S')})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# Odometer reading routes
@app.route('/record_odo', methods=['POST'])
@login_required
def record_odo():
    try:
        data = request.get_json()
        plate_number = data.get('plate_number')
        odometer_reading = data.get('odometer_reading')
        status = data.get('status')  # 'start odo', 'refill odo', or 'end odo'
        litters = data.get('litters')  # Optional: only for refill odo
        amount = data.get('amount')  # Optional: only for refill odo

        if not plate_number or not odometer_reading or not status:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

        # Validate vehicle exists
        vehicle = Vehicle.query.filter_by(plate_number=plate_number).first()
        if not vehicle:
            return jsonify({'success': False, 'message': 'Vehicle not found'}), 404

        # Compute price_per_litter if both litters and amount are provided
        price_per_litter = None
        if litters and amount and float(litters) > 0:
            price_per_litter = float(amount) / float(litters)

        # Create odometer reading
        odo = Odo(
            plate_number=plate_number,
            odometer_reading=float(odometer_reading),
            status=status,
            created_by=current_user.name,
            litters=float(litters) if litters else None,
            amount=float(amount) if amount else None,
            price_per_litter=price_per_litter
        )

        db.session.add(odo)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{status.replace("_", " ").title()} recorded successfully',
            'datetime': odo.datetime.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# Odometer logs view route
@app.route('/odo_logs')
@login_required
def odo_logs():
    # Get filter parameters
    vehicle_filter = request.args.get('vehicle', '')
    status_filter = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Build query
    query = Odo.query

    # Apply filters if provided
    if vehicle_filter:
        query = query.filter(Odo.plate_number == vehicle_filter)
    if status_filter:
        query = query.filter(Odo.status == status_filter)
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Odo.datetime >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            # Include the entire end date
            from datetime import timedelta
            end = end + timedelta(days=1)
            query = query.filter(Odo.datetime < end)
        except ValueError:
            pass

    # Order by datetime descending (newest first) and paginate
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 odometer logs per page

    pagination = query.order_by(Odo.datetime.desc()).paginate(page=page, per_page=per_page, error_out=False)
    odo_logs = pagination.items

    # Get all vehicles for the filter dropdown (use cached data)
    vehicles = get_cached_all_vehicles()

    return render_template('odo_logs.html',
                         odo_logs=odo_logs,
                         vehicles=vehicles,
                         vehicle_filter=vehicle_filter,
                         status_filter=status_filter,
                         start_date=start_date,
                         end_date=end_date,
                         pagination=pagination)


# Reports page route
@app.route('/reports')
@login_required
def reports():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    return render_template('reports.html')

# Dashboard API Routes
@app.route('/api/dashboard/kpis')
@login_required
def dashboard_kpis():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta

    # Check cache unless refresh requested
    bypass_cache = request.args.get('refresh') == 'true'
    cache_key = f"dashboard_kpis_{request.args.get('start_date', 'default')}_{request.args.get('end_date', 'default')}"

    if not bypass_cache:
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

    # Default to last 7 days
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=6)

    # Parse query params if provided
    try:
        if request.args.get('start_date'):
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        if request.args.get('end_date'):
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Validate date range
    if start_date > end_date:
        return jsonify({'error': 'start_date must be before or equal to end_date'}), 400

    max_days = 90
    if (end_date - start_date).days > max_days:
        return jsonify({'error': f'Date range cannot exceed {max_days} days'}), 400

    # Ensure end_date is not in the future
    if end_date > date.today():
        end_date = date.today()

    # Calculate previous period
    period_length = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=period_length - 1)

    # Calculate current period KPIs
    kpis = calculate_period_kpis(start_date, end_date)

    # Calculate previous period KPIs for trends
    previous_kpis = calculate_period_kpis(previous_start_date, previous_end_date)

    # Calculate trends (percentage point difference)
    def calculate_trend(current, previous):
        if previous is None or previous == 0:
            return 0
        return round(current - previous, 1)

    # Calculate daily KPI values for sparklines
    daily_kpis = calculate_daily_kpis(start_date, end_date)

    # Build response with sparkline data
    response = {
        'on_time_delivery_rate': {
            'value': kpis['on_time_rate'],
            'trend': calculate_trend(kpis['on_time_rate'], previous_kpis['on_time_rate']),
            'sparkline': [d['on_time_rate'] for d in daily_kpis]
        },
        'in_full_delivery_rate': {
            'value': kpis['in_full_rate'],
            'trend': calculate_trend(kpis['in_full_rate'], previous_kpis['in_full_rate']),
            'sparkline': [d['in_full_rate'] for d in daily_kpis]
        },
        'difot_score': {
            'value': kpis['difot_score'],
            'trend': calculate_trend(kpis['difot_score'], previous_kpis['difot_score']),
            'sparkline': [d['difot_score'] for d in daily_kpis]
        },
        'truck_utilization': {
            'value': kpis['utilization'],
            'trend': calculate_trend(kpis['utilization'], previous_kpis['utilization']),
            'sparkline': [d['utilization'] for d in daily_kpis]
        },
        'fuel_efficiency': {
            'value': kpis['km_per_liter'],
            'trend': calculate_trend(kpis['km_per_liter'], previous_kpis['km_per_liter']),
            'sparkline': [d['km_per_liter'] for d in daily_kpis]
        },
        'fuel_cost_per_km': {
            'value': kpis['cost_per_km'],
            'trend': calculate_trend(kpis['cost_per_km'], previous_kpis['cost_per_km']),
            'sparkline': [d['cost_per_km'] for d in daily_kpis]
        },
        'data_completeness': {
            'value': kpis['completeness'],
            'trend': calculate_trend(kpis['completeness'], previous_kpis['completeness']),
            'sparkline': [d['completeness'] for d in daily_kpis]
        },
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'previous_start_date': previous_start_date.isoformat(),
            'previous_end_date': previous_end_date.isoformat()
        }
    }

    # Cache response for 5 minutes
    cache.set(cache_key, response, ttl=300)

    return jsonify(response)


def calculate_period_kpis(start_date, end_date):
    """Calculate all KPIs for a given date period"""

    # On-Time Delivery Rate
    on_time_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        TripDetail.original_due_date.isnot(None),
        Schedule.delivery_schedule <= TripDetail.original_due_date
    ).count()

    total_details_with_due = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        TripDetail.original_due_date.isnot(None)
    ).count()

    on_time_rate = (on_time_details / total_details_with_due * 100) if total_details_with_due > 0 else 0

    # In-Full Delivery Rate
    in_full_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        TripDetail.total_delivered_qty >= TripDetail.total_ordered_qty
    ).count()

    total_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).count()

    in_full_rate = (in_full_details / total_details * 100) if total_details > 0 else 0

    # DIFOT Score
    difot_score = (on_time_rate + in_full_rate) / 2

    # Truck Utilization
    from sqlalchemy import func as sql_func
    utilization_records = db.session.query(
        Trip.vehicle_id,
        Vehicle.plate_number,
        Vehicle.capacity,
        sql_func.sum(Trip.total_cbm).label('total_loaded_cbm'),
        sql_func.count(Trip.id).label('trip_count')
    ).join(Vehicle).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        Vehicle.capacity.isnot(None),
        Vehicle.capacity > 0
    ).group_by(Trip.vehicle_id, Vehicle.plate_number, Vehicle.capacity).all()

    total_weighted_util = sum([
        (r.total_loaded_cbm / r.capacity * 100) * r.trip_count
        for r in utilization_records
    ]) if utilization_records else 0

    total_trips = sum([r.trip_count for r in utilization_records]) if utilization_records else 0
    utilization = (total_weighted_util / total_trips) if total_trips > 0 else 0

    # Fuel Efficiency (simplified for now)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    fuel_efficiency_data = []
    for vehicle in db.session.query(Vehicle).filter(Vehicle.status == 'Active').all():
        odo_readings = db.session.query(Odo).filter(
            Odo.plate_number == vehicle.plate_number,
            Odo.datetime.between(start_datetime, end_datetime)
        ).order_by(Odo.datetime).all()

        if not odo_readings:
            continue

        total_km = 0
        total_liters = 0
        total_amount = 0
        last_end_odo = None

        for reading in odo_readings:
            if reading.status == 'start odo':
                last_end_odo = reading.odometer_reading
            elif reading.status == 'end odo' and last_end_odo is not None:
                distance = reading.odometer_reading - last_end_odo
                if distance > 0:
                    total_km += distance
                last_end_odo = None
            elif reading.status == 'refill odo':
                if reading.litters:
                    total_liters += reading.litters
                if reading.amount:
                    total_amount += reading.amount

        if total_km > 0 and total_liters > 0:
            km_per_liter = total_km / total_liters
            cost_per_km = total_amount / total_km if total_km > 0 else 0
            fuel_efficiency_data.append({
                'km_per_liter': km_per_liter,
                'cost_per_km': cost_per_km,
                'distance': total_km
            })

    total_distance = sum([d['distance'] for d in fuel_efficiency_data])
    if total_distance > 0:
        km_per_liter = sum([
            d['km_per_liter'] * d['distance']
            for d in fuel_efficiency_data
        ]) / total_distance
        cost_per_km = sum([
            d['cost_per_km'] * d['distance']
            for d in fuel_efficiency_data
        ]) / total_distance
    else:
        km_per_liter = 0
        cost_per_km = 0

    # Data Completeness (based on trip details with arrive/departure times)
    # Only vehicles that had trips are checked - vehicles without trips don't affect completeness
    from sqlalchemy import or_
    incomplete_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        or_(TripDetail.arrive.is_(None), TripDetail.departure.is_(None))
    ).count()

    complete_details = total_details - incomplete_details
    completeness = (complete_details / total_details * 100) if total_details > 0 else 0

    return {
        'on_time_rate': round(on_time_rate, 1),
        'in_full_rate': round(in_full_rate, 1),
        'difot_score': round(difot_score, 1),
        'utilization': round(utilization, 1),
        'km_per_liter': round(km_per_liter, 1),
        'cost_per_km': round(cost_per_km, 2),
        'completeness': round(completeness, 1)
    }


def calculate_daily_kpis(start_date, end_date):
    """Calculate daily KPI values for sparkline visualization"""
    daily_values = []
    current_date = start_date

    while current_date <= end_date:
        day_kpis = calculate_period_kpis(current_date, current_date)
        daily_values.append({
            'date': current_date.isoformat(),
            'on_time_rate': day_kpis['on_time_rate'],
            'in_full_rate': day_kpis['in_full_rate'],
            'difot_score': day_kpis['difot_score'],
            'utilization': day_kpis['utilization'],
            'km_per_liter': day_kpis['km_per_liter'],
            'cost_per_km': day_kpis['cost_per_km'],
            'completeness': day_kpis['completeness']
        })
        current_date += timedelta(days=1)

    return daily_values


@app.route('/api/dashboard/trends')
@login_required
def dashboard_trends():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta, datetime
    from sqlalchemy import func as sql_func

    # Default to last 7 days
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    # Parse query params if provided
    try:
        if request.args.get('start_date'):
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        if request.args.get('end_date'):
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Validate date range
    if start_date > end_date:
        return jsonify({'error': 'start_date must be before or equal to end_date'}), 400

    max_days = 90
    if (end_date - start_date).days > max_days:
        return jsonify({'error': f'Date range cannot exceed {max_days} days'}), 400

    # Ensure end_date is not in the future
    if end_date > date.today():
        end_date = date.today()

    granularity = request.args.get('granularity', 'daily')

    # Daily delivery counts
    delivery_counts = []
    current_date = start_date
    while current_date <= end_date:
        count = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
            Schedule.delivery_schedule == current_date
        ).count()
        delivery_counts.append({
            'date': current_date.isoformat(),
            'count': count
        })
        current_date += timedelta(days=1)

    # Fuel efficiency trend (calculate daily using ODO pairing logic)
    fuel_efficiency = []
    current_date = start_date
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())

        # Calculate daily fuel efficiency using same logic as KPI calculation
        daily_fe_data = []
        for vehicle in db.session.query(Vehicle).filter(Vehicle.status == 'Active').all():
            odo_readings = db.session.query(Odo).filter(
                Odo.plate_number == vehicle.plate_number,
                Odo.datetime.between(day_start, day_end)
            ).order_by(Odo.datetime).all()

            if not odo_readings:
                continue

            total_km = 0
            total_liters = 0
            total_amount = 0
            last_end_odo = None

            for reading in odo_readings:
                if reading.status == 'start odo':
                    last_end_odo = reading.odometer_reading
                elif reading.status == 'end odo' and last_end_odo is not None:
                    distance = reading.odometer_reading - last_end_odo
                    if distance > 0:
                        total_km += distance
                    last_end_odo = None
                elif reading.status == 'refill odo':
                    if reading.litters:
                        total_liters += reading.litters
                    if reading.amount:
                        total_amount += reading.amount

            if total_km > 0 and total_liters > 0:
                daily_fe_data.append({
                    'km_per_liter': total_km / total_liters,
                    'cost_per_km': total_amount / total_km if total_km > 0 else 0,
                    'distance': total_km
                })

        # Calculate daily average
        total_distance = sum([d['distance'] for d in daily_fe_data])
        if total_distance > 0:
            daily_km_per_liter = sum([
                d['km_per_liter'] * d['distance']
                for d in daily_fe_data
            ]) / total_distance
            daily_cost_per_km = sum([
                d['cost_per_km'] * d['distance']
                for d in daily_fe_data
            ]) / total_distance
        else:
            daily_km_per_liter = 0
            daily_cost_per_km = 0

        fuel_efficiency.append({
            'date': current_date.isoformat(),
            'km_per_liter': round(daily_km_per_liter, 1),
            'cost_per_km': round(daily_cost_per_km, 2)
        })

        current_date += timedelta(days=1)

    # Truck utilization trend
    truck_utilization = []
    current_date = start_date
    while current_date <= end_date:
        # Get total loaded CBM from all trips on this date
        total_loaded = db.session.query(sql_func.sum(Trip.total_cbm)).join(Schedule).filter(
            Schedule.delivery_schedule == current_date
        ).scalar() or 0

        # Get distinct vehicles used on this date and sum their capacity once each
        total_capacity = db.session.query(
            sql_func.sum(Vehicle.capacity)
        ).join(Trip).join(Schedule).filter(
            Schedule.delivery_schedule == current_date,
            Vehicle.capacity.isnot(None),
            Vehicle.capacity > 0
        ).distinct().scalar() or 0

        if total_capacity > 0:
            util_percent = (total_loaded / total_capacity * 100)
        else:
            util_percent = 0

        truck_utilization.append({
            'date': current_date.isoformat(),
            'utilization_percent': round(util_percent, 1)
        })
        current_date += timedelta(days=1)

    return jsonify({
        'daily_deliveries': delivery_counts,
        'fuel_efficiency': fuel_efficiency,
        'truck_utilization': truck_utilization
    })


@app.route('/api/dashboard/comparisons')
@login_required
def dashboard_comparisons():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta, datetime
    from sqlalchemy import func as sql_func

    # Default to last 7 days
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    # Parse query params if provided
    try:
        if request.args.get('start_date'):
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        if request.args.get('end_date'):
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Validate date range
    if start_date > end_date:
        return jsonify({'error': 'start_date must be before or equal to end_date'}), 400

    max_days = 90
    if (end_date - start_date).days > max_days:
        return jsonify({'error': f'Date range cannot exceed {max_days} days'}), 400

    # Ensure end_date is not in the future
    if end_date > date.today():
        end_date = date.today()

    # Vehicle utilization ranking
    vehicle_util = db.session.query(
        Vehicle.plate_number,
        sql_func.sum(Trip.total_cbm).label('total_cbm'),
        Vehicle.capacity,
        sql_func.count(Trip.id).label('trip_count')
    ).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        Vehicle.capacity.isnot(None),
        Vehicle.capacity > 0
    ).group_by(Vehicle.plate_number, Vehicle.capacity).all()

    vehicle_utilization_list = []
    for i, v in enumerate(sorted(vehicle_util, key=lambda x: (x.total_cbm / x.capacity * 100) if x.capacity else 0, reverse=True)):
        utilization = (v.total_cbm / v.capacity * 100) if v.capacity else 0
        vehicle_utilization_list.append({
            'plate_number': v.plate_number,
            'utilization': round(utilization, 1),
            'rank': i + 1,
            'trip_count': v.trip_count
        })

    # Branch frequency ranking
    from sqlalchemy import desc

    branch_counts = db.session.query(
        TripDetail.branch_name_v2,
        sql_func.count(TripDetail.id).label('delivery_count')
    ).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).group_by(TripDetail.branch_name_v2).order_by(
        desc('delivery_count')
    ).limit(10).all()

    branch_frequency = []
    others_count = 0
    for i, b in enumerate(branch_counts):
        branch_frequency.append({
            'branch': b.branch_name_v2,
            'delivery_count': b.delivery_count,
            'rank': i + 1
        })

    # Count "Others"
    total_top_10 = sum([b.delivery_count for b in branch_counts])
    total_all = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).count()
    others_count = total_all - total_top_10

    if others_count > 0:
        branch_frequency.append({
            'branch': 'Others',
            'delivery_count': others_count,
            'rank': len(branch_frequency) + 1
        })

    # Driver/assistant performance
    drivers = db.session.query(
        Manpower.name,
        sql_func.count(Trip.id).label('trips')
    ).join(trip_driver, Manpower.id == trip_driver.c.manpower_id).join(
        Trip, Trip.id == trip_driver.c.trip_id
    ).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).group_by(Manpower.name).all()

    assistants = db.session.query(
        Manpower.name,
        sql_func.count(Trip.id).label('trips')
    ).join(trip_assistant, Manpower.id == trip_assistant.c.manpower_id).join(
        Trip, Trip.id == trip_assistant.c.trip_id
    ).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).group_by(Manpower.name).all()

    driver_performance = []
    all_performance = []

    for d in drivers:
        all_performance.append({'name': d.name, 'trips': d.trips, 'role': 'driver'})

    for a in assistants:
        all_performance.append({'name': a.name, 'trips': a.trips, 'role': 'assistant'})

    all_performance_sorted = sorted(all_performance, key=lambda x: x['trips'], reverse=True)
    for i, p in enumerate(all_performance_sorted):
        driver_performance.append({
            'name': p['name'],
            'trips': p['trips'],
            'role': p['role'],
            'rank': i + 1
        })

    return jsonify({
        'vehicle_utilization': vehicle_utilization_list,
        'branch_frequency': branch_frequency,
        'driver_performance': driver_performance
    })

# Time Log Routes
@app.route('/time_logs')
@login_required
def time_logs():
    """View time logs - admins see all, regular users see only theirs"""
    # Get date filters from query parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Build base query
    if current_user.position == 'admin':
        # Admins see all time logs
        query = TimeLog.query
        active_query = TimeLog.query
    else:
        # Regular users see only their own time logs
        query = TimeLog.query.filter_by(user_id=current_user.id)
        active_query = TimeLog.query.filter_by(user_id=current_user.id)

    # Apply date filters if provided
    if start_date_str:
        try:
            from datetime import datetime, timedelta
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            # Filter time_in >= start_date at 00:00:00
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(TimeLog.time_in >= start_datetime)
            if current_user.position == 'admin':
                active_query = active_query.filter(TimeLog.time_in >= start_datetime)
        except ValueError:
            pass

    if end_date_str:
        try:
            from datetime import datetime, timedelta
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            # Filter time_in < end_date + 1 day (at 23:59:59)
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(TimeLog.time_in <= end_datetime)
            if current_user.position == 'admin':
                active_query = active_query.filter(TimeLog.time_in <= end_datetime)
        except ValueError:
            pass

    # Order by time_in descending
    time_logs = query.order_by(TimeLog.time_in.desc()).all()

    # Get active time logs (those without time_out)
    if current_user.position == 'admin':
        active_time_logs = active_query.filter_by(time_out=None).order_by(TimeLog.time_in.desc()).all()
    else:
        active_time_logs = active_query.filter_by(time_out=None).order_by(TimeLog.time_in.desc()).all()

    return render_template('time_logs.html', time_logs=time_logs, active_time_logs=active_time_logs)

@app.route('/time_in', methods=['POST'])
@login_required
def time_in():
    """Record time in for the current user"""
    try:
        time_in_str = request.form.get('time_in_datetime')

        if not time_in_str:
            flash('Time in is required', 'error')
            return redirect(url_for('time_logs'))

        # Parse the datetime string from datetime-local input
        time_in = datetime.strptime(time_in_str, '%Y-%m-%dT%H:%M')

        # Create new time log entry
        time_log = TimeLog(
            user_id=current_user.id,
            time_in=time_in,
            daily_rate=current_user.daily_rate,
            sched_start=current_user.sched_start,
            sched_end=current_user.sched_end
        )

        db.session.add(time_log)
        db.session.commit()

        flash(f'Successfully timed in at {time_in.strftime("%I:%M %p")}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording time in: {str(e)}', 'error')

    return redirect(url_for('time_logs'))

@app.route('/time_out', methods=['POST'])
@login_required
def time_out():
    """Record time out and calculate hours and pay"""
    try:
        time_out_str = request.form.get('time_out_datetime')
        time_log_id = request.form.get('time_log_id')

        if not time_out_str or not time_log_id:
            flash('Time out and time log selection are required', 'error')
            return redirect(url_for('time_logs'))

        # Parse the datetime string
        time_out = datetime.strptime(time_out_str, '%Y-%m-%dT%H:%M')

        # Get the time log entry (admins can time out any log, regular users only their own)
        if current_user.position == 'admin':
            time_log = TimeLog.query.get_or_404(time_log_id)
        else:
            time_log = TimeLog.query.filter_by(id=time_log_id, user_id=current_user.id).first_or_404()

        # Update time out
        time_log.time_out = time_out

        # Calculate overtime and pay if daily_rate is set
        if time_log.daily_rate and time_log.sched_start and time_log.sched_end:
            try:
                # Parse schedule times
                sched_start_dt = datetime.strptime(time_log.sched_start, '%H:%M')
                sched_end_dt = datetime.strptime(time_log.sched_end, '%H:%M')

                # Create datetime objects for schedule on the same day as time_in
                sched_start_actual = time_log.time_in.replace(
                    hour=sched_start_dt.hour,
                    minute=sched_start_dt.minute,
                    second=0,
                    microsecond=0
                )
                sched_end_actual = time_log.time_in.replace(
                    hour=sched_end_dt.hour,
                    minute=sched_end_dt.minute,
                    second=0,
                    microsecond=0
                )

                # Handle the case where time_in is before sched_start
                # hrs_rendered starts counting from sched_start, not actual time_in
                if time_log.time_in < sched_start_actual:
                    effective_start = sched_start_actual
                else:
                    effective_start = time_log.time_in

                # Calculate total hrs_rendered from effective_start to time_out (for display)
                time_diff = time_out - effective_start
                total_hrs_rendered = time_diff.total_seconds() / 3600  # Convert to hours

                # Deduct 1 hour for lunch break (12:00 PM - 1:00 PM) if work period crosses this time
                lunch_start = effective_start.replace(hour=12, minute=0, second=0, microsecond=0)
                lunch_end = effective_start.replace(hour=13, minute=0, second=0, microsecond=0)

                # Check if the work period crosses lunch time
                crosses_lunch = (effective_start < lunch_end and time_out > lunch_start)

                if crosses_lunch:
                    # Deduct 1 hour for lunch break from total hours
                    time_log.hrs_rendered = round(max(0, total_hrs_rendered - 1.0), 2)
                else:
                    time_log.hrs_rendered = round(total_hrs_rendered, 2)

                # Calculate regular pay: use sched_end as cutoff if time_out > sched_end
                if time_out > sched_end_actual:
                    # Use sched_end as the cutoff for regular pay calculation
                    regular_pay_end_time = sched_end_actual
                else:
                    # Use actual time_out for regular pay calculation
                    regular_pay_end_time = time_out

                # Calculate regular hours (for pay) from effective_start to regular_pay_end_time
                regular_time_diff = regular_pay_end_time - effective_start
                regular_hrs_for_pay = regular_time_diff.total_seconds() / 3600

                # Apply lunch deduction to regular hours if applicable
                if crosses_lunch:
                    regular_hrs_for_pay = max(0, regular_hrs_for_pay - 1.0)

                # Calculate scheduled hours (from sched_start to sched_end)
                scheduled_hours = (sched_end_actual - sched_start_actual).total_seconds() / 3600

                # Calculate overtime: only count hours >= 1 hour after sched_end
                # If time_out is more than 1 hour after sched_end, count the excess as OT
                # Note: Lunch deduction does NOT apply to overtime hours
                time_beyond_sched = (time_out - sched_end_actual).total_seconds() / 3600

                if time_beyond_sched >= 1.0:
                    # Overtime is the time beyond 1 hour after sched_end
                    overtime = time_beyond_sched
                    time_log.over_time = round(overtime, 2)
                else:
                    time_log.over_time = 0.0

                # Calculate regular pay
                hourly_rate = time_log.daily_rate / 8  # Assuming 8-hour workday for daily rate
                time_log.pay = round(hourly_rate * regular_hrs_for_pay, 2)

                # Calculate overtime pay (1.25x hourly rate)
                if time_log.over_time > 0:
                    ot_hourly_rate = hourly_rate * 1.25
                    time_log.ot_pay = round(ot_hourly_rate * time_log.over_time, 2)
                else:
                    time_log.ot_pay = 0.0

            except Exception as e:
                # If schedule calculation fails, still save the time log
                time_diff = time_out - time_log.time_in
                time_log.hrs_rendered = round(time_diff.total_seconds() / 3600, 2)
                time_log.over_time = 0.0
                time_log.pay = None
                time_log.ot_pay = 0.0
        else:
            # No daily rate set, just calculate simple hrs_rendered
            time_diff = time_out - time_log.time_in
            time_log.hrs_rendered = round(time_diff.total_seconds() / 3600, 2)
            time_log.over_time = 0.0
            time_log.pay = None
            time_log.ot_pay = 0.0

        db.session.commit()

        # Customize success message
        if current_user.position == 'admin' and time_log.user_id != current_user.id:
            flash(f'Successfully timed out {time_log.user.name} at {time_out.strftime("%I:%M %p")}! Hours rendered: {time_log.hrs_rendered}', 'success')
        else:
            flash(f'Successfully timed out at {time_out.strftime("%I:%M %p")}! Hours rendered: {time_log.hrs_rendered}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording time out: {str(e)}', 'error')

    return redirect(url_for('time_logs'))

@app.route('/time_logs/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_time_log(id):
    """Edit time log details and recalculate hours/pay"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('time_logs'))

    time_log = TimeLog.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Get form data
            time_in_str = request.form.get('time_in')
            time_out_str = request.form.get('time_out')
            daily_rate_str = request.form.get('daily_rate')
            sched_start = request.form.get('sched_start')
            sched_end = request.form.get('sched_end')

            # Update time_in
            if time_in_str:
                time_log.time_in = datetime.strptime(time_in_str, '%Y-%m-%dT%H:%M')

            # Update time_out (can be empty/null)
            if time_out_str and time_out_str.strip():
                time_log.time_out = datetime.strptime(time_out_str, '%Y-%m-%dT%H:%M')
            else:
                time_log.time_out = None

            # Update daily_rate
            if daily_rate_str and daily_rate_str.strip():
                time_log.daily_rate = float(daily_rate_str)
            else:
                time_log.daily_rate = None

            # Update schedule
            if sched_start and sched_start.strip():
                time_log.sched_start = sched_start
            else:
                time_log.sched_start = None

            if sched_end and sched_end.strip():
                time_log.sched_end = sched_end
            else:
                time_log.sched_end = None

            # Recalculate hours and pay if time_out is set
            if time_log.time_out:
                if time_log.daily_rate and time_log.sched_start and time_log.sched_end:
                    try:
                        # Parse schedule times
                        sched_start_dt = datetime.strptime(time_log.sched_start, '%H:%M')
                        sched_end_dt = datetime.strptime(time_log.sched_end, '%H:%M')

                        # Create datetime objects for schedule on the same day as time_in
                        sched_start_actual = time_log.time_in.replace(
                            hour=sched_start_dt.hour,
                            minute=sched_start_dt.minute,
                            second=0,
                            microsecond=0
                        )
                        sched_end_actual = time_log.time_in.replace(
                            hour=sched_end_dt.hour,
                            minute=sched_end_dt.minute,
                            second=0,
                            microsecond=0
                        )

                        # Handle the case where time_in is before sched_start
                        if time_log.time_in < sched_start_actual:
                            effective_start = sched_start_actual
                        else:
                            effective_start = time_log.time_in

                        # Calculate total hrs_rendered from effective_start to time_out (for display)
                        time_diff = time_log.time_out - effective_start
                        total_hrs_rendered = time_diff.total_seconds() / 3600

                        # Deduct 1 hour for lunch break (12:00 PM - 1:00 PM) if work period crosses this time
                        lunch_start = effective_start.replace(hour=12, minute=0, second=0, microsecond=0)
                        lunch_end = effective_start.replace(hour=13, minute=0, second=0, microsecond=0)

                        # Check if the work period crosses lunch time
                        crosses_lunch = (effective_start < lunch_end and time_log.time_out > lunch_start)

                        if crosses_lunch:
                            # Deduct 1 hour for lunch break from total hours
                            time_log.hrs_rendered = round(max(0, total_hrs_rendered - 1.0), 2)
                        else:
                            time_log.hrs_rendered = round(total_hrs_rendered, 2)

                        # Calculate regular pay: use sched_end as cutoff if time_out > sched_end
                        if time_log.time_out > sched_end_actual:
                            # Use sched_end as the cutoff for regular pay calculation
                            regular_pay_end_time = sched_end_actual
                        else:
                            # Use actual time_out for regular pay calculation
                            regular_pay_end_time = time_log.time_out

                        # Calculate regular hours (for pay) from effective_start to regular_pay_end_time
                        regular_time_diff = regular_pay_end_time - effective_start
                        regular_hrs_for_pay = regular_time_diff.total_seconds() / 3600

                        # Apply lunch deduction to regular hours if applicable
                        if crosses_lunch:
                            regular_hrs_for_pay = max(0, regular_hrs_for_pay - 1.0)

                        # Calculate scheduled hours (from sched_start to sched_end)
                        scheduled_hours = (sched_end_actual - sched_start_actual).total_seconds() / 3600

                        # Calculate overtime: only count hours >= 1 hour after sched_end
                        # Note: Lunch deduction does NOT apply to overtime hours
                        time_beyond_sched = (time_log.time_out - sched_end_actual).total_seconds() / 3600

                        if time_beyond_sched >= 1.0:
                            overtime = time_beyond_sched
                            time_log.over_time = round(overtime, 2)
                        else:
                            time_log.over_time = 0.0

                        # Calculate regular pay
                        hourly_rate = time_log.daily_rate / 8
                        time_log.pay = round(hourly_rate * regular_hrs_for_pay, 2)

                        # Calculate overtime pay (1.25x hourly rate)
                        if time_log.over_time > 0:
                            ot_hourly_rate = hourly_rate * 1.25
                            time_log.ot_pay = round(ot_hourly_rate * time_log.over_time, 2)
                        else:
                            time_log.ot_pay = 0.0

                    except Exception as e:
                        # If schedule calculation fails, calculate simple hrs_rendered
                        time_diff = time_log.time_out - time_log.time_in
                        time_log.hrs_rendered = round(time_diff.total_seconds() / 3600, 2)
                        time_log.over_time = 0.0
                        time_log.pay = None
                        time_log.ot_pay = 0.0
                else:
                    # No daily rate or schedule set
                    time_diff = time_log.time_out - time_log.time_in
                    time_log.hrs_rendered = round(time_diff.total_seconds() / 3600, 2)
                    time_log.over_time = 0.0
                    time_log.pay = None
                    time_log.ot_pay = 0.0
            else:
                # No time_out yet, reset calculations
                time_log.hrs_rendered = None
                time_log.over_time = 0.0
                time_log.pay = None
                time_log.ot_pay = 0.0

            db.session.commit()
            flash('Time log updated successfully and recalculated!', 'success')
            return redirect(url_for('time_logs'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating time log: {str(e)}', 'error')

    return render_template('edit_time_log.html', time_log=time_log)

# Scheduled Trips Report Route
@app.route('/scheduled_trips_report')
@login_required
def scheduled_trips_report():
    """Get scheduled trips with trip details and assigned drivers/assistants"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        from datetime import timedelta
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)

        # Query schedules within date range with eager loading to prevent N+1 queries
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).joinedload(Trip.vehicle),
            subqueryload(Schedule.trips).subqueryload(Trip.drivers),
            subqueryload(Schedule.trips).subqueryload(Trip.assistants),
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).order_by(Schedule.delivery_schedule).all()

        result = []
        for schedule in schedules:
            for trip in schedule.trips:
                # Sort trip details by delivery_order (NULL values last)
                sorted_details = sorted(trip.details, key=lambda d: (d.delivery_order is None, d.delivery_order or 999))
                for detail in sorted_details:
                    # Get all drivers for this trip
                    drivers = ', '.join([driver.name for driver in trip.drivers]) if trip.drivers else 'N/A'

                    # Get all assistants for this trip
                    assistants = ', '.join([assistant.name for assistant in trip.assistants]) if trip.assistants else 'N/A'

                    result.append({
                        'delivery_schedule': schedule.delivery_schedule.strftime('%Y-%m-%d'),
                        'trip_number': trip.trip_number,
                        'plate_number': trip.vehicle.plate_number if trip.vehicle else 'N/A',
                        'drivers': drivers,
                        'assistants': assistants,
                        'delivery_order': detail.delivery_order,
                        'branch_name_v2': detail.branch_name_v2,
                        'total_ordered_qty': detail.total_ordered_qty or 0,
                        'total_delivered_qty': detail.total_delivered_qty or 0,
                        'status': detail.status or 'Delivered'
                    })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500


@app.route('/export_scheduled_trips_report')
@login_required
def export_scheduled_trips_report():
    """Export scheduled trips report to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        from datetime import timedelta
        import io
        import csv

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)

        # Query schedules within date range with eager loading to prevent N+1 queries
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).joinedload(Trip.vehicle),
            subqueryload(Schedule.trips).subqueryload(Trip.drivers),
            subqueryload(Schedule.trips).subqueryload(Trip.assistants),
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).order_by(Schedule.delivery_schedule).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'Date', 'Trip #', 'Vehicle', 'Driver(s)', 'Assistant(s)',
            'Delivery Order', 'Branch', 'Ordered Qty', 'Delivered Qty', 'Status'
        ])

        # Write data rows
        for schedule in schedules:
            for trip in schedule.trips:
                # Sort trip details by delivery_order (NULL values last)
                sorted_details = sorted(trip.details, key=lambda d: (d.delivery_order is None, d.delivery_order or 999))
                for detail in sorted_details:
                    # Get all drivers for this trip
                    drivers = ', '.join([driver.name for driver in trip.drivers]) if trip.drivers else 'N/A'

                    # Get all assistants for this trip
                    assistants = ', '.join([assistant.name for assistant in trip.assistants]) if trip.assistants else 'N/A'

                    # Get ordinal suffix for delivery order
                    def get_ordinal(n):
                        if not n: return '—'
                        s = ["th", "st", "nd", "rd"]
                        v = n % 100
                        return f"{n}{(s[(v - 20) % 10] or s[v] or s[0])}"

                    writer.writerow([
                        schedule.delivery_schedule.strftime('%Y-%m-%d'),
                        trip.trip_number,
                        trip.vehicle.plate_number if trip.vehicle else 'N/A',
                        drivers,
                        assistants,
                        get_ordinal(detail.delivery_order),
                        detail.branch_name_v2,
                        detail.total_ordered_qty or 0,
                        detail.total_delivered_qty or 0,
                        detail.status or 'Delivered'
                    ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"scheduled_trips_report_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting report: {str(e)}", 500

# Report generation routes
@app.route('/generate_report')
def generate_report():
    report_type = request.args.get('report_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    try:
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        if report_type == 'scheduled_trips':
            return generate_scheduled_trips_report(start, end)
        elif report_type == 'cancelled_trips':
            return generate_cancelled_trips_report(start, end)
        elif report_type == 'vehicle_utilization':
            return generate_vehicle_utilization_report(start, end)
        elif report_type == 'driver_performance':
            return generate_driver_performance_report(start, end)
        else:
            return jsonify({'success': False, 'message': 'Invalid report type'})
    except ValueError as e:
        return jsonify({'success': False, 'message': f'Invalid date format: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error generating report: {str(e)}'})

def generate_scheduled_trips_report(start_date, end_date):
    # Query all scheduled trips within the date range with eager loading
    schedules = Schedule.query.options(
        subqueryload(Schedule.trips).joinedload(Trip.vehicle),
        subqueryload(Schedule.trips).subqueryload(Trip.drivers),
        subqueryload(Schedule.trips).subqueryload(Trip.assistants),
        subqueryload(Schedule.trips).subqueryload(Trip.details)
    ).filter(
        Schedule.delivery_schedule >= start_date,
        Schedule.delivery_schedule <= end_date
    ).all()

    headers = [
        'Schedule Date', 'Trip Number', 'Vehicle', 'Driver', 'Assistant', 
        'Document Number', 'Area', 'Total CBM', 'Total Ordered Qty', 'Status'
    ]

    rows = []
    for schedule in schedules:
        for trip in schedule.trips:
            for detail in trip.details:
                driver_name = ', '.join([d.name for d in trip.drivers]) if trip.drivers else 'N/A'
                assistant_name = ', '.join([a.name for a in trip.assistants]) if trip.assistants else 'N/A'
                vehicle_plate = trip.vehicle.plate_number if trip.vehicle else 'N/A'

                rows.append([
                    schedule.delivery_schedule.strftime('%Y-%m-%d'),
                    trip.trip_number,
                    vehicle_plate,
                    driver_name,
                    assistant_name,
                    detail.document_number,
                    detail.area or 'N/A',
                    f"{detail.total_cbm:.2f}",
                    detail.total_ordered_qty,
                    detail.status
                ])

    return jsonify({
        'success': True,
        'headers': headers,
        'rows': rows
    })

def generate_cancelled_trips_report(start_date, end_date):
    # Query all cancelled trip details within the date range
    cancelled_details = db.session.query(TripDetail, Trip, Schedule).join(
        Trip, TripDetail.trip_id == Trip.id
    ).join(
        Schedule, Trip.schedule_id == Schedule.id
    ).filter(
        Schedule.delivery_schedule >= start_date,
        Schedule.delivery_schedule <= end_date,
        TripDetail.status == 'Cancelled'
    ).all()

    headers = [
        'Schedule Date', 'Trip Number', 'Vehicle', 'Driver', 
        'Document Number', 'Area', 'Total CBM', 'Cancel Reason', 'Cause Department'
    ]

    rows = []
    for detail, trip, schedule in cancelled_details:
        driver_name = trip.driver.name if trip.driver else 'N/A'
        vehicle_plate = trip.vehicle.plate_number if trip.vehicle else 'N/A'

        rows.append([
            schedule.delivery_schedule.strftime('%Y-%m-%d'),
            trip.trip_number,
            vehicle_plate,
            driver_name,
            detail.document_number,
            detail.area or 'N/A',
            f"{detail.total_cbm:.2f}",
            detail.cancel_reason or 'N/A',
            detail.cause_department or 'N/A'
        ])

    return jsonify({
        'success': True,
        'headers': headers,
        'rows': rows
    })

def generate_vehicle_utilization_report(start_date, end_date):
    # Query all trips within the date range
    trips = db.session.query(Trip, Schedule).join(
        Schedule, Trip.schedule_id == Schedule.id
    ).filter(
        Schedule.delivery_schedule >= start_date,
        Schedule.delivery_schedule <= end_date
    ).all()

    # Group by vehicle
    vehicle_stats = {}
    for trip, schedule in trips:
        vehicle_id = trip.vehicle_id
        vehicle_plate = trip.vehicle.plate_number

        if vehicle_id not in vehicle_stats:
            vehicle_stats[vehicle_id] = {
                'plate_number': vehicle_plate,
                'total_trips': 0,
                'total_cbm': 0.0,
                'dates_used': set()
            }

        vehicle_stats[vehicle_id]['total_trips'] += 1
        vehicle_stats[vehicle_id]['total_cbm'] += trip.total_cbm
        vehicle_stats[vehicle_id]['dates_used'].add(schedule.delivery_schedule)

    headers = [
        'Vehicle Plate Number', 'Total Trips', 'Total CBM', 'Days Used', 'Average CBM per Trip'
    ]

    rows = []
    for vehicle_id, stats in vehicle_stats.items():
        days_used = len(stats['dates_used'])
        avg_cbm = stats['total_cbm'] / stats['total_trips'] if stats['total_trips'] > 0 else 0

        rows.append([
            stats['plate_number'],
            stats['total_trips'],
            f"{stats['total_cbm']:.2f}",
            days_used,
            f"{avg_cbm:.2f}"
        ])

    return jsonify({
        'success': True,
        'headers': headers,
        'rows': rows
    })

def generate_driver_performance_report(start_date, end_date):
    # Query all trips within the date range
    trips = db.session.query(Trip, Schedule).join(
        Schedule, Trip.schedule_id == Schedule.id
    ).filter(
        Schedule.delivery_schedule >= start_date,
        Schedule.delivery_schedule <= end_date
    ).all()

    # Group by driver
    driver_stats = {}
    for trip, schedule in trips:
        driver_id = trip.driver_id
        driver_name = trip.driver.name

        if driver_id not in driver_stats:
            driver_stats[driver_id] = {
                'name': driver_name,
                'total_trips': 0,
                'total_cbm': 0.0,
                'dates_worked': set()
            }

        driver_stats[driver_id]['total_trips'] += 1
        driver_stats[driver_id]['total_cbm'] += trip.total_cbm
        driver_stats[driver_id]['dates_worked'].add(schedule.delivery_schedule)

    headers = [
        'Driver Name', 'Total Trips', 'Total CBM', 'Days Worked', 'Average CBM per Trip'
    ]

    rows = []
    for driver_id, stats in driver_stats.items():
        days_worked = len(stats['dates_worked'])
        avg_cbm = stats['total_cbm'] / stats['total_trips'] if stats['total_trips'] > 0 else 0

        rows.append([
            stats['name'],
            stats['total_trips'],
            f"{stats['total_cbm']:.2f}",
            days_worked,
            f"{avg_cbm:.2f}"
        ])

    return jsonify({
        'success': True,
        'headers': headers,
        'rows': rows
    })

@app.route('/export_report')
def export_report():
    report_type = request.args.get('report_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    try:
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Generate report data
        if report_type == 'scheduled_trips':
            data = generate_scheduled_trips_report(start, end)
            filename = f"scheduled_trips_{start_date}_to_{end_date}.csv"
        elif report_type == 'cancelled_trips':
            data = generate_cancelled_trips_report(start, end)
            filename = f"cancelled_trips_{start_date}_to_{end_date}.csv"
        elif report_type == 'vehicle_utilization':
            data = generate_vehicle_utilization_report(start, end)
            filename = f"vehicle_utilization_{start_date}_to_{end_date}.csv"
        elif report_type == 'driver_performance':
            data = generate_driver_performance_report(start, end)
            filename = f"driver_performance_{start_date}_to_{end_date}.csv"
        else:
            return "Invalid report type", 400

        if not data.get_json().get('success'):
            return "Error generating report", 500

        # Convert JSON to CSV
        df = pd.DataFrame(
            data.get_json().get('rows'),
            columns=data.get_json().get('headers')
        )

        # Create CSV in memory
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # Return as downloadable CSV file
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting report: {str(e)}", 500

# Truck Load Utilization Routes
@app.route('/truck_utilization')
@login_required
def truck_utilization():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Query schedules within date range and join with trips to count branches
        # We need to get Trip data with Vehicle info and count TripDetails
        from sqlalchemy import func

        query = db.session.query(
            Schedule.delivery_schedule,
            Vehicle.plate_number,
            Vehicle.capacity,
            Trip.total_cbm.label('actual_cbm'),
            func.count(TripDetail.id).label('branch_count')
        ).join(
            Trip, Schedule.id == Trip.schedule_id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).outerjoin(
            TripDetail, Trip.id == TripDetail.trip_id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule <= end_date
        ).group_by(
            Schedule.delivery_schedule,
            Vehicle.plate_number,
            Vehicle.capacity,
            Trip.id,
            Trip.total_cbm
        ).order_by(
            Schedule.delivery_schedule,
            Trip.trip_number
        ).all()

        result = []
        for row in query:
            result.append({
                'delivery_schedule': row.delivery_schedule.strftime('%Y-%m-%d'),
                'plate_number': row.plate_number or 'N/A',
                'capacity': row.capacity or 0,
                'actual': row.actual_cbm or 0,
                'branch_count': row.branch_count or 0
            })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500

@app.route('/export_truck_utilization')
@login_required
def export_truck_utilization():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Query schedules within date range and join with trips to count branches
        from sqlalchemy import func

        query = db.session.query(
            Schedule.delivery_schedule,
            Vehicle.plate_number,
            Vehicle.capacity,
            Trip.total_cbm.label('actual_cbm'),
            func.count(TripDetail.id).label('branch_count')
        ).join(
            Trip, Schedule.id == Trip.schedule_id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).outerjoin(
            TripDetail, Trip.id == TripDetail.trip_id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule <= end_date
        ).group_by(
            Schedule.delivery_schedule,
            Vehicle.plate_number,
            Vehicle.capacity,
            Trip.id,
            Trip.total_cbm
        ).order_by(
            Schedule.delivery_schedule,
            Trip.trip_number
        ).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Delivery Schedule', 'Plate Number', 'Capacity (CBM)', 'Actual (CBM)', '% Utilization', 'Branch Count'])

        # Write data rows
        for row in query:
            capacity = row.capacity or 0
            actual = row.actual_cbm or 0
            utilization = (actual / capacity * 100) if capacity > 0 else 0

            writer.writerow([
                row.delivery_schedule.strftime('%Y-%m-%d'),
                row.plate_number or 'N/A',
                capacity,
                f"{actual:.3f}",
                f"{utilization:.1f}%",
                row.branch_count or 0
            ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"truck_utilization_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting truck utilization: {str(e)}", 500

# Truck Fleet Utilization Routes
@app.route('/truck_fleet_utilization')
@login_required
def truck_fleet_utilization():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Get all dates in the range
        from datetime import timedelta
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)

        result = []

        for date in date_list:
            # Count unique trucks (plate_numbers) used on this date from schedule table
            schedules_on_date = Schedule.query.filter(
                Schedule.delivery_schedule == date,
                Schedule.plate_number.isnot(None)
            ).all()

            # Get unique plate numbers for this date
            unique_trucks = set()
            for schedule in schedules_on_date:
                if schedule.plate_number:
                    unique_trucks.add(schedule.plate_number)

            trucks_used = len(unique_trucks)

            # Get active truck count from daily_vehicle_count table
            daily_count = DailyVehicleCount.query.filter_by(date=date).first()
            active_trucks = daily_count.qty if daily_count else 0

            result.append({
                'date': date.strftime('%Y-%m-%d'),
                'trucks_used': trucks_used,
                'active_trucks': active_trucks
            })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500


@app.route('/export_truck_fleet_utilization')
@login_required
def export_truck_fleet_utilization():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Get all dates in the range
        from datetime import timedelta
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Date', 'Day', 'Trucks Used', 'Active Trucks', '% Utilization'])

        # Write data rows
        for date in date_list:
            # Count unique trucks (plate_numbers) used on this date
            schedules_on_date = Schedule.query.filter(
                Schedule.delivery_schedule == date,
                Schedule.plate_number.isnot(None)
            ).all()

            # Get unique plate numbers for this date
            unique_trucks = set()
            for schedule in schedules_on_date:
                if schedule.plate_number:
                    unique_trucks.add(schedule.plate_number)

            trucks_used = len(unique_trucks)

            # Get active truck count from daily_vehicle_count table
            daily_count = DailyVehicleCount.query.filter_by(date=date).first()
            active_trucks = daily_count.qty if daily_count else 0

            # Calculate utilization percentage
            utilization = (trucks_used / active_trucks * 100) if active_trucks > 0 else 0

            day_name = date.strftime('%A')

            writer.writerow([
                date.strftime('%Y-%m-%d'),
                day_name,
                trucks_used,
                active_trucks,
                f"{utilization:.1f}%"
            ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"truck_fleet_utilization_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting truck fleet utilization: {str(e)}", 500

# Fuel Efficiency / ODO Routes
@app.route('/api/vehicles')
@login_required
def api_vehicles():
    """Get all vehicles for dropdown filter"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    vehicles = Vehicle.query.filter_by(status='Active').order_by(Vehicle.plate_number).all()
    return jsonify([{'plate_number': v.plate_number} for v in vehicles])


@app.route('/fuel_efficiency_data')
@login_required
def fuel_efficiency_data():
    """Get ODO records for fuel efficiency report"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    vehicle_filter = request.args.get('vehicle', '')
    dept_filter = request.args.get('dept', '')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Build query - join with Vehicle to filter by dept
        query = Odo.query.join(Vehicle, Odo.plate_number == Vehicle.plate_number).filter(
            Odo.datetime >= start_date,
            Odo.datetime < end_date
        )

        if vehicle_filter:
            query = query.filter(Odo.plate_number == vehicle_filter)

        if dept_filter:
            query = query.filter(Vehicle.dept == dept_filter)

        # Order by datetime descending (newest first)
        odo_records = query.order_by(Odo.datetime.desc()).all()

        result = []
        for odo in odo_records:
            result.append({
                'datetime': odo.datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'plate_number': odo.plate_number,
                'status': odo.status,
                'odometer_reading': odo.odometer_reading,
                'litters': odo.litters,
                'amount': odo.amount,
                'price_per_litter': odo.price_per_litter,
                'created_by': odo.created_by
            })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500


@app.route('/export_fuel_efficiency')
@login_required
def export_fuel_efficiency():
    """Export ODO records to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    vehicle_filter = request.args.get('vehicle', '')
    dept_filter = request.args.get('dept', '')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Build query - join with Vehicle to filter by dept
        query = Odo.query.join(Vehicle, Odo.plate_number == Vehicle.plate_number).filter(
            Odo.datetime >= start_date,
            Odo.datetime < end_date
        )

        if vehicle_filter:
            query = query.filter(Odo.plate_number == vehicle_filter)

        if dept_filter:
            query = query.filter(Vehicle.dept == dept_filter)

        # Order by datetime descending
        odo_records = query.order_by(Odo.datetime.desc()).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Calculate summary by plate number
        summary = {}
        for odo in odo_records:
            plate = odo.plate_number
            if plate not in summary:
                summary[plate] = {
                    'plate_number': plate,
                    'start_odo': None,
                    'end_odo': None,
                    'total_liters': 0,
                    'total_amount': 0
                }

            odo_reading = float(odo.odometer_reading or 0)

            if odo.status == 'start odo':
                if summary[plate]['start_odo'] is None or odo_reading < summary[plate]['start_odo']:
                    summary[plate]['start_odo'] = odo_reading
            elif odo.status == 'end odo':
                if summary[plate]['end_odo'] is None or odo_reading > summary[plate]['end_odo']:
                    summary[plate]['end_odo'] = odo_reading

            if odo.litters:
                summary[plate]['total_liters'] += float(odo.litters)
            if odo.amount:
                summary[plate]['total_amount'] += float(odo.amount)

        # Write summary section
        writer.writerow([])
        writer.writerow(['SUMMARY BY VEHICLE'])
        writer.writerow([
            'Plate Number', 'Total KM Traveled', 'KM/Liter',
            'Total Liters', 'Total Amount', 'Average Price/Liter'
        ])

        for summary_row in summary.values():
            total_km = (summary_row['end_odo'] is not None and summary_row['start_odo'] is not None)
            total_km_value = (summary_row['end_odo'] - summary_row['start_odo']) if total_km else None

            km_per_liter = (summary_row['total_liters'] > 0 and total_km_value is not None)
            km_per_liter_value = (total_km_value / summary_row['total_liters']) if km_per_liter else None

            avg_price_per_liter = (summary_row['total_amount'] / summary_row['total_liters']) if summary_row['total_liters'] > 0 else None

            writer.writerow([
                summary_row['plate_number'],
                f"{total_km_value:.1f}" if total_km_value is not None else 'N/A',
                f"{km_per_liter_value:.2f}" if km_per_liter_value is not None else 'N/A',
                f"{summary_row['total_liters']:.2f}",
                f"₱{summary_row['total_amount']:.2f}",
                f"₱{avg_price_per_liter:.2f}" if avg_price_per_liter is not None else 'N/A'
            ])

        # Write detailed records section
        writer.writerow([])
        writer.writerow([])
        writer.writerow(['DETAILED ODO RECORDS'])
        writer.writerow([
            'Date & Time', 'Plate Number', 'Status',
            'Odometer Reading', 'Liters', 'Amount',
            'Price Per Liter', 'Created By'
        ])

        # Write data rows
        for odo in odo_records:
            writer.writerow([
                odo.datetime.strftime('%Y-%m-%d %H:%M:%S'),
                odo.plate_number,
                odo.status,
                f"{odo.odometer_reading:.1f}",
                f"{odo.litters:.2f}" if odo.litters else 'N/A',
                f"{odo.amount:.2f}" if odo.amount else 'N/A',
                f"{odo.price_per_litter:.2f}" if odo.price_per_litter else 'N/A',
                odo.created_by
            ])

        output.seek(0)

        # Return as downloadable CSV file
        vehicle_suffix = f"_{vehicle_filter}" if vehicle_filter else ""
        dept_suffix = f"_{dept_filter}" if dept_filter else ""
        filename = f"odo_records{vehicle_suffix}{dept_suffix}_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting fuel efficiency data: {str(e)}", 500

# Frequency Rate Routes
@app.route('/frequency_rate')
@login_required
def frequency_rate():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Query schedules within date range with eager loading
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).all()

        # Dictionary to store areas and their delivery dates
        area_data = {}

        for schedule in schedules:
            # Get all trips for this schedule
            for trip in schedule.trips:
                # Get all trip details for this trip
                for detail in trip.details:
                    # Only count delivered trips
                    if detail.status == 'Delivered':
                        area = detail.area or 'Unknown'
                        delivery_date = schedule.delivery_schedule.strftime('%Y-%m-%d')

                        if area not in area_data:
                            area_data[area] = {
                                'dates': set()
                            }

                        # Add the date to the set (sets automatically handle duplicates)
                        area_data[area]['dates'].add(delivery_date)

        # Convert to list and sort by count of unique dates (descending)
        result = []
        for area, data in sorted(area_data.items(), key=lambda x: len(x[1]['dates']), reverse=True):
            # Get sorted list of unique dates
            sorted_dates = sorted(list(data['dates']))
            # Count unique dates (each day counts as 1 regardless of how many deliveries)
            delivery_count = len(sorted_dates)

            result.append({
                'area': area,
                'delivery_count': delivery_count,
                'areas': sorted_dates
            })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500


@app.route('/export_frequency_rate')
@login_required
def export_frequency_rate():
    """Export frequency rate to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Query schedules within date range with eager loading
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).all()

        # Dictionary to store areas and their delivery dates
        area_data = {}

        for schedule in schedules:
            # Get all trips for this schedule
            for trip in schedule.trips:
                # Get all trip details for this trip
                for detail in trip.details:
                    # Only count delivered trips
                    if detail.status == 'Delivered':
                        area = detail.area or 'Unknown'
                        delivery_date = schedule.delivery_schedule.strftime('%Y-%m-%d')

                        if area not in area_data:
                            area_data[area] = {
                                'dates': set()
                            }

                        # Add the date to the set (sets automatically handle duplicates)
                        area_data[area]['dates'].add(delivery_date)

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Rank', 'Area/Branch', 'Delivery Count', 'Delivery Dates'])

        # Write data rows (sorted by count of unique dates descending)
        rank = 1
        for area, data in sorted(area_data.items(), key=lambda x: len(x[1]['dates']), reverse=True):
            sorted_dates = sorted(list(data['dates']))
            dates_str = ', '.join(sorted_dates)
            delivery_count = len(sorted_dates)  # Count unique dates

            writer.writerow([
                rank,
                area,
                delivery_count,
                dates_str
            ])
            rank += 1

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"frequency_rate_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting frequency rate: {str(e)}", 500

# DIFOT Routes
@app.route('/difot_data')
@login_required
def difot_data():
    """Get DIFOT (Delivery In Full, On Time) data"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Query schedules within date range with eager loading
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).all()

        result = []
        for schedule in schedules:
            for trip in schedule.trips:
                for detail in trip.details:
                    # Show delivered and cancelled items
                    if detail.status in ('Delivered', 'Cancelled'):
                        # Calculate On Time: scheduled_date - original_due_date
                        days_late = None
                        if detail.original_due_date:
                            days_late = (schedule.delivery_schedule - detail.original_due_date).days

                        # Calculate In Full: total_delivered_qty - total_ordered_qty
                        qty_diff = None
                        if detail.total_delivered_qty is not None and detail.total_ordered_qty is not None:
                            qty_diff = detail.total_delivered_qty - detail.total_ordered_qty

                        result.append({
                            'scheduled_date': schedule.delivery_schedule.strftime('%Y-%m-%d'),
                            'branch_name_v2': detail.branch_name_v2,
                            'total_ordered_qty': detail.total_ordered_qty or 0,
                            'original_due_date': detail.original_due_date.strftime('%Y-%m-%d') if detail.original_due_date else 'N/A',
                            'total_delivered_qty': detail.total_delivered_qty or 0,
                            'days_late': days_late,
                            'qty_diff': qty_diff
                        })

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching data: {str(e)}'}), 500


@app.route('/export_difot')
@login_required
def export_difot():
    """Export DIFOT data to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Query schedules within date range with eager loading
        schedules = Schedule.query.options(
            subqueryload(Schedule.trips).subqueryload(Trip.details)
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'Scheduled Date', 'Branch', 'Total Ordered Qty',
            'Original Due Date', 'Total Delivered Qty', 'On Time', 'In Full'
        ])

        # Write data rows
        for schedule in schedules:
            for trip in schedule.trips:
                for detail in trip.details:
                    # Show delivered and cancelled items
                    if detail.status in ('Delivered', 'Cancelled'):
                        # Calculate On Time
                        days_late = None
                        on_time_status = 'N/A'
                        if detail.original_due_date:
                            days_late = (schedule.delivery_schedule - detail.original_due_date).days
                            if days_late <= 0:
                                days_early = abs(days_late)
                                on_time_status = 'On Time' if days_early == 0 else f'{days_early} Day(s) Early'
                            else:
                                on_time_status = f'{days_late} Day(s) Late'

                        # Calculate In Full
                        qty_diff = None
                        in_full_status = 'N/A'
                        if detail.total_delivered_qty is not None and detail.total_ordered_qty is not None:
                            qty_diff = detail.total_delivered_qty - detail.total_ordered_qty
                            if qty_diff >= 0:
                                in_full_status = f'In Full' + (f' (+{qty_diff})' if qty_diff > 0 else '')
                            else:
                                in_full_status = f'Shortage ({abs(qty_diff)})'

                        writer.writerow([
                            schedule.delivery_schedule.strftime('%Y-%m-%d'),
                            detail.branch_name_v2,
                            detail.total_ordered_qty or 0,
                            detail.original_due_date.strftime('%Y-%m-%d') if detail.original_due_date else 'N/A',
                            detail.total_delivered_qty or 0,
                            on_time_status,
                            in_full_status
                        ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"difot_report_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting DIFOT data: {str(e)}", 500


@app.route('/missing_data_report')
@login_required
def missing_data_report():
    """Get Missing Data Report - trips with missing arrive/departure and vehicles with no ODO records"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Part 1: Find trips with missing arrive/departure data
        # Query trip_details where arrive or departure is NULL or empty string
        missing_trips_query = db.session.query(
            TripDetail,
            Trip,
            Schedule,
            Vehicle
        ).join(
            Trip, TripDetail.trip_id == Trip.id
        ).join(
            Schedule, Trip.schedule_id == Schedule.id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date,
            db.or_(
                TripDetail.arrive == None,
                TripDetail.arrive == '',
                TripDetail.departure == None,
                TripDetail.departure == ''
            )
        ).options(
            joinedload(Trip.drivers),
            joinedload(Trip.assistants)
        ).all()

        missing_trips = []
        for detail, trip, schedule, vehicle in missing_trips_query:
            # Get driver and assistant names using the many-to-many relationships
            driver_names = [driver.name for driver in trip.drivers] if trip.drivers else []
            assistant_names = [assistant.name for assistant in trip.assistants] if trip.assistants else []

            missing_trips.append({
                'delivery_schedule': schedule.delivery_schedule.strftime('%Y-%m-%d'),
                'plate_number': vehicle.plate_number,
                'drivers': ', '.join(driver_names) if driver_names else 'N/A',
                'assistants': ', '.join(assistant_names) if assistant_names else 'N/A',
                'trip_number': trip.trip_number,
                'branch_name': detail.branch_name_v2 or 'N/A',
                'arrive': detail.arrive.strftime('%I:%M %p') if detail.arrive else 'Missing',
                'departure': detail.departure.strftime('%I:%M %p') if detail.departure else 'Missing'
            })

        # Part 2: Find vehicles with no ODO records for each day
        # First, get all vehicles used in the date range
        vehicles_used = db.session.query(
            Schedule.delivery_schedule,
            Vehicle.id,
            Vehicle.plate_number,
            Vehicle.dept
        ).join(
            Trip, Trip.schedule_id == Schedule.id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).distinct().all()

        # Get all ODO records in the date range (using datetime field)
        from sqlalchemy import cast, Date
        odo_records = db.session.query(
            Odo
        ).filter(
            cast(Odo.datetime, Date) >= start_date,
            cast(Odo.datetime, Date) < end_date
        ).all()

        # Create a set of (date, plate_number) pairs that have ODO records
        odo_coverage = set()
        for odo in odo_records:
            odo_coverage.add((odo.datetime.date(), odo.plate_number))

        # Find vehicles with no ODO records
        missing_odo = []
        for schedule_date, vehicle_id, plate_number, dept in vehicles_used:
            if (schedule_date, plate_number) not in odo_coverage:
                missing_odo.append({
                    'delivery_schedule': schedule_date.strftime('%Y-%m-%d'),
                    'plate_number': plate_number,
                    'department': dept or 'N/A',
                    'has_start_odo': False,
                    'has_refill_odo': False,
                    'has_end_odo': False
                })

        result = {
            'missing_trips': missing_trips,
            'missing_odo': missing_odo
        }

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching missing data: {str(e)}'}), 500


@app.route('/export_missing_data')
@login_required
def export_missing_data():
    """Export Missing Data Report to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header for Missing Trips section
        writer.writerow(['MISSING TRIPS - ARRIVE/DEPARTURE DATA'])
        writer.writerow([
            'Date', 'Plate Number', 'Driver(s)', 'Assistant(s)', 'Trip #',
            'Branch', 'Arrive Time', 'Departure Time'
        ])

        # Query missing trips
        missing_trips_query = db.session.query(
            TripDetail,
            Trip,
            Schedule,
            Vehicle
        ).join(
            Trip, TripDetail.trip_id == Trip.id
        ).join(
            Schedule, Trip.schedule_id == Schedule.id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date,
            db.or_(
                TripDetail.arrive == None,
                TripDetail.arrive == '',
                TripDetail.departure == None,
                TripDetail.departure == ''
            )
        ).options(
            joinedload(Trip.drivers),
            joinedload(Trip.assistants)
        ).all()

        # Write missing trips data
        for detail, trip, schedule, vehicle in missing_trips_query:
            # Get driver and assistant names using the many-to-many relationships
            driver_names = [driver.name for driver in trip.drivers] if trip.drivers else []
            assistant_names = [assistant.name for assistant in trip.assistants] if trip.assistants else []

            writer.writerow([
                schedule.delivery_schedule.strftime('%Y-%m-%d'),
                vehicle.plate_number,
                ', '.join(driver_names) if driver_names else 'N/A',
                ', '.join(assistant_names) if assistant_names else 'N/A',
                f"Trip {trip.trip_number}",
                detail.branch_name_v2 or 'N/A',
                detail.arrive.strftime('%I:%M %p') if detail.arrive else 'Missing',
                detail.departure.strftime('%I:%M %p') if detail.departure else 'Missing'
            ])

        # Add blank row and header for Missing ODO section
        writer.writerow([])
        writer.writerow(['MISSING ODO RECORDS'])
        writer.writerow([
            'Date', 'Plate Number', 'Department', 'Has Start ODO', 'Has Refill ODO', 'Has End ODO'
        ])

        # Query vehicles used in date range
        vehicles_used = db.session.query(
            Schedule.delivery_schedule,
            Vehicle.id,
            Vehicle.plate_number,
            Vehicle.dept
        ).join(
            Trip, Trip.schedule_id == Schedule.id
        ).join(
            Vehicle, Trip.vehicle_id == Vehicle.id
        ).filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).distinct().all()

        # Get all ODO records in the date range (using datetime field)
        from sqlalchemy import cast, Date
        odo_records = db.session.query(
            Odo
        ).filter(
            cast(Odo.datetime, Date) >= start_date,
            cast(Odo.datetime, Date) < end_date
        ).all()

        # Create a set of (date, plate_number) pairs that have ODO records
        odo_coverage = set()
        for odo in odo_records:
            odo_coverage.add((odo.datetime.date(), odo.plate_number))

        # Write missing ODO data
        for schedule_date, vehicle_id, plate_number, dept in vehicles_used:
            if (schedule_date, plate_number) not in odo_coverage:
                writer.writerow([
                    schedule_date.strftime('%Y-%m-%d'),
                    plate_number,
                    dept or 'N/A',
                    'No',
                    'No',
                    'No'
                ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"missing_data_report_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting missing data: {str(e)}", 500


# Backload Routes
@app.route('/backload')
@login_required
def backload():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    return render_template('backload.html')


@app.route('/search_trip_details')
@login_required
def search_trip_details():
    """Search trip details by document number"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    document_number = request.args.get('document_number', '').strip()

    if not document_number:
        return jsonify({'error': 'Document number is required'}), 400

    try:
        # Search for trip details with the given document number
        trip_details = db.session.query(TripDetail, Schedule).join(
            Trip, TripDetail.trip_id == Trip.id
        ).join(
            Schedule, Trip.schedule_id == Schedule.id
        ).filter(
            TripDetail.document_number == document_number
        ).order_by(Schedule.delivery_schedule.desc()).all()

        result = []
        for detail, schedule in trip_details:
            result.append({
                'id': detail.id,
                'scheduled_date': schedule.delivery_schedule.strftime('%Y-%m-%d'),
                'document_number': detail.document_number,
                'branch_name_v2': detail.branch_name_v2,
                'total_ordered_qty': detail.total_ordered_qty or 0,
                'total_delivered_qty': detail.total_delivered_qty or 0,
                'backload_qty': detail.backload_qty or 0
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error searching: {str(e)}'}), 500


@app.route('/search_data_records')
@login_required
def search_data_records():
    """Search data records by document number"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    document_number = request.args.get('document_number')

    if not document_number:
        return jsonify([])

    try:
        # Query data records matching the document number
        data_records = Data.query.filter(
            Data.document_number == document_number
        ).order_by(Data.item_number).all()

        result = []
        for record in data_records:
            result.append({
                'id': record.id,
                'document_number': record.document_number,
                'item_number': record.item_number,
                'ordered_qty': record.ordered_qty or 0,
                'delivered_qty': record.delivered_qty or 0,
                'branch_name': record.branch_name,
                'branch_name_v2': record.branch_name_v2,
                'original_due_date': record.original_due_date.strftime('%Y-%m-%d') if record.original_due_date else None
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error searching data records: {str(e)}'}), 500


@app.route('/search_backload')
@login_required
def search_backload():
    """Search backload records by document number"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    document_number = request.args.get('document_number')

    if not document_number:
        return jsonify([])

    try:
        # Query backload records matching the document number
        backloads = Backload.query.filter(
            Backload.document_number == document_number
        ).order_by(Backload.created_at.desc()).all()

        result = []
        for backload in backloads:
            result.append({
                'id': backload.id,
                'created_at': backload.created_at.strftime('%Y-%m-%d %H:%M:%S') if backload.created_at else None,
                'document_number': backload.document_number,
                'item_number': backload.item_number,
                'ordered_qty': backload.ordered_qty or 0,
                'backload_qty': backload.backload_qty or 0,
                'branch_name': backload.branch_name,
                'branch_name_v2': backload.branch_name_v2
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error searching backload: {str(e)}'}), 500


@app.route('/get_data_record/<int:id>')
@login_required
def get_data_record(id):
    """Get a single data record by ID"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    try:
        record = Data.query.get_or_404(id)
        return jsonify({
            'id': record.id,
            'document_number': record.document_number,
            'item_number': record.item_number,
            'ordered_qty': record.ordered_qty,
            'delivered_qty': record.delivered_qty
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/apply_data_backload', methods=['POST'])
@login_required
def apply_data_backload():
    """Apply backload to a data record (creates a backload record and updates data and trip_detail)"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    try:
        data = request.get_json()
        record_id = data.get('record_id')
        backload_qty = data.get('backload_qty')
        backload_remarks = data.get('backload_remarks')

        if not record_id:
            return jsonify({'success': False, 'message': 'Record ID is required'}), 400

        if backload_qty is None or backload_qty <= 0:
            return jsonify({'success': False, 'message': 'Backload quantity must be greater than zero'}), 400

        if not backload_remarks:
            return jsonify({'success': False, 'message': 'Backload remarks are required'}), 400

        # Get the data record
        data_record = Data.query.get_or_404(record_id)

        # Validate backload quantity
        if backload_qty > data_record.delivered_qty:
            return jsonify({'success': False, 'message': 'Backload quantity cannot exceed delivered quantity'}), 400

        # Calculate new values for data record
        new_delivered_qty = data_record.delivered_qty - backload_qty
        new_remaining_open_qty = data_record.ordered_qty - new_delivered_qty

        # Update data record
        data_record.delivered_qty = new_delivered_qty
        data_record.remaining_open_qty = new_remaining_open_qty

        # Create backload record with updated values
        backload = Backload(
            type=data_record.type,
            posting_date=data_record.posting_date,
            document_number=data_record.document_number,
            item_number=data_record.item_number,
            ordered_qty=data_record.ordered_qty,
            delivered_qty=new_delivered_qty,
            remaining_open_qty=new_remaining_open_qty,
            from_whse_code=data_record.from_whse_code,
            to_whse=data_record.to_whse,
            remarks=data_record.remarks,
            special_instructions=data_record.special_instructions,
            branch_name=data_record.branch_name,
            branch_name_v2=data_record.branch_name_v2,
            document_status=data_record.document_status,
            original_due_date=data_record.original_due_date,
            due_date=data_record.due_date,
            user_code=data_record.user_code,
            po_number=data_record.po_number,
            isms_so_number=data_record.isms_so_number,
            cbm=data_record.cbm,
            total_cbm=data_record.total_cbm,
            customer_vendor_code=data_record.customer_vendor_code,
            customer_vendor_name=data_record.customer_vendor_name,
            status=data_record.status,
            delivery_type=data_record.delivery_type,
            backload_qty=backload_qty,
            backload_remarks=backload_remarks
        )
        db.session.add(backload)

        # Find and update the associated trip_detail
        # Search for trip_detail that contains this data_record in its data_ids
        trip_details = TripDetail.query.all()
        updated_trip_detail = None

        for td in trip_details:
            if td.data_ids:
                data_ids = td.data_ids.split(',')
                if str(record_id) in data_ids:
                    # This is the trip_detail containing our data_record
                    td.total_delivered_qty = (td.total_delivered_qty or 0) - backload_qty
                    td.backload_qty = (td.backload_qty or 0) + backload_qty
                    updated_trip_detail = td
                    break

        db.session.commit()

        message = f'Backload applied successfully. Backloaded quantity: {backload_qty}'
        if updated_trip_detail:
            message += f'\nUpdated trip_detail total_delivered_qty: {updated_trip_detail.total_delivered_qty}, backload_qty: {updated_trip_detail.backload_qty}'

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating backload record: {str(e)}'}), 500

# LCL Routes
@app.route('/lcl/upload', methods=['GET', 'POST'])
@login_required
def upload_lcl():
    """Upload LCL details from CSV and automatically update summaries"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are allowed', 'error')
            return redirect(request.url)

        try:
            # Read file content
            file_content = file.stream.read()

            # Try multiple encodings
            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            stream = None
            decoded = False

            for encoding in encodings:
                try:
                    stream = file_content.decode(encoding).splitlines()
                    decoded = True
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if not decoded:
                flash("File encoding error. Unable to read the CSV file. Please ensure it's saved as UTF-8, Latin-1, or Windows-1252 encoding.", 'error')
                return redirect(request.url)

            csv_reader = csv.DictReader(stream)

            expected_headers = {
                "SAP Upload Date", "ISMS Upload Date", "Delivery Date", "Doc Type",
                "DR Number", "Customer Name", "Qty", "From Whse", "To Whse",
                "Model", "Serial Number", "ITR SO", "DR IT", "CBM", "Email"
            }

            if set(csv_reader.fieldnames) != expected_headers:
                missing = expected_headers - set(csv_reader.fieldnames)
                extra = set(csv_reader.fieldnames) - expected_headers
                msg = ""
                if missing:
                    msg += f"Missing columns: {', '.join(missing)}. "
                if extra:
                    msg += f"Unexpected columns: {', '.join(extra)}."
                flash(f"Invalid CSV headers. {msg}", 'error')
                return redirect(request.url)

            # Load all CSV rows into memory and validate
            all_rows = list(csv_reader)
            if not all_rows:
                flash("CSV file is empty", 'error')
                return redirect(request.url)

            # ✅ OPTIMIZATION 1: Helper function defined ONCE outside the loop
            def clean(val):
                return val if val != '' else None

            # Validate all rows first
            validated_records = []
            records_skipped = 0

            for row_num, row in enumerate(all_rows, start=2):
                try:
                    # Parse and validate data
                    sap_upload_date = parse_date_flexible(row["SAP Upload Date"])
                    isms_upload_date = parse_date_flexible(row["ISMS Upload Date"]) if row["ISMS Upload Date"] else None
                    delivery_date = parse_date_flexible(row["Delivery Date"]) if row["Delivery Date"] else None

                    qty = int(float(row["Qty"])) if row["Qty"] else 0
                    cbm = float(row["CBM"]) if row["CBM"] else 0.0
                    email = clean(row["Email"])

                    # Validate email format if provided
                    if email:
                        # Basic email validation
                        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                        if not re.match(email_pattern, email):
                            raise ValueError(f"Invalid email format: '{email}'. Email must be in valid format (e.g., user@example.com)")

                    # Store validated record
                    validated_records.append({
                        'row_num': row_num,
                        'sap_upload_date': sap_upload_date,
                        'isms_upload_date': isms_upload_date,
                        'delivery_date': delivery_date,
                        'doc_type': clean(row["Doc Type"]),
                        'dr_number': clean(row["DR Number"]),
                        'customer_name': clean(row["Customer Name"]),
                        'qty': qty,
                        'fr_whse': clean(row["From Whse"]),
                        'to_whse': clean(row["To Whse"]),
                        'model': clean(row["Model"]),
                        'serial_number': clean(row["Serial Number"]),
                        'itr_so': clean(row["ITR SO"]),
                        'dr_it': clean(row["DR IT"]),
                        'cbm': cbm,
                        'email': email
                    })

                except ValueError as ve:
                    flash(f"Row {row_num}: Invalid data format – {str(ve)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)
                except Exception as e:
                    flash(f"Row {row_num}: Unexpected error – {str(e)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)

            # Step 2.5: Check for duplicates within the CSV file itself
            csv_internal_duplicates = {}
            csv_unique_records = []
            csv_internal_skipped = 0
            csv_dup_warnings = []

            for record in validated_records:
                key = (record['sap_upload_date'], record['customer_name'], record['serial_number'])
                if key in csv_internal_duplicates:
                    # Track the duplicate
                    csv_internal_duplicates[key].append(record['row_num'])
                    csv_internal_skipped += 1
                else:
                    csv_internal_duplicates[key] = [record['row_num']]
                    csv_unique_records.append(record)

            # Build error messages for internal duplicates
            for key, row_nums in csv_internal_duplicates.items():
                if len(row_nums) > 1:
                    sap_date = key[0].strftime('%Y-%m-%d') if key[0] else 'N/A'
                    cust_name = key[1] if key[1] else 'N/A'
                    serial = key[2] if key[2] else 'N/A'
                    rows_str = ", ".join(map(str, row_nums))
                    csv_dup_warnings.append(
                        f"Duplicate record in CSV: SAP Date '{sap_date}', Customer '{cust_name}', Serial '{serial}' found in rows {rows_str}. Keeping first occurrence, skipping duplicates."
                    )

            # Update validated_records to only include unique records from CSV
            validated_records = csv_unique_records

            # Batch duplicate check using unique constraint (sap_upload_date, customer_name, serial_number)
            csv_keys = [(r['sap_upload_date'], r['customer_name'], r['serial_number']) for r in validated_records]

            if csv_keys:
                # Split into batches to avoid SQL query size limits
                batch_size = 500
                existing_records = []

                for i in range(0, len(csv_keys), batch_size):
                    batch = csv_keys[i:i + batch_size]
                    # Build OR conditions for each batch
                    or_conditions = db.or_(
                        *(db.and_(
                            LCLDetail.sap_upload_date == sap_date,
                            LCLDetail.customer_name == cust_name,
                            LCLDetail.serial_number == serial_num
                        ) for sap_date, cust_name, serial_num in batch)
                    )
                    batch_records = LCLDetail.query.filter(or_conditions).all()
                    existing_records.extend(batch_records)

                # Build set of existing records for fast lookup
                existing_keys = {(r.sap_upload_date, r.customer_name, r.serial_number) for r in existing_records}
            else:
                existing_keys = set()

            # Filter out duplicates and prepare bulk insert
            records_to_insert = []
            for record in validated_records:
                key = (record['sap_upload_date'], record['customer_name'], record['serial_number'])
                if key in existing_keys:
                    records_skipped += 1
                else:
                    records_to_insert.append(record)

            # ✅ OPTIMIZATION 3: Single transaction for both details and summaries
            if records_to_insert:
                try:
                    # Insert all LCL detail records
                    with db.session.no_autoflush:
                        for record in records_to_insert:
                            lcl_detail = LCLDetail(
                                sap_upload_date=record['sap_upload_date'],
                                isms_upload_date=record['isms_upload_date'],
                                delivery_date=record['delivery_date'],
                                doc_type=record['doc_type'],
                                dr_number=record['dr_number'],
                                customer_name=record['customer_name'],
                                qty=record['qty'],
                                fr_whse=record['fr_whse'],
                                to_whse=record['to_whse'],
                                model=record['model'],
                                serial_number=record['serial_number'],
                                itr_so=record['itr_so'],
                                dr_it=record['dr_it'],
                                cbm=record['cbm'],
                                email=record['email']  # Store email from CSV for visibility
                            )
                            db.session.add(lcl_detail)

                    records_added = len(records_to_insert)

                    # Group by sap_upload_date and customer_name for summary
                    summary_data = defaultdict(lambda: {'qty': 0, 'cbm': 0.0, 'email': None})

                    for record in records_to_insert:
                        key = (record['sap_upload_date'], record['customer_name'])
                        summary_data[key]['qty'] += record['qty']
                        summary_data[key]['cbm'] += record['cbm']
                        # Store email from the record (assuming all records in a group have the same email)
                        if record['email']:
                            summary_data[key]['email'] = record['email']

                    # ✅ OPTIMIZATION 2: Batch fetch existing summaries (N+1 query fix)
                    # Get all unique (posting_date, branch_name) keys
                    summary_keys = list(summary_data.keys())

                    # Batch fetch all existing summaries at once
                    existing_summaries = {}
                    if summary_keys:
                        batch_size = 500
                        for i in range(0, len(summary_keys), batch_size):
                            batch = summary_keys[i:i + batch_size]
                            # Build OR conditions for batch query
                            or_conditions = db.or_(
                                *(db.and_(
                                    LCLSummary.posting_date == p_date,
                                    LCLSummary.branch_name == b_name
                                ) for p_date, b_name in batch)
                            )
                            summaries = LCLSummary.query.filter(or_conditions).all()
                            # Index by key for fast lookup
                            for s in summaries:
                                existing_summaries[(s.posting_date, s.branch_name)] = s

                    # Update or insert summaries using in-memory lookup
                    for (posting_date, branch_name), totals in summary_data.items():
                        key = (posting_date, branch_name)

                        if key in existing_summaries:
                            # Update existing summary
                            summary = existing_summaries[key]
                            summary.tot_qty += totals['qty']
                            summary.tot_cbm += totals['cbm']
                            summary.updated_at = datetime.now()
                            # Update team_lead if email is available
                            if totals['email']:
                                summary.team_lead = totals['email']
                        else:
                            # Create new summary
                            summary = LCLSummary(
                                posting_date=posting_date,
                                company='FINDEN',
                                dept='LOGISTICS',
                                branch_name=branch_name,
                                tot_qty=totals['qty'],
                                tot_cbm=totals['cbm'],
                                team_lead=totals['email'],  # Set team_lead from detail email
                                email=totals['email']  # Store email for visibility
                            )
                            db.session.add(summary)

                    # ✅ Single commit for both details and summaries (atomic transaction)
                    db.session.commit()

                    # Display CSV internal duplicate warnings
                    if csv_dup_warnings:
                        for warning in csv_dup_warnings:
                            flash(warning, 'warning')

                    message = f"Successfully uploaded {records_added} LCL detail record(s)!"
                    total_skipped = records_skipped + csv_internal_skipped
                    if total_skipped > 0:
                        if csv_internal_skipped > 0:
                            message += f" Skipped {total_skipped} duplicate record(s) ({csv_internal_skipped} within CSV, {records_skipped} in database)."
                        else:
                            message += f" Skipped {total_skipped} duplicate record(s)."
                    flash(message, 'success')
                    return redirect(url_for('view_lcl_details'))

                except Exception as e:
                    # Rollback everything if any part fails
                    db.session.rollback()
                    flash(f"Failed to process file: {str(e)}", 'error')
                    return redirect(request.url)
            else:
                # Display CSV internal duplicate warnings even if no records inserted
                if csv_dup_warnings:
                    for warning in csv_dup_warnings:
                        flash(warning, 'warning')

                message = "No new records to upload"
                if csv_internal_skipped > 0:
                    message += f" (skipped {csv_internal_skipped} duplicate(s) within CSV)."
                else:
                    message += " (all duplicates)."
                flash(message, 'info')
                return redirect(url_for('view_lcl_details'))

        except Exception as e:
            flash(f"Failed to process file: {str(e)}", 'error')
            db.session.rollback()
            return redirect(request.url)

    return render_template('lcl_upload.html')


@app.route('/lcl/summary')
@login_required
def view_lcl_summary():
    """View LCL summary records with search and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 records per page
    search_posting_date = request.args.get('posting_date', '').strip()
    search_branch = request.args.get('branch', '').strip()

    # Build query
    query = LCLSummary.query

    # Apply email visibility filter - non-admins only see records with their email
    if current_user.position != 'admin':
        query = query.filter(LCLSummary.email == current_user.email)

    # Apply posting date filter if provided
    if search_posting_date:
        try:
            search_date = parse_date_flexible(search_posting_date)
            query = query.filter(LCLSummary.posting_date == search_date)
        except:
            pass  # Invalid date format, ignore filter

    # Apply branch name filter if provided
    if search_branch:
        query = query.filter(LCLSummary.branch_name.contains(search_branch))

    # Order by posting_date descending, then by id
    query = query.order_by(LCLSummary.posting_date.desc(), LCLSummary.id.desc())

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('lcl_summary.html',
                         summaries=pagination.items,
                         pagination=pagination,
                         search_posting_date=search_posting_date,
                         search_branch=search_branch)


@app.route('/lcl/details')
@login_required
def view_lcl_details():
    """View LCL detail records with search and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 records per page
    search_dr = request.args.get('dr', '').strip()
    search_serial = request.args.get('serial', '').strip()

    # Build query
    query = LCLDetail.query

    # Apply email visibility filter - non-admins only see records with their email
    if current_user.position != 'admin':
        query = query.filter(LCLDetail.email == current_user.email)

    # Apply DR number filter if provided
    if search_dr:
        query = query.filter(LCLDetail.dr_number.contains(search_dr))

    # Apply serial number filter if provided
    if search_serial:
        query = query.filter(LCLDetail.serial_number.contains(search_serial))

    # Order by sap_upload_date descending, then by id
    query = query.order_by(LCLDetail.sap_upload_date.desc(), LCLDetail.id.desc())

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('lcl_details.html',
                         details=pagination.items,
                         pagination=pagination,
                         search_dr=search_dr,
                         search_serial=search_serial)


@app.route('/lcl/download_template')
@login_required
def download_lcl_template():
    """Download CSV template for LCL upload"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Create an in-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'SAP Upload Date', 'ISMS Upload Date', 'Delivery Date', 'Doc Type',
        'DR Number', 'Customer Name', 'Qty', 'From Whse', 'To Whse',
        'Model', 'Serial Number', 'ITR SO', 'DR IT', '3PL', 'WAYBILL', 'CONTAINER NO.', 'ETA', 'CBM', "Email"
    ])

    # Write sample row
    writer.writerow([
    ])

    # Return as downloadable CSV file
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=lcl_upload_template.csv'}
    )


@app.route('/lcl/summary/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lcl_summary(id):
    """Edit LCL summary record"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    summary = LCLSummary.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Helper function to parse dates or return None
            def parse_date_field(field_name):
                date_str = request.form.get(field_name, '')
                return parse_date_flexible(date_str) if date_str else None

            # Helper function to parse integers or return None
            def parse_int_field(field_name):
                value = request.form.get(field_name, '')
                return int(value) if value else None

            # Helper function to parse floats or return None
            def parse_float_field(field_name):
                value = request.form.get(field_name, '')
                return float(value) if value else None

            # Quantities and Measurements
            summary.tot_qty = int(request.form.get('tot_qty', 0))
            summary.tot_cbm = float(request.form.get('tot_cbm', 0.0))
            summary.tot_boxes = parse_int_field('tot_boxes')
            summary.total_kg = parse_float_field('total_kg')
            summary.length_width_height = request.form.get('length_width_height') or None
            summary.declared_value = parse_float_field('declared_value')

            # Shipping Information
            summary.waybill_no = request.form.get('waybill_no') or None
            summary.pl_3pl = request.form.get('pl_3pl') or None
            summary.shipping_line = request.form.get('shipping_line') or None
            summary.container_no = request.form.get('container_no') or None
            summary.seal_no = request.form.get('seal_no') or None
            summary.port_of_destination = request.form.get('port_of_destination') or None
            summary.freight_category = request.form.get('freight_category') or None
            summary.ref_docs = request.form.get('ref_docs') or None

            # Dates and Timeline
            summary.prep_date = parse_date_field('prep_date')
            summary.order_date = parse_date_field('order_date')
            summary.booked_date = parse_date_field('booked_date')
            summary.actual_pickup_date = parse_date_field('actual_pickup_date')
            summary.etd = parse_date_field('etd')
            summary.atd = parse_date_field('atd')
            summary.eta = parse_date_field('eta')
            summary.ata = parse_date_field('ata')
            summary.actual_delivered_date = parse_date_field('actual_delivered_date')

            # Received By and Team Lead
            summary.received_by = request.form.get('received_by') or None
            summary.team_lead = request.form.get('team_lead') or None

            # Financial Information
            summary.freight_charge = parse_float_field('freight_charge')
            summary.total_freight_charge = parse_float_field('total_freight_charge')
            summary.billing_date = parse_date_field('billing_date')
            summary.billing_no = request.form.get('billing_no') or None
            summary.billing_status = request.form.get('billing_status') or None

            # Status and Metrics
            summary.status = request.form.get('status') or None
            summary.year = parse_int_field('year')
            summary.pick_up_month = request.form.get('pick_up_month') or None
            summary.actual_delivery_leadtime = parse_int_field('actual_delivery_leadtime')
            summary.received_date_to_pick_up_date = parse_int_field('received_date_to_pick_up_date')

            # Remarks
            summary.remarks = request.form.get('remarks') or None
            summary.detailed_remarks = request.form.get('detailed_remarks') or None

            # Update timestamp
            summary.updated_at = datetime.now()

            db.session.commit()
            flash('LCL summary updated successfully!', 'success')
            return redirect(url_for('view_lcl_summary'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating LCL summary: {str(e)}', 'error')
            return redirect(url_for('edit_lcl_summary', id=id))

    return render_template('edit_lcl_summary.html', summary=summary)


# Daily Vehicle Count Routes
@app.route('/daily_vehicle_counts')
@login_required
def daily_vehicle_counts():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Get all daily vehicle counts, ordered by date descending
    counts = DailyVehicleCount.query.order_by(DailyVehicleCount.date.desc()).all()

    # Check scheduler status
    scheduler_running = scheduler is not None
    next_run_time = None
    if scheduler and scheduler_running:
        try:
            jobs = scheduler.get_jobs()
            if jobs:
                next_run_time = jobs[0].next_run_time
        except:
            pass

    return render_template('daily_vehicle_counts.html',
                         counts=counts,
                         scheduler_running=scheduler_running,
                         next_run_time=next_run_time)


@app.route('/run_vehicle_count', methods=['POST'])
@login_required
def run_vehicle_count():
    """Manually trigger the daily vehicle count"""
    if current_user.position != 'admin':
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'})

    success = count_daily_active_vehicles()

    if success:
        from models import DailyVehicleCount
        today = datetime.now().date()
        count = DailyVehicleCount.query.filter_by(date=today).first()
        return jsonify({
            'success': True,
            'message': f'Successfully counted {count.qty} active vehicles for {today.strftime("%B %d, %Y")}'
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to count vehicles. Check server logs.'})


@app.route('/daily_vehicle_counts/<int:id>/edit', methods=['POST'])
@login_required
def edit_daily_vehicle_count(id):
    """Edit a daily vehicle count record"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('daily_vehicle_counts'))

    count = DailyVehicleCount.query.get_or_404(id)

    date_str = request.form.get('date')
    qty = request.form.get('qty')

    if not date_str:
        flash('Date is required', 'error')
        return redirect(url_for('daily_vehicle_counts'))

    if not qty:
        flash('Quantity is required', 'error')
        return redirect(url_for('daily_vehicle_counts'))

    try:
        # Parse the date
        new_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check if another record with the same date exists (excluding current record)
        existing = DailyVehicleCount.query.filter(
            DailyVehicleCount.date == new_date,
            DailyVehicleCount.id != id
        ).first()

        if existing:
            flash(f'A record for {new_date.strftime("%B %d, %Y")} already exists.', 'error')
            return redirect(url_for('daily_vehicle_counts'))

        # Update the record
        count.date = new_date
        count.qty = int(qty)
        db.session.commit()

        flash(f'Daily vehicle count updated successfully!', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(f'Invalid date format: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating record: {str(e)}', 'error')

    return redirect(url_for('daily_vehicle_counts'))


@app.route('/export_daily_vehicle_counts')
@login_required
def export_daily_vehicle_counts():
    """Export daily vehicle counts to CSV"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    try:
        # Get all daily vehicle counts
        counts = DailyVehicleCount.query.order_by(DailyVehicleCount.date.desc()).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Date', 'Day', 'Active Vehicles Count', 'Recorded At'])

        # Write data rows
        for count in counts:
            day_name = count.date.strftime('%A')
            recorded_at = count.created_at.strftime('%Y-%m-%d %H:%M:%S') if count.created_at else 'N/A'

            writer.writerow([
                count.date.strftime('%Y-%m-%d'),
                day_name,
                count.qty,
                recorded_at
            ])

        output.seek(0)

        # Return as downloadable CSV file
        filename = f"daily_vehicle_counts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'error')
        return redirect(url_for('daily_vehicle_counts'))


# Scheduler for daily vehicle count
def count_daily_active_vehicles():
    """Count active vehicles and save to DailyVehicleCount table"""
    with app.app_context():
        try:
            from models import DailyVehicleCount
            from sqlalchemy.exc import IntegrityError
            today = datetime.now().date()

            # Count active vehicles
            active_count = Vehicle.query.filter_by(status='Active').count()

            # Check if record already exists for today
            existing_count = DailyVehicleCount.query.filter_by(date=today).first()

            if existing_count:
                # Update existing record
                existing_count.qty = active_count
                db.session.commit()
                print(f"[{datetime.now()}] Updated daily vehicle count for {today}: {active_count} active vehicles")
            else:
                # Create new record
                try:
                    daily_count = DailyVehicleCount(date=today, qty=active_count)
                    db.session.add(daily_count)
                    db.session.commit()
                    print(f"[{datetime.now()}] Created daily vehicle count for {today}: {active_count} active vehicles")
                except IntegrityError:
                    # Handle race condition - another process created the record
                    db.session.rollback()
                    existing_count = DailyVehicleCount.query.filter_by(date=today).first()
                    if existing_count:
                        existing_count.qty = active_count
                        db.session.commit()
                        print(f"[{datetime.now()}] Race condition handled - updated daily vehicle count for {today}: {active_count} active vehicles")
                    else:
                        print(f"[{datetime.now()}] Error: Could not create or update daily vehicle count for {today}")
                        return False

            return True

        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now()}] Error counting daily vehicles: {str(e)}")
            return False


# Initialize and start scheduler
def init_scheduler():
    """Initialize the background scheduler for daily tasks"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import atexit
        from pytz import timezone

        scheduler = BackgroundScheduler()
        manila_tz = timezone('Asia/Manila')

        # Schedule job to run every day at 5:00 AM Manila time
        scheduler.add_job(
            func=count_daily_active_vehicles,
            trigger=CronTrigger(hour=5, minute=0, timezone=manila_tz),
            id='daily_vehicle_count',
            name='Count daily active vehicles',
            replace_existing=True,
            max_instances=1  # Prevent multiple instances running simultaneously
        )

        # Start the scheduler
        scheduler.start()
        print(f"[{datetime.now()}] Scheduler started. Daily vehicle count will run at 5:00 AM Manila time daily.")

        # Shut down the scheduler when exiting the app
        atexit.register(lambda: scheduler.shutdown())

        return scheduler
    except ImportError:
        print("[WARNING] APScheduler not installed. Install it with: pip install apscheduler")
        print("[WARNING] Daily vehicle count will not run automatically.")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to start scheduler: {str(e)}")
        return None


# Initialize scheduler when app starts
scheduler = init_scheduler()


@app.route('/admin/scheduler_status')
@login_required
def scheduler_status():
    """Check if scheduler is running"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    scheduler_status = {
        'scheduler_running': scheduler is not None,
        'apscheduler_installed': False,
        'next_run_time': None,
        'jobs': []
    }

    if scheduler:
        try:
            scheduler_status['apscheduler_installed'] = True
            scheduler_status['jobs'] = [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in scheduler.get_jobs()
            ]
        except Exception as e:
            scheduler_status['error'] = str(e)

    return jsonify(scheduler_status)


@app.route('/admin/test_vehicle_count')
@login_required
def test_vehicle_count():
    """Manual trigger for testing daily vehicle count"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    result = count_daily_active_vehicles()
    if result:
        flash('Daily vehicle count completed successfully!')
    else:
        flash('Error running daily vehicle count.', 'error')
    return redirect(url_for('view_schedule'))


# Archive Management Routes
@app.route('/admin/archive')
@login_required
def archive_admin():
    """Display archive admin page"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    return render_template('archive_admin.html')


@app.route('/admin/archive/status')
@login_required
def archive_status():
    """Return JSON with archive status and counts"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    from archive_service import get_archive_cutoff_year, identify_records_to_archive

    cutoff_year = get_archive_cutoff_year()

    # Get recent archive logs
    recent_archives = ArchiveLog.query.order_by(ArchiveLog.executed_at.desc()).limit(5).all()

    logs = []
    for log in recent_archives:
        logs.append({
            'executed_at': log.executed_at.isoformat() if log.executed_at else None,
            'cutoff_year': log.cutoff_year,
            'records_archived': log.records_archived,
            'tables_affected': log.tables_affected,
            'status': log.status,
            'error_message': log.error_message,
            'execution_time_seconds': log.execution_time_seconds
        })

    return jsonify({
        'cutoff_year': cutoff_year,
        'current_year': datetime.now().year,
        'records_to_archive': identify_records_to_archive(),
        'recent_logs': logs
    })


@app.route('/admin/archive/execute', methods=['POST'])
@login_required
def execute_archive():
    """Execute archive operation and return JSON result"""
    if current_user.position != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    from archive_service import execute_archive

    # Execute the archive
    result = execute_archive()

    # Log the operation
    log_entry = ArchiveLog(
        executed_at=datetime.now(),
        cutoff_year=result['cutoff_year'],
        records_archived=result['total_records_archived'],
        tables_affected=json.dumps(result['tables_affected']),
        status='success' if result['success'] else 'failed',
        error_message=result.get('error'),
        execution_time_seconds=result['execution_time_seconds']
    )
    db.session.add(log_entry)
    db.session.commit()

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5015)
