/**
 * Official sparkline bridge adapter (sample adapter).
 * Register: include after ux-bridge.js
 *   <script src="/ux-channel/static/adapters/sparkline.js"></script>
 */
(function (global) {
  if (!global.uxBridge) {
    console.warn("[ux-sparkline] uxBridge missing");
    return;
  }
  global.uxBridge.register("sparkline", {
    mount: function (el, props) {
      var canvas =
        el.querySelector("canvas") ||
        el.appendChild(document.createElement("canvas"));
      canvas.width = (props && props.width) || 320;
      canvas.height = (props && props.height) || 80;
      var state = { props: props || { values: [] } };
      function draw() {
        var ctx = canvas.getContext("2d");
        var vals = state.props.values || [];
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!vals.length) return;
        var min = Math.min.apply(null, vals),
          max = Math.max.apply(null, vals);
        var pad = 4;
        ctx.strokeStyle = state.props.color || "#2563eb";
        ctx.lineWidth = 2;
        ctx.beginPath();
        vals.forEach(function (v, i) {
          var x = pad + (i * (canvas.width - pad * 2)) / Math.max(vals.length - 1, 1);
          var y =
            canvas.height -
            pad -
            ((v - min) / (max - min || 1)) * (canvas.height - pad * 2);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }
      draw();
      return {
        update: function (p) {
          state.props = p || state.props;
          draw();
        },
        destroy: function () {},
      };
    },
    update: function (handle, props) {
      if (handle && handle.update) handle.update(props);
    },
    call: function (handle, method, args) {
      if (handle && typeof handle[method] === "function")
        return handle[method].apply(handle, args || []);
    },
  });
  try { global.uxBridge && global.uxBridge.scan && global.uxBridge.scan(document); } catch (e) {}
})(typeof window !== "undefined" ? window : globalThis);
