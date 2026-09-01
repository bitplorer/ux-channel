/**
 * Compatibility alias. Canonical file is adapters/widgets.js.
 * Old <script src=".../ux-ui.js"> tags keep working.
 */
(function (global) {
  "use strict";
  if (global.__UX_WIDGETS_LOADED__) return;
  var cur = document.currentScript && document.currentScript.src;
  var src = cur
    ? cur.replace(/ux-ui\.js(\?.*)?$/, "widgets.js")
    : "/ux-channel/static/adapters/widgets.js";
  var s = document.createElement("script");
  s.src = src;
  document.head.appendChild(s);
})(typeof window !== "undefined" ? window : globalThis);
