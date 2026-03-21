# Driver/Assistant Time Log Matrix Report Design

**Date:** 2026-03-21
**Status:** Approved (Revised after review)
**Author:** Claude (Sonnet 4.6)

## Overview

Create a new report that displays driver and assistant TimeLog data in a matrix format, with personnel as rows and dates as columns. This report will be added as a separate card in the existing Reports page alongside other report types.

## Problem Statement

Currently, TimeLog data for drivers and assistants is shown in the "Missing Data Report" as a simple list. Users need a better way to:
- View time logs across multiple dates at a glance
- Identify patterns in attendance (missing days, incomplete clock-outs)
- See which drivers/assistants have complete vs incomplete time logs
- Compare time logs across all assigned personnel for a date range

**Scope Clarification:** This report shows ONLY drivers and assistants who were assigned to trips within the selected date range. Personnel who were not assigned to any trips (even if they have TimeLog entries) will not appear. This aligns with the operational nature of the system - we're reporting on trip-related activity, not all personnel time logs.

## Database Structure

### Relevant Models

**Manpower Model:**
- `id`: Primary key
- `name`: Person's name
- `role`: "Driver" or "Assistant"
- `user_id`: Foreign key to User (optional, nullable)

**Trip Model:**
- Many-to-many relationship with Manpower through:
  - `trip_driver` association table
  - `trip_assistant` association table

**User Model:**
- `id`: Primary key
- Linked to Manpower via `user_id`

**TimeLog Model:**
- `id`: Primary key
- `user_id`: Foreign key to User (required)
- `time_in`: DateTime (required)
- `time_out`: DateTime (nullable)
- Relationship: TimeLog → User → Manpower

### Key Relationship Chain

```
Trip → trip_driver/trip_assistant → Manpower → User → TimeLog
```

## API Design

### New Endpoint

**Route:** `GET /driver_assistant_time_logs`

**Query Parameters:**
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- Maximum date range: 90 days

**Validation:**
```python
from datetime import datetime, timedelta

# Parse and validate dates
try:
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
except ValueError:
    return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

# Validate date range
if start_date > end_date:
    return jsonify({'error': 'Start date must be before or equal to end date'}), 400

delta = end_date - start_date
if delta.days > 90:
    return jsonify({'error': 'Date range cannot exceed 90 days'}), 400

# Include the entire end date
end_date = end_date + timedelta(days=1)
```

**Response Structure:**

```json
{
  "personnel": [
    {
      "manpower_id": 1,
      "name": "Juan Dela Cruz",
      "role": "Driver",
      "dates": {
        "2026-03-15": {
          "time_in": "08:00 AM",
          "time_out": "05:00 PM"
        },
        "2026-03-16": {
          "time_in": "08:15 AM",
          "time_out": "Missing"
        },
        "2026-03-17": {
          "time_in": "Missing",
          "time_out": "Missing"
        }
      }
    }
  ],
  "date_range": {
    "start": "2026-03-15",
    "end": "2026-03-20",
    "dates": [
      "2026-03-15",
      "2026-03-16",
      "2026-03-17",
      "2026-03-18",
      "2026-03-19",
      "2026-03-20"
    ]
  }
}
```

**Response Fields:**
- `personnel`: Array of all drivers/assistants assigned to trips in date range
- `manpower_id`: Unique identifier for the person
- `name`: Person's full name
- `role`: Either "Driver" or "Assistant"
- `dates`: Object with all dates in range as keys
  - Each date contains `time_in` and `time_out` as formatted strings or "Missing"
- `date_range`: Metadata about the query
  - `dates`: Ordered array of date strings for building table headers

**Error Responses:**
- `400 Bad Request`: Invalid date format, date range exceeds 90 days, start_date > end_date
- `403 Forbidden`: Non-admin user attempts access
- `500 Internal Server Error`: Database query error

## Database Query Strategy

### Step 1: Get Assigned Personnel

Query all unique drivers and assistants assigned to trips in the date range using UNION:

