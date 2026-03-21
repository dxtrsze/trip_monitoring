# Driver/Assistant Time Log Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new report card displaying driver/assistant TimeLog data in a matrix format (personnel as rows, dates as columns)

**Architecture:** Backend performs data pivoting into matrix structure, frontend renders dynamic table with green/yellow badges for data completeness

**Tech Stack:** Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Python datetime/timedelta, vanilla JavaScript, Bootstrap 5

---

## File Structure

**Modified files:**
- `app.py` - Add shared helper function and two new endpoints
- `templates/reports.html` - Add 7th report card and results display section

**No new files created** - This extends existing report infrastructure

---

## Task 1: Add shared helper function to query and pivot time log data

**Files:**
- Modify: `app.py` (after `/export_missing_data` endpoint, around line 5315)

**Context:** This helper function will be reused by both the main endpoint and the CSV export endpoint to avoid duplicating complex query and pivot logic.

**Note:** Models (Trip, Schedule, Manpower, etc.) are already imported at module level (line 14). The helper function can use them directly without re-importing.

- [ ] **Step 1: Write the shared helper function skeleton**

Location: In `app.py`, after all model imports and before first route definition (around line 550-600, after `DailyVehicleCount` model definition)

```python
def get_time_log_matrix_data(start_date, end_date):
    """
    Query and pivot time log data for matrix display.

    Args:
        start_date: datetime.date object
        end_date: datetime.date object (exclusive, adjusted with +1 day)

    Returns:
        tuple: (personnel_list, date_list)
            - personnel_list: List of dicts with keys: manpower_id, name, role, dates
            - date_list: List of date strings in YYYY-MM-DD format
    """
    # Import Date casting function locally (following existing codebase pattern)
    from sqlalchemy import cast, Date
    from collections import namedtuple

    # TODO: Implement query logic
    return [], []
```

Run: `python -c "import app; print('Helper function defined')"`
Expected: No syntax errors

- [ ] **Step 2: Implement query for assigned personnel**

Add to function body:

```python
def get_time_log_matrix_data(start_date, end_date):
    """
    Query and pivot time log data for matrix display.

    Args:
        start_date: datetime.date object
        end_date: datetime.date object (exclusive, adjusted with +1 day)

    Returns:
        tuple: (personnel_list, date_list)
            - personnel_list: List of dicts with keys: manpower_id, name, role, dates
            - date_list: List of date strings in YYYY-MM-DD format
    """
    # Import Date casting function locally (following existing codebase pattern)
    from sqlalchemy import cast, Date
    from collections import namedtuple

    # Get all unique drivers and assistants assigned to trips in date range
    # Note: Models are already imported at module level

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

**Note:** Uses `.union()` to eliminate duplicate personnel entries. If the same person appears as both a driver AND an assistant on different trips, they will appear as two separate rows (one for each role), which is the intended behavior per the spec.

    return [], []
```

Run: `python -c "import app; print('Query compiles')"`
Expected: No syntax errors

- [ ] **Step 3: Implement query for TimeLog records**

Add after the personnel query:

```python
    # Get all TimeLog records in the date range
    time_logs = db.session.query(TimeLog).filter(
        cast(TimeLog.time_in, Date) >= start_date,
        cast(TimeLog.time_in, Date) < end_date
    ).all()
```

Run: `python -c "import app; print('TimeLog query compiles')"`
Expected: No syntax errors

- [ ] **Step 4: Implement TimeLog lookup dictionary**

Add after the TimeLog query:

```python
    # Create lookup dictionary: (date, user_id) -> TimeLog data
    # Note: If multiple TimeLog entries exist for the same person on the same day,
    # only the last one will be kept (last write wins). This is acceptable as
    # TimeLog should have one entry per person per day.
    timelog_dict = {}
    for tl in time_logs:
        tl_date = tl.time_in.date()
        key = (tl_date, tl.user_id)
        timelog_dict[key] = {
            'time_in': tl.time_in.strftime('%I:%M %p') if tl.time_in else None,
            'time_out': tl.time_out.strftime('%I:%M %p') if tl.time_out else None
        }
```

Run: `python -c "import app; print('Lookup dict compiles')"`
Expected: No syntax errors

- [ ] **Step 5: Generate date list**

Add after the lookup dictionary:

```python
    # Generate list of all dates in range
    date_list = []
    current_date = start_date
    while current_date < end_date:
        date_list.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
```

