# Admin Dashboard Design

**Date**: 2026-03-21
**Author**: Claude (via brainstorming session)
**Status**: Draft

## Overview

Design a comprehensive operational dashboard for admin users that replaces the current home page redirect, providing at-a-glance visibility into delivery performance, fleet efficiency, and data quality through interactive visualizations powered by Apache ECharts.

## Objectives

- Provide admin users with real-time operational insights through KPIs and trends
- Replace the current home page (`/`) redirect to `view_schedule` with a value-add dashboard
- Focus on high-impact operational metrics: delivery performance, fleet efficiency, and data quality
- Support both daily detail (7-day trends) and weekly aggregate views (30+ day periods)
- Enable quick access to common tasks through an action bar

## Key Requirements

### Access Control
- **Admin-only access**: Only users with `position == 'admin'` can view the dashboard
- Non-admin users continue to be redirected to `/view_schedule`
- Authenticated but unauthorized users see info message and redirect

### Data Scope
- **Primary focus**: Truck Utilization, Fuel Efficiency/ODO, and DIFOT metrics
- **Time granularity**: Mixed approach
  - Daily view for recent 7-day periods
  - Weekly aggregate view for 30+ day periods
- **Date range limits**: Maximum 90-day range to maintain performance
- **Auto-adjustment**: Future dates automatically clamp to today

### Performance Targets
- **Page load time**: < 3 seconds with 30 days of data
- **Refresh time**: < 2 seconds for manual refresh
- **Concurrent handling**: Disable refresh button during loading to prevent race conditions
- **Large dataset handling**: Auto-aggregate to weekly granularity if > 5000 records

## Architecture

### Backend API Layer

New Flask routes in `app.py`:

```
GET /api/dashboard/kpis
- Returns all 6 KPI summary values and trends
- Query params: start_date, end_date (default: last 7 days)
- Response: {
    on_time_delivery_rate: {
      value: 87.5,
      trend: +2.3,
      sparkline: [85.2, 86.1, 84.5, 87.0, 88.2, 87.1, 87.5]
    },
    in_full_delivery_rate: {
      value: 92.1,
      trend: -0.5,
      sparkline: [93.0, 92.8, 92.5, 91.9, 92.0, 92.3, 92.1]
    },
    difot_score: {
      value: 89.8,
      trend: +0.9,
      sparkline: [88.5, 89.1, 88.8, 89.2, 89.5, 89.6, 89.8]
    },
    truck_utilization: {
      value: 76.4,
      trend: +3.2,
      sparkline: [72.1, 73.5, 74.2, 75.0, 75.8, 76.1, 76.4]
    },
    fuel_efficiency: {
      value: 12.8,
      trend: -0.4,
      sparkline: [13.5, 13.2, 13.0, 12.9, 12.7, 12.8, 12.8]
    },
    fuel_cost_per_km: {
      value: 8.45,
      trend: +0.12,
      sparkline: [8.20, 8.25, 8.30, 8.35, 8.40, 8.42, 8.45]
    },
    data_completeness: {
      value: 94.2,
      trend: +1.1,
      sparkline: [92.5, 93.0, 93.2, 93.8, 93.9, 94.0, 94.2]
    },
    period: {
      start_date: '2026-03-14',
      end_date: '2026-03-21',
      previous_start_date: '2026-03-07',
      previous_end_date: '2026-03-13'
    }
  }

Note: sparkline arrays contain daily KPI values for current period (7 values for 7-day period)
Trend is percentage point difference vs previous period (not percentage change)

GET /api/dashboard/trends
- Time-series data for line charts
- Query params: start_date, end_date, granularity (daily/weekly)
- Response: {
    daily_deliveries: [{ date: '2026-03-14', count: 45 }, ...],
    fuel_efficiency: [{ date: '2026-03-14', km_per_liter: 12.5, cost_per_km: 8.20 }, ...],
    truck_utilization: [{ date: '2026-03-14', utilization_percent: 78.2 }, ...]
  }

GET /api/dashboard/comparisons
- Ranked data for bar charts
- Query params: start_date, end_date
- Response: {
    vehicle_utilization: [
      { plate_number: 'ABC-123', utilization: 85.2, rank: 1, trip_count: 15 },
      ...
      { plate_number: 'XYZ-789', utilization: 42.1, rank: 20, trip_count: 8 }
    ],
    branch_frequency: [
      { branch: 'Manila', delivery_count: 156, rank: 1 },
      { branch: 'Quezon City', delivery_count: 142, rank: 2 },
      ...
      { branch: 'Others', delivery_count: 89, rank: 11 }  // Aggregate of branches outside top 10
    ],
    driver_performance: [
      { name: 'Juan Dela Cruz', trips: 42, role: 'driver', rank: 1 },
      { name: 'Pedro Santos', trips: 38, role: 'driver', rank: 2 },
      ...
      { name: 'Maria Reyes', trips: 35, role: 'assistant', rank: 15 }
    ]
  }

Note: Branch frequency "Others" aggregate combines all branches outside top 10 by delivery count

GET /api/dashboard/gauges
- Current values for gauge displays
- Response: {
    on_time_rate: 87.5,
    utilization: 76.4,
    data_completeness: 94.2
  }
```