```python
manpower_assignments = db.session.query(
    Schedule.delivery_schedule,
    Manpower.id,
    Manpower.name,
    Manpower.role,
    Manpower.user_id
).join(Trip, Trip.schedule_id == Schedule.id)
.join(trip_driver, Trip.id == trip_driver.c.trip_id)
.join(Manpower, Manpower.id == trip_driver.c.manpower_id)
.filter(
    Schedule.delivery_schedule >= start_date,
    Schedule.delivery_schedule < end_date
).union(
    db.session.query(
        Schedule.delivery_schedule,
        Manpower.id,
        Manpower.name,
        Manpower.role,
        Manpower.user_id
    ).join(Trip, Trip.schedule_id == Schedule.id)
    .join(trip_assistant, Trip.id == trip_assistant.c.trip_id)
    .join(Manpower, Manpower.id == trip_assistant.c.manpower_id)
    .filter(
        Schedule.delivery_schedule >= start_date,
        Schedule.delivery_schedule < end_date
    )
).order_by(Manpower.name, Manpower.role).all()
```

**Key points:**
- Use `union()` instead of `union_all()` to eliminate duplicate personnel entries
- Add `order_by(Manpower.name, Manpower.role)` for consistent, deterministic results
- Sort by name first, then role to group same-name personnel by role
- Capture `user_id` (nullable) for TimeLog lookup
- Include all dates the person was assigned to work

### Step 2: Get TimeLog Records

Fetch all TimeLog records for the date range:

```python
from sqlalchemy import cast, Date

time_logs = db.session.query(TimeLog).filter(
    cast(TimeLog.time_in, Date) >= start_date,
    cast(TimeLog.time_in, Date) < end_date
).all()
```

**Night Shift Limitation:** TimeLog entries are matched to dates using `time_in` date only. If someone works a night shift (e.g., 11:00 PM to 7:00 AM next day), the TimeLog will only appear on the `time_in` date. This is a known limitation that could be addressed in a future enhancement by showing the entry on both days or using a different matching strategy.

### Step 3: Build Lookup Dictionaries

Create efficient lookup structures:

```python
# Personnel lookup: (manpower_id, role) → {name, user_id, assigned_dates}
personnel_dict = {}

# TimeLog lookup: (date, user_id) → {time_in, time_out}
timelog_dict = {}
for tl in time_logs:
    tl_date = tl.time_in.date()
    key = (tl_date, tl.user_id)
    timelog_dict[key] = {
        'time_in': tl.time_in.strftime('%I:%M %p') if tl.time_in else None,
        'time_out': tl.time_out.strftime('%I:%M %p') if tl.time_out else None
    }
```

### Step 4: Pivot Data into Matrix

For each person, iterate through all dates in range and build the dates object:

```python
personnel_list = []
date_list = []

# Generate list of all dates in range
current_date = start_date
while current_date < end_date:
    date_list.append(current_date.strftime('%Y-%m-%d'))
    current_date += timedelta(days=1)

# Build matrix for each person
for person in unique_personnel:
    dates_dict = {}
    for date_str in date_list:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        if person.user_id is None:
            # No user account linked
            dates_dict[date_str] = {
                'time_in': 'Missing',
                'time_out': 'Missing'
            }
        else:
            key = (date_obj, person.user_id)
            if key in timelog_dict:
                dates_dict[date_str] = {
                    'time_in': timelog_dict[key]['time_in'] or 'Missing',
                    'time_out': timelog_dict[key]['time_out'] or 'Missing'
                }
            else:
                # No TimeLog record for this date
                dates_dict[date_str] = {
                    'time_in': 'Missing',
                    'time_out': 'Missing'
                }

    personnel_list.append({
        'manpower_id': person.manpower_id,
        'name': person.name,
        'role': person.role,
        'dates': dates_dict
    })
```

## Frontend Design

### Report Card Structure

**Location:** Add as 7th card in the reports page grid (after Missing Data Report)

**Card Configuration:**
- Background color: `bg-info` (light blue, distinct from other cards)
  - Note: `bg-primary` is used by "Scheduled Tripping Reports", `bg-dark` by "Missing Data Report"
- Icon: `<i class="bi bi-clock-history"></i>`
- Title: "Driver/Assistant Time Logs"
- Grid position: Will be the 7th card in the grid layout (row 3, column 1 if maintaining 3-per-row layout)

