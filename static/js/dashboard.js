// Trend charts (My Report and Analysis) and heatmap behaviour.
(function () {
  var source = document.getElementById("chart-data");
  if (source && window.Chart) {
    var charts = JSON.parse(source.textContent);
    var words = JSON.parse(document.getElementById("chart-labels").textContent);
    var instances = {};
    Chart.defaults.font.family = '"Noto Sans", system-ui, sans-serif';
    // Chart colours follow the theme's CSS variables ("R G B" channels).
    var style = getComputedStyle(document.documentElement);
    var themed = function (name, alpha) {
      return "rgba(" + style.getPropertyValue(name).trim().replace(/ /g, ", ") + ", " + alpha + ")";
    };
    var gridColor = themed("--c-cream-dark", 1);
    Chart.defaults.color = themed("--c-ink", 0.7);

    // Festival days get a soft gold band behind the bars.
    var festivalBands = {
      id: "festivalBands",
      beforeDatasetsDraw: function (chart) {
        var days = chart.$sadhana.festivals;
        var x = chart.scales.x, area = chart.chartArea, ctx = chart.ctx;
        var width = chart.data.labels.length > 1 ? x.getPixelForValue(1) - x.getPixelForValue(0) : area.width;
        ctx.save();
        ctx.fillStyle = themed("--c-gold", 0.22);
        Object.keys(days).forEach(function (index) {
          ctx.fillRect(x.getPixelForValue(Number(index)) - width / 2, area.top, width, area.bottom - area.top);
        });
        ctx.restore();
      },
    };

    // In the "usual range" view, days above the cap are cut off at the top: mark them with their real value.
    var clipMarkers = {
      id: "clipMarkers",
      afterDatasetsDraw: function (chart) {
        if (!chart.$sadhana.capped) return;
        var ctx = chart.ctx, x = chart.scales.x, top = chart.chartArea.top;
        var lastRight = -Infinity;
        ctx.save();
        ctx.font = '600 11px "Noto Sans", system-ui, sans-serif';
        ctx.fillStyle = themed("--c-ink", 1);
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        chart.$sadhana.clipped.forEach(function (day) {
          var center = x.getPixelForValue(day.index);
          var text = "▲ " + day.value;
          var half = ctx.measureText(text).width / 2;
          if (center - half > lastRight + 4) {
            ctx.fillText(text, center, top - 2);
            lastRight = center + half;
          } else if (center - 5 > lastRight) {
            // No room for the number: the arrow alone; the value is in the tooltip and listed under the chart.
            ctx.fillText("▲", center, top - 2);
            lastRight = center + 5;
          }
        });
        ctx.restore();
      },
    };

    document.querySelectorAll("[data-chart]").forEach(function (canvas) {
      var id = canvas.getAttribute("data-chart");
      var chart = charts[parseInt(id, 10)];
      var instance = new Chart(canvas, {
        data: {
          labels: chart.labels,
          datasets: [
            {
              type: "line",
              // A comparison chart draws the previous period here; a trend chart draws the 7-day average.
              label: chart.previous ? words.previous : words.average,
              data: chart.previous || chart.average,
              borderColor: themed("--c-maroon", 1),
              backgroundColor: themed("--c-maroon", 1),
              borderWidth: 2,
              pointRadius: chart.previous && chart.labels.length <= 15 ? 3 : 0,
              pointHoverRadius: 4,
              tension: chart.previous ? 0 : 0.25,
              order: 0,
            },
            {
              type: "bar",
              label: chart.previous ? words.current : words.daily,
              data: chart.values,
              backgroundColor: themed("--c-saffron", 0.85),
              hoverBackgroundColor: themed("--c-saffron-dark", 1),
              borderRadius: { topLeft: 4, topRight: 4 },
              maxBarThickness: 28,
              order: 1,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          layout: { padding: { top: 18 } },
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: {
              callbacks: {
                // Always the real value, even when the bar is clipped.
                label: function (item) {
                  var name = item.dataset.label;
                  // The previous period's point belongs to another date: say which.
                  if (chart.previous && item.dataset.type === "line" && chart.previous_labels[item.dataIndex]) {
                    name += " (" + chart.previous_labels[item.dataIndex] + ")";
                  }
                  return name + ": " + item.formattedValue + (chart.unit ? " " + chart.unit : "");
                },
                afterTitle: function (items) {
                  return chart.festivals[items[0].dataIndex] || "";
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } },
            y: {
              beginAtZero: true,
              max: chart.cap || undefined,
              grid: { color: gridColor },
              border: { display: false },
              ticks: { precision: 0 },
            },
          },
        },
        plugins: [festivalBands, clipMarkers],
      });
      instance.$sadhana = { festivals: chart.festivals, clipped: chart.clipped, capped: Boolean(chart.cap), cap: chart.cap };
      instance.update("none");
      instances[id] = instance;
    });

    // "Usual range" / "Full range" switch above a chart.
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-range]");
      if (!button) return;
      var instance = instances[button.getAttribute("data-range-for")];
      if (!instance) return;
      var usual = button.getAttribute("data-range") === "usual";
      instance.$sadhana.capped = usual;
      instance.options.scales.y.max = usual ? instance.$sadhana.cap : undefined;
      instance.update();
      button.parentNode.querySelectorAll("[data-range]").forEach(function (other) {
        var active = other === button;
        other.classList.toggle("range-toggle-active", active);
        other.setAttribute("aria-pressed", active ? "true" : "false");
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
