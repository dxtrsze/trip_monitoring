# Vehicle Route Map Visualization Design

**Date:** 2026-04-27
**Status:** Design Approved
**Author:** Dexter Sze + Claude

## Overview

Add an interactive map tab to the Location Logs page that visualizes vehicle movements throughout the day. Users can see all In/Out locations as map markers, view route lines connecting stops, filter by vehicle, and click markers for details.

## Requirements

### Functional Requirements
- [ ] Add "Map View" tab to Location Logs page
- [ ] Display all In/Out locations as colored markers on map
- [ ] Show route lines connecting In→Out for each vehicle
- [ ] Allow filtering by vehicle
- [ ] Date picker to select which day to view (defaults to today)
- [ ] Click markers to see details (branch, time, vehicle name)
- [ ] Different marker styles for In vs Out actions
- [ ] Color-coded routes per vehicle

### Non-Functional Requirements
- Use Leaflet.js for mapping (no API key required)
- Map should be responsive and work on mobile
- Page load should be fast with efficient queries
- Handle cases with no location data gracefully

## Architecture

### UI Structure

**Location Logs Page with Two Tabs:**

```
Location Logs Page
├── [Table View] (current)
│   └── Filters + paginated table
└── [Map View] (new)
    ├── Date picker + vehicle filter
    ├── Interactive Leaflet map
    └── Vehicle legend
```

### Components

**1. Date Picker & Filter Bar**
- Date input: defaults to today, max date = today
- Vehicle dropdown: "All Vehicles" + list of vehicles with routes
- Filter applies on change (no submit button needed)

**2. Leaflet Map**
- Full-width map container
- Auto-fit to show all markers
- Base layer: OpenStreetMap tiles
- Marker clusters for close locations
- Click marker → show details in popup/sidebar

**3. Markers**
- **In locations**: Green circle icon (📍)
- **Out locations**: Orange square icon (🏁)
- Clustered locations: Circle marker with number
- Click → popup with details

**4. Route Lines**
- Polyline connecting In→Out for each route
- Color-coded by vehicle (different colors per vehicle)
- Dashed lines for visual distinction
- Click route → highlight that vehicle's markers

**5. Details Panel (Sidebar or Popup)**
Shows when marker is clicked:
- Branch name
- Vehicle name/plate
- Time In
- Time Out
- Coordinates (with link to Google Maps)

## Data Model

### API Endpoint

**New Route:** `GET /api/vehicle-routes`

**Query Parameters:**
- `date` (required): Date in YYYY-MM-DD format
- `vehicle_id` (optional): Filter by specific vehicle

**Response Format:**
```json
{
  "date": "2026-04-27",
  "vehicles": [
    {
      "vehicle_id": 123,
      "vehicle_name": "ABC 1234",
      "plate_number": "ABC-1234",
      "driver_name": "John Doe",
      "routes": [
        {
          "trip_detail_id": 456,
          "branch": "WESTERN MOLINO",
          "in_time": "2026-04-27 09:30:00",
          "out_time": "2026-04-27 10:15:00",
          "in_location": {"lat": 14.606673, "lng": 121.091546},
          "out_location": {"lat": 14.606673, "lng": 121.091546}
        }
      ]
    }
  ]
}
```

**Query Logic:**
```python
def get_vehicle_routes(date, vehicle_id=None):
    # Get all location logs for the date
    query = LocationLog.query.filter(
        func.date(LocationLog.captured_at) == date
    ).join(TripDetail).order_by(LocationLog.captured_at)
    
    if vehicle_id:
        query = query.filter(TripDetail.vehicle.has(vehicle_id=vehicle_id))
    
    location_logs = query.all()
    
    # Group by vehicle
    vehicles = {}
    for log in location_logs:
        vehicle_id = log.trip_detail.vehicle.id
        if vehicle_id not in vehicles:
            vehicles[vehicle_id] = {
                'vehicle_id': vehicle_id,
                'plate_number': log.trip_detail.vehicle.plate_number,
                'routes': []
            }
        
        # Add to routes
        vehicles[vehicle_id]['routes'].append({
            'trip_detail_id': log.trip_detail.id,
            'branch': log.trip_detail.branch_name_v2,
            'in_time': log.captured_at if log.action_type == 'arrival' else None,
            'out_time': log.captured_at if log.action_type == 'departure' else None,
            'in_location': {'lat': log.latitude, 'lng': log.longitude},
            'out_location': {'lat': log.latitude, 'lng': log.longitude}
        })
    
    # Pair up In/Out routes
    for vehicle in vehicles.values():
        paired_routes = []
        i = 0
        while i < len(vehicle['routes']):
            in_route = vehicle['routes'][i]
            if in_route['in_time']:
                # Find matching out
                for j in range(i+1, len(vehicle['routes'])):
                    if vehicle['routes'][j]['out_time']:
                        paired_routes.append({
                            'trip_detail_id': in_route['trip_detail_id'],
                            'branch': in_route['branch'],
                            'in_time': in_route['in_time'],
                            'out_time': vehicle['routes'][j]['out_time'],
                            'in_location': in_route['in_location'],
                            'out_location': vehicle['routes'][j]['out_location']
                        })
                        break
                i += 1
            else:
                i += 1
        
        vehicle['routes'] = paired_routes
    
    return list(vehicles.values())
```