**Current card layout:**
- Row 1: Scheduled Tripping (primary), Truck Load (success), Truck Utilization (info)
- Row 2: Fuel Efficiency (warning), Frequency Rate (secondary), DIFOT (danger)
- Row 2 (continued): Missing Data (dark)
- Row 3: Driver/Assistant Time Logs (info) ← NEW

**Form Elements:**
- Start Date input (type="date")
- End Date input (type="date")
- Submit button: "View Time Logs"
- Both dates default to last 7 days (consistent with other reports)

### Results Display

**Table Structure:**

```html
<div class="card mt-4" id="timeLogMatrixResults" style="display:none;">
  <div class="card-header d-flex justify-content-between align-items-center bg-primary text-white">
    <h5><i class="bi bi-clock-history"></i> Driver/Assistant Time Log Matrix</h5>
    <div>
      <span id="timeLogDateRange" class="me-3"></span>
      <button type="button" class="btn btn-sm btn-light" id="exportTimeLogBtn">
        <i class="bi bi-download"></i> Export CSV
      </button>
    </div>
  </div>
  <div class="card-body">
    <div class="table-responsive">
      <table class="table table-striped table-hover" id="timeLogMatrixTable">
        <thead>
          <tr>
            <th>Name</th>
            <th>Role</th>
            <!-- Date columns added dynamically -->
          </tr>
        </thead>
        <tbody id="timeLogMatrixBody">
          <!-- Data rows added dynamically -->
        </tbody>
      </table>
    </div>
  </div>
</div>
```

**Cell Display Logic:**

For each date cell, display one of:

1. **Complete time log** (both time_in and time_out exist):
```html
<small><span class="badge bg-success">08:00 AM</span></small><br>
<small><span class="badge bg-success">05:00 PM</span></small>
```

2. **Missing data** (no TimeLog or no user account):
```html
<span class="badge bg-warning text-dark">Missing</span>
```

3. **Incomplete time log** (time_in exists but time_out is null):
```html
<small><span class="badge bg-success">08:00 AM</span></small><br>
<span class="badge bg-warning text-dark">Missing</span>
```

**Responsive Behavior:**
- On desktop: Show all columns in table
- On mobile (< 768px): Add `table-responsive` wrapper for horizontal scrolling
- Consider sticky first column (Name, Role) for easier navigation on wide tables

**JavaScript Implementation:**

```javascript
function displayTimeLogMatrix(data) {
  const tbody = document.getElementById('timeLogMatrixBody');
  const thead = document.querySelector('#timeLogMatrixTable thead tr');
  tbody.innerHTML = '';

  // Display date range in header
  document.getElementById('timeLogDateRange').textContent =
    `${data.date_range.start} to ${data.date_range.end}`;

  // Build date columns
  data.date_range.dates.forEach(date => {
    const th = document.createElement('th');
    th.textContent = date;
    thead.appendChild(th);
  });

  // Build personnel rows
  data.personnel.forEach(person => {
    const tr = document.createElement('tr');

    // Name column
    const nameTd = document.createElement('td');
    nameTd.innerHTML = `<strong>${person.name}</strong>`;
    tr.appendChild(nameTd);

    // Role column
    const roleTd = document.createElement('td');
    const roleColor = person.role === 'Driver' ? 'primary' : 'info';
    roleTd.innerHTML = `<span class="badge bg-${roleColor}">${person.role}</span>`;
    tr.appendChild(roleTd);

    // Date columns
    data.date_range.dates.forEach(date => {
      const td = document.createElement('td');
      const timeData = person.dates[date];

      if (timeData.time_in === 'Missing' && timeData.time_out === 'Missing') {
        td.innerHTML = '<span class="badge bg-warning text-dark">Missing</span>';
      } else {
        const timeInClass = timeData.time_in !== 'Missing' ? 'success' : 'warning';
        const timeOutClass = timeData.time_out !== 'Missing' ? 'success' : 'warning';
        td.innerHTML = `
          <small><span class="badge bg-${timeInClass}">${timeData.time_in}</span></small><br>
          <small><span class="badge bg-${timeOutClass}">${timeData.time_out}</span></small>
        `;
      }
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
}
```

## Error Handling & Edge Cases

### Edge Case Handling

