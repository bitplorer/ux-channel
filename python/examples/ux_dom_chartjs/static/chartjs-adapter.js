/**
 * ux-bridge adapter for Chart.js (CDN).
 * Package name: "chart.js"
 *
 * mount props: {
 *   type: "bar"|"line"|"doughnut",
 *   labels: string[],
 *   datasets: [{ label, data, backgroundColor?, borderColor?, ... }],
 *   options?: Chart options
 * }
 */
(function (global) {
  "use strict";
  if (!global.uxBridge) {
    console.warn("[chart.js adapter] uxBridge missing — load ux-bridge.js first");
    return;
  }

  var CHART_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
  var loading = null;

  function loadChart() {
    if (global.Chart) return Promise.resolve(global.Chart);
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = CHART_CDN;
      s.async = true;
      s.onload = function () {
        resolve(global.Chart);
      };
      s.onerror = function () {
        loading = null;
        reject(new Error("Failed to load Chart.js from CDN"));
      };
      document.head.appendChild(s);
    });
    return loading;
  }

  function ensureCanvas(el) {
    var canvas = el.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      el.appendChild(canvas);
    }
    return canvas;
  }

  function buildConfig(props) {
    props = props || {};
    return {
      type: props.type || "bar",
      data: {
        labels: props.labels || [],
        datasets: props.datasets || [],
      },
      options: Object.assign(
        {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 450 },
          plugins: {
            legend: { display: true, position: "bottom" },
            title: {
              display: !!props.title,
              text: props.title || "",
              font: { size: 16, weight: "600" },
            },
          },
          scales:
            (props.type || "bar") === "doughnut"
              ? {}
              : {
                  y: { beginAtZero: true, grid: { color: "rgba(0,0,0,.06)" } },
                  x: { grid: { display: false } },
                },
        },
        props.options || {}
      ),
    };
  }

  global.uxBridge.register("chart.js", {
    mount: function (el, props) {
      return loadChart().then(function (Chart) {
        var canvas = ensureCanvas(el);
        var chart = new Chart(canvas.getContext("2d"), buildConfig(props));
        return {
          chart: chart,
          update: function (next) {
            var cfg = buildConfig(next);
            chart.config.type = cfg.type;
            chart.data.labels = cfg.data.labels;
            chart.data.datasets = cfg.data.datasets;
            // rebuild options lightly
            Object.assign(chart.options, cfg.options);
            chart.update();
          },
          destroy: function () {
            try {
              chart.destroy();
            } catch (e) {}
          },
          setType: function (type) {
            chart.config.type = type || "bar";
            chart.update();
          },
        };
      });
    },
    update: function (handle, props) {
      if (handle && handle.update) handle.update(props || {});
    },
    call: function (handle, method, args) {
      if (!handle) return;
      if (typeof handle[method] === "function") {
        return handle[method].apply(handle, args || []);
      }
      if (handle.chart && typeof handle.chart[method] === "function") {
        return handle.chart[method].apply(handle.chart, args || []);
      }
    },
    destroy: function (handle) {
      if (handle && handle.destroy) handle.destroy();
    },
  });
})(typeof window !== "undefined" ? window : globalThis);
