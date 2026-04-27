# Vehicle Route Map Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive map tab to the Location Logs page showing vehicle routes with In/Out markers and route lines.

**Architecture:** New API endpoint returns grouped location data by vehicle. Frontend uses Leaflet.js (CDN) to render markers and polylines on an OpenStreetMap base layer. Tab navigation switches between existing table view and new map view.

**Tech Stack:** Flask, SQLAlchemy, Leaflet.js, Bootstrap 5.2.3, OpenStreetMap tiles

---

## File Structure

### Files to Modify
- `app.py` - Add `/api/vehicle-routes` endpoint (after line 3279)
- `templates/location_logs.html` - Add tab navigation and map container

### Files to Create
- None (map view is added inline to location_logs.html)

---

## Task 1: Create Vehicle Routes API Endpoint

**Files:**
- Modify: `app.py` (insert after line 3279, after the `location_logs` route)

- [ ] **Step 1: Add the API endpoint**

Insert this code after line 3279 (after the `location_logs` route function ends):

```python
@app.route("/api/vehicle-routes")
@login_required
def api_vehicle_routes():
    """API endpoint returning vehicle route data for map visualization."""
    date_str = request.args.get('date')
    vehicle_id = request.args.get('vehicle_id')

    if not date_str:
        return jsonify({"success": False, "message": "Date parameter required"}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"success": False, "message": "Invalid date format"}), 400

    # Build query: location logs for the given date
    next_day = target_date + timedelta(days=1)
    query = LocationLog.query.filter(
        LocationLog.captured_at >= target_date,
        LocationLog.captured_at < next_day
    ).outerjoin(TripDetail).order_by(LocationLog.captured_at)

    if vehicle_id:
        try:
            query = query.join(Trip).filter(Trip.vehicle_id == int(vehicle_id))
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid vehicle_id"}), 400

    location_logs = query.all()

    # Group logs by vehicle, pairing In/Out for same trip_detail
    vehicles_dict = {}
    for log in location_logs:
        if log is None or log.trip_detail is None:
            continue

        trip = Trip.query.get(log.trip_detail.trip_id)
        if not trip:
            continue

        v_id = trip.vehicle_id
        if v_id not in vehicles_dict:
            vehicles_dict[v_id] = {
                'vehicle_id': v_id,
                'plate_number': trip.vehicle.plate_number if trip.vehicle else 'Unknown',
                'stops': {}
            }

        td_id = log.trip_detail_id
        if td_id not in vehicles_dict[v_id]['stops']:
            vehicles_dict[v_id]['stops'][td_id] = {
                'trip_detail_id': td_id,
                'branch': log.trip_detail.branch_name_v2,
                'delivery_order': log.trip_detail.delivery_order,
                'in_time': None,
                'out_time': None,
                'in_location': None,
                'out_location': None
            }

        stop = vehicles_dict[v_id]['stops'][td_id]
        if log.action_type == 'arrival':
            stop['in_time'] = log.captured_at.strftime('%Y-%m-%d %H:%M:%S')
            stop['in_location'] = {'lat': log.latitude, 'lng': log.longitude}
        elif log.action_type == 'departure':
            stop['out_time'] = log.captured_at.strftime('%Y-%m-%d %H:%M:%S')
            stop['out_location'] = {'lat': log.latitude, 'lng': log.longitude}

    # Convert stops dict to sorted list per vehicle
    vehicles_list = []
    for v_id, v_data in vehicles_dict.items():
        sorted_stops = sorted(
            v_data['stops'].values(),
            key=lambda s: s.get('delivery_order') or 999
        )
        vehicles_list.append({
            'vehicle_id': v_data['vehicle_id'],
            'plate_number': v_data['plate_number'],
            'stops': sorted_stops
        })

    return jsonify({
        "success": True,
        "date": date_str,
        "vehicles": vehicles_list
    })
```

- [ ] **Step 2: Verify Flask loads**

Run: `.venv/bin/python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add /api/vehicle-routes endpoint for map visualization"
```

---

## Task 2: Add Tab Navigation to Location Logs Page

**Files:**
- Modify: `templates/location_logs.html`

- [ ] **Step 1: Wrap existing content in tabs**

Read the current `templates/location_logs.html`. The file has this structure:
- Lines 1-2: extends/title blocks
- Lines 3-8: header with title and back button
- Lines 10-50: filter form card
- Lines 52-151: location logs table card

We need to:
1. Add a tab navigation bar after the header (after line 8)
2. Wrap existing table content in a tab pane
3. Add a map view tab pane

Find the header section (around line 3-8):
```html
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
  <h1><i class="bi bi-geo-alt"></i> Location Logs</h1>
  <a href="{{ url_for('view_schedule') }}" class="btn btn-outline-secondary">Back to Schedules</a>
</div>
```

