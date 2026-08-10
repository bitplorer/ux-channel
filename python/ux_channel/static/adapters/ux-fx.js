/**
 * ux-fx — stunning self-contained bridge adapters for ux-channel.
 * Include after ux-bridge.js:
 *   <script src="/ux-channel/static/adapters/ux-fx.js"></script>
 *
 * Packages:
 *   ux-fx/confetti | ux-fx/particles | ux-fx/aurora
 *   ux-fx/countup  | ux-fx/spotlight | lottie-web (CDN)
 */
(function (global) {
  "use strict";
  if (!global.uxBridge) {
    console.warn("[ux-fx] uxBridge missing — load ux-bridge.js first");
    return;
  }
  // Re-register on re-include is intentional (overwrites same package names).
  if (global.__UX_FX_LOADED__) {
    try { console.info("[ux-fx] re-registering adapters"); } catch (e0) {}
  }
  global.__UX_FX_LOADED__ = true;
  var reg = global.uxBridge.register.bind(global.uxBridge);

  function clamp(n, a, b) {
    return Math.max(a, Math.min(b, n));
  }

  // ── confetti ─────────────────────────────────────────────────────────
  reg("ux-fx/confetti", {
    mount: function (el, props) {
      el.style.pointerEvents = "none";
      el.style.position = el.style.position || "relative";
      var canvas = el.querySelector("canvas") || el.appendChild(document.createElement("canvas"));
      canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
      var ctx = canvas.getContext("2d");
      var pieces = [];
      var raf = 0;
      var raining = false;

      function size() {
        var r = el.getBoundingClientRect();
        canvas.width = Math.max(1, Math.floor(r.width * (window.devicePixelRatio || 1)));
        canvas.height = Math.max(1, Math.floor(r.height * (window.devicePixelRatio || 1)));
        canvas.style.width = r.width + "px";
        canvas.style.height = r.height + "px";
        return r;
      }

      function spawn(opts) {
        opts = opts || {};
        var r = size();
        var count = opts.particleCount || 100;
        var colors = opts.colors || ["#22d3ee", "#a78bfa", "#f472b6"];
        var origin = opts.origin || { x: 0.5, y: 0.5 };
        var ox = origin.x * r.width;
        var oy = origin.y * r.height;
        var spread = ((opts.spread != null ? opts.spread : 70) * Math.PI) / 180;
        var vel = opts.startVelocity != null ? opts.startVelocity : 45;
        var grav = opts.gravity != null ? opts.gravity : 1;
        var scalar = opts.scalar != null ? opts.scalar : 1;
        var ticks = opts.ticks != null ? opts.ticks : 200;
        var dpr = window.devicePixelRatio || 1;
        for (var i = 0; i < count; i++) {
          var angle = -Math.PI / 2 + (Math.random() - 0.5) * spread;
          var speed = (vel * (0.5 + Math.random())) * dpr;
          pieces.push({
            x: ox * dpr,
            y: oy * dpr,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            w: (4 + Math.random() * 6) * scalar * dpr,
            h: (6 + Math.random() * 8) * scalar * dpr,
            rot: Math.random() * Math.PI,
            vr: (Math.random() - 0.5) * 0.3,
            color: colors[i % colors.length],
            life: ticks,
            max: ticks,
            grav: grav * 0.25 * dpr,
          });
        }
        if (!raf) loop();
      }

      function loop() {
        raf = requestAnimationFrame(loop);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (var i = pieces.length - 1; i >= 0; i--) {
          var p = pieces[i];
          p.vy += p.grav;
          p.x += p.vx;
          p.y += p.vy;
          p.rot += p.vr;
          p.life -= 1;
          if (p.life <= 0 || p.y > canvas.height + 40) {
            pieces.splice(i, 1);
            continue;
          }
          ctx.save();
          ctx.globalAlpha = clamp(p.life / p.max, 0, 1);
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
          ctx.restore();
        }
        if (!pieces.length && !raining) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      }

      var handle = {
        props: props || {},
        burst: function (p) {
          spawn(p || handle.props);
        },
        cannon: function (p) {
          var o = Object.assign({}, handle.props, p || {}, {
            spread: 35,
            startVelocity: 55,
            particleCount: (p && p.particleCount) || 80,
          });
          spawn(o);
        },
        rain: function (p) {
          p = p || handle.props;
          raining = true;
          var end = Date.now() + (p.durationMs || 2500);
          function tick() {
            if (Date.now() > end) {
              raining = false;
              return;
            }
            spawn(
              Object.assign({}, p, {
                particleCount: 12,
                origin: { x: Math.random(), y: -0.05 },
                startVelocity: 15,
                spread: 100,
                gravity: 1.2,
              })
            );
            setTimeout(tick, 80);
          }
          tick();
        },
        stop: function () {
          pieces = [];
          raining = false;
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        },
        destroy: function () {
          handle.stop();
          if (raf) cancelAnimationFrame(raf);
          raf = 0;
        },
        update: function (p) {
          handle.props = p || handle.props;
        },
      };
      size();
      window.addEventListener("resize", size);
      handle._onResize = size;
      return handle;
    },
    update: function (h, props) {
      if (h && h.update) h.update(props);
    },
    call: function (h, method, args) {
      if (!h) return;
      if (typeof h[method] === "function") return h[method].apply(h, args || []);
    },
  });

  // ── particles ────────────────────────────────────────────────────────
  reg("ux-fx/particles", {
    mount: function (el, props) {
      el.style.position = el.style.position || "relative";
      el.style.overflow = "hidden";
      var canvas = el.querySelector("canvas") || el.appendChild(document.createElement("canvas"));
      canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
      var ctx = canvas.getContext("2d");
      var parts = [];
      var mouse = { x: -9999, y: -9999 };
      var raf = 0;
      var state = { props: props || {} };

      function resize() {
        var r = el.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, r.width * dpr);
        canvas.height = Math.max(1, r.height * dpr);
        canvas.style.width = r.width + "px";
        canvas.style.height = r.height + "px";
        return { w: canvas.width, h: canvas.height, dpr: dpr };
      }

      function seed() {
        var p = state.props;
        var dim = resize();
        parts = [];
        var n = p.count || 55;
        var colors = p.colors || ["#22d3ee", "#a78bfa"];
        for (var i = 0; i < n; i++) {
          parts.push({
            x: Math.random() * dim.w,
            y: Math.random() * dim.h,
            vx: (Math.random() - 0.5) * (p.speed || 0.45) * dim.dpr * 2,
            vy: (Math.random() - 0.5) * (p.speed || 0.45) * dim.dpr * 2,
            r: (p.size || 2.2) * (0.6 + Math.random()) * dim.dpr,
            color: colors[i % colors.length],
          });
        }
      }

      function frame() {
        raf = requestAnimationFrame(frame);
        var p = state.props;
        var w = canvas.width,
          h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        var linkDist = (p.linkDistance || 120) * (window.devicePixelRatio || 1);
        var op = p.opacity != null ? p.opacity : 0.85;
        for (var i = 0; i < parts.length; i++) {
          var a = parts[i];
          a.x += a.vx;
          a.y += a.vy;
          if (a.x < 0 || a.x > w) a.vx *= -1;
          if (a.y < 0 || a.y > h) a.vy *= -1;
          if (p.interactive !== false) {
            var dx = a.x - mouse.x,
              dy = a.y - mouse.y;
            var d = Math.sqrt(dx * dx + dy * dy) || 1;
            if (d < 120 * (window.devicePixelRatio || 1)) {
              a.vx += (dx / d) * 0.05;
              a.vy += (dy / d) * 0.05;
            }
          }
          ctx.beginPath();
          ctx.globalAlpha = op;
          ctx.fillStyle = a.color;
          ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
          ctx.fill();
          for (var j = i + 1; j < parts.length; j++) {
            var b = parts[j];
            var ddx = a.x - b.x,
              ddy = a.y - b.y;
            var dist = Math.sqrt(ddx * ddx + ddy * ddy);
            if (dist < linkDist) {
              ctx.beginPath();
              ctx.globalAlpha = (1 - dist / linkDist) * 0.5 * op;
              ctx.strokeStyle = p.linkColor || "rgba(167,139,250,0.2)";
              ctx.lineWidth = 1;
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(b.x, b.y);
              ctx.stroke();
            }
          }
        }
        ctx.globalAlpha = 1;
      }

      function onMove(e) {
        var r = canvas.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        mouse.x = (e.clientX - r.left) * dpr;
        mouse.y = (e.clientY - r.top) * dpr;
      }

      seed();
      frame();
      el.addEventListener("pointermove", onMove);
      window.addEventListener("resize", seed);

      return {
        update: function (props) {
          state.props = props || state.props;
          seed();
        },
        pulse: function () {
          parts.forEach(function (pt) {
            pt.vx *= 1.8;
            pt.vy *= 1.8;
          });
        },
        burst: function (origin) {
          origin = origin || { x: 0.5, y: 0.5 };
          var ox = origin.x * canvas.width;
          var oy = origin.y * canvas.height;
          parts.forEach(function (pt) {
            var dx = pt.x - ox,
              dy = pt.y - oy;
            var d = Math.sqrt(dx * dx + dy * dy) || 1;
            pt.vx += (dx / d) * 3;
            pt.vy += (dy / d) * 3;
          });
        },
        destroy: function () {
          cancelAnimationFrame(raf);
          el.removeEventListener("pointermove", onMove);
          window.removeEventListener("resize", seed);
        },
      };
    },
    update: function (h, props) {
      if (h && h.update) h.update(props);
    },
    call: function (h, method, args) {
      if (h && typeof h[method] === "function") return h[method].apply(h, args || []);
    },
  });

  // ── aurora ───────────────────────────────────────────────────────────
  reg("ux-fx/aurora", {
    mount: function (el, props) {
      el.style.position = el.style.position || "relative";
      el.style.overflow = "hidden";
      var canvas = el.querySelector("canvas") || el.appendChild(document.createElement("canvas"));
      canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
      var ctx = canvas.getContext("2d");
      var state = { props: props || {}, t: 0, paused: false };
      var raf = 0;
      var blobs = [];

      function resize() {
        var r = el.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, r.width * dpr);
        canvas.height = Math.max(1, r.height * dpr);
        canvas.style.width = r.width + "px";
        canvas.style.height = r.height + "px";
        rebuild();
      }

      function rebuild() {
        var p = state.props;
        var colors = p.colors || ["#0f172a", "#312e81", "#4c1d95", "#0e7490"];
        var n = p.blobs || 5;
        blobs = [];
        for (var i = 0; i < n; i++) {
          blobs.push({
            color: colors[i % colors.length],
            x: Math.random(),
            y: Math.random(),
            r: 0.25 + Math.random() * 0.35,
            px: 0.2 + Math.random() * 0.5,
            py: 0.2 + Math.random() * 0.5,
            phase: Math.random() * Math.PI * 2,
          });
        }
      }

      function frame() {
        raf = requestAnimationFrame(frame);
        if (state.paused) return;
        var p = state.props;
        if (p.reduceMotion) {
          state.t += 0.002;
        } else {
          state.t += (p.speed != null ? p.speed : 0.35) * 0.01;
        }
        var w = canvas.width,
          h = canvas.height;
        var intensity = p.intensity != null ? p.intensity : 0.85;
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = (p.colors && p.colors[0]) || "#0f172a";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "lighter";
        var blur = p.blur != null ? p.blur : 48;
        for (var i = 0; i < blobs.length; i++) {
          var b = blobs[i];
          var x = (b.x + Math.sin(state.t * b.px + b.phase) * 0.15) * w;
          var y = (b.y + Math.cos(state.t * b.py + b.phase) * 0.12) * h;
          var rad = b.r * Math.min(w, h);
          var g = ctx.createRadialGradient(x, y, 0, x, y, rad);
          g.addColorStop(0, b.color);
          g.addColorStop(1, "transparent");
          ctx.globalAlpha = 0.35 * intensity;
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(x, y, rad, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "source-over";
        // soft vignette
        var vg = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.2, w / 2, h / 2, Math.max(w, h) * 0.7);
        vg.addColorStop(0, "transparent");
        vg.addColorStop(1, "rgba(0,0,0,0.35)");
        ctx.fillStyle = vg;
        ctx.fillRect(0, 0, w, h);
      }

      resize();
      frame();
      window.addEventListener("resize", resize);
      return {
        update: function (props) {
          state.props = props || state.props;
          rebuild();
        },
        pause: function () {
          state.paused = true;
        },
        play: function () {
          state.paused = false;
        },
        destroy: function () {
          cancelAnimationFrame(raf);
          window.removeEventListener("resize", resize);
        },
      };
    },
    update: function (h, props) {
      if (h && h.update) h.update(props);
    },
    call: function (h, method, args) {
      if (h && typeof h[method] === "function") return h[method].apply(h, args || []);
    },
  });

  // ── countup ──────────────────────────────────────────────────────────
  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }
  function easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }
  function formatNum(n, decimals, separator) {
    var fixed = n.toFixed(decimals);
    if (!separator) return fixed;
    var parts = fixed.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
  }

  reg("ux-fx/countup", {
    mount: function (el, props) {
      el.style.fontVariantNumeric = "tabular-nums";
      el.style.fontWeight = el.style.fontWeight || "700";
      el.style.letterSpacing = el.style.letterSpacing || "-0.02em";
      var state = { props: props || {}, from: 0, to: 0, start: 0, raf: 0 };

      function applyStyle() {
        var p = state.props;
        el.style.color = p.color || "#34d399";
        el.style.textShadow = p.glow ? "0 0 24px " + p.glow : "";
        el.style.fontSize = el.style.fontSize || "2.5rem";
      }

      function paint(v) {
        var p = state.props;
        var text =
          (p.prefix || "") +
          formatNum(v, p.decimals != null ? p.decimals : 0, p.separator !== false) +
          (p.suffix || "");
        el.textContent = text;
      }

      function animateTo(target) {
        var p = state.props;
        state.from = state.current != null ? state.current : 0;
        state.to = target;
        state.start = performance.now();
        var dur = p.durationMs || 1200;
        var ease = p.easing === "easeOutExpo" ? easeOutExpo : easeOutCubic;
        if (state.raf) cancelAnimationFrame(state.raf);
        function tick(now) {
          var t = clamp((now - state.start) / dur, 0, 1);
          var v = state.from + (state.to - state.from) * ease(t);
          state.current = v;
          paint(v);
          if (t < 1) state.raf = requestAnimationFrame(tick);
        }
        state.raf = requestAnimationFrame(tick);
      }

      applyStyle();
      var initial = (props && props.value) || 0;
      state.current = 0;
      paint(0);
      animateTo(initial);

      return {
        update: function (props) {
          state.props = props || state.props;
          applyStyle();
          animateTo((props && props.value) != null ? props.value : state.to);
        },
        setValue: function (props) {
          state.props = Object.assign({}, state.props, props || {});
          applyStyle();
          animateTo(state.props.value || 0);
        },
        replay: function () {
          state.current = 0;
          paint(0);
          animateTo(state.props.value || 0);
        },
        destroy: function () {
          if (state.raf) cancelAnimationFrame(state.raf);
        },
      };
    },
    update: function (h, props) {
      if (h && h.update) h.update(props);
    },
    call: function (h, method, args) {
      if (h && typeof h[method] === "function") return h[method].apply(h, args || []);
    },
  });

  // ── spotlight ────────────────────────────────────────────────────────
  reg("ux-fx/spotlight", {
    mount: function (el, props) {
      el.style.position = el.style.position || "relative";
      el.style.overflow = el.style.overflow || "hidden";
      var overlay =
        el.querySelector("[data-channel-fx-spot]") ||
        el.appendChild(document.createElement("div"));
      overlay.setAttribute("data-channel-fx-spot", "1");
      overlay.style.cssText =
        "pointer-events:none;position:absolute;inset:0;transition:opacity .2s ease;opacity:0;z-index:2";
      var state = { props: props || {} };

      function paint(x, y, on) {
        var p = state.props;
        var r = p.radius || 260;
        var color = p.color || "rgba(167,139,250,0.28)";
        var soft = p.softness != null ? p.softness : 0.55;
        overlay.style.opacity = on ? "1" : "0";
        overlay.style.background =
          "radial-gradient(" +
          r +
          "px circle at " +
          x +
          "px " +
          y +
          "px, " +
          color +
          ", transparent " +
          soft * 100 +
          "%)";
        if (p.borderGlow) {
          el.style.boxShadow = on ? "0 0 0 1px " + color + ", 0 20px 50px rgba(0,0,0,.25)" : "";
        }
      }

      function move(e) {
        var rect = el.getBoundingClientRect();
        paint(e.clientX - rect.left, e.clientY - rect.top, true);
      }
      function leave() {
        overlay.style.opacity = "0";
        el.style.boxShadow = "";
      }

      el.addEventListener("pointermove", move);
      el.addEventListener("pointerleave", leave);

      return {
        update: function (props) {
          state.props = props || state.props;
        },
        destroy: function () {
          el.removeEventListener("pointermove", move);
          el.removeEventListener("pointerleave", leave);
          if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        },
      };
    },
    update: function (h, props) {
      if (h && h.update) h.update(props);
    },
  });

  // ── lottie-web (CDN) ─────────────────────────────────────────────────
  function loadLottie() {
    if (global.lottie) return Promise.resolve(global.lottie);
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js";
      s.onload = function () {
        resolve(global.lottie);
      };
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  reg("lottie-web", {
    mount: function (el, props) {
      props = props || {};
      el.style.background = props.background || "transparent";
      var anim = null;
      var handle = {
        ready: loadLottie().then(function (lottie) {
          var opts = {
            container: el,
            renderer: props.renderer || "svg",
            loop: props.loop !== false,
            autoplay: props.autoplay !== false,
          };
          if (props.animationData) opts.animationData = props.animationData;
          else if (props.src) opts.path = props.src;
          else return null;
          anim = lottie.loadAnimation(opts);
          if (props.speed) anim.setSpeed(props.speed);
          return anim;
        }),
        play: function () {
          if (anim) anim.play();
        },
        pause: function () {
          if (anim) anim.pause();
        },
        stop: function () {
          if (anim) anim.stop();
        },
        setSpeed: function (s) {
          if (anim) anim.setSpeed(s);
        },
        goToAndPlay: function (frame, isFrame) {
          if (anim) anim.goToAndPlay(frame, isFrame !== false);
        },
        update: function (p) {
          props = p || props;
          if (anim) {
            anim.destroy();
            anim = null;
          }
          return handle.ready;
        },
        destroy: function () {
          if (anim) anim.destroy();
          anim = null;
          el.innerHTML = "";
        },
      };
      // remount on update via ready chain
      handle.ready.then(function () {});
      return handle;
    },
    update: function (h, props) {
      if (!h) return;
      h.destroy();
      return this.mount(h.el || document.createElement("div"), props);
    },
    call: function (h, method, args) {
      if (h && typeof h[method] === "function") return h[method].apply(h, args || []);
    },
  });

  // Mount any hosts already in the DOM (channel may have scanned too early).
  try {
    if (global.uxBridge && typeof global.uxBridge.scan === "function") {
      global.uxBridge.scan(document);
    }
  } catch (eScan) {}

})(typeof window !== "undefined" ? window : globalThis);
