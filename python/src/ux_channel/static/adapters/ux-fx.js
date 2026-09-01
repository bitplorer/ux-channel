/**
 * Compatibility alias. Canonical file is adapters/builtins.js.
 * Old <script src=".../ux-fx.js"> tags keep working for one release.
 */
(function (global) {
  "use strict";
  if (global.__UX_BUILTINS_LOADED__) return;
  var cur = document.currentScript && document.currentScript.src;
  var src = cur
    ? cur.replace(/ux-fx\.js(\?.*)?$/, "builtins.js")
    : "/ux-channel/static/adapters/builtins.js";
  var s = document.createElement("script");
  s.src = src;
  document.head.appendChild(s);
})(typeof window !== "undefined" ? window : globalThis);
