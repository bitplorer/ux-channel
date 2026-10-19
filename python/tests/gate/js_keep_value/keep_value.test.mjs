/**
 * jsdom always. Chromium when a Chrome/Chromium binary is on PATH.
 * UX_KEEP_VALUE_REQUIRE_BROWSER=1 turns a missing browser into a hard failure.
 * The keep-value chromium CI job sets that flag. The verify job does not.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";

const here = path.dirname(fileURLToPath(import.meta.url));
const channelPath = path.resolve(here, "../../../src/ux_channel/static/ux-channel.js");
const idiomorphPath = path.join(here, "node_modules/idiomorph/dist/idiomorph.js");
const casesPath = path.join(here, "keep_value_cases.js");

function read(file) {
  return fs.readFileSync(file, "utf8");
}

async function runJsdom() {
  const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
    url: "http://127.0.0.1/",
    pretendToBeVisual: true,
    runScripts: "dangerously",
  });
  const win = dom.window;
  win.eval(read(channelPath));
  win.eval(read(idiomorphPath));
  win.eval(read(casesPath));
  // jsdom throws on scrollTo. The product always restores scroll after morph.
  win.scrollTo = function () {};
  const result = await win.runKeepValueCases(win);
  dom.window.close();
  return result.failures;
}

function chromeBinary() {
  const env = process.env.CHROME_PATH;
  if (env && fs.existsSync(env)) return env;
  const names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"];
  const dirs = (process.env.PATH || "").split(path.delimiter);
  for (const name of names) {
    for (const dir of dirs) {
      const candidate = path.join(dir, name);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return null;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(label + " timed out")), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

async function waitForJson(url) {
  const started = Date.now();
  let last = "";
  while (Date.now() - started < 10000) {
    try {
      const res = await fetch(url);
      if (res.ok) return await res.json();
      last = String(res.status);
    } catch (err) {
      last = String(err && err.message ? err.message : err);
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("devtools not ready: " + last);
}

function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const opened = new Promise((resolve, reject) => {
    ws.addEventListener("open", () => resolve());
    ws.addEventListener("error", () => reject(new Error("devtools websocket failed")));
  });
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (!msg.id || !pending.has(msg.id)) return;
    const slot = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) slot.reject(new Error(JSON.stringify(msg.error)));
    else slot.resolve(msg.result);
  });
  return {
    ready: opened,
    send(method, params) {
      const msgId = ++id;
      return new Promise((resolve, reject) => {
        pending.set(msgId, { resolve, reject });
        ws.send(JSON.stringify({ id: msgId, method, params }));
      });
    },
    close() {
      ws.close();
    },
  };
}

function inlinePage() {
  const escape = (src) => src.replace(/<\/script/gi, "<\\/script");
  return (
    "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>" +
    "<script>" + escape(read(channelPath)) + "</script>" +
    "<script>" + escape(read(idiomorphPath)) + "</script>" +
    "<script>" + escape(read(casesPath)) + "</script>" +
    "</body></html>"
  );
}

async function runChrome(binary) {
  const port = await freePort();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "ux-keep-"));
  const htmlPath = path.join(profile, "keep-value.html");
  fs.writeFileSync(htmlPath, inlinePage());
  const url = pathToFileURL(htmlPath).href;
  const chrome = spawn(
    binary,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "about:blank",
    ],
    { detached: true, stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  chrome.stderr.on("data", (buf) => {
    stderr += buf.toString();
    if (stderr.length > 4000) stderr = stderr.slice(-4000);
  });
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`);
    const created = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, {
      method: "PUT",
    });
    if (!created.ok) {
      throw new Error("json/new " + created.status + " " + (await created.text()));
    }
    const target = await created.json();
    const client = cdp(target.webSocketDebuggerUrl);
    await client.ready;
    await client.send("Runtime.enable");
    // json/new returns before the document's scripts have run.
    const started = Date.now();
    let probe = "";
    while (Date.now() - started < 8000) {
      const ready = await client.send("Runtime.evaluate", {
        expression: "typeof runKeepValueCases",
        returnByValue: true,
      });
      probe = ready.result && ready.result.value;
      if (probe === "function") break;
      await new Promise((r) => setTimeout(r, 40));
    }
    if (probe !== "function") {
      throw new Error("runKeepValueCases was not defined (" + probe + ")");
    }
    const evaluated = await withTimeout(
      client.send("Runtime.evaluate", {
        expression: "runKeepValueCases(window)",
        awaitPromise: true,
        returnByValue: true,
      }),
      20000,
      "runKeepValueCases",
    );
    client.close();
    if (evaluated.exceptionDetails) {
      throw new Error(JSON.stringify(evaluated.exceptionDetails));
    }
    const value = evaluated.result && evaluated.result.value;
    if (!value || !Array.isArray(value.failures) || typeof value.checks !== "number") {
      throw new Error("chrome returned " + JSON.stringify(evaluated.result));
    }
    return value;
  } catch (err) {
    const detail = stderr
      ? "\n" + stderr.split("\n").filter((line) => line && !/dbus|DevTools listening/i.test(line)).slice(-8).join("\n")
      : "";
    throw new Error(String(err && err.message ? err.message : err) + detail);
  } finally {
    try {
      process.kill(-chrome.pid, "SIGKILL");
    } catch (eKill) {
      try { chrome.kill("SIGKILL"); } catch (eOnce) {}
    }
    await new Promise((resolve) => {
      if (chrome.exitCode !== null || chrome.signalCode !== null) resolve();
      else {
        chrome.once("exit", () => resolve());
        setTimeout(resolve, 2000);
      }
    });
    for (let attempt = 0; attempt < 8; attempt++) {
      try {
        fs.rmSync(profile, { recursive: true, force: true });
        break;
      } catch (eRm) {
        if (attempt === 7) throw eRm;
        await new Promise((r) => setTimeout(r, 40));
      }
    }
  }
}

const requireBrowser = process.env.UX_KEEP_VALUE_REQUIRE_BROWSER === "1";
const jsdomFailures = await runJsdom();
const binary = chromeBinary();
let chrome;
if (!binary) {
  if (requireBrowser) {
    console.log("CHROMIUM passed=0 skipped=0");
    console.error("CHROMIUM browser required but no Chrome or Chromium binary was found");
    process.exit(1);
  }
  chrome = { skipped: true, ok: true, failures: [], passed: 0, skippedCases: 1 };
} else {
  try {
    const result = await runChrome(binary);
    chrome = {
      skipped: false,
      ok: result.failures.length === 0,
      failures: result.failures,
      passed: result.checks - result.failures.length,
      skippedCases: 0,
      binary,
    };
  } catch (err) {
    chrome = {
      skipped: false,
      ok: false,
      failures: [String(err && err.stack ? err.stack : err)],
      passed: 0,
      skippedCases: 0,
      binary,
    };
  }
}
const payload = {
  jsdom: { ok: jsdomFailures.length === 0, failures: jsdomFailures },
  chrome,
};
console.log(
  "CHROMIUM passed=" + chrome.passed + " skipped=" + (chrome.skipped ? chrome.skippedCases : 0),
);
console.log("KEEP_VALUE_RESULT " + JSON.stringify(payload));
if (!payload.jsdom.ok || !payload.chrome.ok) process.exit(1);
