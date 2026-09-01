/**
 * Compatibility alias. Canonical file is adapters/scenes.js.
 * Old <script src=".../ux-fx.js"> tags keep working.
 */
(function (global) {
  "use strict";
  if (global.__UX_SCENES_LOADED__) return;
  var cur = document.currentScript && document.currentScript.src;
  var src = cur
    ? cur.replace(/ux-fx\.js(\?.*)?$/, "scenes.js")
    : "/ux-channel/static/adapters/scenes.js";
  var s = document.createElement("script");
  s.src = src;
  document.head.appendChild(s);
})(typeof window !== "undefined" ? window : globalThis);
