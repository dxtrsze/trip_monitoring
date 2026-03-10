import os
import csv
import io
from dateutil import parser as date_parser
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pandas as pd
from models import db, Vehicle, Manpower, Data, Schedule, Trip, TripDetail, Cluster, User, Odo, DailyVehicleCount, Backload
from sqlalchemy import func
from functools import wraps



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trip_monitoring.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

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

# Home page
@app.route('/')
def index():
    if current_user.is_authenticated:
        # Redirect to view_schedule for all authenticated users
        return redirect(url_for('view_schedule'))
    else:
        # Redirect to login for non-authenticated users
        return redirect(url_for('login'))

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
                return redirect(url_for('view_data'))
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
   # ✅ Only fetch records with status = 'Not Scheduled'
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    not_scheduled_data = Data.query.filter_by(status='Not Scheduled').all()
    return render_template('view_data.html', data=not_scheduled_data)

@app.route('/data/scheduled')
@login_required
def view_scheduled_data():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    # This page will use JavaScript to fetch scheduled data via API
    return render_template('view_scheduled_data.html')
 
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
        "ITR",
        "2025-10-02",
        "345709",
        "50QUHW01",
        "5",
        "5.00",
        "0.00",
        "FWH14P1F",
        "ALS005",
        "",
        "",
        "ALSONS MASBATE",
        "",
        "C",
        "2025-10-04",
        "rexconde",
        "916253958",
        "202509-0020594",
        "0.09",
        "",
        "",
        ""
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

            records_added = 0
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # ✅ Use ONLY the flexible parser — remove old strptime lines!
                    posting_date = parse_date_flexible(row["Posting Date"])
                    due_date = parse_date_flexible(row["Due Date"])
                    cbm = float(row["CBM"]) if row["CBM"] else 0.0
                    ordered_qty = float(row["Ordered Quantity"]) if row["Ordered Quantity"] else 0

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

                    data_entry = Data(
                        type=row["Type"],
                        posting_date=posting_date,
                        document_number=row["Document Number"],
                        item_number=row["Item No."],
                        ordered_qty=int(float(row["Ordered Quantity"])) if row["Ordered Quantity"] else 0,
                        delivered_qty=float(row["Delivered Quantity"]) if row["Delivered Quantity"] else 0.0,
                        remaining_open_qty=float(row["Remaining Open Qty"]) if row["Remaining Open Qty"] else 0.0,
                        from_whse_code=clean(row["From Warehouse Code"]),
                        to_whse=clean(row["To Warehouse"]),
                        remarks=clean(row["Remarks"]),
                        special_instructions=clean(row["Special Instruction"]),
                        branch_name=branch_name,
                        branch_name_v2=branch_name_v2,
                        document_status=clean(row["Document Status"]),
                        original_due_date=due_date,
                        due_date=due_date,
                        user_code=clean(row["User_Code"]),
                        po_number=clean(row["PO Number"]),
                        isms_so_number=clean(row["ISMS SO#"]),
                        cbm=float(row["CBM"]) if row["CBM"] else 0.0,
                        total_cbm = round(cbm * ordered_qty, 2),
                        customer_vendor_code=clean(row["Customer/Vendor Code"]),
                        customer_vendor_name=clean(row["Customer/Vendor Name"]),
                        delivery_type=clean(row["Delivery Type"]),
                        status="Not Scheduled"
                    )

                    db.session.add(data_entry)
                    records_added += 1

                except ValueError as ve:
                    flash(f"Row {row_num}: Invalid data format – {str(ve)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)
                except Exception as e:
                    flash(f"Row {row_num}: Unexpected error – {str(e)}", 'error')
                    db.session.rollback()
                    return redirect(request.url)

            db.session.commit()
            flash(f"Successfully uploaded {records_added} record(s)!", 'success')
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
            data.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

            # Handle numeric fields
            data.ordered_qty = int(request.form['ordered_qty'])
            data.delivered_qty = float(request.form['delivered_qty'])
            data.remaining_open_qty = float(request.form['remaining_open_qty']) if request.form['remaining_open_qty'] else 0.0
            data.cbm = float(request.form['cbm']) if request.form['cbm'] else 0.0

            # Save to DB
            db.session.commit()
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

        if not data_id:
            return jsonify({'success': False, 'message': 'Data ID is required'}), 400

        if not delete_remarks:
            return jsonify({'success': False, 'message': 'Delete remarks are required'}), 400

        # Get the data record
        data_record = Data.query.get_or_404(data_id)

        # Soft delete by updating status
        data_record.status = "Deleted"
        data_record.delete_remarks = delete_remarks

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

    if not plate_number:
        flash('Plate number is required')
        return redirect(url_for('manage_vehicles'))

    if not capacity:
        flash('Capacity is required')
        return redirect(url_for('manage_vehicles'))

    try:
        vehicle = Vehicle(plate_number=plate_number, capacity=float(capacity))
        db.session.add(vehicle)
        db.session.commit()
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

    if not plate_number:
        flash('Plate number is required')
        return redirect(url_for('manage_vehicles'))

    if not capacity:
        flash('Capacity is required')
        return redirect(url_for('manage_vehicles'))

    try:
        vehicle.plate_number = plate_number
        vehicle.capacity = float(capacity)
        db.session.commit()
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
    users = User.query.all()
    return render_template('manage_users.html', users=users)

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

            # Check if email already exists (excluding current user)
            existing_user = User.query.filter(User.email == user.email, User.id != id).first()
            if existing_user:
                flash('Email already exists', 'error')
                return redirect(url_for('manage_users'))

            user.position = position
            user.status = status

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
 
    if not search_term:
        return jsonify([])
 
    query = Data.query.filter(Data.status == 'Scheduled')
 
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
    if current_user.position == 'admin':
        # Admins see all schedules
        schedules = Schedule.query.order_by(Schedule.delivery_schedule.desc()).all()
    else:
        # Regular users only see schedules where they are assigned
        # Get the user's associated manpower entry
        user_manpower = getattr(current_user, 'manpower', None)

        if user_manpower:
            # Find all trips where this manpower is a driver or assistant
            trips = Trip.query.filter(
                db.or_(
                    Trip.drivers.any(id=user_manpower.id),
                    Trip.assistants.any(id=user_manpower.id)
                )
            ).all()

            # Get unique schedules from these trips
            schedule_ids = list(set([trip.schedule_id for trip in trips]))
            schedules = Schedule.query.filter(Schedule.id.in_(schedule_ids)).order_by(Schedule.delivery_schedule.desc()).all()
        else:
            # User has no associated manpower entry - show no schedules
            schedules = []

    return render_template('view_schedule.html', schedules=schedules)


@app.route('/schedules/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    if request.method == 'POST':
        try:
            delivery_date = datetime.strptime(request.form['delivery_schedule'], '%Y-%m-%d').date()
            
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
                                'original_due_date': data.original_due_date  # Store original due date
                            }

                        branch_groups[branch_name]['data_ids'].append(data.id)
                        branch_groups[branch_name]['document_numbers'].append(data.document_number)
                        branch_groups[branch_name]['total_cbm'] += data.cbm * data.ordered_qty or 0.0
                        branch_groups[branch_name]['total_ordered_qty'] += data.ordered_qty or 0

                        # Mark as Scheduled
                        data.status = "Scheduled"
                        data.delivered_qty = data.ordered_qty or 0.0

                # Create aggregated TripDetail entries grouped by branch
                trip_total_cbm = 0.0
                for branch_name, branch_data in branch_groups.items():
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
                        original_due_date=branch_data['original_due_date']  # Save original due date
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

    # GET: Load resources for form
    vehicles = Vehicle.query.filter_by(status='Active').order_by(Vehicle.plate_number).all()
    drivers = Manpower.query.filter_by(role='Driver').order_by(Manpower.name).all()
    assistants = Manpower.query.filter_by(role='Assistant').order_by(Manpower.name).all()
    return render_template('add_schedule.html',
                         vehicles=vehicles,
                         drivers=drivers,
                         assistants=assistants)


@app.route('/api/not_scheduled')
def api_not_scheduled():
    due_date_str = request.args.get('due_date')
    if not due_date_str:
        return jsonify([])

    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    # Subquery: Get all "Not Scheduled" data with due_date == selected date
    subq = Data.query.filter(
        Data.status == 'Not Scheduled',
        Data.due_date == due_date
    ).subquery()

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

    # Fetch all clusters for lookup (create a dictionary for fast lookup)
    clusters = Cluster.query.all()
    cluster_dict = {}
    for cluster in clusters:
        if cluster.branch:
            cluster_dict[cluster.branch.lower()] = cluster.area or ''

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


@app.route('/api/available_for_edit')
def api_available_for_edit():
    """Get available shipments for editing a trip (Not Scheduled, not assigned to any trip in the schedule)"""
    delivery_date_str = request.args.get('delivery_date')
    trip_id = request.args.get('trip_id')

    if not delivery_date_str or not trip_id:
        return jsonify([])

    delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
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

    # Get all "Not Scheduled" data with due_date == delivery date
    subq = Data.query.filter(
        Data.status == 'Not Scheduled',
        Data.due_date == delivery_date
    ).subquery()

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
                original_due_date=branch_data['original_due_date']
            )
            db.session.add(detail)
            trip_total_cbm += branch_data['total_cbm']

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

    # Order by datetime descending (newest first)
    odo_logs = query.order_by(Odo.datetime.desc()).all()

    # Get all vehicles for the filter dropdown
    vehicles = Vehicle.query.all()

    return render_template('odo_logs.html',
                         odo_logs=odo_logs,
                         vehicles=vehicles,
                         vehicle_filter=vehicle_filter,
                         status_filter=status_filter,
                         start_date=start_date,
                         end_date=end_date)


