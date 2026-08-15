/**
 * ux-peer-continuations.js — Peer slot-fill for Result.continuations (Wave B)
 *
 * SEPARATE module. Does not mint Caps. Does not invent policy.
 * On event: match continuation → fill args_from → submit Intent with given cap.
 *
 * Requires: host already attached continuations envelope on Result.
 * Optional: works with or without uxcPerception.
 */
(function (global) {
  "use strict";

  function create(options) {
    options = options || {};
    var submitIntent = options.submitIntent;
    if (typeof submitIntent !== "function") {
      throw new Error("uxcContinuations: submitIntent required");
    }
    var getStore = options.getStore || function () {
      return {};
    };
    var armed = [];
    var log = [];

    function armFromResult(result) {
      armed = [];
      if (!result || !Array.isArray(result.continuations)) return;
      for (var i = 0; i < result.continuations.length; i++) {
        armed.push(Object.assign({}, result.continuations[i]));
      }
      log.push(["arm", armed.length]);
    }

    function resolvePath(path, event) {
      var store = getStore() || {};
      var detail = (event && event.detail) || event || {};
      if (typeof path !== "string") return undefined;
      if (path.indexOf("event.") === 0) return dig(detail, path.slice(6).split("."));
      if (path.indexOf("store.") === 0) return dig(store, path.slice(6).split("."));
      if (Object.prototype.hasOwnProperty.call(detail, path)) return detail[path];
      return store[path];
    }

    function dig(obj, parts) {
      var cur = obj;
      for (var i = 0; i < parts.length; i++) {
        if (cur == null || typeof cur !== "object") return undefined;
        cur = cur[parts[i]];
      }
      return cur;
    }

    function handleEvent(event) {
      if (!event) return false;
      var et = event.type || event.event;
      if (!et) return false;
      var idx = -1;
      var cont = null;
      for (var i = 0; i < armed.length; i++) {
        if (armed[i].event === et) {
          idx = i;
          cont = armed[i];
          break;
        }
      }
      if (!cont) return false;
      if (cont.once !== false) armed.splice(idx, 1);

      var args = {};
      var from = cont.args_from || {};
      var keys = Object.keys(from);
      for (var k = 0; k < keys.length; k++) {
        var key = keys[k];
        var val = resolvePath(from[key], event);
        if (val !== undefined) args[key] = val;
      }

      var intent = {
        v: "1",
        action: cont.action,
        args: args,
        cap: cont.cap,
      };
      log.push(["submit", cont.action, et]);
      submitIntent(intent);
      return true;
    }

    function clear() {
      armed = [];
    }

    return {
      armFromResult: armFromResult,
      handleEvent: handleEvent,
      clear: clear,
      get armed() {
        return armed.slice();
      },
      get log() {
        return log.slice();
      },
    };
  }

  var api = { create: create, version: "continuations.v1" };
  if (typeof global !== "undefined") global.uxcContinuations = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