After this header div and before the filter form, insert the tab navigation:

```html
<!-- Tab Navigation -->
<ul class="nav nav-tabs mb-3" id="locationLogsTabs" role="tablist">
  <li class="nav-item" role="presentation">
    <button class="nav-link active" id="table-tab" data-bs-toggle="tab" data-bs-target="#table-view" type="button" role="tab">
      <i class="bi bi-table"></i> Table View
    </button>
  </li>
  <li class="nav-item" role="presentation">
    <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#map-view" type="button" role="tab">
      <i class="bi bi-map"></i> Map View
    </button>
  </li>
</ul>

<!-- Tab Content -->
<div class="tab-content" id="locationLogsTabContent">

<!-- Table View Tab Pane -->
<div class="tab-pane fade show active" id="table-view" role="tabpanel">
```

Then at the very end of the file (before `{% endblock %}`), close the table-view div and add the map-view div:

Find `{% endblock %}` at the end of the file and replace it with:

```html
</div><!-- end table-view -->

<!-- Map View Tab Pane -->
<div class="tab-pane fade" id="map-view" role="tabpanel">

  <!-- Map Controls -->
  <div class="card mb-3">
    <div class="card-body">
      <div class="row g-3 align-items-end">
        <div class="col-md-3">
          <label for="map-date" class="form-label">Date</label>
          <input type="date" class="form-control" id="map-date" value="{{ today }}" max="{{ today }}">
        </div>
        <div class="col-md-3">
          <label for="map-vehicle" class="form-label">Vehicle</label>
          <select class="form-select" id="map-vehicle">
            <option value="">All Vehicles</option>
          </select>
        </div>
        <div class="col-md-2">
          <button type="button" class="btn btn-primary w-100" id="btn-load-map">
            <i class="bi bi-search"></i> Load
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Map Container -->
  <div class="card">
    <div class="card-body p-0">
      <div id="vehicle-map" style="height: 600px; border-radius: 0.375rem;"></div>
    </div>
  </div>

  <!-- Empty State for Map -->
  <div id="map-empty-state" class="alert alert-info mt-3" style="display: none;">
    <i class="bi bi-info-circle"></i> No location data found for the selected date.
  </div>

  <!-- Vehicle Legend -->
  <div id="map-legend" class="card mt-3" style="display: none;">
    <div class="card-header">
      <h6 class="mb-0"><i class="bi bi-palette"></i> Vehicle Legend</h6>
    </div>
    <div class="card-body">
      <div id="legend-items" class="d-flex flex-wrap gap-3"></div>
    </div>
  </div>

</div><!-- end map-view -->

</div><!-- end tab-content -->
{% endblock %}
```

- [ ] **Step 2: Add today variable to the location_logs route**

In `app.py`, find the `render_template` call in the `location_logs` function (around line 3271) and add `today=datetime.now().strftime('%Y-%m-%d')`:

Change:
```python
    return render_template(
        'location_logs.html',
        location_logs=pagination.items,
        pagination=pagination,
        users=users,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action_type=action_type
    )
```

To:
```python
    return render_template(
        'location_logs.html',
        location_logs=pagination.items,
        pagination=pagination,
        users=users,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action_type=action_type,
        today=datetime.now().strftime('%Y-%m-%d')
    )
```

- [ ] **Step 3: Verify Flask loads**

Run: `.venv/bin/python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add templates/location_logs.html app.py
git commit -m "feat: add tab navigation and map container to location logs page"
```

---

## Task 3: Add Leaflet.js and Map JavaScript

**Files:**
- Modify: `templates/location_logs.html` (add before `{% endblock %}`)

- [ ] **Step 1: Add Leaflet CSS and JS CDN links**

In the map-view tab pane, before the closing `</div><!-- end map-view -->`, add the Leaflet CDN and all the map JavaScript.

Insert this code just before `</div><!-- end map-view -->`:

