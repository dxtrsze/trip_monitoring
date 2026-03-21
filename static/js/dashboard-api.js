// Dashboard API client

const DashboardAPI = {
  // Fetch all KPI data
  async fetchKPIs(startDate = null, endDate = null) {
    let url = '/api/dashboard/kpis';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch KPIs: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch trends data
  async fetchTrends(startDate = null, endDate = null, granularity = 'daily') {
    let url = '/api/dashboard/trends';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    params.append('granularity', granularity);
    url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch trends: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch comparison data
  async fetchComparisons(startDate = null, endDate = null, today = false) {
    let url = '/api/dashboard/comparisons';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (today) params.append('today', 'true');
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch comparisons: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch gauge data
  async fetchGauges(startDate = null, endDate = null) {
    let url = '/api/dashboard/gauges';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) url += '?' + params.toString();

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch gauges: ${response.statusText}`);
    }
    return await response.json();
  },

  // Fetch all dashboard data in parallel
  async fetchAll(startDate = null, endDate = null) {
    const [kpis, trends, comparisons, gauges] = await Promise.all([
      this.fetchKPIs(startDate, endDate),
      this.fetchTrends(startDate, endDate),
      this.fetchComparisons(startDate, endDate),
      this.fetchGauges(startDate, endDate)
    ]);
    return { kpis, trends, comparisons, gauges };
  }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DashboardAPI;
}
