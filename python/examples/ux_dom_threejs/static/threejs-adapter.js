/**
 * ux-bridge adapter for three.js (CDN UMD build).
 * Package name: "three"
 *
 * props: {
 *   shape: "box"|"torus"|"icosahedron"|"sphere",
 *   color: "#hex",
 *   wireframe: bool,
 *   autoRotate: bool,
 *   speed: number,
 *   metalness: 0..1,
 *   roughness: 0..1,
 *   title?: string
 * }
 */
(function (global) {
  "use strict";
  if (!global.uxBridge) {
    console.warn("[three adapter] uxBridge missing");
    return;
  }

  // r160 UMD build exposes global THREE
  var THREE_CDN =
    "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js";
  var loading = null;

  function loadThree() {
    if (global.THREE) return Promise.resolve(global.THREE);
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = THREE_CDN;
      s.async = true;
      s.onload = function () {
        if (!global.THREE) reject(new Error("THREE global missing after load"));
        else resolve(global.THREE);
      };
      s.onerror = function () {
        loading = null;
        reject(new Error("Failed to load three.js CDN"));
      };
      document.head.appendChild(s);
    });
    return loading;
  }

  function makeGeometry(THREE, shape) {
    switch (shape) {
      case "torus":
        return new THREE.TorusKnotGeometry(0.7, 0.24, 128, 24);
      case "icosahedron":
        return new THREE.IcosahedronGeometry(1.1, 1);
      case "sphere":
        return new THREE.SphereGeometry(1.05, 48, 32);
      case "box":
      default:
        return new THREE.BoxGeometry(1.4, 1.4, 1.4);
    }
  }

  function applyMaterial(mat, props) {
    mat.color.set(props.color || "#6366f1");
    mat.wireframe = !!props.wireframe;
    mat.metalness = props.metalness != null ? props.metalness : 0.35;
    mat.roughness = props.roughness != null ? props.roughness : 0.35;
    mat.needsUpdate = true;
  }

  global.uxBridge.register("three", {
    mount: function (el, props) {
      return loadThree().then(function (THREE) {
        props = props || {};
        el.style.position = el.style.position || "relative";
        el.style.overflow = "hidden";

        var width = el.clientWidth || 640;
        var height = el.clientHeight || 360;

        var scene = new THREE.Scene();
        scene.background = new THREE.Color(props.bg || "#0b1020");
        scene.fog = new THREE.Fog(props.bg || "#0b1020", 6, 14);

        var camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
        camera.position.set(0, 0.35, 4.2);

        var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(width, height, false);
        renderer.domElement.style.width = "100%";
        renderer.domElement.style.height = "100%";
        renderer.domElement.style.display = "block";
        el.innerHTML = "";
        el.appendChild(renderer.domElement);

        var ambient = new THREE.AmbientLight(0xffffff, 0.45);
        scene.add(ambient);
        var key = new THREE.DirectionalLight(0xffffff, 1.1);
        key.position.set(3, 4, 5);
        scene.add(key);
        var fill = new THREE.PointLight(0x818cf8, 0.7, 20);
        fill.position.set(-3, -1, 2);
        scene.add(fill);

        // ground grid
        var grid = new THREE.GridHelper(8, 16, 0x334155, 0x1e293b);
        grid.position.y = -1.4;
        scene.add(grid);

        var mat = new THREE.MeshStandardMaterial({
          color: props.color || "#6366f1",
          metalness: props.metalness != null ? props.metalness : 0.35,
          roughness: props.roughness != null ? props.roughness : 0.35,
          wireframe: !!props.wireframe,
        });
        var mesh = new THREE.Mesh(makeGeometry(THREE, props.shape || "torus"), mat);
        scene.add(mesh);

        // soft orbit particles
        var dotsGeo = new THREE.BufferGeometry();
        var N = 80;
        var pos = new Float32Array(N * 3);
        for (var i = 0; i < N; i++) {
          var r = 1.8 + Math.random() * 1.4;
          var th = Math.random() * Math.PI * 2;
          var ph = (Math.random() - 0.5) * Math.PI;
          pos[i * 3] = r * Math.cos(th) * Math.cos(ph);
          pos[i * 3 + 1] = r * Math.sin(ph);
          pos[i * 3 + 2] = r * Math.sin(th) * Math.cos(ph);
        }
        dotsGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        var dots = new THREE.Points(
          dotsGeo,
          new THREE.PointsMaterial({ color: 0x94a3b8, size: 0.03 })
        );
        scene.add(dots);

        var state = {
          props: Object.assign({ autoRotate: true, speed: 1 }, props),
          mesh: mesh,
          mat: mat,
          THREE: THREE,
          dragging: false,
          lastX: 0,
          lastY: 0,
          velX: 0.004,
          velY: 0.002,
        };

        function onDown(e) {
          state.dragging = true;
          state.lastX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
          state.lastY = e.clientY || (e.touches && e.touches[0].clientY) || 0;
        }
        function onMove(e) {
          if (!state.dragging) return;
          var x = e.clientX || (e.touches && e.touches[0].clientX) || 0;
          var y = e.clientY || (e.touches && e.touches[0].clientY) || 0;
          var dx = x - state.lastX;
          var dy = y - state.lastY;
          state.lastX = x;
          state.lastY = y;
          state.velX = dx * 0.005;
          state.velY = dy * 0.005;
          mesh.rotation.y += state.velX;
          mesh.rotation.x += state.velY;
        }
        function onUp() {
          state.dragging = false;
        }
        renderer.domElement.addEventListener("pointerdown", onDown);
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);

        var running = true;
        function frame() {
          if (!running) return;
          requestAnimationFrame(frame);
          var sp = state.props.speed != null ? state.props.speed : 1;
          if (state.props.autoRotate && !state.dragging) {
            mesh.rotation.y += 0.008 * sp;
            mesh.rotation.x += 0.003 * sp;
          } else if (!state.dragging) {
            mesh.rotation.y += state.velX;
            mesh.rotation.x += state.velY;
            state.velX *= 0.95;
            state.velY *= 0.95;
          }
          dots.rotation.y += 0.0015 * sp;
          renderer.render(scene, camera);
        }
        frame();

        var ro = null;
        if (typeof ResizeObserver !== "undefined") {
          ro = new ResizeObserver(function () {
            var w = el.clientWidth || width;
            var h = el.clientHeight || height;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h, false);
          });
          ro.observe(el);
        }

        function replaceShape(shape) {
          scene.remove(mesh);
          mesh.geometry.dispose();
          mesh = new THREE.Mesh(makeGeometry(THREE, shape || "box"), mat);
          state.mesh = mesh;
          scene.add(mesh);
        }

        return {
          update: function (next) {
            state.props = Object.assign({}, state.props, next || {});
            applyMaterial(mat, state.props);
            if (next && next.shape && next.shape !== mesh.userData.shape) {
              replaceShape(next.shape);
              mesh.userData.shape = next.shape;
            } else if (next && next.shape) {
              // always allow explicit shape change
              replaceShape(next.shape);
              mesh.userData.shape = next.shape;
            }
            if (next && next.bg) {
              scene.background = new THREE.Color(next.bg);
              if (scene.fog) scene.fog.color = new THREE.Color(next.bg);
            }
          },
          setShape: function (shape) {
            replaceShape(shape);
            state.props.shape = shape;
            mesh.userData.shape = shape;
          },
          setColor: function (color) {
            state.props.color = color;
            applyMaterial(mat, state.props);
          },
          toggleWireframe: function () {
            state.props.wireframe = !state.props.wireframe;
            applyMaterial(mat, state.props);
          },
          toggleSpin: function () {
            state.props.autoRotate = !state.props.autoRotate;
          },
          pulse: function () {
            // quick scale pop
            mesh.scale.set(1.25, 1.25, 1.25);
            setTimeout(function () {
              mesh.scale.set(1, 1, 1);
            }, 180);
          },
          destroy: function () {
            running = false;
            renderer.domElement.removeEventListener("pointerdown", onDown);
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            if (ro) ro.disconnect();
            try {
              mesh.geometry.dispose();
              mat.dispose();
              renderer.dispose();
            } catch (e) {}
            el.innerHTML = "";
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
    },
    destroy: function (handle) {
      if (handle && handle.destroy) handle.destroy();
    },
  });
})(typeof window !== "undefined" ? window : globalThis);
