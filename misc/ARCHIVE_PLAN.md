 Implementation Plan

 1. Create Archive Database Models Module

 File: archive_models.py (new file)

 - Duplicate the models from models.py
 - Modify to use a separate SQLAlchemy database instance for archive
 - All models: Vehicle, Manpower, Data, Schedule, Trip, TripDetail, Cluster, User, Odo, DailyVehicleCount, Backload, TimeLog, LCLSummary,
 LCLDetail
 - Association tables: trip_driver, trip_assistant

 Rationale: Separate models file allows the same application to interact with both databases simultaneously.

 2. Create Archive Service Module

 File: archive_service.py (new file)

 Functions:

 def get_archive_cutoff_year():
     """Return the year cutoff for archiving (current_year - 2)"""

 def init_archive_database():
     """Initialize archive database and create all tables"""

 def identify_records_to_archive():
     """Identify all records to archive by calendar year
     Returns dict with table names and lists of IDs/records"""

 def archive_data_records():
     """Archive Data table records by due_date"""

 def archive_lcl_detail_records():
     """Archive LCLDetail records by sap_upload_date"""

 def archive_lcl_summary_records():
     """Archive LCLSummary records by posting_date"""

 def archive_odo_records():
     """Archive Odo records by datetime"""

 def archive_schedule_and_related_records():
     """Archive Schedule + Trip + TripDetail + trip_driver + trip_assistant + Vehicle"""

 def archive_time_log_records():
     """Archive TimeLog records by time_in + User"""

 def archive_daily_vehicle_count_records():
     """Archive DailyVehicleCount records by date"""

 def execute_archive():
     """Main orchestration function
     - Begin transaction on both databases
     - Copy records to archive database
     - Delete from main database
     - Commit both transactions
     - Rollback both on any error
     Returns: dict with counts and status"""

 Key Implementation Details:
 - Use calendar year logic: record.year <= (current_year - 2)
 - Handle transactions across both databases with rollback capability
 - Archive Vehicle/Manpower copies when referenced by archived trips
 - Preserve User, Cluster tables (don't archive, only reference)
 - Use SQLAlchemy ORM for all operations (database-agnostic)

 3. Create Archive Web Interface

 File: templates/archive_admin.html (new file)

 Features:
 - Display archive database status (last archive date, record counts)
 - Show preview of what will be archived (count by table)
 - "Execute Archive" button with confirmation
 - Progress indicator during archive operation
 - Success/error message display
 - Archive history log (optional)

 Design:
 - Bootstrap-styled admin page
 - Card-based layout for status information
 - Modal confirmation before executing archive
 - Progress bar for long-running operations
 - AJAX calls for non-blocking execution

 4. Add Archive Routes to app.py

 New Routes:

 @app.route('/admin/archive')
 @login_required
 def archive_admin():
     """Display archive admin page"""

 @app.route('/admin/archive/status')
 @login_required
 def archive_status():
     """Return JSON with archive status and counts"""

 @app.route('/admin/archive/execute', methods=['POST'])
 @login_required
 def execute_archive():
     """Execute archive operation and return JSON result"""

 Security: Add admin-only decorator to restrict access

 5. Create Archive Log Table

 New Model: ArchiveLog in models.py

 class ArchiveLog(db.Model):
     __tablename__ = 'archive_log'
     id = db.Column(db.Integer, primary_key=True)
     executed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
     cutoff_year = db.Column(db.Integer, nullable=False)
     records_archived = db.Column(db.Integer, nullable=False)
     tables_affected = db.Column(db.Text)  # JSON string
     status = db.Column(db.String(50))  # 'success', 'failed', 'partial'
     error_message = db.Column(db.Text)
     execution_time_seconds = db.Column(db.Float)

 Purpose: Track archive operations for audit trail and debugging

 Database Schema Changes

 Main Database (trip_monitoring.db)

 - Add archive_log table for tracking archive operations

 Archive Database (trip_archive.db)

 - Complete schema replication from main database
 - Same tables, columns, relationships, indexes
 - Association tables: trip_driver, trip_assistant

 Implementation Order

 1. Create archive_models.py - Separate models for archive database
 2. Create archive_service.py - Core archival logic
 3. Add ArchiveLog model to models.py - Track operations
 4. Add archive routes to app.py - Web interface endpoints
 5. Create templates/archive_admin.html - Admin UI
 6. Update templates/admin_dashboard.html - Add link to archive admin

 Critical Files

 New Files

 - /Users/dextercuasze/Desktop/trip_monitoring/archive_models.py
 - /Users/dextercuasze/Desktop/trip_monitoring/archive_service.py
 - /Users/dextercuasze/Desktop/trip_monitoring/templates/archive_admin.html

 Modified Files

 - /Users/dextercuasze/Desktop/trip_monitoring/models.py - Add ArchiveLog model
 - /Users/dextercuasze/Desktop/trip_monitoring/app.py - Add archive routes
 - /Users/dextercuasze/Desktop/trip_monitoring/templates/admin_dashboard.html - Add archive link

 Testing & Verification

 1. Unit Testing:
   - Test cutoff year calculation logic
   - Test record identification for each table
   - Test transaction rollback on errors
 2. Integration Testing:
   - Create test data with dates > 2 years old
   - Execute archive operation
   - Verify records exist in archive database
   - Verify records deleted from main database
   - Verify foreign key relationships preserved
   - Test error handling and rollback
 3. Manual Testing Steps:
 # 1. Check current database
 sqlite3 instance/trip_monitoring.db "SELECT COUNT(*) FROM data WHERE strftime('%Y', due_date) <= '2023'"

 # 2. Run archive via web interface
 # Navigate to /admin/archive, click Execute Archive

 # 3. Verify archive database
 sqlite3 instance/trip_archive.db "SELECT COUNT(*) FROM data WHERE strftime('%Y', due_date) <= '2023'"

 # 4. Verify main database
 sqlite3 instance/trip_monitoring.db "SELECT COUNT(*) FROM data WHERE strftime('%Y', due_date) <= '2023'"

 # 5. Check archive log
 sqlite3 instance/trip_monitoring.db "SELECT * FROM archive_log ORDER BY executed_at DESC LIMIT 1"
 4. Performance Testing:
   - Test with large datasets (10k+ records)
   - Monitor memory usage during archive
   - Verify execution time is acceptable (< 5 minutes for typical data)

 Edge Cases & Considerations

 1. Referential Integrity:
   - Trip/Schedule → Vehicle/Manpower references
   - Solution: Archive copies of referenced entities
 2. Duplicate IDs:
   - Both databases use same ID sequences
   - Solution: Archive maintains same IDs, no conflicts
 3. Partial Failures:
   - Transaction spans both databases
   - Solution: Two-phase commit pattern with rollback
 4. Concurrent Access:
   - Prevent conflicts during archive
   - Solution: Use app.app_context() with session isolation
 5. Calendar Year Edge Cases:
   - Leap years, different date formats
   - Solution: Extract year via SQLAlchemy extract('year', field)

 Rollback Plan

 If issues arise after deployment:
 1. Restore from backup (pre-archive backup created automatically)
 2. Copy data back from archive to main database manually
 3. Monitor archive_log table for operation history

 Future Enhancements (Out of Scope)

 - Scheduled automatic archival (cron job)
 - Restore from archive functionality
 - Archive database search interface
 - Compression of archive database
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