### Data Computation Logic

**On-Time Delivery Rate**:
```python
from sqlalchemy import func, case
from datetime import datetime

# Count TripDetails where scheduled delivery date <= original due date
on_time_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    TripDetail.original_due_date.isnot(None),
    Schedule.delivery_schedule <= TripDetail.original_due_date
).count()

total_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    TripDetail.original_due_date.isnot(None)
).count()

on_time_rate = (on_time_details / total_details * 100) if total_details > 0 else 0
```

**In-Full Delivery Rate**:
```python
# Count TripDetails where delivered_qty >= ordered_qty
in_full_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    TripDetail.total_delivered_qty >= TripDetail.total_ordered_qty
).count()

total_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date)
).count()

in_full_rate = (in_full_details / total_details * 100) if total_details > 0 else 0
```

**DIFOT Score**:
```python
difot_score = (on_time_rate + in_full_rate) / 2
```

**Truck Utilization**:
```python
# Calculate actual CBM loaded vs vehicle capacity for each trip
utilization_records = db.session.query(
    Trip.vehicle_id,
    Vehicle.plate_number,
    Vehicle.capacity,
    func.sum(Trip.total_cbm).label('total_loaded_cbm'),
    func.count(Trip.id).label('trip_count')
).join(Vehicle).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    Vehicle.capacity.isnot(None),
    Vehicle.capacity > 0
).group_by(Trip.vehicle_id, Vehicle.plate_number, Vehicle.capacity).all()

# Calculate weighted average utilization (weighted by trip count)
total_weighted_util = sum([
    (r.total_loaded_cbm / r.capacity * 100) * r.trip_count
    for r in utilization_records
])
total_trips = sum([r.trip_count for r in utilization_records])

utilization_percent = (total_weighted_util / total_trips) if total_trips > 0 else 0

# Note: Vehicles with no trips in period are excluded from average
```

**Fuel Efficiency**:
```python
# Calculate KM/Liter for each vehicle using ODO readings
fuel_efficiency_data = []

for vehicle in db.session.query(Vehicle).filter(Vehicle.status == 'Active').all():
    # Get all ODO readings for this vehicle in the period
    odo_readings = db.session.query(Odo).filter(
        Odo.plate_number == vehicle.plate_number,
        Odo.datetime.between(start_datetime, end_datetime)
    ).order_by(Odo.datetime).all()

    if not odo_readings:
        continue

    # Pair start and end ODO readings to calculate distance
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
            'plate_number': vehicle.plate_number,
            'km_per_liter': km_per_liter,
            'cost_per_km': cost_per_km,
            'distance': total_km
        })

# Calculate weighted average by distance traveled
total_distance = sum([d['distance'] for d in fuel_efficiency_data])
if total_distance > 0:
    weighted_km_per_liter = sum([
        d['km_per_liter'] * d['distance']
        for d in fuel_efficiency_data
    ]) / total_distance
    weighted_cost_per_km = sum([
        d['cost_per_km'] * d['distance']
        for d in fuel_efficiency_data
    ]) / total_distance
else:
    weighted_km_per_liter = 0
    weighted_cost_per_km = 0
```

**Data Completeness**:
```python
# Total trip details in period
total_details = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date)
).count()

# Trip details missing arrival time
details_missing_arrival = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    TripDetail.arrive.is_(None)
).count()

# Trip details missing departure time
details_missing_departure = db.session.query(TripDetail).join(Trip).join(Schedule).filter(
    Schedule.delivery_schedule.between(start_date, end_date),
    TripDetail.departure.is_(None)
).count()

# Check for missing ODO records by querying vehicles that had trips
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

# Calculate completeness: avoid double-counting by tracking unique incomplete details
# A detail is incomplete if missing arrival OR departure OR vehicle has no ODO
incomplete_details = details_missing_arrival + details_missing_departure
complete_details = total_details - incomplete_details

completeness = (complete_details / total_details * 100) if total_details > 0 else 0
```