```html
<!-- Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>
// Vehicle Route Map
(function() {
  const VEHICLE_COLORS = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
    '#dcbeff', '#9A6324', '#800000', '#aaffc3', '#808000',
    '#ffd8b1', '#000075', '#a9a9a9'
  ];

  let map = null;
  let markersGroup = null;
  let linesGroup = null;

  function initMap() {
    if (map) return;

    map = L.map('vehicle-map').setView([14.606, 121.091], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);
    linesGroup = L.layerGroup().addTo(map);

    // Load routes on init
    loadVehicleRoutes();
  }

  function createInIcon(color) {
    return L.divIcon({
      className: 'custom-div-icon',
      html: '<div style="background:' + color + ';width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4);"></div>',
      iconSize: [14, 14],
      iconAnchor: [7, 7]
    });
  }

  function createOutIcon(color) {
    return L.divIcon({
      className: 'custom-div-icon',
      html: '<div style="background:' + color + ';width:12px;height:12px;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4);transform:rotate(45deg);"></div>',
      iconSize: [12, 12],
      iconAnchor: [6, 6]
    });
  }

  function formatTime(timeStr) {
    if (!timeStr) return '—';
    return timeStr.split(' ')[1] || timeStr;
  }

  function buildPopupContent(stop, plateNumber) {
    let html = '<div style="min-width:200px;">';
    html += '<strong>' + (stop.branch || 'Unknown Branch') + '</strong><br>';
    html += '<small class="text-muted">' + plateNumber + '</small><hr style="margin:5px 0;">';
    html += '<table style="font-size:12px;width:100%;">';
    html += '<tr><td><span style="color:#28a745;">&#9679;</span> In:</td><td>' + formatTime(stop.in_time) + '</td></tr>';
    html += '<tr><td><span style="color:#fd7e14;">&#9670;</span> Out:</td><td>' + formatTime(stop.out_time) + '</td></tr>';
    html += '</table>';
    if (stop.in_location) {
      html += '<a href="https://www.google.com/maps?q=' + stop.in_location.lat + ',' + stop.in_location.lng + '" target="_blank" style="font-size:11px;">View on Google Maps</a>';
    }
    html += '</div>';
    return html;
  }

  function loadVehicleRoutes() {
    const date = document.getElementById('map-date').value;
    const vehicleId = document.getElementById('map-vehicle').value;

    if (!date) {
      alert('Please select a date');
      return;
    }

    // Clear existing layers
    markersGroup.clearLayers();
    linesGroup.clearLayers();

    // Build URL
    let url = '/api/vehicle-routes?date=' + date;
    if (vehicleId) url += '&vehicle_id=' + vehicleId;

    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (!data.success) {
          alert('Error: ' + data.message);
          return;
        }

        const vehicles = data.vehicles;
        const emptyState = document.getElementById('map-empty-state');
        const legend = document.getElementById('map-legend');
        const legendItems = document.getElementById('legend-items');

        // Handle empty state
        if (!vehicles || vehicles.length === 0) {
          emptyState.style.display = 'block';
          legend.style.display = 'none';
          return;
        }

        emptyState.style.display = 'none';
        legend.style.display = 'block';

        // Populate vehicle filter dropdown if not already populated
        if (!vehicleId) {
          const select = document.getElementById('map-vehicle');
          if (select.options.length <= 1) {
            vehicles.forEach(function(v) {
              const opt = document.createElement('option');
              opt.value = v.vehicle_id;
              opt.textContent = v.plate_number;
              select.appendChild(opt);
            });
          }
        }

        // Build legend
        legendItems.innerHTML = '';
        const allCoords = [];

        vehicles.forEach(function(vehicle, vIndex) {
          const color = VEHICLE_COLORS[vIndex % VEHICLE_COLORS.length];

          // Legend item
          const legendItem = document.createElement('div');
          legendItem.className = 'd-flex align-items-center';
          legendItem.innerHTML = '<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:' + color + ';margin-right:6px;"></span>' +
            '<strong>' + vehicle.plate_number + '</strong>' +
            '<span class="badge bg-secondary ms-2">' + vehicle.stops.length + ' stops</span>';
          legendItems.appendChild(legendItem);

          // Draw stops
          const routeCoords = [];

          vehicle.stops.forEach(function(stop) {
            // In marker
            if (stop.in_location) {
              const inMarker = L.marker(
                [stop.in_location.lat, stop.in_location.lng],
                { icon: createInIcon(color) }
              );
              inMarker.bindPopup(buildPopupContent(stop, vehicle.plate_number));
              markersGroup.addLayer(inMarker);
              routeCoords.push([stop.in_location.lat, stop.in_location.lng]);
              allCoords.push([stop.in_location.lat, stop.in_location.lng]);
            }

            // Out marker
            if (stop.out_location) {
              const outMarker = L.marker(
                [stop.out_location.lat, stop.out_location.lng],
                { icon: createOutIcon(color) }
              );
              outMarker.bindPopup(buildPopupContent(stop, vehicle.plate_number));
              markersGroup.addLayer(outMarker);
              routeCoords.push([stop.out_location.lat, stop.out_location.lng]);
              allCoords.push([stop.out_location.lat, stop.out_location.lng]);
            }

            // Route line from In to Out for same stop
            if (stop.in_location && stop.out_location) {
              const line = L.polyline([
                [stop.in_location.lat, stop.in_location.lng],
                [stop.out_location.lat, stop.out_location.lng]
              ], {
                color: color,
                weight: 3,
                opacity: 0.7,
                dashArray: '6, 4'
              });
              linesGroup.addLayer(line);
            }
          });

          // Full route line connecting all stops in order
          if (routeCoords.length > 1) {
            const fullLine = L.polyline(routeCoords, {
              color: color,
              weight: 2,
              opacity: 0.4
            });
            linesGroup.addLayer(fullLine);
          }
        });

        // Fit map to show all markers
        if (allCoords.length > 0) {
          const bounds = L.latLngBounds(allCoords);
          map.fitBounds(bounds, { padding: [30, 30] });
        }
      })
      .catch(error => {
        console.error('Error loading vehicle routes:', error);
        alert('Failed to load vehicle route data');
      });
  }

  // Initialize map when tab is shown
  document.getElementById('map-tab').addEventListener('shown.bs.tab', function() {
    initMap();
    setTimeout(function() { map.invalidateSize(); }, 100);
  });

  // Load button click
  document.getElementById('btn-load-map').addEventListener('click', loadVehicleRoutes);

  // Date change - reload
  document.getElementById('map-date').addEventListener('change', function() {
    if (map) loadVehicleRoutes();
  });

  // Vehicle filter change - reload
  document.getElementById('map-vehicle').addEventListener('change', function() {
    if (map) loadVehicleRoutes();
  });
})();
</script>
```