| Scenario | Behavior |
|----------|----------|
| Personnel with no user account (`user_id` is NULL) | All date cells show "Missing" badge |
| Large date ranges (30+ days) | Table becomes horizontally scrollable; validate max 90 days |
| No personnel assigned in date range | Show friendly message: "No drivers or assistants assigned to trips in this date range" |
| No TimeLog records exist | Show all assigned personnel with all "Missing" badges |
| Multiple trips on same day for same person | Show ONE row per person with their TimeLog for that day (TimeLog is per person per day, not per trip) |
| TimeLog exists but `time_out` is NULL | Show `time_in` in green badge, `time_out` as "Missing" in yellow badge |
| Invalid date range (start > end) | Return 400 error with clear message |
| Non-admin user attempts access | Return 403 Forbidden; redirect to schedule view |
| Date range exceeds 90 days | Return 400 error with message "Date range cannot exceed 90 days" |

### Empty State Handling

When `personnel` array is empty:

```javascript
const tbody = document.getElementById('timeLogMatrixBody');
const colspan = 2 + data.date_range.dates.length;  // Name + Role + date columns
tbody.innerHTML = `
  <tr>
    <td colspan="${colspan}" class="text-center text-muted">
      <i class="bi bi-info-circle"></i>
      No drivers or assistants assigned to trips in this date range
    </td>
  </tr>
`;
```

## CSV Export Design

### Export Endpoint

**Route:** `GET /export_driver_assistant_time_logs`

**Parameters:** Same as main endpoint (`start_date`, `end_date`)

**Response:** CSV file download

### CSV Format

**File structure:**

```csv
Driver/Assistant Time Logs Report
Start Date: 2026-03-15, End Date: 2026-03-20

Name,Role,2026-03-15 In,2026-03-15 Out,2026-03-16 In,2026-03-16 Out,2026-03-17 In,2026-03-17 Out
Juan Dela Cruz,Driver,08:00 AM,05:00 PM,08:15 AM,Missing,Missing,Missing
Maria Santos,Assistant,Missing,Missing,08:00 AM,05:00 PM,08:00 AM,05:00 PM
```

**Format specifications:**
- Two columns per date: "YYYY-MM-DD In" and "YYYY-MM-DD Out"
- Flat structure (no nested cells)
- "Missing" string for null/missing values (matches UI)
- Header row includes all dates in range
- Comma-separated values (standard CSV)

**Filename:** `driver_assistant_time_logs_2026-03-15_to_2026-03-20.csv`

**Content-Type:** `text/csv`

**Content-Disposition:** `attachment; filename=driver_assistant_time_logs_{start}_to_{end}.csv`

### Backend Implementation

```python
import csv
import io
from datetime import datetime, timedelta
from flask import jsonify, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import cast, Date

@app.route('/export_driver_assistant_time_logs')
@login_required
def export_driver_assistant_time_logs():
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # ... validation ...

    # Reuse the same logic as /driver_assistant_time_logs endpoint
    # to get personnel_list and date_list

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header rows
    writer.writerow(['Driver/Assistant Time Logs Report'])
    writer.writerow([f'Start Date: {start_date_str}, End Date: {end_date_str}'])
    writer.writerow([])

    # Build column headers
    headers = ['Name', 'Role']
    for date_str in date_list:
        headers.extend([f'{date_str} In', f'{date_str} Out'])
    writer.writerow(headers)

    # Write data rows
    for person in personnel_list:
        row = [person['name'], person['role']]
        for date_str in date_list:
            time_data = person['dates'][date_str]
            row.extend([time_data['time_in'], time_data['time_out']])
        writer.writerow(row)

    output.seek(0)

    filename = f"driver_assistant_time_logs_{start_date_str}_to_{end_date_str}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
```

## Implementation Tasks

### Backend Tasks (app.py)

1. **Create `/driver_assistant_time_logs` endpoint**
   - Validate date range (max 90 days)
   - Query personnel assignments using UNION
   - Query TimeLog records
   - Build lookup dictionaries
   - Pivot data into matrix structure
   - Return JSON response

2. **Create `/export_driver_assistant_time_logs` endpoint**
   - Reuse query logic from main endpoint
   - Generate CSV with two columns per date
   - Return file download response

### Frontend Tasks (templates/reports.html)

1. **Add new report card**
   - Position after Missing Data Report card
   - Purple header to distinguish from other reports
   - Form with start/end date inputs
   - Submit button