### Frontend Architecture

**Template Structure** (`templates/dashboard.html`):
```
dashboard.html (extends base.html)
├── Action Bar (fixed top)
│   ├── Logo/title
│   ├── Quick action buttons
│   └── User info + Refresh + Timestamp
├── KPI Summary Cards (6 cards, 2×3 grid)
├── Main Chart Section (2-column layout)
│   ├── Left Column: Trend Line Charts
│   │   ├── Daily delivery counts
│   │   ├── Fuel efficiency (dual-axis)
│   │   └── Truck utilization
│   └── Right Column: Comparison Bar Charts
│       ├── Vehicle utilization ranking
│       ├── Branch delivery frequency
│       └── Driver/assistant performance
└── Performance Gauges (3 gauges in row)
```

**JavaScript Modules**:
- `dashboard-api.js`: API client functions (fetchKPIs, fetchTrends, fetchComparisons, fetchGauges)
- `dashboard-charts.js`: ECharts initialization and update functions
- `dashboard-main.js`: Main controller, event handlers, refresh logic
- `dashboard-utils.js`: Helper functions (date formatting, trend calculation, color coding)

**Data Loading Strategy**:
```javascript
// Parallel fetch on initial load
Promise.all([
  fetch('/api/dashboard/kpis').then(r => r.json()),
  fetch('/api/dashboard/trends').then(r => r.json()),
  fetch('/api/dashboard/comparisons').then(r => r.json()),
  fetch('/api/dashboard/gauges').then(r => r.json())
])
.then(([kpis, trends, comparisons, gauges]) => {
  renderKPIs(kpis);
  renderTrendCharts(trends);
  renderComparisonCharts(comparisons);
  renderGauges(gauges);
  updateTimestamp();
})
.catch(handleDashboardError);

// Manual refresh
document.getElementById('refreshBtn').addEventListener('click', () => {
  refreshDashboard(); // Re-runs Promise.all
});
```

## Layout & Visual Design

### Color Scheme

**Performance Tiers**:
- Green (Good): On-Time ≥90%, Utilization ≥80%, Completeness ≥95%
- Yellow (Caution): On-Time 70-89%, Utilization 50-79%, Completeness 85-94%
- Red (Needs Attention): On-Time <70%, Utilization <50%, Completeness <85%

**Chart Palette**: Professional 5-color scheme
- Primary: #3b82f6 (blue)
- Secondary: #14b8a6 (teal)
- Tertiary: #8b5cf6 (purple)
- Quaternary: #f97316 (orange)
- Neutral: #6b7280 (gray)

**KPI Card Design**:
- Compact 200px height, white background, subtle shadow
- Layout: Icon (left) → Value (center) → Sparkline (right)
- Bottom: "View details →" link scrolls to relevant chart
- Icon colored by performance tier (green/yellow/red)

### Chart Specifications

**Line Charts (Trends)**:
- Delivery Counts: Smooth curved line, gradient area fill, tooltips on hover
- Fuel Efficiency: Dual-axis chart (blue line for KM/Liter, orange for cost/KM)
- Truck Utilization: Step-line chart, horizontal target line at 80%
- All: Data zoom slider at bottom, legend toggle for series

**Bar Charts (Comparisons)**:
- Vehicle Utilization: Horizontal bars, sorted by %, color-coded by performance tier
- Branch Frequency: Vertical bars, top 10 + "Others" aggregate, count labels on bars
- Driver Performance: Vertical bars, trip count, different color for drivers vs assistants

**Gauge Charts**:
- Semi-circular (180°), 3 gauges in a row
- Color bands: Red (0-50%), Yellow (50-80%), Green (80-100%)
- Needle pointer + percentage text in center
- Subtitle: "Target: 80%" (placeholder reference)

### Responsive Design

**Desktop (≥992px)**:
- 2-column chart layout
- 3×2 KPI grid (3 columns, 2 rows)
- Full ECharts interactivity

**Tablet (768-991px)**:
- Stacked charts (single column)
- 2×3 KPI grid (2 columns, 3 rows)
- Reduced chart heights

**Mobile (<768px)**:
- Single column layout
- Stacked KPI cards (1 column)
- Simplified charts (hide secondary y-axes, smaller fonts)
- Action bar collapses to hamburger menu

## Error Handling & Edge Cases

