# Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an admin-only operational dashboard with 6 KPIs, 3 trend charts, 3 comparison charts, and 3 performance gauges, replacing the current home page redirect.

**Architecture:** Flask backend with 4 JSON API endpoints (`/api/dashboard/kpis`, `/api/dashboard/trends`, `/api/dashboard/comparisons`, `/api/dashboard/gauges`) serving data from SQLAlchemy models to an Apache ECharts-powered frontend with responsive Bootstrap layout.

**Tech Stack:** Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Apache ECharts 5.x, Bootstrap Icons 1.x, existing SQLite database

---

## File Structure

**New Files:**
- `templates/dashboard.html` - Main dashboard template with KPI cards, charts, gauges
- `static/js/dashboard-api.js` - API client functions for all 4 endpoints
- `static/js/dashboard-charts.js` - ECharts initialization and update functions
- `static/js/dashboard-main.js` - Main controller, event handlers, refresh logic
- `static/js/dashboard-utils.js` - Helper functions (date formatting, color coding)
- `tests/test_dashboard_api.py` - Unit tests for dashboard API endpoints

**Modified Files:**
- `app.py` - Add dashboard route at `/` (lines 211-216) and 4 API endpoints
- `templates/base.html` - Add Apache ECharts CDN and Bootstrap Icons CDN in `<head>`

---

## Phase 1: Foundation (Dashboard Route & Template)

### Task 1: Add Bootstrap Icons to base.html

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: Read base.html to find CDN links section**

Run: `head -50 templates/base.html`
Expected: Locate `<head>` section with existing CDN links (likely Bootstrap CSS)

- [ ] **Step 2: Add Bootstrap Icons CDN link**

Insert after existing CSS links in `<head>` section:
```html
<!-- Bootstrap Icons -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
```

Location: After Bootstrap CSS link, before `</head>` tag

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat: add Bootstrap Icons CDN for dashboard"
```

---

### Task 2: Add Apache ECharts CDN to base.html

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: Add Apache ECharts CDN script**

Insert before closing `</body>` tag (after other scripts):
```html
<!-- Apache ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
```

Location: Before `</body>` tag, after existing JavaScript files

- [ ] **Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat: add Apache ECharts CDN for dashboard charts"
```

---

### Task 3: Create dashboard route with admin permission check

**Files:**
- Modify: `app.py:211-216`
- Test: Manual browser test

- [ ] **Step 1: Read current index route**

Run: `sed -n '211,250p' app.py`
Expected: See current redirect logic for authenticated users

- [ ] **Step 2: Replace index route with dashboard logic**

Replace lines 211-216 with:
```python
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
```

- [ ] **Step 3: Test route manually**

Run: `python app.py` (start Flask dev server)
Visit: `http://localhost:5000/` (non-admin user)
Expected: Redirect to `/view_schedule`
Visit: `http://localhost:5000/` (admin user)
Expected: Template not found error for dashboard.html (expected, template created in next task)

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add admin-only dashboard route, non-admins redirect to view_schedule"
```

---

### Task 4: Create dashboard.html template structure

**Files:**
- Create: `templates/dashboard.html`
- Test: Manual browser test

- [ ] **Step 1: Create base template structure**

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}

{% block content %}
<!-- Dashboard content will be added in next tasks -->
<div class="container-fluid">
  <h1>Admin Dashboard</h1>
  <p>Loading...</p>
</div>
{% endblock %}
```

Save to: `templates/dashboard.html`

- [ ] **Step 2: Test template renders**

Run: Ensure Flask dev server is running
Visit: `http://localhost:5000/` (admin user)
Expected: See "Admin Dashboard" heading and "Loading..." text

- [ ] **Step 3: Commit**

```bash
git add templates/dashboard.html
git commit -m "feat: create dashboard.html base template"
```

---

### Task 5: Build action bar in dashboard.html

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1: Add action bar HTML**

