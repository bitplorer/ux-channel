#!/usr/bin/env node
/**
 * Live browser chaos against ux-channel.js (Playwright).
 * Usage: node scripts/js_live_chaos.mjs http://127.0.0.1:8765/
 * Exit 0 ok, 1 nav fail, 2 console/runtime errors, 3 behavioral fail
 */
import { chromium } from "playwright";

const url = process.argv[2] || "http://127.0.0.1:8765/";
const timeoutMs = 45000;
const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(String(err?.message || err)));
  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ""}`);
  });

  const resp = await page.goto(url, { waitUntil: "networkidle", timeout: timeoutMs });
  const status = resp?.status() ?? 0;
  if (status >= 400 || status === 0) {
    console.log(JSON.stringify({ ok: false, stage: "goto", status, consoleErrors, pageErrors }, null, 2));
    process.exit(1);
  }

  // JS globals present
  const client = await page.evaluate(() => {
    const u = window.uidChannel || window.UxChannel || null;
    return {
      hasUxChannel: !!u,
      version: u && (u.version || u.VERSION) || null,
      keys: u ? Object.keys(u).slice(0, 30) : [],
      scripts: [...document.scripts].map((s) => s.src).filter(Boolean),
    };
  });

  // Click once and capture Intent request headers
  let intentHeaders = null;
  let intentStatus = null;
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/_uid/action")) {
      intentHeaders = req.headers();
    }
  });
  page.on("response", async (res) => {
    if (res.request().method() === "POST" && res.url().includes("/_uid/action")) {
      intentStatus = res.status();
    }
  });

  const btn = page.locator("[data-ux-action]").first();
  const btnCount = await page.locator("[data-ux-action]").count();
  if (btnCount === 0) {
    console.log(JSON.stringify({ ok: false, stage: "no-controls", client }, null, 2));
    process.exit(3);
  }

  await btn.click();
  await page.waitForTimeout(500);

  // Chaos: 20 rapid concurrent clicks
  await page.evaluate(async () => {
    const el = document.querySelector("[data-ux-action]");
    if (!el) return;
    const n = 20;
    const clicks = [];
    for (let i = 0; i < n; i++) clicks.push(el.click());
    await Promise.all(clicks);
  });
  await page.waitForTimeout(1500);

  // Counter should have advanced (server increments)
  const counterText = await page.locator("#counter").innerText().catch(() => "");
  const counter = parseInt(counterText, 10);

  // Version parity
  const serverRuntime = await page.evaluate(async () => {
    // last result might be in DOM notice
    return document.body.getAttribute("data-ux-runtime") || null;
  });

  const channelHdr =
    intentHeaders &&
    (intentHeaders["x-ux-channel"] || intentHeaders["X-Ux-Channel"]);
  const clientVer =
    intentHeaders &&
    (intentHeaders["x-uid-client-version"] || intentHeaders["X-Ux-Client-Version"]);

  const report = {
    ok: true,
    status,
    client,
    btnCount,
    intentStatus,
    channelHdr,
    clientVer,
    counter,
    counterText,
    serverRuntime,
    consoleErrors,
    pageErrors,
    failedRequests: failedRequests.slice(0, 10),
  };

  const problems = [];
  if (!client.hasUxChannel) problems.push("uidChannel global missing");
  if (channelHdr !== "1") problems.push(`X-Ux-Channel missing/wrong: ${channelHdr}`);
  if (!clientVer) problems.push("X-Ux-Client-Version missing");
  if (intentStatus && intentStatus >= 400) problems.push(`intent HTTP ${intentStatus}`);
  if (!(counter >= 1)) problems.push(`counter not advanced: ${counterText}`);
  if (pageErrors.length) problems.push(`pageErrors: ${pageErrors.join("; ")}`);
  if (consoleErrors.length) problems.push(`consoleErrors: ${consoleErrors.join("; ")}`);

  report.problems = problems;
  report.ok = problems.length === 0;
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : problems.some((p) => p.startsWith("page") || p.startsWith("console")) ? 2 : 3);
} catch (err) {
  console.error(JSON.stringify({ ok: false, error: String(err?.message || err) }, null, 2));
  process.exit(1);
} finally {
  await browser.close();
}