- [ ] **Step 2: Verify Flask loads**

Run: `.venv/bin/python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add templates/location_logs.html
git commit -m "feat: add Leaflet.js map with vehicle route visualization"
```

---

## Task 4: Add Navigation Link from Location Logs Table View

**Files:**
- Modify: `templates/location_logs.html`

- [ ] **Step 1: Add a "View on Map" link in the table view header**

In the Location Logs table card header (find `<h6 class="mb-0">Location History`), add a small map link button next to it:

Find:
```html
    <h6 class="mb-0">Location History ({{ pagination.total }} records)</h6>
```

Replace with:
```html
    <div class="d-flex justify-content-between align-items-center">
      <h6 class="mb-0">Location History ({{ pagination.total }} records)</h6>
      <button class="btn btn-sm btn-outline-primary" id="switch-to-map-btn">
        <i class="bi bi-map"></i> View on Map
      </button>
    </div>
```

- [ ] **Step 2: Add JavaScript to handle the switch-to-map button**

In the map JavaScript section, add this click handler inside the IIFE:

```javascript
  // Switch to map tab from table view button
  document.getElementById('switch-to-map-btn').addEventListener('click', function() {
    const mapTab = document.getElementById('map-tab');
    const tab = new bootstrap.Tab(mapTab);
    tab.show();
  });
```

- [ ] **Step 3: Commit**

```bash
git add templates/location_logs.html
git commit -m "feat: add 'View on Map' button in table view header"
```

---

## Task 5: Test and Verify

**Files:**
- None (manual verification)

- [ ] **Step 1: Verify table view still works**

1. Navigate to Location Logs page
2. Table view should show as before
3. Filters should still work

- [ ] **Step 2: Test map view tab**

1. Click "Map View" tab
2. Expected: Map loads centered on Philippines
3. Date defaults to today
4. If location data exists, markers and routes should appear

- [ ] **Step 3: Test vehicle filter**

1. Select a specific vehicle from dropdown
2. Click "Load"
3. Expected: Only that vehicle's routes shown

- [ ] **Step 4: Test date selection**

1. Pick a date with known location data
2. Click "Load"
3. Expected: Map shows routes for that date

- [ ] **Step 5: Test marker popups**

1. Click any marker on map
2. Expected: Popup shows branch name, plate number, In/Out times

- [ ] **Step 6: Test "View on Map" button**

1. Go to Table View
2. Click "View on Map" button
3. Expected: Switches to Map View tab

- [ ] **Step 7: Test empty state**

1. Select a date with no location data
2. Expected: Shows "No location data found" message

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup for vehicle route map feature"
```

---

## Completion Checklist

- [ ] API endpoint returns correct vehicle route data
- [ ] Tab navigation works (Table View ↔ Map View)
- [ ] Map loads with Leaflet.js
- [ ] In markers are green circles
- [ ] Out markers are orange diamonds
- [ ] Route lines connect stops per vehicle
- [ ] Vehicle filter works
- [ ] Date picker defaults to today
- [ ] Popups show branch, times, vehicle
- [ ] Vehicle legend shows colors and stop counts
- [ ] Empty state shows when no data
- [ ] "View on Map" button in table view works