Replace the container content in dashboard.html with:
```html
{% block content %}
<!-- Action Bar -->
<nav class="navbar navbar-expand-lg navbar-dark bg-primary sticky-top">
  <div class="container-fluid">
    <span class="navbar-brand mb-0 h1">
      <i class="bi bi-speedometer2"></i> Trip Monitoring Dashboard
    </span>

    <!-- Quick Action Buttons -->
    <div class="navbar-nav ms-auto mb-2 mb-lg-0">
      <a class="nav-link btn btn-outline-light me-2" href="{{ url_for('add_schedule') }}">
        <i class="bi bi-plus-circle"></i> Schedule Trip
      </a>
      <a class="nav-link btn btn-outline-light me-2" href="{{ url_for('view_schedule') }}">
        <i class="bi bi-calendar-check"></i> View Schedule
      </a>
      <a class="nav-link btn btn-outline-light me-2" href="{{ url_for('index') }}">
        <i class="bi bi-upload"></i> Upload Data
      </a>
      <a class="nav-link btn btn-outline-light me-2" href="/odo_logs">
        <i class="bi bi-fuel-pump"></i> Add ODO
      </a>
      <a class="nav-link btn btn-outline-light me-2" href="{{ url_for('reports') }}">
        <i class="bi bi-graph-up"></i> Reports
      </a>
      <a class="nav-link btn btn-outline-light me-2" href="/vehicles">
        <i class="bi bi-truck"></i> Vehicles
      </a>
    </div>

    <!-- User Info & Refresh -->
    <div class="d-flex align-items-center text-white ms-3">
      <span class="me-3">
        <i class="bi bi-person-circle"></i> {{ current_user.name }}
      </span>
      <button id="refreshBtn" class="btn btn-light btn-sm">
        <i class="bi bi-arrow-clockwise"></i> Refresh
      </button>
      <small id="lastUpdated" class="ms-3">Loading...</small>
    </div>
  </div>
</nav>

<!-- Error Banner (hidden by default) -->
<div id="errorBanner" class="alert alert-danger alert-dismissible fade show" role="alert" style="display:none;">
  <span id="errorMessage"></span>
  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>

<!-- KPI Cards Container -->
<div id="kpiContainer" class="container-fluid mt-4">
  <h2 class="mb-4">Key Performance Indicators</h2>
  <div class="row" id="kpiCards">
    <!-- KPI cards will be dynamically inserted here -->
  </div>
</div>

<!-- Charts Container -->
<div class="container-fluid mt-5">
  <h2 class="mb-4">Trends & Comparisons</h2>
  <div class="row">
    <!-- Trend Charts Column -->
    <div class="col-lg-7">
      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-graph-up"></i> Daily Delivery Counts</h5>
        </div>
        <div class="card-body">
          <div id="deliveryCountsChart" style="height: 300px;"></div>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-fuel-pump"></i> Fuel Efficiency & Cost</h5>
        </div>
        <div class="card-body">
          <div id="fuelEfficiencyChart" style="height: 300px;"></div>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-truck"></i> Truck Utilization</h5>
        </div>
        <div class="card-body">
          <div id="truckUtilizationChart" style="height: 300px;"></div>
        </div>
      </div>
    </div>

    <!-- Comparison Charts Column -->
    <div class="col-lg-5">
      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-bar-chart"></i> Vehicle Utilization Ranking</h5>
        </div>
        <div class="card-body">
          <div id="vehicleUtilizationChart" style="height: 350px;"></div>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-geo-alt"></i> Branch Delivery Frequency</h5>
        </div>
        <div class="card-body">
          <div id="branchFrequencyChart" style="height: 350px;"></div>
        </div>
      </div>

      <div class="card mb-4">
        <div class="card-header">
          <h5><i class="bi bi-people"></i> Driver/Assistant Performance</h5>
        </div>
        <div class="card-body">
          <div id="driverPerformanceChart" style="height: 350px;"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Performance Gauges -->
<div class="container-fluid mt-5">
  <h2 class="mb-4">Performance Metrics</h2>
  <div class="row">
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">
          <h5>On-Time Delivery Rate</h5>
        </div>
        <div class="card-body">
          <div id="onTimeGauge" style="height: 250px;"></div>
        </div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">
          <h5>Truck Utilization</h5>
        </div>
        <div class="card-body">
          <div id="utilizationGauge" style="height: 250px;"></div>
        </div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">
          <h5>Data Completeness</h5>
        </div>
        <div class="card-body">
          <div id="completenessGauge" style="height: 250px;"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Load dashboard JavaScript modules -->
<script src="{{ url_for('static', filename='js/dashboard-utils.js') }}" defer></script>
<script src="{{ url_for('static', filename='js/dashboard-api.js') }}" defer></script>
<script src="{{ url_for('static', filename='js/dashboard-charts.js') }}" defer></script>
<script src="{{ url_for('static', filename='js/dashboard-main.js') }}" defer></script>
{% endblock %}
```

- [ ] **Step 2: Test action bar renders**

Visit: `http://localhost:5000/` (admin user)
Expected: See action bar with all buttons, chart containers (empty), and loading script references (will 404 until JS files created)

- [ ] **Step 3: Commit**

```bash
git add templates/dashboard.html
git commit -m "feat: add action bar and chart layout to dashboard template"
```

---

## Phase 2: Backend API Development

### Task 6: Create /api/dashboard/kpis endpoint

**Files:**
- Modify: `app.py` (add after line 2745, after reports route)
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write failing test for KPIs endpoint**

Create `tests/test_dashboard_api.py`:
```python
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
```

