#!/usr/bin/env node
/**
 * Full live-DOM enterprise pass: multi-region isolation, concurrency, bridges, stress.
 * Usage: node scripts/js_enterprise_live.mjs http://127.0.0.1:8768
 */
import { chromium } from "playwright";

const base = (process.argv[2] || "http://127.0.0.1:8768").replace(/\/$/, "");
const problems = [];
const report = { base, phases: {}, ok: true, problems };

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

function fail(msg) {
  problems.push(msg);
}

try {
  const page = await browser.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => pageErrors.push(String(e?.message || e)));

  const resp = await page.goto(base + "/", { waitUntil: "networkidle", timeout: 60000 });
  report.phases.goto = { status: resp?.status() };
  if (resp?.status() !== 200) fail("goto not 200");

  await page.waitForTimeout(600);

  // Globals
  const globals = await page.evaluate(() => ({
    channel: !!(window.uidChannel && window.uidChannel.version),
    bridge: !!(window.uidBridge && window.uidBridge.register),
    instances: Object.keys((window.uidBridge && window.uidBridge.instances) || {}),
    inspector: !!window.uidInspector,
    webrtc: !!window.UxWebRTC,
    scripts: [...document.scripts].map((s) => (s.src || "").split("/").pop()).filter(Boolean),
  }));
  report.phases.globals = globals;
  if (!globals.channel) fail("uidChannel missing");
  if (!globals.bridge) fail("uidBridge missing");
  if (!globals.instances.includes("fx1") || !globals.instances.includes("cu1")) {
    fail("bridge instances not mounted: " + JSON.stringify(globals.instances));
  }

  async function vals() {
    return page.evaluate(() => {
      const a = document.querySelector("#panel_a .val")?.textContent?.trim();
      const b = document.querySelector("#panel_b .val")?.textContent?.trim();
      const c = document.querySelector("#panel_c .val")?.textContent?.trim();
      const note = document.querySelector("#panel_c_note")?.textContent?.trim();
      const keepA = document.querySelectorAll("[data-keep-a]").length;
      const keepB = document.querySelectorAll("[data-keep-b]").length;
      const keep = document.querySelectorAll("[data-keep]").length;
      return { a, b, c, note, keepA, keepB, keep };
    });
  }

  const v0 = await vals();

  // ── Isolation: bump A only ─────────────────────────────────────────
  await page.locator("#ba").click();
  await page.waitForTimeout(500);
  const vA = await vals();
  report.phases.bumpA = { before: v0, after: vA };
  if (vA.a !== "1") fail(`A not 1: ${vA.a}`);
  if (vA.b !== v0.b) fail(`B changed when bumping A: ${v0.b}→${vA.b}`);
  if (vA.c !== v0.c) fail(`C changed when bumping A: ${v0.c}→${vA.c}`);
  if (vA.keepA !== 1) fail("keep-a lost on A morph");
  if (vA.keepB !== 1) fail("keep-b lost when A morphed");
  if (vA.keep !== 3) fail(`static siblings damaged: ${vA.keep}`);

  // ── Isolation: bump B only ─────────────────────────────────────────
  await page.locator("#bb").click();
  await page.waitForTimeout(500);
  const vB = await vals();
  report.phases.bumpB = vB;
  if (vB.b !== "1") fail(`B not 1: ${vB.b}`);
  if (vB.a !== "1") fail(`A changed when bumping B: ${vB.a}`);

  // ── Nested: bump C note only (not outer C val via region note) ─────
  await page.locator("#bc").click();
  await page.waitForTimeout(500);
  const vC = await vals();
  report.phases.bumpC = vC;
  if (!String(vC.note || "").includes("1")) fail(`note not updated: ${vC.note}`);
  // outer C val may stay 0 until bump_all — intentional nested partial refresh
  if (vC.a !== "1" || vC.b !== "1") fail("A/B disturbed by C note refresh");

  // ── Concurrent stress on A ─────────────────────────────────────────
  await page.evaluate(() => {
    const el = document.querySelector("#ba");
    for (let i = 0; i < 25; i++) el.click();
  });
  await page.waitForTimeout(2000);
  const vStress = await vals();
  report.phases.stressA = vStress;
  const aN = parseInt(vStress.a, 10);
  if (!(aN >= 20)) fail(`stress A expected ~26 got ${vStress.a}`);
  if (vStress.b !== "1") fail(`B changed during A stress: ${vStress.b}`);
  if (vStress.keep !== 3) fail("siblings lost under stress");

  // ── Mixed concurrent A/B/all ───────────────────────────────────────
  await page.evaluate(() => {
    const ba = document.querySelector("#ba");
    const bb = document.querySelector("#bb");
    const ball = document.querySelector("#ball");
    for (let i = 0; i < 10; i++) {
      ba.click();
      bb.click();
      if (i % 3 === 0) ball.click();
    }
  });
  await page.waitForTimeout(2500);
  const vMix = await vals();
  report.phases.mixed = vMix;
  if (parseInt(vMix.a, 10) <= aN) fail("mixed: A did not advance");
  if (parseInt(vMix.b, 10) < 5) fail("mixed: B did not advance enough");
  if (vMix.keep !== 3) fail("mixed: siblings damaged");

  // ── Bridge still alive ─────────────────────────────────────────────
  await page.locator("#boom").click();
  await page.waitForTimeout(400);
  const inst = await page.evaluate(() => Object.keys(window.uidBridge.instances || {}));
  report.phases.bridgeAfter = inst;
  if (!inst.includes("fx1")) fail("fx1 destroyed unexpectedly");

  // ── Server state consistency ───────────────────────────────────────
  const server = await page.evaluate(async () => (await fetch("/api/state")).json());
  report.phases.server = server;
  if (server.hits < 30) fail(`hits too low: ${server.hits}`);

  // ── Rapid reload stability ─────────────────────────────────────────
  for (let i = 0; i < 3; i++) {
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(300);
  }
  const afterReload = await page.evaluate(() => !!(window.uidChannel && window.uidBridge));
  report.phases.reload = { afterReload, consoleErrors: consoleErrors.slice(0, 10), pageErrors };
  if (!afterReload) fail("globals missing after reload");

  // filter benign CDN noise
  const hardErr = consoleErrors.filter(
    (e) => !/Failed to load resource/i.test(e) || /ux-channel|ux-bridge|ux-fx/i.test(e),
  );
  if (hardErr.length) fail("console: " + hardErr.slice(0, 3).join(" | "));
  if (pageErrors.length) fail("pageErrors: " + pageErrors.join("; "));

  report.problems = problems;
  report.ok = problems.length === 0;
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : 3);
} catch (err) {
  console.error(JSON.stringify({ ok: false, error: String(err?.message || err) }, null, 2));
  process.exit(1);
} finally {
  await browser.close();
}