### No Data Scenarios
- **Empty date range**: Show "No data available for selected period" in each chart, display "—" in KPI cards
- **Missing ODO records**: Calculate with available data, show "⚠️ Partial data" badge
- **New vehicles** (< 7 days): Include in calculations, mark with "New" tooltip

### Data Validation
- **Invalid date ranges**: Client-side prevents end_date before start_date, max 90-day limit
- **Future dates**: Auto-adjust end_date to today
- **Extreme values**: Filter outliers (KM/Liter > 100 or < 2), show filtered data note

### Performance Edge Cases
- **Large datasets** (> 5000 records): Auto-aggregate to weekly granularity
- **Slow queries**: Show loading spinners, progressive rendering
- **Concurrent refreshes**: Disable refresh button during loading

### API Error Handling
- Format: `{"error": "Human-readable message", "details": "Technical context"}`
- Client displays dismissible error banner at top of dashboard (below action bar)
- Error banner: Red background, white text, auto-dismiss after 10 seconds or manual close (X button)
- Failed chart sections show "Unable to load data. Retry?" button that retries individual endpoint
- Network errors show specific message: "Unable to connect to server. Check your internet connection."

### Caching Strategy

**Backend Caching** (using existing SimpleCache):
- KPI endpoint: Cache for 5 minutes
  - Reason: Expensive aggregations, changes infrequently within 5 minutes
  - Key: `dashboard_kpis_{start_date}_{end_date}`
- Trends endpoint: Cache for 10 minutes
  - Reason: Historical data doesn't change, longer cache acceptable
  - Key: `dashboard_trends_{start_date}_{end_date}_{granularity}`
- Comparisons endpoint: Cache for 10 minutes
  - Reason: Ranked data stable over time
  - Key: `dashboard_comparisons_{start_date}_{end_date}`
- Gauges endpoint: Cache for 5 minutes (or remove if redundant with KPIs)

**Cache Invalidation**:
- Manual refresh button bypasses cache (`?refresh=true` query param)
- Auto-invalidate when new trips/ODO records added (listen to model changes in Phase 2)
- Cache keys include date ranges, automatically invalidates when dates change

**Frontend Caching**:
- ECharts instances cached in JavaScript variables
- Destroy and recreate charts on refresh (prevents memory leaks)
- Store previous period data for trend comparison (in-memory)

### Browser Compatibility
- **Supported**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Graceful degradation**: Show table-based fallback if canvas rendering fails

## Implementation Phases

### Phase 1: Foundation
- Create Flask route `/` with admin permission check
- Build `templates/dashboard.html` with action bar and grid layout
- Add Bootstrap Icons library
- Set up responsive layout (mobile-first)

### Phase 2: Backend API Development
- Implement `GET /api/dashboard/kpis` with SQLAlchemy aggregations
- Implement `GET /api/dashboard/trends` with time-series data
- Implement `GET /api/dashboard/comparisons` with ranked data
- Implement `GET /api/dashboard/gauges` with current values
- Add query parameter handling
- Write unit tests for KPI calculations

### Phase 3: Frontend Integration
- Add Apache ECharts library via CDN
- Implement KPI card rendering with data binding
- Create line chart components (3 charts)
- Create bar chart components (3 charts)
- Create gauge chart components (3 charts)
- Implement refresh functionality

### Phase 4: Polish & Optimization
- Add loading spinners and progressive rendering
- Implement error handling and user-friendly messages
- Add responsive breakpoints
- Optimize slow queries with database indexes if needed
- Test cross-browser compatibility

### Phase 5: Documentation & Deployment
- Update CLAUDE.md with dashboard architecture
- Document API endpoints in code comments
- Create user guide markdown
- Deploy to staging for UAT
- Monitor and optimize based on usage

**Estimated Effort**: 1 week (5-7 days) for full implementation

## Testing Strategy

### Unit Testing (Backend)
- KPI calculations with known data sets
- Edge cases: empty datasets, single record, all-missing data
- Date range handling: future dates, inverted ranges, 90+ day ranges
- Permission checks: admin vs non-admin access

### Integration Testing (API)
- Verify all 4 endpoints return valid JSON structure
- Test with production-like data volumes (1000+ records)
- Verify query parameter filtering
- Test error response format

### Frontend Testing (Charts)
- Manual testing: Chart rendering with different data sizes
- Browser testing: Chrome, Firefox, Safari, Edge (latest versions)
- Responsive testing: Desktop (1920×1080), tablet (768×1024), mobile (375×667)
- Interaction testing: Tooltips, legend toggles, zoom sliders

