// Dashboard main controller

(function() {
  'use strict';

  let lastUpdateTime = null;

  // Initialize dashboard on page load
  async function initDashboard() {
    try {
      showLoading();

      // Fetch all data in parallel
      const data = await DashboardAPI.fetchAll();

      // Render all components
      DashboardCharts.renderKPIs(data.kpis);
      DashboardCharts.initDeliveryCountsChart(data.trends.daily_deliveries);
      DashboardCharts.initFuelEfficiencyChart(data.trends.fuel_efficiency);
      DashboardCharts.initTruckUtilizationChart(data.trends.truck_utilization);
      DashboardCharts.initVehicleUtilizationChart(data.comparisons.vehicle_utilization);
      DashboardCharts.initBranchFrequencyChart(data.comparisons.branch_frequency);
      DashboardCharts.initDriverPerformanceChart(data.comparisons.driver_performance);
      DashboardCharts.initGauges(data.gauges);

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

      // Re-fetch and render
      await initDashboard();

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
    const container = document.getElementById('kpiContainer');
    if (container) {
      container.style.opacity = '0.5';
      container.style.pointerEvents = 'none';
    }
  }

  // Hide loading state
  function hideLoading() {
    const container = document.getElementById('kpiContainer');
    if (container) {
      container.style.opacity = '1';
      container.style.pointerEvents = 'auto';
    }
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
