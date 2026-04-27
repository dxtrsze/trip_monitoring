# Browser Location Capture for In/Out Actions

**Date:** 2026-04-27
**Status:** Design Approved
**Author:** Dexter Sze + Claude

## Overview

When users click **In** or **Out** buttons on delivery schedules, the browser will capture the user's current location (latitude, longitude, timestamp) and send it to the server. If location cannot be obtained or permission is denied, the action is blocked with a clear error message.

## Requirements

### Functional Requirements
- [ ] Capture browser location (latitude, longitude) when user clicks In or Out
- [ ] Block the action if location permission is denied or unavailable
- [ ] Store location data in a new database table
- [ ] Provide admin interface to view location history
- [ ] 10-second timeout for location acquisition

### Non-Functional Requirements
- Location must be obtained before timestamp is recorded
- Clear error messages for all failure scenarios
- No degradation of existing In/Out functionality
- Location data should be queryable for auditing

## Architecture

### Database Schema

**New Table: `location_log`**

```sql
CREATE TABLE location_log (
    id SERIAL PRIMARY KEY,
    trip_detail_id INTEGER NOT NULL REFERENCES trip_detail(id),
    action_type VARCHAR(20) NOT NULL, -- 'arrival' or 'departure'
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    captured_at TIMESTAMP NOT NULL,  -- When location was captured
    user_id INTEGER NOT NULL REFERENCES user(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_location_log_trip_detail ON location_log(trip_detail_id);
CREATE INDEX idx_location_log_user ON location_log(user_id);
CREATE INDEX idx_location_log_created ON location_log(created_at);
```

### API Changes

**Modified Endpoints:**

1. `POST /record_arrival` - Now accepts optional location data
   ```json
   {
     "branch_name_v2": "string",
     "schedule_id": int,
     "trip_number": int,
     "reason": "string",
     "latitude": float,
     "longitude": float
   }
   ```

2. `POST /record_departure` - Now accepts optional location data
   ```json
   {
     "branch_name_v2": "string",
     "schedule_id": int,
     "trip_number": int,
     "reason": "string",
     "latitude": float,
     "longitude": float
   }
   ```

**New Endpoints:**

3. `GET /location_logs` - Admin page to view location history
   - Query params: `start_date`, `end_date`, `user_id`, `action_type`
   - Returns paginated list of location logs

### Frontend Changes

**JavaScript in `templates/view_schedule.html`:**

Wrap the existing fetch calls for arrival/departure with geolocation:

```javascript
function recordArrivalWithLocation(branchName, scheduleId, tripNumber, reason) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject('Geolocation is not supported by your browser');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const locationData = {
          branch_name_v2: branchName,
          schedule_id: scheduleId,
          trip_number: tripNumber,
          reason: reason,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        };
        fetch('/record_arrival', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(locationData)
        })
        .then(response => response.json())
        .then(data => data.success ? resolve(data) : reject(data.message))
        .catch(reject);
      },
      (error) => {
        switch(error.code) {
          case error.PERMISSION_DENIED:
            reject('Location access is required to record In/Out. Please enable location permissions in your browser.');
            break;
          case error.TIMEOUT:
            reject('Could not get your location in time. Please try again.');
            break;
          default:
            reject('Unable to get your location. Please check your device settings.');
        }
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  });
}
```

Same pattern for `recordDepartureWithLocation()`.

### Backend Changes

**New Model: `LocationLog`** (in `models.py`)

```python
class LocationLog(db.Model):
    __tablename__ = 'location_log'

    id = db.Column(db.Integer, primary_key=True)
    trip_detail_id = db.Column(db.Integer, db.ForeignKey('trip_detail.id'), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)  # 'arrival' or 'departure'
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    captured_at = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo('Asia/Manila')))

    trip_detail = db.relationship('TripDetail', backref='location_logs')
    user = db.relationship('User', backref='location_logs')
```

**Updated Route Handlers:**

Modify `record_arrival()` and `record_departure()` in `app.py`:
- Extract latitude/longitude from request if present
- If provided, create LocationLog entry
- Then proceed with existing logic

**New Route:** `/location_logs`
- Admin-only access
- Renders `location_logs.html` template
- Supports filtering by date range, user, action type

### Admin Interface

**New Template: `templates/location_logs.html`**

Features:
- Filterable table with columns:
  - Date/Time
  - User
  - Branch
  - Action (In/Out)
  - Coordinates (clickable Google Maps link)
  - View on Map button
- Export to CSV functionality
- Pagination

## Error Messages

| Scenario | Message |
|----------|---------|
| Permission denied | "Location access is required to record In/Out. Please enable location permissions in your browser." |
| Timeout (10s) | "Could not get your location in time. Please try again." |
| Position unavailable | "Unable to get your location. Please check your device settings and try again." |
| Browser not supported | "Geolocation is not supported by your browser. Please use a modern browser." |

## Implementation Plan

1. **Database Migration** - Create `location_log` table
2. **Model** - Add `LocationLog` class to `models.py`
3. **Backend Routes** - Update arrival/departure endpoints, add location logs viewer
4. **Frontend** - Modify click handlers in `view_schedule.html` to capture location
5. **Admin Page** - Create `location_logs.html` template and route
6. **Testing** - Verify location capture, error handling, and admin viewing

## Testing Checklist

- [ ] In button captures location and records arrival
- [ ] Out button captures location and records departure
- [ ] Permission denied shows error and blocks action
- [ ] Timeout shows error and blocks action
- [ ] Successful action shows same success message as before
- [ ] Admin can view location logs
- [ ] Filters work correctly on admin page
- [ ] Google Maps links are correct

## Success Criteria

- All In/Out actions require location to succeed
- Location data is accurately captured and stored
- Admin can audit location history
- No regression in existing In/Out functionality