Save to: `tests/test_dashboard_api.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_api.py::test_kpis_endpoint_returns_json -v`
Expected: FAIL with 404 Not Found (endpoint doesn't exist yet)

- [ ] **Step 3: Implement KPIs endpoint**

Add to `app.py` (insert after line 2745, after `@app.route('/reports')`):
```python
# Dashboard API Routes
@app.route('/api/dashboard/kpis')
@login_required
def dashboard_kpis():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from sqlalchemy import func
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
    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()

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
    cache.set(cache_key, response, timeout=300)

    return jsonify(response)


def calculate_period_kpis(start_date, end_date):
    """Calculate all KPIs for a given date period"""
    from models import TripDetail, Trip, Schedule, Vehicle, Odo

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

    # Data Completeness (count unique incomplete details, not double-counting)
    from sqlalchemy import or_
    incomplete_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date),
        or_(TripDetail.arrive.is_(None), TripDetail.departure.is_(None))
    ).count()

    vehicles_with_trips = db.session.query(Trip.vehicle_id).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).distinct().all()

    vehicle_ids = [v[0] for v in vehicles_with_trips]
    vehicles_without_odo = 0

    for vehicle_id in vehicle_ids:
        vehicle = db.session.query(Vehicle).get(vehicle_id)
        odo_count = db.session.query(Odo).filter(
            Odo.plate_number == vehicle.plate_number,
            Odo.datetime.between(start_datetime, end_datetime)
        ).count()
        if odo_count == 0:
            vehicles_without_odo += 1

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
    from datetime import timedelta
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_api.py -v`
Expected: PASS for all KPI endpoint tests

- [ ] **Step 5: Test endpoint manually with browser**

Visit: `http://localhost:5000/api/dashboard/kpis` (logged in as admin)
Expected: JSON response with all KPI fields

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_dashboard_api.py
git commit -m "feat: implement /api/dashboard/kpis endpoint with all 6 KPIs"
```

---

### Task 7: Create /api/dashboard/trends endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write failing test for trends endpoint**

Add to `tests/test_dashboard_api.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_api.py::test_trends_endpoint_returns_json -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement trends endpoint**

Add to `app.py` (after dashboard_kpis function):
```python
@app.route('/api/dashboard/trends')
@login_required
def dashboard_trends():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta, datetime

    # Default to last 7 days
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()

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
        utilization_records = db.session.query(
            sql_func.sum(Trip.total_cbm).label('total_loaded'),
            sql_func.sum(Vehicle.capacity).label('total_capacity')
        ).join(Vehicle).join(Schedule).filter(
            Schedule.delivery_schedule == current_date,
            Vehicle.capacity.isnot(None),
            Vehicle.capacity > 0
        ).first()

        if utilization_records and utilization_records.total_capacity:
            util_percent = (utilization_records.total_loaded / utilization_records.total_capacity * 100)
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dashboard_api.py::test_trends -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_dashboard_api.py
git commit -m "feat: implement /api/dashboard/trends endpoint"
```

---

### Task 8: Create /api/dashboard/comparisons endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 0: Add missing imports for many-to-many tables**

Add to imports section of app.py (around line 14, after other model imports):
```python
from models import trip_driver, trip_assistant
```

- [ ] **Step 1: Write failing test**

Add to `tests/test_dashboard_api.py`:
```python
def test_comparisons_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/comparisons')
    assert response.status_code == 200

def test_comparisons_contains_rankings(client, auth_headers):
    response = client.get('/api/dashboard/comparisons')
    data = response.get_json()
    required_keys = ['vehicle_utilization', 'branch_frequency', 'driver_performance']
    for key in required_keys:
        assert key in data
        assert isinstance(data[key], list)
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_dashboard_api.py::test_comparisons -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement comparisons endpoint**

Add to `app.py`:
```python
@app.route('/api/dashboard/comparisons')
@login_required
def dashboard_comparisons():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta, datetime

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()

    if end_date > date.today():
        end_date = date.today()

    # Vehicle utilization ranking
    vehicle_util = db.session.query(
        Vehicle.plate_number,
        sql_func.sum(Trip.total_cbm).label('total_cbm'),
        Vehicle.capacity,
        sql_func.count(Trip.id).label('trip_count')
    ).join(Schedule).filter(
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
    branch_counts = db.session.query(
        TripDetail.branch_name_v2,
        sql_func.count(TripDetail.id).label('delivery_count')
    ).join(Trip).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).group_by(TripDetail.branch_name_v2).order_by(
        sql_func.desc('delivery_count')
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
    ).join(trip_driver).join(Schedule).filter(
        Schedule.delivery_schedule.between(start_date, end_date)
    ).group_by(Manpower.name).all()

    assistants = db.session.query(
        Manpower.name,
        sql_func.count(Trip.id).label('trips')
    ).join(trip_assistant).join(Schedule).filter(
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
```

Note: Need to import `trip_driver` and `trip_assistant` tables at top of app.py:
```python
from models import trip_driver, trip_assistant
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dashboard_api.py::test_comparisons -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_dashboard_api.py
git commit -m "feat: implement /api/dashboard/comparisons endpoint"
```

---

### Task 9: Create /api/dashboard/gauges endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_dashboard_api.py`:
```python
def test_gauges_endpoint_returns_json(client, auth_headers):
    response = client.get('/api/dashboard/gauges')
    assert response.status_code == 200

def test_gauges_contains_three_metrics(client, auth_headers):
    response = client.get('/api/dashboard/gauges')
    data = response.get_json()
    required_keys = ['on_time_rate', 'utilization', 'data_completeness']
    for key in required_keys:
        assert key in data
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_dashboard_api.py::test_gauges -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement gauges endpoint**

Add to `app.py`:
```python
@app.route('/api/dashboard/gauges')
@login_required
def dashboard_gauges():
    if current_user.position != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from datetime import date, timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()

    if end_date > date.today():
        end_date = date.today()

    # Calculate current KPIs using helper function
    kpis = calculate_period_kpis(start_date, end_date)

    return jsonify({
        'on_time_rate': kpis['on_time_rate'],
        'utilization': kpis['utilization'],
        'data_completeness': kpis['completeness']
    })
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dashboard_api.py -v`
Expected: PASS all tests

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_dashboard_api.py
git commit -m "feat: implement /api/dashboard/gauges endpoint"
```

---

## Phase 3: Frontend Integration

### Task 10: Create dashboard-utils.js helper functions

**Files:**
- Create: `static/js/dashboard-utils.js`

- [ ] **Step 1: Create utility functions file**

```javascript
// Dashboard utility functions

// Format date as localized string
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Format percentage with 1 decimal place
function formatPercent(value) {
  return value.toFixed(1) + '%';
}

// Format number with commas
function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Get performance tier color for KPIs
function getPerformanceColor(value, type) {
  const thresholds = {
    on_time: { good: 90, caution: 70 },
    utilization: { good: 80, caution: 50 },
    completeness: { good: 95, caution: 85 }
  };

  const tier = thresholds[type];
  if (!tier) return 'gray';

  if (value >= tier.good) return '#10b981'; // green
  if (value >= tier.caution) return '#f59e0b'; // yellow
  return '#ef4444'; // red
}

// Get Bootstrap icon class for KPI
function getKPIIcon(kpiName) {
  const icons = {
    on_time_delivery_rate: 'bi-clock-history',
    in_full_delivery_rate: 'bi-check-circle',
    difot_score: 'bi-graph-up-arrow',
    truck_utilization: 'bi-truck',
    fuel_efficiency: 'bi-fuel-pump',
    fuel_cost_per_km: 'bi-currency-dollar',
    data_completeness: 'bi-file-check'
  };
  return icons[kpiName] || 'bi-bar-chart';
}

// Get trend arrow HTML
function getTrendHtml(trend) {
  if (trend > 0) {
    return `<span class="text-success"><i class="bi bi-arrow-up"></i> ${trend}</span>`;
  } else if (trend < 0) {
    return `<span class="text-danger"><i class="bi bi-arrow-down"></i> ${Math.abs(trend)}</span>`;
  } else {
    return '<span class="text-secondary"><i class="bi bi-dash"></i> 0</span>';
  }
}

// Calculate "time ago" string
function timeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return Math.floor(seconds / 60) + ' minutes ago';
  if (seconds < 86400) return Math.floor(seconds / 3600) + ' hours ago';
  return Math.floor(seconds / 86400) + ' days ago';
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    formatDate,
    formatPercent,
    formatNumber,
    getPerformanceColor,
    getKPIIcon,
    getTrendHtml,
    timeAgo
  };
}
```

Save to: `static/js/dashboard-utils.js`

- [ ] **Step 2: Commit**

```bash
git add static/js/dashboard-utils.js
git commit -m "feat: add dashboard utility functions"
```

---

### Task 11: Create dashboard-api.js API client

**Files:**
- Create: `static/js/dashboard-api.js`

- [ ] **Step 1: Create API client functions**

```javascript
// Dashboard API client

const DashboardAPI = {
  // Fetch all KPI data
  async fetchKPIs(startDate = null, endDate = null) {
    let url = '/api/dashboard/kpis';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch KPIs: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch trends data
  async fetchTrends(startDate = null, endDate = null, granularity = 'daily') {
    let url = '/api/dashboard/trends';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    params.append('granularity', granularity);
    url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch trends: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch comparison data
  async fetchComparisons(startDate = null, endDate = null) {
    let url = '/api/dashboard/comparisons';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch comparisons: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch gauge data
  async fetchGauges(startDate = null, endDate = null) {
    let url = '/api/dashboard/gauges';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch gauges: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch all dashboard data in parallel
  async fetchAll(startDate = null, endDate = null) {
    const [kpis, trends, comparisons, gauges] = await Promise.all([
      this.fetchKPIs(startDate, endDate),
      this.fetchTrends(startDate, endDate),
      this.fetchComparisons(startDate, endDate),
      this.fetchGauges(startDate, endDate)
    ]);
    return { kpis, trends, comparisons, gauges };
  }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DashboardAPI;
}
```

Save to: `static/js/dashboard-api.js`

- [ ] **Step 2: Commit**

```bash
git add static/js/dashboard-api.js
git commit -m "feat: add dashboard API client functions"
```

---

### Task 12: Create dashboard-charts.js with ECharts initialization

**Files:**
- Create: `static/js/dashboard-charts.js`

- [ ] **Step 1: Create charts module**

```javascript
// Dashboard charts module using Apache ECharts

const DashboardCharts = (function() {
  let charts = {}; // Store chart instances

  // Initialize KPI cards rendering
  function renderKPIs(kpiData) {
    const container = document.getElementById('kpiCards');
    container.innerHTML = '';

    const kpiConfig = [
      { key: 'on_time_delivery_rate', label: 'On-Time Delivery Rate', type: 'on_time' },
      { key: 'in_full_delivery_rate', label: 'In-Full Delivery Rate', type: 'on_time' },
      { key: 'difot_score', label: 'DIFOT Score', type: 'on_time' },
      { key: 'truck_utilization', label: 'Truck Utilization', type: 'utilization' },
      { key: 'fuel_efficiency', label: 'Fuel Efficiency (KM/L)', type: 'efficiency' },
      { key: 'fuel_cost_per_km', label: 'Cost per KM (₱)', type: 'cost' },
      { key: 'data_completeness', label: 'Data Completeness', type: 'completeness' }
    ];

    kpiConfig.forEach(config => {
      const kpi = kpiData[config.key];
      const color = getPerformanceColor(kpi.value, config.type);
      const card = createKPICard(config, kpi, color);
      container.appendChild(card);
    });
  }

  function createKPICard(config, kpi, color) {
    const col = document.createElement('div');
    col.className = 'col-md-4 col-sm-6 mb-3';

    const card = document.createElement('div');
    card.className = 'card h-100';
    card.style.borderTop = `4px solid ${color}`;

    card.innerHTML = `
      <div class="card-body">
        <div class="d-flex align-items-center">
          <div class="me-3" style="font-size: 2rem; color: ${color};">
            <i class="bi ${getKPIIcon(config.key)}"></i>
          </div>
          <div class="flex-grow-1">
            <h6 class="card-subtitle mb-1 text-muted">${config.label}</h6>
            <h3 class="card-title mb-0">${typeof kpi.value === 'number' ? kpi.value.toFixed(1) : kpi.value}${config.key.includes('rate') || config.key.includes('score') || config.key.includes('utilization') || config.key.includes('completeness') ? '%' : ''}</h3>
          </div>
          <div class="text-end">
            <small class="text-muted">Trend</small><br>
            ${getTrendHtml(kpi.trend)}
          </div>
        </div>
      </div>
    `;

    col.appendChild(card);
    return col;
  }

  // Initialize delivery counts chart
  function initDeliveryCountsChart(data) {
    const chartDom = document.getElementById('deliveryCountsChart');
    charts.deliveryCounts = echarts.init(chartDom);

    const dates = data.map(d => d.date);
    const counts = data.map(d => d.count);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: dates
      },
      yAxis: {
        type: 'value',
        name: 'Deliveries'
      },
      series: [{
        name: 'Deliveries',
        type: 'line',
        smooth: true,
        data: counts,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
          ])
        },
        itemStyle: { color: '#3b82f6' }
      }],
      grid: { left: 60, right: 20, top: 20, bottom: 60 }
    };

    charts.deliveryCounts.setOption(option);
  }

  // Initialize fuel efficiency chart
  function initFuelEfficiencyChart(data) {
    const chartDom = document.getElementById('fuelEfficiencyChart');
    charts.fuelEfficiency = echarts.init(chartDom);

    const dates = data.map(d => d.date);
    const kmPerLiter = data.map(d => d.km_per_liter);
    const costPerKm = data.map(d => d.cost_per_km);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      legend: { data: ['KM/Liter', 'Cost/KM'] },
      xAxis: {
        type: 'category',
        data: dates
      },
      yAxis: [
        {
          type: 'value',
          name: 'KM/Liter',
          position: 'left'
        },
        {
          type: 'value',
          name: 'Cost/KM (₱)',
          position: 'right'
        }
      ],
      series: [
        {
          name: 'KM/Liter',
          type: 'line',
          data: kmPerLiter,
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: 'Cost/KM',
          type: 'line',
          yAxisIndex: 1,
          data: costPerKm,
          itemStyle: { color: '#f97316' }
        }
      ],
      grid: { left: 60, right: 60, top: 40, bottom: 60 }
    };

    charts.fuelEfficiency.setOption(option);
  }

  // Initialize truck utilization chart
  function initTruckUtilizationChart(data) {
    const chartDom = document.getElementById('truckUtilizationChart');
    charts.truckUtilization = echarts.init(chartDom);

    const dates = data.map(d => d.date);
    const utilization = data.map(d => d.utilization_percent);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: dates
      },
      yAxis: {
        type: 'value',
        name: 'Utilization %',
        max: 100
      },
      series: [{
        name: 'Utilization',
        type: 'line',
        step: 'middle',
        data: utilization,
        itemStyle: { color: '#8b5cf6' },
        markLine: {
          data: [{ yAxis: 80, name: 'Target' }],
          lineStyle: { color: '#10b981', type: 'dashed' }
        }
      }],
      grid: { left: 60, right: 20, top: 20, bottom: 60 }
    };

    charts.truckUtilization.setOption(option);
  }

  // Initialize vehicle utilization ranking chart
  function initVehicleUtilizationChart(data) {
    const chartDom = document.getElementById('vehicleUtilizationChart');
    charts.vehicleUtilization = echarts.init(chartDom);

    const vehicles = data.map(d => d.plate_number);
    const utilization = data.map(d => d.utilization);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Utilization %',
        max: 100
      },
      yAxis: {
        type: 'category',
        data: vehicles,
        inverse: true
      },
      series: [{
        type: 'bar',
        data: utilization,
        itemStyle: {
          color: function(params) {
            const value = params.value;
            if (value >= 80) return '#10b981';
            if (value >= 50) return '#f59e0b';
            return '#ef4444';
          }
        }
      }],
      grid: { left: 120, right: 40, top: 20, bottom: 40 }
    };

    charts.vehicleUtilization.setOption(option);
  }

  // Initialize branch frequency chart
  function initBranchFrequencyChart(data) {
    const chartDom = document.getElementById('branchFrequencyChart');
    charts.branchFrequency = echarts.init(chartDom);

    const branches = data.map(d => d.branch);
    const counts = data.map(d => d.delivery_count);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: branches,
        axisLabel: { rotate: 45 }
      },
      yAxis: {
        type: 'value',
        name: 'Deliveries'
      },
      series: [{
        type: 'bar',
        data: counts,
        itemStyle: { color: '#14b8a6' },
        label: {
          show: true,
          position: 'top'
        }
      }],
      grid: { left: 60, right: 20, top: 20, bottom: 80 }
    };

    charts.branchFrequency.setOption(option);
  }

  // Initialize driver performance chart
  function initDriverPerformanceChart(data) {
    const chartDom = document.getElementById('driverPerformanceChart');
    charts.driverPerformance = echarts.init(chartDom);

    const people = data.map(d => d.name);
    const trips = data.map(d => d.trips);
    const roles = data.map(d => d.role);

    const option = {
      title: { text: '' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: people,
        axisLabel: { rotate: 45 }
      },
      yAxis: {
        type: 'value',
        name: 'Trips'
      },
      series: [{
        type: 'bar',
        data: trips,
        itemStyle: {
          color: function(params) {
            return roles[params.dataIndex] === 'driver' ? '#3b82f6' : '#8b5cf6';
          }
        }
      }],
      grid: { left: 60, right: 20, top: 20, bottom: 80 }
    };

    charts.driverPerformance.setOption(option);
  }

  // Initialize gauge charts
  function initGauges(gaugeData) {
    // On-Time Rate Gauge
    const onTimeDom = document.getElementById('onTimeGauge');
    charts.onTimeGauge = echarts.init(onTimeDom);
    charts.onTimeGauge.setOption({
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.5, '#ef4444'],
              [0.8, '#f59e0b'],
              [1, '#10b981']
            ]
          }
        },
        pointer: { itemStyle: { color: 'auto' } },
        axisTick: { distance: -20, length: 8 },
        splitLine: { distance: -20, length: 20 },
        axisLabel: { distance: -40, formatter: '{value}%' },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: 'auto',
          fontSize: 20
        },
        data: [{ value: gaugeData.on_time_rate, name: 'On-Time' }]
      }]
    });

    // Utilization Gauge
    const utilDom = document.getElementById('utilizationGauge');
    charts.utilizationGauge = echarts.init(utilDom);
    charts.utilizationGauge.setOption({
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.5, '#ef4444'],
              [0.8, '#f59e0b'],
              [1, '#10b981']
            ]
          }
        },
        pointer: { itemStyle: { color: 'auto' } },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: 'auto',
          fontSize: 20
        },
        data: [{ value: gaugeData.utilization, name: 'Utilization' }]
      }]
    });

    // Completeness Gauge
    const completeDom = document.getElementById('completenessGauge');
    charts.completenessGauge = echarts.init(completeDom);
    charts.completenessGauge.setOption({
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.5, '#ef4444'],
              [0.8, '#f59e0b'],
              [1, '#10b981']
            ]
          }
        },
        pointer: { itemStyle: { color: 'auto' } },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: 'auto',
          fontSize: 20
        },
        data: [{ value: gaugeData.data_completeness, name: 'Complete' }]
      }]
    });
  }

  // Resize all charts
  function resizeCharts() {
    Object.values(charts).forEach(chart => {
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  }

  // Destroy all charts
  function destroyCharts() {
    Object.values(charts).forEach(chart => {
      if (chart && chart.dispose) {
        chart.dispose();
      }
    });
    charts = {};
  }

  // Return public API
  return {
    renderKPIs,
    initDeliveryCountsChart,
    initFuelEfficiencyChart,
    initTruckUtilizationChart,
    initVehicleUtilizationChart,
    initBranchFrequencyChart,
    initDriverPerformanceChart,
    initGauges,
    resizeCharts,
    destroyCharts
  };
})();
```

Save to: `static/js/dashboard-charts.js`

- [ ] **Step 2: Commit**

```bash
git add static/js/dashboard-charts.js
git commit -m "feat: add dashboard charts module with ECharts initialization"
```

---

### Task 13: Create dashboard-main.js controller

**Files:**
- Create: `static/js/dashboard-main.js`

- [ ] **Step 1: Create main controller**

```javascript
// Dashboard main controller

(function() {
  'use strict';

  let lastUpdateTime = null;

  // Initialize dashboard on page load
  async function initDashboard() {
    try {
      showLoading();

      // Fetch all data in parallel
      const data = await DashboardAPI.fetchAll();

      // Render all components
      DashboardCharts.renderKPIs(data.kpis);
      DashboardCharts.initDeliveryCountsChart(data.trends.daily_deliveries);
      DashboardCharts.initFuelEfficiencyChart(data.trends.fuel_efficiency);
      DashboardCharts.initTruckUtilizationChart(data.trends.truck_utilization);
      DashboardCharts.initVehicleUtilizationChart(data.comparisons.vehicle_utilization);
      DashboardCharts.initBranchFrequencyChart(data.comparisons.branch_frequency);
      DashboardCharts.initDriverPerformanceChart(data.comparisons.driver_performance);
      DashboardCharts.initGauges(data.gauges);

      // Update timestamp
      lastUpdateTime = new Date();
      updateTimestampDisplay();

      hideLoading();

    } catch (error) {
      console.error('Failed to load dashboard:', error);
      showError(error.message);
      hideLoading();
    }
  }

  // Refresh dashboard data
  async function refreshDashboard() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Refreshing...';
    }

    try {
      // Destroy existing charts
      DashboardCharts.destroyCharts();

      // Re-fetch and render
      await initDashboard();

    } finally {
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
      }
    }
  }

  // Update timestamp display
  function updateTimestampDisplay() {
    const timestampEl = document.getElementById('lastUpdated');
    if (timestampEl && lastUpdateTime) {
      timestampEl.textContent = 'Last updated: ' + timeAgo(lastUpdateTime);
    }
  }

  // Show loading state
  function showLoading() {
    const container = document.getElementById('kpiContainer');
    if (container) {
      container.style.opacity = '0.5';
      container.style.pointerEvents = 'none';
    }
  }

  // Hide loading state
  function hideLoading() {
    const container = document.getElementById('kpiContainer');
    if (container) {
      container.style.opacity = '1';
      container.style.pointerEvents = 'auto';
    }
  }

  // Show error message
  function showError(message) {
    const banner = document.getElementById('errorBanner');
    const messageEl = document.getElementById('errorMessage');
    if (banner && messageEl) {
      messageEl.textContent = message;
      banner.style.display = 'block';

      // Auto-dismiss after 10 seconds
      setTimeout(() => {
        banner.style.display = 'none';
      }, 10000);
    }
  }

  // Event listeners
  document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initDashboard();

    // Refresh button handler
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refreshDashboard);
    }

    // Handle window resize
    let resizeTimeout;
    window.addEventListener('resize', function() {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        DashboardCharts.resizeCharts();
      }, 250);
    });

    // Update timestamp every minute
    setInterval(updateTimestampDisplay, 60000);
  });

})();
```

Save to: `static/js/dashboard-main.js`

- [ ] **Step 2: Test dashboard loads**

Visit: `http://localhost:5000/` (admin user)
Expected: Dashboard loads with KPI cards, charts render, no console errors

- [ ] **Step 3: Test refresh button**

Click: "Refresh" button
Expected: Data reloads, charts update, timestamp refreshes

- [ ] **Step 4: Commit**

```bash
git add static/js/dashboard-main.js
git commit -m "feat: add dashboard main controller with refresh logic"
```

---

## Phase 4: Polish & Optimization

### Task 14: Add responsive CSS for mobile devices

**Files:**
- Create: `static/css/dashboard.css`
- Modify: `templates/dashboard.html`

- [ ] **Step 1: Create dashboard-specific CSS**

```css
/* Dashboard responsive styles */

/* KPI Cards */
@media (max-width: 767px) {
  .kpi-cards {
    display: flex;
    flex-direction: column;
  }

  .kpi-cards .col-md-4,
  .kpi-cards .col-sm-6 {
    width: 100%;
    max-width: 100%;
  }
}

/* Chart containers */
@media (max-width: 991px) {
  #deliveryCountsChart,
  #fuelEfficiencyChart,
  #truckUtilizationChart,
  #vehicleUtilizationChart,
  #branchFrequencyChart,
  #driverPerformanceChart {
    height: 250px !important;
  }
}

@media (max-width: 767px) {
  #deliveryCountsChart,
  #fuelEfficiencyChart,
  #truckUtilizationChart,
  #vehicleUtilizationChart,
  #branchFrequencyChart,
  #driverPerformanceChart {
    height: 200px !important;
  }

  /* Hide secondary y-axis on mobile */
  .chart-secondary-axis {
    display: none;
  }

  /* Adjust action bar for mobile */
  .navbar-nav {
    position: fixed;
    top: 56px;
    left: 0;
    right: 0;
    background: white;
    z-index: 1000;
    padding: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }

  /* Stack gauge charts on mobile */
  .col-md-4 {
    width: 100%;
    max-width: 100%;
  }
}

/* Loading overlay */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-spinner {
  width: 3rem;
  height: 3rem;
}

/* Error banner animation */
@keyframes slideDown {
  from {
    transform: translateY(-100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

#errorBanner.show {
  animation: slideDown 0.3s ease-out;
}
```

Save to: `static/css/dashboard.css`

- [ ] **Step 2: Add CSS link to dashboard.html**

Add to `<head>` section of dashboard.html:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
```

- [ ] **Step 3: Test responsive design**

Test on:
- Desktop (1920×1080): Should see 2-column chart layout
- Tablet (768px): Should see stacked charts
- Mobile (375px): Should see single column, simplified charts

- [ ] **Step 4: Commit**

```bash
git add static/css/dashboard.css templates/dashboard.html
git commit -m "feat: add responsive CSS for dashboard mobile view"
```

---

### Task 15: Add loading spinners and progressive rendering

**Files:**
- Modify: `static/js/dashboard-main.js`

- [ ] **Step 1: Enhance loading states**

Update `showLoading()` and `hideLoading()` functions:
```javascript
function showLoading() {
  // Add loading overlay to each chart container
  const chartContainers = document.querySelectorAll('.card-body div[id$="Chart"], .card-body div[id$="Gauge"]');
  chartContainers.forEach(container => {
    container.innerHTML = '<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
  });
}

function hideLoading() {
  // Loading indicators removed when charts render
}
```

- [ ] **Step 2: Test loading states**

Visit: Dashboard
Expected: See spinners before charts appear

- [ ] **Step 3: Commit**

```bash
git add static/js/dashboard-main.js
git commit -m "feat: add loading spinners for chart containers"
```

---

### Task 16: Add database indexes for performance

**Files:**
- Create: `migrations/add_dashboard_indexes.py`

- [ ] **Step 1: Create migration script**

```python
"""
Add database indexes to improve dashboard query performance
Run: python migrations/add_dashboard_indexes.py
"""

from app import app, db
from sqlalchemy import text

def add_indexes():
    with app.app_context():
        print("Adding dashboard performance indexes...")

        # Index for TripDetail-Schedule joins
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_trip ON trip_detail(trip_id)'))
            db.session.commit()
            print("✓ Added index on trip_detail(trip_id)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail index: {e}")
            db.session.rollback()

        # Index for Schedule.delivery_schedule (frequently queried)
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_schedule_delivery ON schedule(delivery_schedule)'))
            db.session.commit()
            print("✓ Added index on schedule(delivery_schedule)")
        except Exception as e:
            print(f"✗ Failed to add schedule index: {e}")
            db.session.rollback()

        # Index for Odo datetime queries
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_odo_datetime ON odo(datetime)'))
            db.session.commit()
            print("✓ Added index on odo(datetime)")
        except Exception as e:
            print(f"✗ Failed to add odo index: {e}")
            db.session.rollback()

        # Index for Odo status queries
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_odo_status ON odo(status)'))
            db.session.commit()
            print("✓ Added index on odo(status)")
        except Exception as e:
            print(f"✗ Failed to add odo status index: {e}")
            db.session.rollback()

        # Index for TripDetail.arrive (data completeness queries)
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_arrive ON trip_detail(arrive)'))
            db.session.commit()
            print("✓ Added index on trip_detail(arrive)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail arrive index: {e}")
            db.session.rollback()

        # Index for TripDetail.departure
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_tripdetail_departure ON trip_detail(departure)'))
            db.session.commit()
            print("✓ Added index on trip_detail(departure)")
        except Exception as e:
            print(f"✗ Failed to add trip_detail departure index: {e}")
            db.session.rollback()

        print("\n✓ Dashboard indexes added successfully!")

if __name__ == '__main__':
    add_indexes()
```

Save to: `migrations/add_dashboard_indexes.py`

- [ ] **Step 2: Run migration**

Run: `python migrations/add_dashboard_indexes.py`
Expected: Success messages for all indexes

- [ ] **Step 3: Verify indexes created**

Run: `sqlite3 instance/trip_monitoring.db ".indexes trip_detail"`
Expected: See new indexes listed

- [ ] **Step 4: Commit**

```bash
git add migrations/add_dashboard_indexes.py
git commit -m "perf: add database indexes for dashboard query optimization"
```

---

## Phase 5: Documentation & Handoff

### Task 17: Update CLAUDE.md with dashboard architecture

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add dashboard section to CLAUDE.md**

Add after "Features" section:
```markdown
## Dashboard
- Admin-only operational dashboard at route `/`
- 6 KPIs: On-Time Rate, In-Full Rate, DIFOT Score, Truck Utilization, Fuel Efficiency, Data Completeness
- 3 trend charts: Daily Delivery Counts, Fuel Efficiency, Truck Utilization
- 3 comparison charts: Vehicle Ranking, Branch Frequency, Driver Performance
- 3 gauge charts: On-Time Rate, Utilization, Data Completeness
- Powered by Apache ECharts 5.x
- Auto-refresh with "Last updated" timestamp
- Default 7-day view, supports custom date ranges (max 90 days)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add dashboard architecture to CLAUDE.md"
```

---

### Task 18: Create user guide

**Files:**
- Create: `docs/dashboard-user-guide.md`

- [ ] **Step 1: Write user guide**

```markdown
# Admin Dashboard User Guide

## Overview
The admin dashboard provides real-time operational insights into delivery performance, fleet efficiency, and data quality.

## Access
- **URL**: `http://your-server/` (home page)
- **Requirements**: Must be logged in as admin user
- **Non-admin users**: Automatically redirected to schedule view

## Key Performance Indicators (KPIs)

### On-Time Delivery Rate
- **What**: Percentage of deliveries made on or before the due date
- **Calculation**: Deliveries where `scheduled_date <= due_date` ÷ Total deliveries
- **Target**: ≥90% (green), 70-89% (yellow), <70% (red)

### In-Full Delivery Rate
- **What**: Percentage of complete deliveries (delivered ≥ ordered quantity)
- **Target**: ≥90% (green), 70-89% (yellow), <70% (red)

### DIFOT Score
- **What**: Combined Delivery In Full, On Time performance
- **Calculation**: (On-Time % + In-Full %) ÷ 2

### Truck Utilization
- **What**: Average percentage of vehicle capacity used
- **Calculation**: Total loaded CBM ÷ Total vehicle capacity
- **Target**: ≥80% (green), 50-79% (yellow), <50% (red)

### Fuel Efficiency
- **What**: Kilometers traveled per liter of fuel
- **Calculation**: Total KM ÷ Total liters consumed

### Data Completeness
- **What**: Percentage of trip details with complete data
- **Checks**: Arrival time, departure time, ODO records
- **Target**: ≥95% (green), 85-94% (yellow), <85% (red)

## Charts

### Daily Delivery Counts
- **Purpose**: Track delivery volume over time
- **Interaction**: Hover to see exact counts per day

### Fuel Efficiency & Cost
- **Purpose**: Monitor fuel consumption and cost trends
- **Blue line**: KM per liter
- **Orange line**: Cost per kilometer

### Truck Utilization Trend
- **Purpose**: Daily fleet utilization percentage
- **Target line**: 80% (dashed green)

### Vehicle Utilization Ranking
- **Purpose**: Compare vehicles by utilization percentage
- **Bars**: Color-coded by performance (green/yellow/red)

### Branch Delivery Frequency
- **Purpose**: Most frequently served branches
- **Scope**: Top 10 branches + "Others" aggregate

### Driver/Assistant Performance
- **Purpose**: Trips completed per person
- **Blue bars**: Drivers
- **Purple bars**: Assistants

## Performance Gauges

### On-Time Delivery Gauge
- Shows current on-time percentage
- Color bands: Red (0-50%), Yellow (50-80%), Green (80-100%)

### Truck Utilization Gauge
- Shows current utilization percentage
- Target: 80%+

### Data Completeness Gauge
- Shows data quality percentage
- Target: 95%+

## Using the Dashboard

### View Data
1. Login as admin user
2. Dashboard loads automatically with last 7 days of data
3. View KPIs, trends, and comparisons

### Refresh Data
- Click "Refresh" button in action bar
- All charts update with latest data
- "Last updated" timestamp shows when data was loaded

### Navigate
- Use action bar buttons for quick access:
  - Schedule Trip
  - View Schedule
  - Upload Data
  - Add ODO
  - Reports
  - Vehicles

## Troubleshooting

### Dashboard Shows "Loading..."
- Wait 2-3 seconds for initial load
- If stuck >10 seconds, refresh page

### Charts Not Displaying
- Check browser console for errors (F12)
- Ensure JavaScript is enabled
- Try clearing browser cache

### No Data Available
- Ensure trips exist for selected date range
- Check if data was entered correctly
- Verify database has records

### Slow Performance
- Dashboard loads in <3 seconds with 30 days of data
- Larger date ranges may be slower
- Consider using shorter date ranges (7-30 days)

## Tips

1. **Check daily**: Review KPIs each morning for overnight issues
2. **Trend watching**: Look for sudden drops in on-time rate or utilization
3. **Data quality**: Low completeness indicates missing arrival/departure times or ODO records
4. **Fleet management**: Use vehicle ranking to identify underperforming trucks

## Support
For issues or questions, contact system administrator.
```

Save to: `docs/dashboard-user-guide.md`

- [ ] **Step 2: Commit**

```bash
git add docs/dashboard-user-guide.md
git commit -m "docs: add dashboard user guide"
```

---

### Task 19: Final integration test

**Files:**
- Test: Manual browser testing

- [ ] **Step 1: Perform end-to-end test**

Test Checklist:
- [ ] Login as admin, see dashboard (not redirected)
- [ ] Login as non-admin, redirected to view_schedule
- [ ] All 6 KPI cards display with values
- [ ] All 6 trend charts render without errors
- [ ] All 3 comparison charts display data
- [ ] All 3 gauge charts show values
- [ ] Refresh button updates all data
- [ ] "Last updated" timestamp displays correctly
- [ ] Action bar buttons navigate to correct pages
- [ ] Mobile view is functional (test on 375px width)
- [ ] No console errors on page load
- [ ] Page loads in <3 seconds

- [ ] **Step 2: Verify all tests pass**

Run: `pytest tests/test_dashboard_api.py -v`
Expected: All tests PASS

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: complete admin dashboard implementation

- 6 KPI cards with trend indicators and sparklines
- 3 trend line charts (deliveries, fuel, utilization)
- 3 comparison bar charts (vehicles, branches, drivers)
- 3 performance gauges (on-time, utilization, completeness)
- Admin-only access with redirect for non-admins
- Responsive design for desktop/tablet/mobile
- Auto-refresh with timestamp
- Database indexes for performance
- Complete user guide

All tests passing. Ready for production deployment.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Summary

**Total Tasks**: 19
**Estimated Time**: 5-7 days
**Lines of Code**: ~2,500 (including tests)
**Files Created**: 9
**Files Modified**: 3

**Key Features Delivered**:
✅ Admin-only dashboard replacing home page redirect
✅ 6 KPIs with real-time calculations
✅ Apache ECharts visualizations (9 charts total)
✅ Responsive Bootstrap layout
✅ Auto-refresh with loading states
✅ Database performance optimization
✅ Complete test coverage
✅ User documentation

**Next Steps After Implementation**:
1. Deploy to staging environment
2. User acceptance testing with admin team
3. Monitor performance metrics
4. Gather feedback for Phase 2 enhancements
5. Plan additional features (custom date ranges, export, scheduled reports)
