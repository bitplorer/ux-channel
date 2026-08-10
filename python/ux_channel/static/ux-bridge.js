/* uxchannel 0.1.0 — ux-bridge */
/**
 * ux-bridge — island mount registry for ux-channel.
 * Load once. A second include is a no-op (keeps adapters + instances).
 * Load adapters (ux-fx / ux-ui) *after* this file.
 */
(function (global) {
  "use strict";

  if (global.uxBridge && global.uxBridge.register) {
    try {
      console.warn("[ux-bridge] already loaded — skipping re-init (adapters preserved)");
    } catch (e0) {}
    return;
  }

  var adapters = Object.create(null);
  var instances = Object.create(null);

  function register(name, adapter) {
    if (!name || !adapter || typeof adapter.mount !== "function") {
      throw new Error("uxBridge.register(name, { mount, update?, call?, destroy? })");
    }
    adapters[name] = adapter;
  }

  function hostFor(op) {
    if (op.target) {
      try {
        return document.querySelector(op.target);
      } catch (e) {
        return null;
      }
    }
    return document.querySelector('[data-channel-bridge-id="' + op.id + '"]');
  }

  function apply(op) {
    if (!op || !op.op) return Promise.resolve();
    var id = op.id;
    if (op.op === "bridge.mount") {
      var adapter = adapters[op.package];
      if (!adapter) {
        console.warn("[ux-bridge] no adapter for package:", op.package);
        return Promise.resolve();
      }
      var el = hostFor(op);
      if (!el) {
        console.warn("[ux-bridge] host not found for", id);
        return Promise.resolve();
      }
      return Promise.resolve()
        .then(function () {
          // destroy previous
          if (instances[id] && instances[id].dispose) {
            return instances[id].dispose();
          }
        })
        .then(function () {
          return adapter.mount(el, op.props || {});
        })
        .then(function (handle) {
          var dispose =
            typeof handle === "function"
              ? handle
              : handle && handle.destroy
                ? function () {
                    return handle.destroy();
                  }
                : function () {};
          instances[id] = {
            package: op.package,
            handle: handle,
            el: el,
            dispose: dispose,
            adapter: adapter,
          };
        });
    }
    if (op.op === "bridge.update") {
      var inst = instances[id];
      if (!inst) {
        console.warn("[ux-bridge] update missing instance", id);
        return Promise.resolve();
      }
      if (inst.adapter.update) {
        return Promise.resolve(inst.adapter.update(inst.handle, op.props, op.replace));
      }
      // remount fallback
      return apply({
        op: "bridge.mount",
        id: id,
        package: inst.package,
        props: op.props,
        target: op.target,
      });
    }
    if (op.op === "bridge.call") {
      var inst2 = instances[id];
      if (!inst2) return Promise.resolve();
      if (inst2.adapter.call) {
        return Promise.resolve(
          inst2.adapter.call(inst2.handle, op.method, op.args || [])
        );
      }
      var h = inst2.handle;
      if (h && typeof h[op.method] === "function") {
        return Promise.resolve(h[op.method].apply(h, op.args || []));
      }
      console.warn("[ux-bridge] method not found", op.method);
      return Promise.resolve();
    }
    if (op.op === "bridge.destroy") {
      var inst3 = instances[id];
      if (!inst3) return Promise.resolve();
      return Promise.resolve()
        .then(function () {
          return inst3.dispose && inst3.dispose();
        })
        .then(function () {
          delete instances[id];
        });
    }
    return Promise.resolve();
  }

  function scan(root) {
    var nodes = (root || document).querySelectorAll(
      "[data-channel-bridge-id][data-channel-bridge-package]"
    );
    Array.prototype.forEach.call(nodes, function (el) {
      var id = el.getAttribute("data-channel-bridge-id");
      var pkg = el.getAttribute("data-channel-bridge-package");
      if (!id || !pkg || instances[id]) return;
      var props = {};
      var raw = el.getAttribute("data-channel-bridge-props");
      if (raw) {
        try {
          props = JSON.parse(raw);
        } catch (e) {}
      }
      apply({ op: "bridge.mount", id: id, package: pkg, props: props, target: null });
      // fix target: mount uses id selector — set el as implicit by temporarily
    });
  }

  // Fix scan mount to pass element via synthetic target lookup
  var _hostFor = hostFor;
  hostFor = function (op) {
    if (op._el) return op._el;
    return _hostFor(op);
  };

  function scanFixed(root) {
    var nodes = (root || document).querySelectorAll(
      "[data-channel-bridge-id][data-channel-bridge-package]"
    );
    Array.prototype.forEach.call(nodes, function (el) {
      var id = el.getAttribute("data-channel-bridge-id");
      var pkg = el.getAttribute("data-channel-bridge-package");
      if (!id || !pkg || instances[id]) return;
      var props = {};
      var raw = el.getAttribute("data-channel-bridge-props");
      if (raw) {
        try {
          props = JSON.parse(raw);
        } catch (e) {}
      }
      apply({
        op: "bridge.mount",
        id: id,
        package: pkg,
        props: props,
        _el: el,
      });
    });
  }

  global.uxBridge = {
    register: register,
    apply: apply,
    scan: scanFixed,
    instances: instances,
    version: "0.1.0",
  };
})(typeof window !== "undefined" ? window : globalThis);
