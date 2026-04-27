# Trip Monitoring System - Features

## Overview
A comprehensive web application for managing delivery schedules, tracking vehicle utilization, monitoring fuel efficiency, and managing logistics operations with role-based access control.

---

## 🚚 Core Operations

### Delivery Schedule Management
- **Schedule Creation**: Create multi-day delivery schedules with automatic date range support
- **Trip Management**:
  - Assign multiple vehicles, drivers, and assistants per day
  - Real-time vehicle editing capabilities
  - Dynamic truck load utilization monitoring (CBM & quantity)
  - Automatic capacity utilization calculation with color-coded indicators
  - Multi-stop delivery planning with branch-based grouping
- **Delivery Order Optimization**: Reordering of delivery stops per trip (1st stop, 2nd stop, etc.)
- **Real-time Status Tracking**:
  - Track arrival/departure times at each location
  - In/Out button interface for drivers/assistants
  - Automatic status updates (Delivered, Cancelled, Not Scheduled)

### Vehicle Management
- **Vehicle Fleet Tracking**:
  - Manage vehicle inventory with plate numbers
  - Track vehicle capacity (CBM)
  - Department classification (Logistics, Executive, Service)
  - Active/Inactive status management
- **Vehicle Assignment**: Assign vehicles to specific trips with duplicate prevention
- **Vehicle Schedule Conflict Detection**: Alert if vehicle is already scheduled

### Manpower (Crew) Management
- **Driver & Assistant Management**:
  - Comprehensive personnel database
  - Role-based assignment (Driver, Assistant, Executive, TeamLead)
  - Link personnel to user accounts for time-tracking
- **Crew Assignment**:
  - Assign multiple drivers and assistants per trip
  - Real-time crew editing capabilities

---

## 📊 Monitoring & Tracking

### Odometer & Fuel Efficiency Tracking
- **ODO Logging System**:
  - Start ODO recording at trip beginning
  - End ODO recording at trip completion
  - Refill tracking (liters, amount, price per liter)
- **Fuel Efficiency Monitoring**:
  - Calculate total KM traveled per vehicle
  - Track fuel consumption and costs
  - Average price per liter calculations
  - Department-based filtering (Logistics, Executive, Service)
- **Executive Refill Logging**: Separate refill tracking for executive vehicles
- **Comprehensive ODO Logs**: View all ODO records with timestamps and user tracking

### Time-Keeping & Attendance
- **User Time Tracking**:
  - Time In/Time Out recording
  - Automatic overtime calculation
  - Daily schedule management (start/end times)
- **Time Log Management**:
  - Edit time logs for corrections
  - View attendance history
  - User-specific schedule tracking

### Truck Load Utilization
- **Capacity Monitoring**:
  - Real-time CBM utilization percentage
  - Color-coded utilization alerts:
    - Green: >75% utilization
    - Warning: >90% utilization
    - Danger: >100% utilization
- **Drop Count Tracking**: Number of delivery stops per trip
- **Fleet Utilization Reports**: Daily percentage of active trucks used

### Backload Management
- **Backload Identification**: Track undelivered quantities
- **Reason Tracking**: Categorize reasons for non-delivery
- **Search & Management**: Search trip details and apply backload status
- **Comprehensive Reason Codes**: 30+ predefined reasons including:
  - Branch-specific issues
  - Vehicle concerns
  - Documentation problems
  - Weather conditions
  - Unit concerns

---

## 📈 Reporting & Analytics

### Operational Reports
1. **Scheduled Trips Report**
   - View all scheduled deliveries within date range
   - Trip-level details with crew assignments
   - Delivery order tracking
   - Branch and quantity information
   - CSV export functionality

2. **Truck Load Utilization Report**
   - Per-trip capacity vs. actual load analysis
   - Utilization percentage calculations
   - Number of drops per trip
   - Identify underutilized or over capacity trips

3. **Truck Fleet Utilization Report**
   - Daily fleet usage metrics
   - Percentage of active trucks deployed
   - Track fleet efficiency over time

4. **Fuel Efficiency Report**
   - ODO records with comprehensive summary
   - Fuel consumption analysis by vehicle
   - Cost tracking and price per liter trends
   - Filter by vehicle and department

5. **Frequency Rate Report**
   - Delivery frequency by area/branch
   - Ranking of most frequently served locations
   - Support for route optimization decisions

6. **DIFOT Report** (Delivery In Full, On Time)
   - On-time delivery tracking
   - In-full delivery monitoring
   - Days late/early calculations
   - Identify delivery performance issues

