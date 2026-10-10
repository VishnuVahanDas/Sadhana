// Individual dashboard: trend charts and heatmap behaviour.
(function () {
  var source = document.getElementById("chart-data");
  if (source && window.Chart) {
    var charts = JSON.parse(source.textContent);
    Chart.defaults.font.family = '"Noto Sans", system-ui, sans-serif';
    Chart.defaults.color = "#6B5E52";
    document.querySelectorAll("[data-chart]").forEach(function (canvas) {
      var chart = charts[parseInt(canvas.getAttribute("data-chart"), 10)];
      var few = chart.labels.length <= 15;
      new Chart(canvas, {
        type: "line",
        data: {
          labels: chart.labels,
          datasets: chart.datasets.map(function (series) {
            return {
              label: series.label,
              data: series.data,
              borderColor: series.color,
              backgroundColor: series.color,
              borderWidth: 2,
              pointRadius: few ? 3 : 0,
              pointHoverRadius: 5,
              pointBorderColor: "#FFFFFF",
              pointBorderWidth: 2,
              tension: 0,
            };
          }),
        },
        options: {
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { display: chart.datasets.length > 1, position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: {
              callbacks: {
                label: function (item) {
                  return item.dataset.label + ": " + item.formattedValue + (chart.unit ? " " + chart.unit : "");
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } },
            y: { beginAtZero: true, grid: { color: "#F3E6D0" }, border: { display: false }, ticks: { precision: 0 } },
          },
        },
      });
    });
  }

  // The heatmap opens on the most recent weeks.
  document.querySelectorAll("[data-scroll-end]").forEach(function (box) {
    box.scrollLeft = box.scrollWidth;
  });

  // Touch screens have no hover: show the tapped day's value under the heatmap.
  document.addEventListener("click", function (event) {
    var cell = event.target.closest("[data-heat]");
    var detail = document.getElementById("heat-detail");
    if (cell && detail) detail.textContent = cell.getAttribute("title");
  });
})();
