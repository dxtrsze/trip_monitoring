// Dashboard main controller

(function() {
  'use strict';

  let lastUpdateTime = null;
  let autoRefreshInterval = null;

  // Initialize dashboard on page load
  async function initDashboard() {
    try {
      showLoading();

      // Get today's date in Manila timezone
      const manilaNow = new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' });
      const today = new Date(manilaNow).toISOString().split('T')[0];

      // Fetch all data in parallel
      const data = await DashboardAPI.fetchAll();

      // Fetch today's KPIs (KPI Daily section)
      const todayKPIs = await DashboardAPI.fetchKPIs(today, today);

      // Fetch today's vehicle utilization separately (backend uses Manila time)
      const todayComparisons = await DashboardAPI.fetchComparisons(null, null, true);

      // Set default date range to last 7 days
      const end_date = new Date(manilaNow);
      const start_date = new Date(end_date);
      start_date.setDate(start_date.getDate() - 6);
      const startDateStr = start_date.toISOString().split('T')[0];
      const endDateStr = end_date.toISOString().split('T')[0];

      // Fetch KPI Range with default 7-day range
      const rangeKPIs = await DashboardAPI.fetchKPIs(startDateStr, endDateStr);

      // Render all components
      DashboardCharts.renderKPIs(data.kpis, 'kpiCards');
      DashboardCharts.renderKPIs(todayKPIs, 'kpiDailyCards');
      DashboardCharts.renderKPIs(rangeKPIs, 'kpiRangeCards');
      DashboardCharts.initDeliveryCountsChart(data.trends.daily_deliveries);
      DashboardCharts.initFuelEfficiencyChart(data.trends.fuel_efficiency);
      DashboardCharts.initTruckUtilizationChart(data.trends.truck_utilization);
      DashboardCharts.initVehicleUtilizationChart(todayComparisons.vehicle_utilization);
      DashboardCharts.initGauges(data.gauges);

      // Set date range inputs
      document.getElementById('rangeStartDate').value = startDateStr;
      document.getElementById('rangeEndDate').value = endDateStr;

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

      // Get today's date in Manila timezone
      const manilaNow = new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' });
      const today = new Date(manilaNow).toISOString().split('T')[0];

      // Re-fetch and render with bypass cache
      const data = await DashboardAPI.fetchAll(null, null, true);

      // Fetch today's KPIs (KPI Daily section)
      const todayKPIs = await DashboardAPI.fetchKPIs(today, today, true);

      // Fetch today's vehicle utilization separately (backend uses Manila time)
      const todayComparisons = await DashboardAPI.fetchComparisons(null, null, true);

      // Get current date range from inputs
      const startDateStr = document.getElementById('rangeStartDate').value;
      const endDateStr = document.getElementById('rangeEndDate').value;

      // Fetch KPI Range with current date range
      const rangeKPIs = await DashboardAPI.fetchKPIs(startDateStr, endDateStr, true);

      // Render all components
      DashboardCharts.renderKPIs(data.kpis, 'kpiCards');
      DashboardCharts.renderKPIs(todayKPIs, 'kpiDailyCards');
      DashboardCharts.renderKPIs(rangeKPIs, 'kpiRangeCards');
      DashboardCharts.initDeliveryCountsChart(data.trends.daily_deliveries);
      DashboardCharts.initFuelEfficiencyChart(data.trends.fuel_efficiency);
      DashboardCharts.initTruckUtilizationChart(data.trends.truck_utilization);
      DashboardCharts.initVehicleUtilizationChart(todayComparisons.vehicle_utilization);
      DashboardCharts.initGauges(data.gauges);

      // Update timestamp
      lastUpdateTime = new Date();
      updateTimestampDisplay();

      hideLoading();

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
    // Add loading overlay to each chart container
    const chartContainers = document.querySelectorAll('.card-body div[id$="Chart"], .card-body div[id$="Gauge"]');
    chartContainers.forEach(container => {
      container.innerHTML = '<div class="d-flex justify-content-center align-items-center h-100"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    });

    // Add loading overlay to KPI card containers
    const kpiContainers = document.querySelectorAll('#kpiCards, #kpiDailyCards, #kpiRangeCards');
    kpiContainers.forEach(container => {
      container.innerHTML = '<div class="col-12"><div class="d-flex justify-content-center align-items-center p-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading KPIs...</span></div></div></div>';
    });
  }

  // Hide loading state
  function hideLoading() {
    // Loading indicators removed when charts render
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

    // Auto-refresh toggle
    const autoRefreshToggle = document.getElementById('autoRefreshToggle');
    if (autoRefreshToggle) {
      autoRefreshToggle.addEventListener('change', function () {
        if (this.checked) {
          autoRefreshInterval = setInterval(refreshDashboard, 300000); // 5 min
        } else {
          clearInterval(autoRefreshInterval);
          autoRefreshInterval = null;
        }
      });
    }

    // Date preset buttons
    document.querySelectorAll('.date-presets .btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        // Remove active from all
        document.querySelectorAll('.date-presets .btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        const days = parseInt(this.dataset.days);
        const manilaNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' }));
        const end = new Date(manilaNow);
        const start = new Date(manilaNow);
        start.setDate(start.getDate() - (days - 1));

        document.getElementById('rangeStartDate').value = start.toISOString().split('T')[0];
        document.getElementById('rangeEndDate').value = end.toISOString().split('T')[0];

        // Trigger range refresh
        document.getElementById('rangeRefreshBtn').click();
      });
    });

    // KPI Range Apply button handler
    const rangeRefreshBtn = document.getElementById('rangeRefreshBtn');
    if (rangeRefreshBtn) {
      rangeRefreshBtn.addEventListener('click', async function() {
        const startDate = document.getElementById('rangeStartDate').value;
        const endDate = document.getElementById('rangeEndDate').value;

        if (!startDate || !endDate) {
          showError('Please select both start and end dates');
          return;
        }

        // Validate date range
        const start = new Date(startDate);
        const end = new Date(endDate);
        const diffTime = Math.abs(end - start);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

        if (diffDays > 90) {
          showError('Date range cannot exceed 90 days');
          return;
        }

        if (start > end) {
          showError('Start date must be before or equal to end date');
          return;
        }

        // Disable button and show loading
        rangeRefreshBtn.disabled = true;
        rangeRefreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';

        try {
          // Fetch KPI data for selected range
          const rangeKPIs = await DashboardAPI.fetchKPIs(startDate, endDate, true);
          DashboardCharts.renderKPIs(rangeKPIs, 'kpiRangeCards');
        } catch (error) {
          console.error('Failed to load KPI range:', error);
          showError(error.message);
        } finally {
          rangeRefreshBtn.disabled = false;
          rangeRefreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Apply Range';
        }
      });
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
