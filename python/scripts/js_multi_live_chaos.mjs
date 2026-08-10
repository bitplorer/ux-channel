#!/usr/bin/env node
/**
 * Multi-JS live chaos: all runtimes + bridges + double-load + wrong order.
 * Usage: node scripts/js_multi_live_chaos.mjs http://127.0.0.1:8767
 */
import { chromium } from "playwright";

const base = (process.argv[2] || "http://127.0.0.1:8767").replace(/\/$/, "");

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const report = { base, pages: {}, ok: true, problems: [] };

async function openPage(path) {
  const page = await browser.newPage();
  const consoleErrors = [];
  const consoleWarns = [];
  const pageErrors = [];
  page.on("console", (msg) => {
    const t = msg.type();
    const text = msg.text();
    if (t === "error") consoleErrors.push(text);
    if (t === "warning") consoleWarns.push(text);
  });
  page.on("pageerror", (err) => pageErrors.push(String(err?.message || err)));
  const resp = await page.goto(base + path, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(400);
  return { page, status: resp?.status() ?? 0, consoleErrors, consoleWarns, pageErrors };
}

try {
  // ── 1) Full multi-script page ───────────────────────────────────────
  {
    const { page, status, consoleErrors, pageErrors, consoleWarns } = await openPage("/");
    const snap = await page.evaluate(() => {
      const g = window;
      const bridgePkgs = g.uidBridge
        ? Object.keys(
            // adapters are private; probe via register overwrite no-op
            (function () {
              try {
                // instance map
                return g.uidBridge.instances || {};
              } catch (e) {
                return {};
              }
            })(),
          )
        : [];
      // try mount confetti via bridge API
      let mountOk = false;
      let packagesGuess = [];
      try {
        if (g.uidBridge) {
          // scan should have mounted hosts
          packagesGuess = Object.keys(g.uidBridge.instances || {});
          mountOk = packagesGuess.length >= 0;
        }
      } catch (e) {}
      return {
        uidChannel: !!(g.uidChannel && g.uidChannel.version),
        channelVersion: g.uidChannel && g.uidChannel.version,
        uidBridge: !!(g.uidBridge && g.uidBridge.register),
        bridgeVersion: g.uidBridge && g.uidBridge.version,
        uidInspector: !!(g.uidInspector && g.uidInspector.version),
        UxWebRTC: !!g.UxWebRTC,
        flags: {
          channelLoaded: !!g.__UX_CHANNEL_RUNTIME_LOADED__,
          fxLoaded: !!g.__UX_FX_LOADED__,
          uiLoaded: !!g.__UX_UI_LOADED__,
          webrtcLoaded: !!g.__UX_WEBRTC_LOADED__,
        },
        instances: packagesGuess,
        scripts: [...document.scripts].map((s) => s.src.split("/").pop()).filter(Boolean),
        keepSiblings: document.querySelectorAll("[data-keep]").length,
        bodyChildren: document.body ? document.body.children.length : 0,
      };
    });

    // click bump once
    await page.locator("#bump").click();
    await page.waitForTimeout(600);
    const counter1 = parseInt(await page.locator("#counter").innerText(), 10);

    // concurrent chaos
    await page.evaluate(() => {
      const el = document.querySelector("#bump");
      for (let i = 0; i < 10; i++) el.click();
    });
    await page.waitForTimeout(1200);
    const counter2 = parseInt(await page.locator("#counter").innerText(), 10);
    const keepAfter = await page.locator("[data-keep]").count();

    // boom confetti (bridge call path)
    await page.locator("#boom").click().catch(() => {});
    await page.waitForTimeout(400);

    const entry = {
      status,
      snap,
      counter1,
      counter2,
      keepAfter,
      consoleErrors,
      consoleWarns: consoleWarns.slice(0, 8),
      pageErrors,
    };
    report.pages.full = entry;

    if (status !== 200) report.problems.push("full: bad status");
    if (!snap.uidChannel) report.problems.push("full: uidChannel missing");
    if (!snap.uidBridge) report.problems.push("full: uidBridge missing");
    if (!(counter1 >= 1)) report.problems.push(`full: counter after 1 click=${counter1}`);
    if (!(counter2 > counter1)) report.problems.push(`full: concurrent clicks failed ${counter1}->${counter2}`);
    if (keepAfter !== 2) report.problems.push(`full: DOM siblings damaged keep=${keepAfter}`);
    if (pageErrors.length) report.problems.push(`full: pageErrors ${pageErrors.join(";")}`);
    // filter network noise from optional CDN in uid-ui
    const hard = consoleErrors.filter((e) => !/Failed to load resource/i.test(e) || /ux-channel|ux-bridge|ux-fx|uid-ui\.js/i.test(e));
    if (hard.length) report.problems.push(`full: console ${hard.slice(0, 3).join(" | ")}`);
    await page.close();
  }

  // ── 2) Double-load scripts ──────────────────────────────────────────
  {
    const { page, status, consoleErrors, pageErrors, consoleWarns } = await openPage("/double");
    await page.waitForTimeout(500);
    // one click must increment by 1 not 2
    const before = await page.evaluate(async () => {
      const r = await fetch("/api/state");
      return r.json();
    });
    await page.locator("#bump").click();
    await page.waitForTimeout(700);
    const after = await page.evaluate(async () => {
      const r = await fetch("/api/state");
      return r.json();
    });
    const delta = after.hits - before.hits;
    const skipWarns = consoleWarns.filter((w) => /already loaded/i.test(w));
    report.pages.double = {
      status,
      delta,
      skipWarns,
      consoleErrors: consoleErrors.slice(0, 5),
      pageErrors,
    };
    if (delta !== 1) {
      report.problems.push(`double: expected +1 hit per click, got +${delta} (double-bind?)`);
    }
    if (pageErrors.length) report.problems.push(`double: pageErrors ${pageErrors.join(";")}`);
    await page.close();
  }

  // ── 3) Wrong order: fx before bridge ────────────────────────────────
  {
    const { page, status, consoleErrors, pageErrors, consoleWarns } = await openPage("/wrong-order");
    const alive = await page.locator("#ok").innerText().catch(() => "");
    const hasFxAfterSecond = await page.evaluate(() => !!window.__UX_FX_LOADED__);
    report.pages.wrongOrder = {
      status,
      alive,
      hasFxAfterSecond,
      warns: consoleWarns.filter((w) => /ux-fx|uidBridge/i.test(w)).slice(0, 5),
      pageErrors,
    };
    if (alive !== "still alive") report.problems.push("wrong-order: page crashed");
    if (pageErrors.length) report.problems.push(`wrong-order: pageErrors ${pageErrors.join(";")}`);
    // first fx load warns; second after bridge should register
    await page.close();
  }

  report.ok = report.problems.length === 0;
  console.log(JSON.stringify(report, null, 2));
  process.exit(report.ok ? 0 : 3);
} catch (err) {
  console.error(JSON.stringify({ ok: false, error: String(err?.message || err) }, null, 2));
  process.exit(1);
} finally {
  await browser.close();
}