Run: `python -c "import app; print('Date list generation compiles')"`
Expected: No syntax errors

- [ ] **Step 6: Build unique personnel set and pivot data**

Replace the `return [], []` with full implementation:

```python
    # Build unique personnel set
    from collections import namedtuple
    PersonInfo = namedtuple('PersonInfo', ['manpower_id', 'name', 'role', 'user_id'])

    unique_personnel = {}
    for schedule_date, manpower_id, name, role, user_id in manpower_assignments:
        key = (manpower_id, role)
        if key not in unique_personnel:
            unique_personnel[key] = PersonInfo(manpower_id, name, role, user_id)

    # Build matrix for each person
    personnel_list = []
    for person in unique_personnel.values():
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

    return personnel_list, date_list
```

Run: `python -c "import app; print('Full implementation compiles')"`
Expected: No syntax errors

- [ ] **Step 8: Commit helper function**

```bash
git add app.py
git commit -m "feat: add get_time_log_matrix_data helper function

- Queries personnel assigned to trips in date range (drivers + assistants)
- Queries TimeLog records and builds lookup dictionary
- Pivots data into matrix format: personnel x dates
- Returns tuple: (personnel_list, date_list)
- Handles edge cases: no user account, missing TimeLog records

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add /driver_assistant_time_logs endpoint

**Files:**
- Modify: `app.py` (after existing report endpoints, around line 5315 after `/export_missing_data` endpoint)

- [ ] **Step 1: Write endpoint skeleton with validation**

Location: In `app.py`, after the `/export_missing_data` endpoint (around line 5315)

```python
@app.route('/driver_assistant_time_logs')
@login_required
def driver_assistant_time_logs():
    """Get driver/assistant time log matrix data"""
    # TODO: Implement validation and response
    pass
```

Run: `python -c "import app; print('Endpoint skeleton compiles')"`
Expected: No syntax errors

- [ ] **Step 2: Add authentication and authorization check**

```python
@app.route('/driver_assistant_time_logs')
@login_required
def driver_assistant_time_logs():
    """Get driver/assistant time log matrix data"""
    if current_user.position != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('view_schedule'))

    # TODO: Continue implementation
    pass
```

Run: `python -c "import app; print('Auth check compiles')"`
Expected: No syntax errors

- [ ] **Step 3: Add date parameter extraction and validation**

```python
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Start date and end date are required'}), 400

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

    # Include the entire end date by adding 1 day
    # This makes the range inclusive: if user selects Mar 15-20, we query through Mar 20 23:59:59
    end_date = end_date + timedelta(days=1)

    # TODO: Call helper and build response
    pass
```

Run: `python -c "import app; print('Validation compiles')"`
Expected: No syntax errors

- [ ] **Step 4: Call helper function and build response**

Replace the TODO comment:

```python
    try:
        # Get matrix data using shared helper
        personnel_list, date_list = get_time_log_matrix_data(start_date, end_date)

        # Build response
        result = {
            'personnel': personnel_list,
            'date_range': {
                'start': start_date_str,
                'end': end_date_str,
                'dates': date_list
            }
        }

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching time log data: {str(e)}'}), 500
```

Run: `python -c "import app; print('Endpoint implementation compiles')"`
Expected: No syntax errors

- [ ] **Step 5: Test endpoint manually**

Start Flask app and test:
```bash
python app.py
```

Then in another terminal:
```bash
curl "http://localhost:5000/driver_assistant_time_logs?start_date=2026-03-15&end_date=2026-03-20" \
  -H "Cookie: session=<your_session_cookie>"
```

Expected: JSON response with `personnel` array and `date_range` object (may be empty if no data)

- [ ] **Step 6: Commit endpoint**

```bash
git add app.py
git commit -m "feat: add /driver_assistant_time_logs endpoint

- Returns time log data in matrix format (personnel x dates)
- Validates date format and range (max 90 days)
- Admin-only access with @login_required decorator
- Uses get_time_log_matrix_data() helper function
- Returns JSON with personnel list and date range metadata

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Add /export_driver_assistant_time_logs endpoint

**Files:**
- Modify: `app.py` (after `/driver_assistant_time_logs` endpoint)

- [ ] **Step 1: Write endpoint skeleton**

Location: In `app.py`, immediately after the `/driver_assistant_time_logs` endpoint