### User Acceptance Testing (Admin Workflow)
- Can admin users load dashboard and see all KPIs?
- Does refresh button update data correctly?
- Do quick action links work?
- Is dashboard readable and actionable?
- Performance: < 3 seconds load time with 30 days data

### Regression Testing (Existing Features)
- Verify `/reports` page still works
- Confirm non-admin users still redirect to `/view_schedule`
- Test all quick action links navigate correctly
- Ensure no breaking changes to existing routes

### Success Criteria
- Dashboard loads in < 3 seconds with 30 days of data
- All 6 KPIs calculate correctly (verified against manual calculations)
- Charts render without errors across all supported browsers
- Admin users can access dashboard, non-admins cannot
- Refresh functionality works reliably
- Mobile view is functional for basic monitoring

## Dependencies & Libraries

### Backend (Flask)
- Flask 3.1.3 (existing)
- Flask-SQLAlchemy 3.1.1 (existing)
- Flask-Login 0.6.3 (existing)
- pytz (existing, for timezone handling)

### Frontend
- Apache ECharts 5.x (via CDN)
- Bootstrap Icons 1.x (via CDN, if not already present)
- Bootstrap CSS (existing)

### Optional Enhancements
- Flask-Caching (SimpleCache already in codebase)
- Database indexes on frequently queried fields

## Clarifications & Decisions

### Business Logic Decisions

**1. Trip-to-Delivery Relationship for DIFOT**
- A TripDetail is considered "on-time" if `Schedule.delivery_schedule <= TripDetail.original_due_date`
- A TripDetail is considered "in-full" if `TripDetail.total_delivered_qty >= TripDetail.total_ordered_qty`
- KPIs are calculated at TripDetail level (not Trip level) since multiple deliveries can happen per trip
- This matches the existing DIFOT report implementation

**2. Odo-to-Schedule Link**
- Odo records are linked to Vehicle, not Schedule or Trip
- For data completeness, we check if a vehicle that had trips in the period has any ODO records in the same datetime range
- This assumes ODO records are logged daily for active vehicles

**3. Truck Utilization Baseline**
- Vehicles with NO trips in the period are excluded from the utilization average
- This provides a more accurate measure of active fleet performance
- Alternative approach (counting inactive vehicles as 0%) can be added in Phase 2 if needed

**4. Data Completeness Business Rule**
- TripDetails missing arrival OR departure time are counted as incomplete
- Vehicles with trips but no ODO records in the period are flagged
- Missing arrival and missing departure are tracked separately (not double-counted)
- Formula: `completeness = (total_details - incomplete_details) / total_details * 100`

**5. Fuel Cost Calculation**
- Cost per KM uses weighted average by distance traveled
- Vehicles with more distance contribute more to the average
- Formula: `weighted_cost_per_km = sum(cost_per_km_i * distance_i) / sum(distance_i)`

**6. Weekly Aggregation**
- Weeks start on Monday (ISO 8601 standard)
- Can be made configurable in Phase 2 if needed

**7. Trend Calculation**
- Trend values compare current period vs previous period of same length
- Example: For 7-day dashboard (Mar 15-21), compare with previous 7 days (Mar 8-14)
- Trend is percentage point difference, not percentage change
- Example: On-time rate was 85% last period, 87.5% this period = +2.5 trend

## Open Questions & Future Enhancements
- Custom target thresholds for KPIs (currently using placeholder 80%)
- Scheduled report delivery (email dashboard PDF on schedule)
- User-role customization (different views for admins, coordinators)
- Historical comparison (compare current period vs previous period)
- Public share link for read-only dashboard access

### Data Quality Improvements
- Automated data quality alerts (email when completeness < 85%)
- Trend anomaly detection (flag unusual spikes/drops)
- Predictive analytics (forecast utilization based on trends)

### Interactive Features
- Drill-down from KPI cards to detailed filtered reports
- Custom date range presets (Last 7 days, Last 30 days, This Month)
- Export dashboard as PDF/image
- Customizable dashboard layout (user can rearrange cards)

## Metrics & Success Measurement

- **Dashboard adoption**: % of admin users who access dashboard daily/weekly
- **Page load performance**: Average load time (target: < 3 seconds)
- **Data quality improvement**: Trend in data completeness % over time
- **User satisfaction**: Feedback from admin users after 2 weeks of use
- **Operational impact**: Correlation between dashboard visibility and KPI improvements

---

**Next Steps**: After approval, this spec will be used to create a detailed implementation plan using the writing-plans skill.
