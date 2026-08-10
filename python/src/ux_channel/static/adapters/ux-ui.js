/**
 * ux-ui — high-value UI library adapters for uxchannel + UxDom.
 * Load after ux-bridge.js:
 *   <script src="/ux-channel/static/adapters/ux-ui.js"></script>
 *
 * Packages: leaflet, codemirror, tom-select, flatpickr, sortablejs,
 *           swiper, mermaid, quill
 */
(function (global) {
  "use strict";
  if (!global.uxBridge) {
    console.warn("[ux-ui] uxBridge missing — load ux-bridge.js first");
    return;
  }
  if (global.__UX_UI_LOADED__) {
    try { console.info("[ux-ui] re-registering adapters"); } catch (e0) {}
  }
  global.__UX_UI_LOADED__ = true;
  var reg = global.uxBridge.register.bind(global.uxBridge);

  function loadCss(href, id) {
    if (id && document.getElementById(id)) return;
    var l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = href;
    if (id) l.id = id;
    document.head.appendChild(l);
  }
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = function () { resolve(); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  function once(key, fn) {
    global.__uidUiLoad = global.__uidUiLoad || {};
    if (!global.__uidUiLoad[key]) global.__uidUiLoad[key] = fn();
    return global.__uidUiLoad[key];
  }

  // ── Leaflet ──────────────────────────────────────────────────────────
  function loadLeaflet() {
    return once("leaflet", function () {
      loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "ux-leaflet-css");
      return loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js").then(function () {
        return global.L;
      });
    });
  }
  reg("leaflet", {
    mount: function (el, props) {
      props = props || {};
      el.style.minHeight = el.style.minHeight || "16rem";
      var map, layer, markers = [];
      var handle = {
        ready: loadLeaflet().then(function (L) {
          map = L.map(el).setView(props.center || [20, 0], props.zoom || 2);
          layer = L.tileLayer(props.tiles || "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: props.attribution || "&copy; OpenStreetMap",
          }).addTo(map);
          handle._applyMarkers(props.markers || [], props.fitMarkers);
          setTimeout(function () { map.invalidateSize(); }, 50);
          return map;
        }),
        _applyMarkers: function (list, fit) {
          markers.forEach(function (m) { map.removeLayer(m); });
          markers = [];
          (list || []).forEach(function (m) {
            var ll = m.latlng || m.center || [m.lat, m.lng];
            if (!ll || ll[0] == null) return;
            var mk = global.L.marker(ll);
            if (m.popup) mk.bindPopup(m.popup);
            mk.addTo(map);
            markers.push(mk);
          });
          if (fit && markers.length) {
            var g = global.L.featureGroup(markers);
            map.fitBounds(g.getBounds().pad(0.2));
          }
        },
        update: function (p) {
          props = p || props;
          if (!map) return handle.ready;
          if (p.center) map.setView(p.center, p.zoom != null ? p.zoom : map.getZoom());
          handle._applyMarkers(p.markers || [], p.fitMarkers);
        },
        setView: function (center, zoom) {
          if (map) map.setView(center, zoom != null ? zoom : map.getZoom());
        },
        flyTo: function (center, zoom) {
          if (map) map.flyTo(center, zoom != null ? zoom : map.getZoom());
        },
        invalidateSize: function () {
          if (map) map.invalidateSize();
        },
        destroy: function () {
          if (map) { map.remove(); map = null; }
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) return h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── CodeMirror (simple textarea fallback + CodeMirror 5 CDN) ─────────
  function loadCM() {
    return once("codemirror", function () {
      loadCss("https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css", "ux-cm-css");
      loadCss("https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css", "ux-cm-theme");
      return loadScript("https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js").then(function () {
        return global.CodeMirror;
      });
    });
  }
  reg("codemirror", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      var ta = document.createElement("textarea");
      ta.value = props.value || "";
      el.appendChild(ta);
      var cm = null;
      var handle = {
        ready: loadCM().then(function (CM) {
          cm = CM.fromTextArea(ta, {
            lineNumbers: props.lineNumbers !== false,
            theme: props.theme === "dark" ? "material-darker" : "default",
            readOnly: props.readOnly || false,
            tabSize: props.tabSize || 2,
            mode: props.language || "javascript",
          });
          cm.setSize("100%", el.clientHeight || 280);
          return cm;
        }),
        update: function (p) {
          props = p || props;
          if (cm && p && p.value != null) cm.setValue(p.value);
        },
        setValue: function (v) { if (cm) cm.setValue(v); },
        getValue: function () { return cm ? cm.getValue() : ta.value; },
        focus: function () { if (cm) cm.focus(); },
        destroy: function () {
          if (cm) { cm.toTextArea(); cm = null; }
          el.innerHTML = "";
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── Tom Select ───────────────────────────────────────────────────────
  function loadTom() {
    return once("tom-select", function () {
      loadCss("https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/css/tom-select.default.min.css", "ux-ts-css");
      return loadScript("https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/js/tom-select.complete.min.js").then(function () {
        return global.TomSelect;
      });
    });
  }
  reg("tom-select", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      var sel = document.createElement("select");
      if (props.multiple) sel.multiple = true;
      el.appendChild(sel);
      var ts = null;
      var handle = {
        ready: loadTom().then(function (TomSelect) {
          (props.options || []).forEach(function (o) {
            var opt = document.createElement("option");
            opt.value = o.value;
            opt.textContent = o.label;
            sel.appendChild(opt);
          });
          ts = new TomSelect(sel, {
            maxItems: props.multiple ? (props.maxItems || null) : 1,
            create: !!props.create,
            placeholder: props.placeholder || "Select…",
          });
          if (props.value != null) ts.setValue(props.value);
          return ts;
        }),
        update: function (p) {
          props = p || props;
          if (!ts) return;
          if (p.options) {
            ts.clearOptions();
            p.options.forEach(function (o) {
              ts.addOption({ value: o.value, text: o.label });
            });
            ts.refreshOptions(false);
          }
          if (p.value != null) ts.setValue(p.value);
        },
        setValue: function (v) { if (ts) ts.setValue(v); },
        clear: function () { if (ts) ts.clear(); },
        enable: function () { if (ts) ts.enable(); },
        disable: function () { if (ts) ts.disable(); },
        destroy: function () {
          if (ts) { ts.destroy(); ts = null; }
          el.innerHTML = "";
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── Flatpickr ────────────────────────────────────────────────────────
  function loadFp() {
    return once("flatpickr", function () {
      loadCss("https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css", "ux-fp-css");
      loadCss("https://cdn.jsdelivr.net/npm/flatpickr/dist/themes/dark.css", "ux-fp-dark");
      return loadScript("https://cdn.jsdelivr.net/npm/flatpickr").then(function () {
        return global.flatpickr;
      });
    });
  }
  reg("flatpickr", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      var input = document.createElement("input");
      input.type = "text";
      input.className = "ux-flatpickr-input";
      input.style.cssText = "width:100%;padding:.6rem .75rem;border-radius:.5rem;border:1px solid #334155;background:#0f172a;color:#e2e8f0";
      el.appendChild(input);
      var fp = null;
      var handle = {
        ready: loadFp().then(function (flatpickr) {
          fp = flatpickr(input, {
            mode: props.mode || "single",
            enableTime: !!props.enableTime,
            dateFormat: props.dateFormat || "Y-m-d",
            minDate: props.minDate || undefined,
            maxDate: props.maxDate || undefined,
            inline: !!props.inline,
            defaultDate: props.value || undefined,
          });
          return fp;
        }),
        update: function (p) {
          props = p || props;
          if (fp && p && p.value != null) fp.setDate(p.value, true);
        },
        setDate: function (v) { if (fp) fp.setDate(v, true); },
        clear: function () { if (fp) fp.clear(); },
        open: function () { if (fp) fp.open(); },
        close: function () { if (fp) fp.close(); },
        destroy: function () {
          if (fp) { fp.destroy(); fp = null; }
          el.innerHTML = "";
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── SortableJS ───────────────────────────────────────────────────────
  function loadSortable() {
    return once("sortablejs", function () {
      return loadScript("https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js").then(function () {
        return global.Sortable;
      });
    });
  }
  reg("sortablejs", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      el.style.listStyle = "none";
      el.style.padding = "0";
      el.style.margin = "0";
      function paint(items) {
        el.innerHTML = "";
        (items || []).forEach(function (it) {
          var li = document.createElement("div");
          li.dataset.id = it.id;
          li.style.cssText =
            "padding:.75rem 1rem;margin:.35rem 0;border-radius:.75rem;" +
            "background:rgba(30,41,59,.9);border:1px solid rgba(148,163,184,.2);cursor:grab";
          li.innerHTML = it.html || it.label || it.id;
          el.appendChild(li);
        });
      }
      paint(props.items || []);
      var sortable = null;
      var handle = {
        ready: loadSortable().then(function (Sortable) {
          sortable = Sortable.create(el, {
            animation: props.animation || 150,
            handle: props.handle || undefined,
            ghostClass: props.ghostClass || "opacity-50",
            group: props.group || undefined,
            disabled: !!props.disabled,
          });
          return sortable;
        }),
        update: function (p) {
          props = p || props;
          if (p && p.items) paint(p.items);
          if (sortable && p && p.disabled != null) sortable.option("disabled", !!p.disabled);
        },
        setOrder: function (ids) {
          if (!sortable) return;
          // Sortable does not set by ids easily; re-paint order
          var by = {};
          (props.items || []).forEach(function (it) { by[it.id] = it; });
          var next = (ids || []).map(function (id) { return by[id]; }).filter(Boolean);
          props.items = next;
          paint(next);
        },
        toArray: function () {
          return sortable ? sortable.toArray() : [];
        },
        destroy: function () {
          if (sortable) { sortable.destroy(); sortable = null; }
          el.innerHTML = "";
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── Swiper ───────────────────────────────────────────────────────────
  function loadSwiper() {
    return once("swiper", function () {
      loadCss("https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css", "ux-swiper-css");
      return loadScript("https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js").then(function () {
        return global.Swiper;
      });
    });
  }
  reg("swiper", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      el.classList.add("swiper");
      el.style.width = "100%";
      var wrap = document.createElement("div");
      wrap.className = "swiper-wrapper";
      el.appendChild(wrap);
      if (props.pagination !== false) {
        var pag = document.createElement("div");
        pag.className = "swiper-pagination";
        el.appendChild(pag);
      }
      if (props.navigation !== false) {
        var prev = document.createElement("div");
        prev.className = "swiper-button-prev";
        var next = document.createElement("div");
        next.className = "swiper-button-next";
        el.appendChild(prev);
        el.appendChild(next);
      }
      function slides(list) {
        wrap.innerHTML = "";
        (list || []).forEach(function (s) {
          var slide = document.createElement("div");
          slide.className = "swiper-slide";
          slide.style.cssText = "padding:1.5rem;box-sizing:border-box";
          slide.innerHTML = (s && s.html) || s || "";
          wrap.appendChild(slide);
        });
      }
      slides(props.slides || []);
      var sw = null;
      var handle = {
        ready: loadSwiper().then(function (Swiper) {
          sw = new Swiper(el, {
            loop: props.loop !== false,
            spaceBetween: props.spaceBetween || 16,
            slidesPerView: props.slidesPerView || 1,
            pagination: props.pagination === false ? undefined : { el: ".swiper-pagination", clickable: true },
            navigation:
              props.navigation === false
                ? undefined
                : { nextEl: ".swiper-button-next", prevEl: ".swiper-button-prev" },
            autoplay: props.autoplayMs ? { delay: props.autoplayMs } : undefined,
          });
          return sw;
        }),
        update: function (p) {
          props = p || props;
          if (p && p.slides) {
            slides(p.slides);
            if (sw) sw.update();
          }
        },
        slideTo: function (i) { if (sw) sw.slideTo(i); },
        slideNext: function () { if (sw) sw.slideNext(); },
        slidePrev: function () { if (sw) sw.slidePrev(); },
        destroy: function () {
          if (sw) { sw.destroy(true, true); sw = null; }
          el.innerHTML = "";
        },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── Mermaid ──────────────────────────────────────────────────────────
  function loadMermaid() {
    return once("mermaid", function () {
      return loadScript("https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js").then(function () {
        global.mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" });
        return global.mermaid;
      });
    });
  }
  reg("mermaid", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      var pre = document.createElement("div");
      pre.className = "mermaid";
      pre.textContent = props.chart || "graph TD;A-->B";
      el.appendChild(pre);
      var handle = {
        ready: loadMermaid().then(function (mermaid) {
          mermaid.initialize({
            startOnLoad: false,
            theme: props.theme || "dark",
            securityLevel: props.securityLevel || "strict",
          });
          return mermaid.run({ nodes: [pre] });
        }),
        update: function (p) {
          props = p || props;
          el.innerHTML = "";
          pre = document.createElement("div");
          pre.className = "mermaid";
          pre.textContent = (p && p.chart) || props.chart || "";
          el.appendChild(pre);
          return loadMermaid().then(function (m) {
            return m.run({ nodes: [pre] });
          });
        },
        render: function (p) { return handle.update(p || props); },
        destroy: function () { el.innerHTML = ""; },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) return h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  // ── Quill ────────────────────────────────────────────────────────────
  function loadQuill() {
    return once("quill", function () {
      loadCss("https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.snow.css", "ux-quill-css");
      return loadScript("https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.js").then(function () {
        return global.Quill;
      });
    });
  }
  reg("quill", {
    mount: function (el, props) {
      props = props || {};
      el.innerHTML = "";
      var box = document.createElement("div");
      el.appendChild(box);
      var q = null;
      var handle = {
        ready: loadQuill().then(function (Quill) {
          q = new Quill(box, {
            theme: props.theme || "snow",
            placeholder: props.placeholder || "Write…",
            readOnly: !!props.readOnly,
            modules: { toolbar: props.toolbar === false ? false : true },
          });
          if (props.html) q.root.innerHTML = props.html;
          return q;
        }),
        update: function (p) {
          props = p || props;
          if (q && p && p.html != null) q.root.innerHTML = p.html;
        },
        setContents: function (html) { if (q) q.root.innerHTML = html; },
        setText: function (t) { if (q) q.setText(t); },
        enable: function (on) { if (q) q.enable(on !== false); },
        destroy: function () { el.innerHTML = ""; q = null; },
      };
      return handle;
    },
    update: function (h, p) { if (h && h.update) h.update(p); },
    call: function (h, m, a) { if (h && typeof h[m] === "function") return h[m].apply(h, a || []); },
  });

  try {
    if (global.uxBridge && typeof global.uxBridge.scan === "function") {
      global.uxBridge.scan(document);
    }
  } catch (eScan) {}

})(typeof window !== "undefined" ? window : globalThis);
