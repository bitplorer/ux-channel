/**
 * Shared morph cases for data-ux-keep-value.
 * Loaded as a classic script in Chromium and via window.eval under jsdom.
 * The product file under test is ux-channel.js; this file only drives it.
 */
async function runKeepValueCases(win) {
  var saved = win.Idiomorph;
  var failures = [];
  var checks = 0;
  win.Idiomorph = undefined;
  var replacePart = await runKeepValuePath(win, "replaceWith");
  failures = failures.concat(replacePart.failures);
  checks += replacePart.checks;
  if (saved && typeof saved.morph === "function") {
    win.Idiomorph = saved;
    var idioPart = await runKeepValuePath(win, "idiomorph");
    failures = failures.concat(idioPart.failures);
    checks += idioPart.checks;
  } else {
    checks += 1;
    failures.push("idiomorph Idiomorph global missing");
  }
  win.Idiomorph = saved;
  return { failures: failures, checks: checks };
}

var KEEP_SECRET = "s3cret-from-visitor";
var KEEP_MARKUP = '"><img src=x onerror=alert(1)>';

function keepRegionHtml(dropMarked) {
  var drop = dropMarked ? "" : " data-ux-keep-value";
  return (
    '<div id="region" data-channel-id="login">' +
    '<input id="password" name="password" type="password" data-ux-keep-value value="">' +
    '<input id="username" name="username" type="text" value="">' +
    '<input id="remember" name="remember" type="checkbox" data-ux-keep-value value="yes">' +
    '<input id="radio-a" name="channel" type="radio" data-ux-keep-value value="a">' +
    '<input id="radio-b" name="channel" type="radio" data-ux-keep-value value="b">' +
    '<textarea id="note" name="note" data-ux-keep-value></textarea>' +
    '<input name="otp" type="text" data-ux-keep-value value="">' +
    '<input id="token" name="token" type="hidden" data-ux-keep-value value="">' +
    '<select id="color" name="color" data-ux-keep-value><option value="a">a</option><option value="b">b</option></select>' +
    '<input id="dropme" name="dropme" type="text"' + drop + ' value="">' +
    '<button id="toggle" type="button">Show</button>' +
    "</div>"
  );
}

async function applyKeepMorph(win, html) {
  var pending = win.uxChannel.applyResult({
    ok: true,
    ops: [{ op: "morph", target: "#region", html: html }],
  });
  if (pending && typeof pending.then === "function") await pending;
}

