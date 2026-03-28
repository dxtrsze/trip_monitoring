// Dashboard charts module using Apache ECharts

const DashboardCharts = (function () {
  let charts = {}; // Store chart instances

  // Initialize KPI cards rendering
  function renderKPIs(kpiData, containerId = "kpiCards") {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";

    const kpiConfig = [
      {
        key: "on_time_delivery_rate",
        label: "On-Time Delivery Rate",
        type: "on_time",
      },
      {
        key: "in_full_delivery_rate",
        label: "In-Full Delivery Rate",
        type: "on_time",
      },
      { key: "difot_score", label: "DIFOT Score", type: "on_time" },
      {
        key: "truck_utilization",
        label: "Truck Utilization",
        type: "utilization",
      },
      {
        key: "fuel_efficiency",
        label: "Fuel Efficiency (KM/L)",
        type: "efficiency",
      },
      {
        key: "data_completeness",
        label: "Data Completeness",
        type: "completeness",
      },
    ];

    kpiConfig.forEach((config) => {
      const kpi = kpiData[config.key];
      const color = getPerformanceColor(kpi.value, config.type);
      const card = createKPICard(config, kpi, color);
      container.appendChild(card);
    });
  }

  function createKPICard(config, kpi, color) {
    const col = document.createElement("div");
    col.className = "col-md-4 col-sm-6 mb-3";

    const card = document.createElement("div");
    card.className = "card h-100";
    card.style.borderTop = `4px solid ${color}`;

    // Format value based on KPI type
    let formattedValue;
    if (typeof kpi.value === "number") {
      if (
        config.key.includes("rate") ||
        config.key.includes("score") ||
        config.key.includes("utilization") ||
        config.key.includes("completeness")
      ) {
        formattedValue = kpi.value.toFixed(1) + "%";
      } else {
        formattedValue = kpi.value.toFixed(1);
      }
    } else {
      formattedValue = kpi.value;
    }

    card.innerHTML = `
      <div class="card-body">
        <div class="d-flex align-items-center">
          <div class="me-3" style="font-size: 2rem; color: ${color};">
            <i class="bi ${getKPIIcon(config.key)}"></i>
          </div>
          <div class="flex-grow-1">
            <h6 class="card-subtitle mb-1 text-muted">${config.label}</h6>
            <h3 class="card-title mb-0">${formattedValue}</h3>
          </div>
          <div class="text-end">
            <small class="text-muted">Trend</small><br>
            ${getTrendHtml(kpi.trend)}
          </div>
        </div>
      </div>
    `;

    col.appendChild(card);
    return col;
  }

  // Initialize delivery counts chart
  function initDeliveryCountsChart(data) {
    const chartDom = document.getElementById("deliveryCountsChart");
    if (!chartDom) return;

    charts.deliveryCounts = echarts.init(chartDom);

    const dates = data.map((d) => formatDate(d.date));
    const counts = data.map((d) => d.count);

    const option = {
      title: { text: "" },
      tooltip: {
        trigger: "axis",
        formatter: function (params) {
          const p = params[0];
          return `${p.axisValue}<br/>Deliveries: <strong>${p.value}</strong>`;
        },
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { rotate: 30 },
      },
      yAxis: {
        type: "value",
        name: "Deliveries",
      },
      series: [
        {
          name: "Deliveries",
          type: "line",
          smooth: true,
          data: counts,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
              { offset: 1, color: "rgba(59, 130, 246, 0.05)" },
            ]),
          },
          itemStyle: { color: "#3b82f6" },
          lineStyle: { width: 3 },
        },
      ],
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
    };

    charts.deliveryCounts.setOption(option);
  }

  // Initialize fuel efficiency chart
  function initFuelEfficiencyChart(data) {
    const chartDom = document.getElementById("fuelEfficiencyChart");
    if (!chartDom) return;

    charts.fuelEfficiency = echarts.init(chartDom);

    const dates = data.map((d) => formatDate(d.date));
    const kmPerLiter = data.map((d) => d.km_per_liter);

    const option = {
      title: { text: "" },
      tooltip: {
        trigger: "axis",
        formatter: function (params) {
          const p = params[0];
          return `${p.axisValue}<br/>${p.marker}${p.seriesName}: <strong>${p.value.toFixed(2)}</strong>`;
        },
      },
      legend: { data: ["KM/Liter"] },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { rotate: 30 },
      },
      yAxis: {
        type: "value",
        name: "KM/Liter",
      },
      series: [
        {
          name: "KM/Liter",
          type: "line",
          smooth: true,
          data: kmPerLiter,
          itemStyle: { color: "#3b82f6" },
          lineStyle: { width: 2 },
        },
      ],
      grid: { left: 60, right: 40, top: 40, bottom: 60 },
    };

    charts.fuelEfficiency.setOption(option);
  }

  // Initialize truck utilization chart
  function initTruckUtilizationChart(data) {
    const chartDom = document.getElementById("truckUtilizationChart");
    if (!chartDom) return;

    charts.truckUtilization = echarts.init(chartDom);

    const dates = data.map((d) => formatDate(d.date));
    const utilization = data.map((d) => d.utilization_percent);

    const option = {
      title: { text: "" },
      tooltip: {
        trigger: "axis",
        formatter: function (params) {
          const p = params[0];
          return `${p.axisValue}<br/>Utilization: <strong>${p.value.toFixed(1)}%</strong>`;
        },
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { rotate: 30 },
      },
      yAxis: {
        type: "value",
        name: "Utilization %",
        max: 100,
        axisLabel: { formatter: "{value}%" },
      },
      series: [
        {
          name: "Utilization",
          type: "line",
          step: "middle",
          data: utilization,
          itemStyle: { color: "#8b5cf6" },
          lineStyle: { width: 2 },
          markLine: {
            data: [{ yAxis: 80, name: "Target" }],
            lineStyle: { color: "#10b981", type: "dashed", width: 2 },
            label: { formatter: "Target: 80%" },
          },
        },
      ],
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
    };

    charts.truckUtilization.setOption(option);
  }

  // Initialize vehicle utilization ranking chart
  function initVehicleUtilizationChart(data) {
    const chartDom = document.getElementById("vehicleUtilizationChart");
    if (!chartDom) return;

    charts.vehicleUtilization = echarts.init(chartDom);

    const vehicles = data.map((d) => d.plate_number);
    const utilization = data.map((d) => d.utilization);

    const option = {
      title: { text: "" },
      tooltip: {
        trigger: "axis",
        formatter: function (params) {
          const p = params[0];
          return `${p.name}<br/>Utilization: <strong>${p.value.toFixed(1)}%</strong>`;
        },
      },
      xAxis: {
        type: "value",
        max: 100,
        axisLabel: { formatter: "{value}%" },
      },
      yAxis: {
        type: "category",
        data: vehicles,
        inverse: true,
      },
      series: [
        {
          type: "bar",
          data: utilization,
          itemStyle: {
            color: function (params) {
              const value = params.value;
              if (value >= 80) return "#10b981";
              if (value >= 50) return "#f59e0b";
              return "#ef4444";
            },
          },
          label: {
            show: true,
            position: "right",
            formatter: "{c}%",
          },
        },
      ],
      grid: { left: 120, right: 40, top: 20, bottom: 40 },
    };

    charts.vehicleUtilization.setOption(option);
  }

  // Initialize gauge charts
  function initGauges(gaugeData) {
    // On-Time Rate Gauge
    const onTimeDom = document.getElementById("onTimeGauge");
    if (onTimeDom) {
      charts.onTimeGauge = echarts.init(onTimeDom);
      charts.onTimeGauge.setOption({
        series: [
          {
            type: "gauge",
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 5,
            axisLine: {
              lineStyle: {
                width: 20,
                color: [
                  [0.5, "#ef4444"],
                  [0.8, "#f59e0b"],
                  [1, "#10b981"],
                ],
              },
            },
            pointer: { itemStyle: { color: "auto" } },
            axisTick: { distance: -20, length: 8 },
            splitLine: { distance: -20, length: 20 },
            axisLabel: { distance: -40, formatter: "{value}%" },
            detail: {
              valueAnimation: true,
              formatter: "{value}%",
              color: "auto",
              fontSize: 20,
              offsetCenter: [0, "80%"],
            },
            title: {
              offsetCenter: [0, "95%"],
              fontSize: 12,
            },
            data: [{ value: gaugeData.on_time_rate, name: "On-Time" }],
          },
        ],
      });
    }

    // Utilization Gauge
    const utilDom = document.getElementById("utilizationGauge");
    if (utilDom) {
      charts.utilizationGauge = echarts.init(utilDom);
      charts.utilizationGauge.setOption({
        series: [
          {
            type: "gauge",
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 5,
            axisLine: {
              lineStyle: {
                width: 20,
                color: [
                  [0.5, "#ef4444"],
                  [0.8, "#f59e0b"],
                  [1, "#10b981"],
                ],
              },
            },
            pointer: { itemStyle: { color: "auto" } },
            axisTick: { distance: -20, length: 8 },
            splitLine: { distance: -20, length: 20 },
            axisLabel: { distance: -40, formatter: "{value}%" },
            detail: {
              valueAnimation: true,
              formatter: "{value}%",
              color: "auto",
              fontSize: 20,
              offsetCenter: [0, "80%"],
            },
            title: {
              offsetCenter: [0, "95%"],
              fontSize: 12,
            },
            data: [{ value: gaugeData.utilization, name: "Utilization" }],
          },
        ],
      });
    }

    // Completeness Gauge
    const completeDom = document.getElementById("completenessGauge");
    if (completeDom) {
      charts.completenessGauge = echarts.init(completeDom);
      charts.completenessGauge.setOption({
        series: [
          {
            type: "gauge",
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 5,
            axisLine: {
              lineStyle: {
                width: 20,
                color: [
                  [0.5, "#ef4444"],
                  [0.85, "#f59e0b"],
                  [1, "#10b981"],
                ],
              },
            },
            pointer: { itemStyle: { color: "auto" } },
            axisTick: { distance: -20, length: 8 },
            splitLine: { distance: -20, length: 20 },
            axisLabel: { distance: -40, formatter: "{value}%" },
            detail: {
              valueAnimation: true,
              formatter: "{value}%",
              color: "auto",
              fontSize: 20,
              offsetCenter: [0, "80%"],
            },
            title: {
              offsetCenter: [0, "95%"],
              fontSize: 12,
            },
            data: [{ value: gaugeData.data_completeness, name: "Complete" }],
          },
        ],
      });
    }
  }

  // Resize all charts
  function resizeCharts() {
    Object.values(charts).forEach((chart) => {
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  }

  // Destroy all charts
  function destroyCharts() {
    Object.values(charts).forEach((chart) => {
      if (chart && chart.dispose) {
        chart.dispose();
      }
    });
    charts = {};
  }

  // Return public API
  return {
    renderKPIs,
    initDeliveryCountsChart,
    initFuelEfficiencyChart,
    initTruckUtilizationChart,
    initVehicleUtilizationChart,
    initGauges,
    resizeCharts,
    destroyCharts,
  };
})();