### Automated Reports
- **Daily Vehicle Count**: Automated daily tracking of active vehicle count
  - Scheduled execution at 5:00 AM Manila Time
  - Historical tracking and trend analysis
  - Edit capability for manual adjustments
- **CSV Export**: All reports support CSV export for external analysis

---

## 🗂️ Data Management

### Deliveries/Data Management
- **CSV Upload**: Bulk upload shipment data
- **Data Editing**: Modify shipment details
- **Soft Delete**: Retain records with deletion tracking
  - Reason codes for deletion
  - Detailed remarks for audit trail
- **Search & Filter**: Advanced search capabilities
- **Template Download**: CSV template for data entry

### LCL Management
- **LCL Upload**: Bulk upload LCL shipment data
- **LCL Summary**: Track LCL shipments by posting date and company
- **LCL Details**: View individual LCL shipment records
- **SAP/ISMS Integration**: Track upload dates from multiple systems
- **Department Filtering**: View by LOGISTICS or TEAMLEAD

### Cluster Management
- **Cluster Database**: Manage delivery clusters/areas
- **Cluster Assignment**: Assign shipments to specific clusters
- **Weekly Schedule Tracking**: Per-cluster delivery schedules
- **Delivery Personnel Tracking**: Track who delivers to each cluster
- **Bulk Upload**: CSV upload for cluster data

---

## 👥 User Management & Security

### User Administration
- **Role-Based Access Control**:
  - **Admin**: Full system access
  - **Executive**: Limited to refill logging and view schedules
  - **TeamLead**: Middle management access
  - **User**: Basic access for assigned operations
- **User Management**:
  - Create, edit, delete users
  - Password management with secure reset
  - Individual password reset with auto-generation
  - Bulk password reset for all users (position='user')
  - User credential CSV export
- **Payroll Integration**:
  - Daily rate tracking per user
  - Schedule management (work hours)
  - Default values for new users

### Authentication & Security
- **Secure Login**: Password-protected access
- **Session Management**: Login/logout functionality
- **Password Security**: Hashed password storage
- **Access Control**: Route-level permission checks

---

## 🔧 Advanced Features

### Real-time Features
- **AJAX-powered Interface**: Dynamic content updates without page reload
- **Live Status Updates**: Real-time trip status changes
- **Conflict Detection**: Immediate feedback on scheduling conflicts
- **Dynamic Dropdowns**: Context-aware form options

### Data Caching
- **Performance Optimization**: Cached queries for vehicles and manpower
- **Automatic Cache Invalidation**: Smart cache management

### Scheduled Tasks
- **Automated Daily Tasks**: APScheduler for background jobs
- **Vehicle Count Scheduler**: Daily automated vehicle count
- **Configurable Schedule Times**: Manila Timezone (Asia/Manila) support

### Search & Filtering
- **Advanced Search**: Search across trip details, data records, backloads
- **Multi-criteria Filtering**: Filter by date, status, vehicle, department
- **Real-time Search**: Instant search results as you type

---

## 📋 Data Models

### Core Entities
- **Vehicle**: Fleet management with department classification
- **Manpower**: Drivers and assistants
- **User**: System users with role-based access
- **Schedule**: Delivery schedule management
- **Trip**: Individual trips within schedules
- **TripDetail**: Delivery stops within trips
- **Data**: Shipment/delivery data
- **Cluster**: Delivery area/cluster management
- **Odo**: Odometer and fuel tracking
- **TimeLog**: User time and attendance
- **DailyVehicleCount**: Automated daily metrics
- **Backload**: Undelivered quantity tracking
- **LCLSummary/LCLDetail**: Less-than-container-load management

---

## 📝 System Configuration

- **Scheduling**: APScheduler for automated tasks
- **Timezone**: Asia/Manila (Philippines)
- **Default Values**:
  - Daily Rate: ₱0.0
  - Schedule Start: 08:00
  - Schedule End: 18:00
  - Default Date: Tomorrow (for schedule creation)

---

## 📊 Reports Summary

| Report | Description | Export |
|--------|-------------|--------|
| Scheduled Trips | All scheduled deliveries by date range | CSV |
| Truck Load Utilization | Capacity vs actual load per trip | CSV |
| Fleet Utilization | Daily truck deployment metrics | CSV |
| Fuel Efficiency | ODO records and fuel consumption | CSV |
| Frequency Rate | Delivery frequency by area | CSV |
| DIFOT | On-time & in-full delivery performance | CSV |
| Daily Vehicle Counts | Automated daily active vehicle count | CSV |
| User Credentials | User list with generated passwords | CSV |

---

