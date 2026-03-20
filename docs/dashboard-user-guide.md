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