# Reports page route
@app.route('/reports')
@login_required
def reports():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))
    return render_template('reports.html')

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

        # Query schedules within date range
        schedules = Schedule.query.filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).order_by(Schedule.delivery_schedule).all()

        result = []
        for schedule in schedules:
            for trip in schedule.trips:
                for detail in trip.details:
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

        # Query schedules within date range
        schedules = Schedule.query.filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule < end_date
        ).order_by(Schedule.delivery_schedule).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'Date', 'Trip #', 'Vehicle', 'Driver(s)', 'Assistant(s)',
            'Branch', 'Ordered Qty', 'Delivered Qty', 'Status'
        ])

        # Write data rows
        for schedule in schedules:
            for trip in schedule.trips:
                for detail in trip.details:
                    # Get all drivers for this trip
                    drivers = ', '.join([driver.name for driver in trip.drivers]) if trip.drivers else 'N/A'

                    # Get all assistants for this trip
                    assistants = ', '.join([assistant.name for assistant in trip.assistants]) if trip.assistants else 'N/A'

                    writer.writerow([
                        schedule.delivery_schedule.strftime('%Y-%m-%d'),
                        trip.trip_number,
                        trip.vehicle.plate_number if trip.vehicle else 'N/A',
                        drivers,
                        assistants,
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
    # Query all scheduled trips within the date range
    schedules = Schedule.query.filter(
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
                driver_name = trip.driver.name if trip.driver else 'N/A'
                assistant_name = trip.assistant.name if trip.assistant else 'N/A'
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

        # Query schedules within date range that have vehicle info
        schedules = Schedule.query.filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule <= end_date,
            Schedule.plate_number.isnot(None)
        ).order_by(Schedule.delivery_schedule).all()

        result = []
        for schedule in schedules:
            result.append({
                'delivery_schedule': schedule.delivery_schedule.strftime('%Y-%m-%d'),
                'plate_number': schedule.plate_number or 'N/A',
                'capacity': schedule.capacity or 0,
                'actual': schedule.actual or 0
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

        # Query schedules within date range
        schedules = Schedule.query.filter(
            Schedule.delivery_schedule >= start_date,
            Schedule.delivery_schedule <= end_date,
            Schedule.plate_number.isnot(None)
        ).order_by(Schedule.delivery_schedule).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Delivery Schedule', 'Plate Number', 'Capacity', 'Actual', '% Utilization'])

        # Write data rows
        for schedule in schedules:
            capacity = schedule.capacity or 0
            actual = schedule.actual or 0
            utilization = (actual / capacity * 100) if capacity > 0 else 0

            writer.writerow([
                schedule.delivery_schedule.strftime('%Y-%m-%d'),
                schedule.plate_number or 'N/A',
                capacity,
                f"{actual:.3f}",
                f"{utilization:.1f}%"
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
    status_filter = request.args.get('status', '')

    if not start_date_str or not end_date_str:
        return jsonify([])

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Build query
        query = Odo.query.filter(Odo.datetime >= start_date, Odo.datetime < end_date)

        if vehicle_filter:
            query = query.filter(Odo.plate_number == vehicle_filter)

        if status_filter:
            query = query.filter(Odo.status == status_filter)

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
    status_filter = request.args.get('status', '')

    if not start_date_str or not end_date_str:
        return "Start date and end date are required", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Include the entire end date
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)

        # Build query
        query = Odo.query.filter(Odo.datetime >= start_date, Odo.datetime < end_date)

        if vehicle_filter:
            query = query.filter(Odo.plate_number == vehicle_filter)

        if status_filter:
            query = query.filter(Odo.status == status_filter)

        # Order by datetime descending
        odo_records = query.order_by(Odo.datetime.desc()).all()

        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
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
        status_suffix = f"_{status_filter}" if status_filter else ""
        filename = f"odo_records{vehicle_suffix}{status_suffix}_{start_date_str}_to_{end_date_str}.csv"
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

        # Query schedules within date range
        schedules = Schedule.query.filter(
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

        # Query schedules within date range
        schedules = Schedule.query.filter(
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

        # Query schedules within date range with trip details
        schedules = Schedule.query.filter(
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

        # Query schedules within date range with trip details
        schedules = Schedule.query.filter(
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

# Daily Vehicle Count Routes
@app.route('/daily_vehicle_counts')
@login_required
def daily_vehicle_counts():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # Get all daily vehicle counts, ordered by date descending
    counts = DailyVehicleCount.query.order_by(DailyVehicleCount.date.desc()).all()
    return render_template('daily_vehicle_counts.html', counts=counts)


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
    try:
        from models import DailyVehicleCount
        today = datetime.now().date()

        # Check if record already exists for today
        existing_count = DailyVehicleCount.query.filter_by(date=today).first()

        # Count active vehicles
        active_count = Vehicle.query.filter_by(status='Active').count()

        if existing_count:
            # Update existing record
            existing_count.qty = active_count
            print(f"[{datetime.now()}] Updated daily vehicle count for {today}: {active_count} active vehicles")
        else:
            # Create new record
            daily_count = DailyVehicleCount(date=today, qty=active_count)
            db.session.add(daily_count)
            print(f"[{datetime.now()}] Created daily vehicle count for {today}: {active_count} active vehicles")

        db.session.commit()
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

        scheduler = BackgroundScheduler()

        # Schedule job to run every day at 5:00 AM
        scheduler.add_job(
            func=count_daily_active_vehicles,
            trigger=CronTrigger(hour=5, minute=0),
            id='daily_vehicle_count',
            name='Count daily active vehicles',
            replace_existing=True
        )

        # Start the scheduler
        scheduler.start()
        print(f"[{datetime.now()}] Scheduler started. Daily vehicle count will run at 5:00 AM daily.")

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
scheduler = None


if __name__ == '__main__':
    # Start the scheduler
    scheduler = init_scheduler()

    app.run(debug=True, host='0.0.0.0', port=5015)