### Frontend Implementation

**New Template:** `templates/location_logs_map.html`

**Key Components:**

1. **Tab Navigation:**
```html
<ul class="nav nav-tabs" role="tablist">
  <li class="nav-item">
    <a class="nav-link active" data-bs-toggle="tab" href="#table-view">Table View</a>
  </li>
  <li class="nav-item">
    <a class="nav-link" data-bs-toggle="tab" href="#map-view">Map View</a>
  </li>
</ul>
```

2. **Map Container:**
```html
<div class="tab-pane fade" id="map-view">
  <div class="d-flex gap-3 mb-3">
    <input type="date" class="form-control" id="map-date" max="{{ today }}">
    <select class="form-select" id="vehicle-filter">
      <option value="">All Vehicles</option>
    </select>
  </div>
  <div id="map" style="height: 600px;"></div>
</div>
```

3. **Leaflet Initialization:**
```javascript
// Initialize map
const map = L.map('map').setView([14.606, 121.091], 11);

// Add tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Load vehicle routes and render
```

4. **Vehicle Colors:**
```javascript
const vehicleColors = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#D4A5A9', '#9B59B6', '#FF8A65', '#3E2723', '#1ABC9C'
];
```

5. **Markers:**
```javascript
// In marker (green circle)
const inIcon = L.divIcon({
  className: 'custom-div-icon',
  html: '<div style="background: #28a745; width: 16px; height:16px; border-radius: 50%; border: 2px solid white;"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8]
});

// Out marker (orange square)
const outIcon = L.divIcon({
  className: 'custom-div-icon',
  html: '<div style="background: #fd7e14; width: 14px; height:14px; border: 1px solid white;"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});
```

6. **Route Lines:**
```javascript
// Polyline for route
const routeLine = L.polyline([
  [in_coords.lat, in_coords.lng],
  [out_coords.lat, out_coords.lng]
], {
  color: vehicleColors[vehicleIndex % vehicleColors.length],
  weight: 3,
  opacity: 0.7,
  dashArray: '5, 5'
}).addTo(map);
```

## Implementation Plan

### Phase 1: Backend API
1. Create `/api/vehicle-routes` endpoint
2. Implement vehicle route grouping logic
3. Handle date filtering and vehicle filtering
4. Test API returns correct data structure

### Phase 2: Frontend Map View
1. Add tab navigation to Location Logs page
2. Create location_logs_map.html template
3. Integrate Leaflet.js
4. Implement date picker and vehicle filter
5. Add map initialization logic

### Phase 3: Map Interactivity
1. Add marker click handlers with popups
2. Implement route line rendering
3. Add vehicle legend
4. Handle empty state (no locations for selected date)
5. Add loading states

### Phase 4: Polish
1. Add vehicle color consistency
2. Optimize for multiple vehicles
3. Add responsive design
4. Test on different devices

## File Structure

### Files to Create
- `templates/location_logs_map.html` - Map view template

### Files to Modify
- `app.py` - Add `/api/vehicle-routes` endpoint
- `templates/location_logs.html` - Add tab navigation

## Edge Cases

- **No location data for selected date**: Show empty state message
- **Orphaned location logs** (trip_detail deleted): Skip gracefully
- **Single location (In only)**: Show marker without route line
- **Many locations**: Use marker clustering for performance
- **Overlapping routes**: Use semi-transparent lines

## Success Criteria

- [ ] Map displays correctly for today's date by default
- [ ] Vehicle filter works to show specific vehicle routes
- [ ] Markers show correct colors for In vs Out
- [ ] Route lines connect In→Out points properly
- [ ] Clicking markers shows branch, time, vehicle details
- [ ] All vehicles have distinct colors
- [ ] Page loads quickly with no errors

## Future Enhancements (Out of Scope)

- Animate route playback (show movement over time)
- Heat map of frequent locations
- Export route data as GPX for GPS devices
- Show vehicle capacity utilization on routes
- Optimize route suggestions based on historical data