```python
@app.route('/export_driver_assistant_time_logs')
@login_required
def export_driver_assistant_time_logs():
    """Export Driver/Assistant Time Log Matrix to CSV"""
    # TODO: Implement
    pass
```

Run: `python -c "import app; print('Export endpoint skeleton compiles')"`
Expected: No syntax errors

- [ ] **Step 2: Add auth, validation, and helper call**

```python
@app.route('/export_driver_assistant_time_logs')
@login_required
def export_driver_assistant_time_logs():
    """Export Driver/Assistant Time Log Matrix to CSV"""
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

        delta = end_date - start_date
        if delta.days > 90:
            return "Date range cannot exceed 90 days", 400

        # Include the entire end date
        end_date = end_date + timedelta(days=1)

        # Get matrix data using shared helper
        personnel_list, date_list = get_time_log_matrix_data(start_date, end_date)

        # TODO: Generate CSV
        pass

    except ValueError as e:
        return f"Invalid date format: {str(e)}", 400
    except Exception as e:
        return f"Error exporting time log data: {str(e)}", 500
```

Run: `python -c "import app; print('Export endpoint with validation compiles')"`
Expected: No syntax errors

- [ ] **Step 3: Implement CSV generation**

Replace the TODO comment:

```python
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

        # Return as downloadable CSV file
        filename = f"driver_assistant_time_logs_{start_date_str}_to_{end_date_str}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
```

Run: `python -c "import app; print('CSV generation compiles')"`
Expected: No syntax errors

- [ ] **Step 4: Test CSV export manually**

Start Flask app if not running:
```bash
python app.py
```

Then in browser or curl:
```bash
curl "http://localhost:5000/export_driver_assistant_time_logs?start_date=2026-03-15&end_date=2026-03-20" \
  -H "Cookie: session=<your_session_cookie>" \
  --output test_export.csv
```

Expected: Downloads `test_export.csv` with headers and data rows

- [ ] **Step 5: Commit export endpoint**

```bash
git add app.py
git commit -m "feat: add /export_driver_assistant_time_logs CSV export

- Exports time log matrix data to CSV format
- Two columns per date: 'YYYY-MM-DD In' and 'YYYY-MM-DD Out'
- Reuses get_time_log_matrix_data() helper function
- Admin-only access with validation
- Returns downloadable CSV file

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Add new report card to Reports page

**Files:**
- Modify: `templates/reports.html` (after Missing Data Report card, around line 231)

- [ ] **Step 1: Add report card HTML**

Location: In `templates/reports.html`, after the Missing Data Report card (after `</div>` that closes the Missing Data card's parent div, around line 231)

```html
  <!-- Driver/Assistant Time Log Matrix Card -->
  <div class="col-md-4 mb-3">
    <div class="card h-100">
      <div class="card-header bg-info text-white">
        <h5 class="mb-0"><i class="bi bi-clock-history"></i> Driver/Assistant Time Logs</h5>
      </div>
      <div class="card-body">
        <form id="timeLogMatrixForm">
          <div class="row mb-3">
            <div class="col-md-6">
              <label for="timeLogStartDate" class="form-label">Start Date</label>
              <input type="date" class="form-control" id="timeLogStartDate" required>
            </div>
            <div class="col-md-6">
              <label for="timeLogEndDate" class="form-label">End Date</label>
              <input type="date" class="form-control" id="timeLogEndDate" required>
            </div>
          </div>
          <div class="row mb-3">
            <div class="col-md-12">
              <button type="submit" class="btn btn-info w-100 text-white">
                <i class="bi bi-clock"></i> View Time Log Matrix
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div>
```

Run: Open `http://localhost:5000/reports` in browser
Expected: New card appears with light blue (info) header, form with date inputs

- [ ] **Step 2: Add results display section**

Location: In `templates/reports.html`, after the Missing Data Results section (after `</div>` that closes the Missing Data Results card, around line 545)

```html
<!-- Driver/Assistant Time Log Matrix Results -->
<div class="card mt-4" id="timeLogMatrixResults" style="display:none;">
  <div class="card-header d-flex justify-content-between align-items-center bg-info text-white">
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

Run: Refresh reports page
Expected: Page renders without errors (results section hidden initially)

- [ ] **Step 3: Initialize form variables in JavaScript**

Location: In `templates/reports.html`, in the `<script>` section, find where other form variables are declared (around line 595-602, after `missingDateRange` declaration)

Add:
```javascript
  // Time Log Matrix Form
  const timeLogMatrixForm = document.getElementById('timeLogMatrixForm');
  const timeLogMatrixResults = document.getElementById('timeLogMatrixResults');
  const timeLogMatrixTable = document.getElementById('timeLogMatrixTable');
  const timeLogMatrixBody = document.getElementById('timeLogMatrixBody');
  const exportTimeLogBtn = document.getElementById('exportTimeLogBtn');
  const timeLogDateRange = document.getElementById('timeLogDateRange');