2. **Add results display section**
   - Table with Name and Role as fixed columns
   - Dynamic date columns added via JavaScript
   - Cell styling based on data completeness
   - Export CSV button

3. **JavaScript implementation**
   - Form submission handler
   - Fetch data from new endpoint
   - `displayTimeLogMatrix()` function
   - Dynamic table generation
   - Export button handler

### Testing Considerations

- Test with various date ranges (1 day, 7 days, 30 days, 90 days)
- Test with personnel who have no user account
- Test with incomplete TimeLogs (missing time_out)
- Test with no data in date range
- Test CSV export opens correctly in Excel/Google Sheets
- Test responsive behavior on mobile devices

### Code Reuse Strategy

To avoid duplicating the complex data query and pivot logic between the main endpoint and the export endpoint, create a shared helper function:

```python
def get_time_log_matrix_data(start_date, end_date):
    """
    Query and pivot time log data for matrix display.

    Args:
        start_date: datetime.date object
        end_date: datetime.date object

    Returns:
        tuple: (personnel_list, date_list)
    """
    # All the query and pivot logic from Steps 1-4
    # Returns (personnel_list, date_list)

@app.route('/driver_assistant_time_logs')
@login_required
def driver_assistant_time_logs():
    # Validation...
    personnel_list, date_list = get_time_log_matrix_data(start_date, end_date)
    # Build response...
    return jsonify(result)

@app.route('/export_driver_assistant_time_logs')
@login_required
def export_driver_assistant_time_logs():
    # Validation...
    personnel_list, date_list = get_time_log_matrix_data(start_date, end_date)
    # Generate CSV...
    return Response(...)
```

### Security Considerations

Both endpoints use GET requests (no state modification) and include:
- **Authentication:** `@login_required` decorator ensures only authenticated users can access
- **Authorization:** Check `current_user.position != 'admin'` to restrict to admin-only
- **Input Validation:** Date format validation, range validation, and logical validation (start ≤ end)
- **SQL Injection Prevention:** Using SQLAlchemy ORM with parameterized queries (no raw SQL)
- **XSS Prevention:** Data is properly escaped in templates and JSON responses

No CSRF protection is needed for GET requests as they don't modify state.

## Design Decisions

### Why Backend Pivot (Approach 1)?

**Chosen approach:** Backend performs all data pivoting into matrix structure

**Rationale:**
1. **Consistency:** Existing reports (Truck Load Utilization, DIFOT, etc.) all process data on backend
2. **Performance:** Matrix pivot done once in Python, not on every client
3. **Maintainability:** Clear API contract; easier to debug backend logic independently
4. **User Experience:** Faster frontend rendering with pre-formatted data

**Trade-off:** More complex backend code, but this is acceptable given the benefits.

### Why "Missing" String for All Missing Data?

**Decision:** Use single "Missing" indicator for all scenarios (no account, no TimeLog, incomplete TimeLog)

**Rationale:**
1. **Simplicity:** Easier for users to scan - yellow = problem, green = good
2. **Consistency:** Matches existing Missing Data Report pattern
3. **Clarity:** Users can investigate further by checking individual TimeLog records if needed

**Alternative rejected:** Differentiating between "No Account", "Missing", "Incomplete" - this would add visual complexity without clear user benefit for this report's purpose.

### Why Two CSV Columns Per Date?

**Decision:** "YYYY-MM-DD In" and "YYYY-MM-DD Out" as separate columns

**Rationale:**
1. **Parseability:** Easy to import into Excel/Google Sheets for analysis
2. **Filtering:** Can filter/sort by individual time_in or time_out values
3. **Compatibility:** Standard CSV format works with all spreadsheet applications

**Alternative rejected:** Single column with "In: 08:00 / Out: 05:00" format - harder to parse and analyze programmatically.

## Future Enhancements (Out of Scope)

- Add filters for role (Driver-only, Assistant-only, or both)
- Add search functionality to find specific personnel
- Add summary statistics (attendance rate per person, most common missing days)
- Add drill-down to view individual TimeLog details
- Add ability to edit TimeLog directly from this report
- Add visualization (heatmap showing attendance patterns)
- Export to Excel format with conditional formatting