async function runKeepValuePath(win, path) {
  var failures = [];
  var checks = 0;
  function check(cond, msg) {
    checks += 1;
    if (!cond) failures.push(path + " " + msg);
  }
  var doc = win.document;
  var using = !!(win.Idiomorph && typeof win.Idiomorph.morph === "function");
  check(path === "idiomorph" ? using : !using, "engine armed=" + using);

  var calls = 0;
  var restoreSpy = function () {};
  if (path === "idiomorph") {
    var origMorph = win.Idiomorph.morph;
    win.Idiomorph.morph = function () {
      calls += 1;
      return origMorph.apply(this, arguments);
    };
    restoreSpy = function () {
      win.Idiomorph.morph = origMorph;
    };
  } else {
    var origReplace = win.Element.prototype.replaceWith;
    win.Element.prototype.replaceWith = function () {
      calls += 1;
      return origReplace.apply(this, arguments);
    };
    restoreSpy = function () {
      win.Element.prototype.replaceWith = origReplace;
    };
  }

  var warns = [];
  var origWarn = win.console.warn;
  win.console.warn = function () {
    warns.push(Array.prototype.join.call(arguments, " "));
    return origWarn.apply(win.console, arguments);
  };

  try {
    doc.body.innerHTML = keepRegionHtml(false);
    doc.getElementById("password").value = KEEP_SECRET;
    doc.getElementById("username").value = "ada";
    doc.getElementById("remember").checked = true;
    doc.getElementById("radio-b").checked = true;
    doc.getElementById("note").value = "hello note";
    doc.querySelector('[name="otp"]').value = "2468";
    doc.getElementById("token").value = "hidden-secret";
    doc.getElementById("color").value = "b";
    doc.getElementById("dropme").value = "temporary";

    var serverHtml = keepRegionHtml(true);
    // Show, Hide, a tab switch and back, and a failed submit each morph value="".
    var steps = [
      { name: "show", focus: "toggle" },
      { name: "hide", focus: "toggle" },
      { name: "tab-switch-and-back", focus: "toggle" },
      { name: "failed-submit", focus: "password", select: [1, 4] },
    ];
    var s;
    var step;
    var pw;
    for (s = 0; s < steps.length; s++) {
      step = steps[s];
      if (step.focus === "toggle") {
        doc.getElementById("toggle").focus();
      } else {
        pw = doc.getElementById("password");
        pw.focus();
        try {
          pw.setSelectionRange(step.select[0], step.select[1]);
        } catch (eSel) {
          check(false, step.name + " setSelectionRange threw");
        }
      }
      await applyKeepMorph(win, serverHtml);
      pw = doc.getElementById("password");
      check(pw.value === KEEP_SECRET, step.name + " password " + JSON.stringify(pw.value));
      check(
        pw.getAttribute("value") === "",
        step.name + " value attribute " + JSON.stringify(pw.getAttribute("value"))
      );
      check(
        doc.getElementById("region").innerHTML.indexOf(KEEP_SECRET) === -1,
        step.name + " secret leaked into html"
      );
      check(
        doc.getElementById("username").value === "",
        step.name + " unmarked username " + JSON.stringify(doc.getElementById("username").value)
      );
      check(doc.getElementById("remember").checked === false, step.name + " checkbox kept");
      check(doc.getElementById("radio-b").checked === false, step.name + " radio kept");
      check(doc.getElementById("radio-a").checked === false, step.name + " other radio checked");
      check(
        doc.getElementById("token").value === "",
        step.name + " hidden " + JSON.stringify(doc.getElementById("token").value)
      );
      var ignoredWarns = warns.filter(function (line) {
        return line.indexOf("data-ux-keep-value") !== -1;
      });
      check(ignoredWarns.length === 5, step.name + " warnings " + ignoredWarns.length);
      warns.length = 0;
      check(
        doc.getElementById("note").value === "hello note",
        step.name + " textarea " + JSON.stringify(doc.getElementById("note").value)
      );
      check(
        doc.querySelector('[name="otp"]').value === "2468",
        step.name + " name key " + JSON.stringify(doc.querySelector('[name="otp"]').value)
      );
      var drop = doc.getElementById("dropme");
      check(drop.hasAttribute("data-ux-keep-value") === false, step.name + " drop mark kept");
      check(drop.value === "", step.name + " unmarked new node kept " + JSON.stringify(drop.value));
      if (step.focus === "toggle") {
        check(
          doc.activeElement && doc.activeElement.id === "toggle",
          step.name + " focus " + (doc.activeElement && doc.activeElement.id)
        );
      } else {
        check(doc.activeElement === pw, step.name + " focus moved off password");
        check(
          pw.selectionStart === 1 && pw.selectionEnd === 4,
          step.name + " selection " + pw.selectionStart + "," + pw.selectionEnd
        );
      }
    }
    check(calls === steps.length, "engine calls " + calls + " wanted " + steps.length);

    doc.body.innerHTML =
      '<div id="region" data-channel-id="login">' +
      '<input id="payload" name="payload" type="text" data-ux-keep-value value="">' +
      '<button id="toggle" type="button">Show</button>' +
      "</div>";
    var beforeCount = doc.body.querySelectorAll("*").length;
    doc.getElementById("payload").value = KEEP_MARKUP;
    doc.getElementById("toggle").focus();
    await applyKeepMorph(
      win,
      '<div id="region" data-channel-id="login">' +
        '<input id="payload" name="payload" type="text" data-ux-keep-value value="">' +
        '<button id="toggle" type="button">Show</button>' +
        "</div>"
    );
    var payload = doc.getElementById("payload");
    check(payload.value === KEEP_MARKUP, "markup value " + JSON.stringify(payload.value));
    check(
      payload.getAttribute("value") === "",
      "markup value attribute " + JSON.stringify(payload.getAttribute("value"))
    );
    check(doc.querySelector("img") == null, "markup created an img");
    check(
      doc.body.querySelectorAll("*").length === beforeCount,
      "markup element count " + doc.body.querySelectorAll("*").length
    );
    check(calls === steps.length + 1, "markup morph calls " + calls);

    doc.body.innerHTML =
      '<div id="region" data-channel-id="login">' +
      '<input id="upload" name="upload" type="text" data-ux-keep-value value="">' +
      '<input id="password" name="password" type="password" data-ux-keep-value value="">' +
      '<button id="toggle" type="button">Show</button>' +
      "</div>";
    doc.getElementById("upload").value = "secret.txt";
    doc.getElementById("password").value = KEEP_SECRET;
    doc.getElementById("toggle").focus();
    warns.length = 0;
    await applyKeepMorph(
      win,
      '<div id="region" data-channel-id="login">' +
        '<input id="upload" name="upload" type="file" data-ux-keep-value>' +
        '<input id="password" name="password" type="password" data-ux-keep-value value="">' +
        '<button id="toggle" type="button">Show</button>' +
        "</div>"
    );
    var upload = doc.getElementById("upload");
    check(upload.type === "file", "file switch type " + upload.type);
    check(upload.value === "", "file switch value " + JSON.stringify(upload.value));
    check(
      doc.getElementById("password").value === KEEP_SECRET,
      "file switch sibling " + JSON.stringify(doc.getElementById("password").value)
    );
    check(
      doc.activeElement && doc.activeElement.id === "toggle",
      "file switch focus " + (doc.activeElement && doc.activeElement.id)
    );
    check(calls === steps.length + 2, "file switch calls " + calls);

    var callsBeforeEmpty = calls;
    var region = doc.getElementById("region");
    await applyKeepMorph(win, "no-element");
    check(calls === callsBeforeEmpty, "empty fragment used the element engine");
    check(doc.getElementById("region") === region, "empty fragment replaced the target");
    check(doc.getElementById("password") == null, "empty fragment left the password");
    check(region.textContent === "no-element", "empty fragment text " + JSON.stringify(region.textContent));
  } catch (err) {
    check(false, "threw " + (err && err.stack ? err.stack : err));
  } finally {
    win.console.warn = origWarn;
    restoreSpy();
  }
  return { failures: failures, checks: checks };
}