```

Run: Refresh reports page, check browser console
Expected: No JavaScript errors

- [ ] **Step 4: Set default dates for the new form**

Location: In `templates/reports.html`, find the Manila date loading section (around line 604-623, where default dates are set for other forms)

Add inside the `.then(data => {` block:
```javascript
      document.getElementById('timeLogStartDate').value = defaultStart;
      document.getElementById('timeLogEndDate').value = defaultEnd;
```

Run: Refresh reports page
Expected: New form's date inputs are pre-filled with last 7 days

- [ ] **Step 5: Commit report card HTML**

```bash
git add templates/reports.html
git commit -m "feat: add Driver/Assistant Time Log Matrix report card

- Add 7th report card with light blue (bg-info) header
- Form with start/end date inputs
- Results display section with dynamic table structure
- Initialize JavaScript variables for the new form
- Set default date range to last 7 days

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Implement form submission handler

**Files:**
- Modify: `templates/reports.html` (in `<script>` section, after other form handlers, around line 946 after Missing Data Form Submit handler)

- [ ] **Step 1: Add form submit event listener skeleton**

```javascript
  // Time Log Matrix Form Submit
  timeLogMatrixForm.addEventListener('submit', function(e) {
    e.preventDefault();
    // TODO: Implement form submission
  });
```

Run: Refresh reports page, submit the new form
Expected: Page doesn't reload (preventDefault works), no console errors

- [ ] **Step 2: Add date extraction and display**

Replace TODO comment:

```javascript
  // Time Log Matrix Form Submit
  timeLogMatrixForm.addEventListener('submit', function(e) {
    e.preventDefault();

    const startDate = document.getElementById('timeLogStartDate').value;
    const endDate = document.getElementById('timeLogEndDate').value;

    // Show date range in the report header
    const start = new Date(startDate).toLocaleDateString();
    const end = new Date(endDate).toLocaleDateString();
    timeLogDateRange.textContent = `${start} - ${end}`;

    // TODO: Fetch and display data
  });
```

Run: Submit the new form
Expected: Date range appears in results header, but results section doesn't show yet

- [ ] **Step 3: Hide other report results and fetch data**

Replace the TODO comment:

```javascript
    // Fetch time log matrix data
    fetch(`/driver_assistant_time_logs?start_date=${startDate}&end_date=${endDate}`)
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => {
            throw new Error(err.error || 'Failed to fetch time log data');
          });
        }
        return response.json();
      })
      .then(data => {
        if (data.error) {
          throw new Error(data.error);
        }
        displayTimeLogMatrix(data);
        // Hide other report results
        reportResults.style.display = 'none';
        truckResults.style.display = 'none';
        fleetResults.style.display = 'none';
        fuelResults.style.display = 'none';
        frequencyResults.style.display = 'none';
        difotResults.style.display = 'none';
        missingResults.style.display = 'none';
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Error: ' + error.message);
      });
  });
```

Run: Submit the new form
Expected: Either data displays or error alert shows (check browser console for errors)

- [ ] **Step 4: Commit form handler**

```bash
git add templates/reports.html
git commit -m "feat: add time log matrix form submission handler

- Extract start/end dates from form inputs
- Display date range in results header
- Fetch data from /driver_assistant_time_logs endpoint
- Hide other report results when showing this one
- Basic error handling with alert

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Implement displayTimeLogMatrix function

**Files:**
- Modify: `templates/reports.html` (in `<script>` section, after other display functions, around line 1445 after `displayMissingData` function)

- [ ] **Step 1: Write function skeleton**

```javascript
  function displayTimeLogMatrix(data) {
    const tbody = document.getElementById('timeLogMatrixBody');
    const thead = document.querySelector('#timeLogMatrixTable thead tr');
    tbody.innerHTML = '';

    // TODO: Implement display logic
  }
```

Run: Submit the time log matrix form
Expected: Function is called, no console errors

- [ ] **Step 2: Handle empty personnel array**

Add after `tbody.innerHTML = '';`:

```javascript
    // Handle empty data
    if (!data.personnel || data.personnel.length === 0) {
      const colspan = 2 + data.date_range.dates.length;
      tbody.innerHTML = `
        <tr>
          <td colspan="${colspan}" class="text-center text-muted">
            <i class="bi bi-info-circle"></i>
            No drivers or assistants assigned to trips in this date range
          </td>
        </tr>
      `;
      timeLogMatrixResults.style.display = 'block';
      return;
    }
```

Run: Submit form with date range that has no trips
Expected: Empty state message displays

- [ ] **Step 3: Build date column headers**

Add after the empty data check:

```javascript
    // Display date range in header
    document.getElementById('timeLogDateRange').textContent =
      `${data.date_range.start} to ${data.date_range.end}`;

    // Clear existing date columns from previous submissions (keep Name and Role)
    while (thead.children.length > 2) {
      thead.removeChild(thead.lastChild);
    }

    // Build date columns
    data.date_range.dates.forEach(date => {
      const th = document.createElement('th');
      th.textContent = date;
      thead.appendChild(th);
    });
```

Run: Submit form with valid date range
Expected: Table header shows date columns

- [ ] **Step 4: Build personnel data rows**

Add after the date column loop:

```javascript
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
```

Run: Submit form with valid date range that has data
Expected: Table rows display with personnel names, roles, and time data

- [ ] **Step 5: Show results and add to end of function**

Add at the very end of the function:

```javascript
    timeLogMatrixResults.style.display = 'block';
  }
```

Run: Submit form
Expected: Results section becomes visible after data loads

- [ ] **Step 6: Commit display function**

```bash
git add templates/reports.html
git commit -m "feat: implement displayTimeLogMatrix function

- Builds dynamic table header with date columns
- Creates personnel rows with name, role, and time data
- Handles empty state with friendly message
- Shows green badges for complete time logs
- Shows yellow badges for missing/incomplete data
- Responsive table with horizontal scroll support

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Implement export button handler

**Files:**
- Modify: `templates/reports.html` (in `<script>` section, after other export handlers, around line 1008 after Export Missing Data handler)

- [ ] **Step 1: Add export button click handler**

```javascript
  // Export Time Log Matrix
  exportTimeLogBtn.addEventListener('click', function() {
    const startDate = document.getElementById('timeLogStartDate').value;
    const endDate = document.getElementById('timeLogEndDate').value;

    window.location.href = `/export_driver_assistant_time_logs?start_date=${startDate}&end_date=${endDate}`;
  });
```

Run: Click the export button after loading time log matrix data
Expected: CSV file downloads

- [ ] **Step 2: Commit export handler**

```bash
git add templates/reports.html
git commit -m "feat: add export button handler for time log matrix

- Extracts date values from form inputs
- Triggers CSV download via /export_driver_assistant_time_logs endpoint
- Downloads file with name format: driver_assistant_time_logs_YYYY-MM-DD_to_YYYY-MM-DD.csv

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Testing and validation

**Files:**
- All modified files: `app.py`, `templates/reports.html`

- [ ] **Step 1: Start Flask application**

```bash
python app.py
```

Expected: Application starts without errors, listens on port 5000

- [ ] **Step 2: Test with empty date range (no data)**

Navigate to `http://localhost:5000/reports` (login as admin)
1. Find the "Driver/Assistant Time Logs" card (7th card, light blue header)
2. Select dates with no trip assignments (e.g., far future dates)
3. Click "View Time Log Matrix"

Expected: Shows "No drivers or assistants assigned to trips in this date range" message

- [ ] **Step 3: Test with valid date range (has data)**

1. Select last 7 days (default)
2. Click "View Time Log Matrix"

Expected:
- Table displays with personnel as rows
- Date columns appear across the top
- Green badges show for complete time_in/time_out
- Yellow badges show for missing data
- Date range shows in header

- [ ] **Step 4: Test CSV export**

1. After viewing time log matrix data
2. Click "Export CSV" button

Expected:
- CSV file downloads
- File opens in Excel/Google Sheets
- Headers: Name, Role, 2026-03-15 In, 2026-03-15 Out, etc.
- Data matches what's shown in the UI

- [ ] **Step 5: Test date validation**

Test various invalid inputs:
1. Start date after end date → Expected: Error alert
2. Date range > 90 days → Expected: Error alert
3. Invalid date format → Expected: Error alert (should be caught by HTML5 date input)

- [ ] **Step 6: Test non-admin access denial**

1. Log out as admin
2. Log in as a non-admin user (e.g., driver or dispatcher)
3. Navigate to Reports page
4. Try to access the endpoint directly via browser console:
   ```javascript
   fetch('/driver_assistant_time_logs?start_date=2026-03-15&end_date=2026-03-20')
     .then(r => r.json())
     .then(data => console.log(data))
   ```

Expected:
- Error response with access denied message
- Or redirect to schedule view with flash message "Access denied. Admin privileges required."

- [ ] **Step 7: Test responsive behavior**

Resize browser window to mobile width (< 768px)

Expected:
- Table gains horizontal scroll
- First columns (Name, Role) remain visible
- Can scroll horizontally to see all date columns

- [ ] **Step 8: Test with incomplete TimeLog data**

1. Find a date where someone has time_in but missing time_out
2. View that date range

Expected:
- time_in shows in green badge
- time_out shows in yellow "Missing" badge

- [ ] **Step 9: Commit any final adjustments**

```bash
git add app.py templates/reports.html
git commit -m "fix: minor adjustments after testing

- [List any fixes made during testing]
- All validation working correctly
- CSV export format confirmed
- Responsive behavior verified

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Documentation and cleanup

**Files:**
- None (just verification)

- [ ] **Step 1: Verify all commits are pushed**

```bash
git log --oneline -10
```

Expected: See all implementation commits in sequence

- [ ] **Step 2: Verify implementation matches spec**

Check spec document: `docs/superpowers/specs/2026-03-21-driver-assistant-time-log-matrix-design.md`

Verify:
- ✅ New report card added
- ✅ Matrix format (personnel x dates)
- ✅ Green/yellow badge color coding
- ✅ Date validation (max 90 days)
- ✅ CSV export with two columns per date
- ✅ Admin-only access
- ✅ Edge cases handled

- [ ] **Step 3: Create summary commit**

```bash
git add docs/superpowers/specs docs/superpowers/plans
git commit -m "docs: complete Driver/Assistant Time Log Matrix implementation

- Spec: 2026-03-21-driver-assistant-time-log-matrix-design.md
- Plan: 2026-03-21-driver-assistant-time-log-matrix.md
- Implementation complete with 9 tasks and 33 steps
- All edge cases handled and tested
- Ready for production use

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Success Criteria

Implementation is complete when:

1. **Backend**
   - `get_time_log_matrix_data()` helper function works correctly
   - `/driver_assistant_time_logs` endpoint returns valid JSON
   - `/export_driver_assistant_time_logs` downloads valid CSV
   - All validation rules enforced (90-day max, date format, etc.)

2. **Frontend**
   - New report card visible on Reports page
   - Matrix table displays correctly with dynamic columns
   - Green badges for complete data, yellow for missing
   - Empty state shows friendly message
   - Export button triggers CSV download

3. **Edge Cases**
   - No user account: Shows "Missing" for all dates
   - No TimeLog record: Shows "Missing" for that date
   - Incomplete TimeLog (missing time_out): Shows green for time_in, yellow for time_out
   - Large date range: Table horizontally scrollable
   - Empty date range: Shows empty state message

4. **Security**
   - Non-admin users redirected with access denied message
   - SQL injection prevented (using SQLAlchemy ORM)
   - XSS prevented (proper template escaping)

---

## Notes for Implementation

- **Night Shift Limitation:** TimeLog entries are matched using `time_in` date only. Night shifts that span multiple days will only appear on the `time_in` date. This is documented in the spec as a known limitation.

- **Performance:** For 90-day range with 50 personnel, expect ~4,500 cells. This is manageable but could be slow on older devices. The spec mentions this could be optimized in future enhancements if needed.

- **Bootstrap 5 Colors:** The report uses `bg-info` (light blue) to distinguish from other cards. Other colors used: primary (blue), success (green), warning (yellow), danger (red), secondary (gray), dark (black).

- **Date Range Inclusive:** The backend adds `timedelta(days=1)` to `end_date` to make the range inclusive. This is consistent with other reports in the system.

- **Testing Without Data:** If testing in a development environment with no trip data, create dummy data by assigning drivers/assistants to trips in the selected date range, then create TimeLog entries for their linked User accounts.

---

**End of Implementation Plan**
