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

function keepWrap(inner) {
  return '<div id="region" data-channel-id="login">' + inner + "</div>";
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

    await runIdentityCases(win, doc, check);
    await runErrorCases(win, doc, check);

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

async function runIdentityCases(win, doc, check) {
  var show =
    '<input id="password" name="password" type="password" data-ux-keep-value value="">' +
    '<button id="toggle" type="button">Show</button>';
  doc.body.innerHTML = keepWrap(show);
  doc.getElementById("password").value = KEEP_SECRET;
  doc.getElementById("toggle").focus();
  await applyKeepMorph(
    win,
    keepWrap(
      '<input id="password" name="password" type="text" data-ux-keep-value value="">' +
        '<button id="toggle" type="button">Show</button>'
    )
  );
  check(doc.getElementById("password").type === "text", "show type");
  check(
    doc.getElementById("password").value === KEEP_SECRET,
    "password to text " + JSON.stringify(doc.getElementById("password").value)
  );
  await applyKeepMorph(win, keepWrap(show));
  check(doc.getElementById("password").type === "password", "hide type");
  check(
    doc.getElementById("password").value === KEEP_SECRET,
    "text to password " + JSON.stringify(doc.getElementById("password").value)
  );

  doc.body.innerHTML = keepWrap(
    '<input id="q" name="q" type="text" data-ux-keep-value value="">'
  );
  doc.getElementById("q").value = "visible";
  await applyKeepMorph(
    win,
    keepWrap('<input id="q" name="q" type="hidden" data-ux-keep-value value="">')
  );
  check(
    doc.getElementById("q").value === "",
    "text to hidden " + JSON.stringify(doc.getElementById("q").value)
  );

  doc.body.innerHTML = keepWrap(
    '<input id="q" name="q" type="text" data-ux-keep-value value="">'
  );
  doc.getElementById("q").value = "secret.txt";
  await applyKeepMorph(
    win,
    keepWrap('<input id="q" name="q" type="file" data-ux-keep-value>')
  );
  check(doc.getElementById("q").type === "file", "text to file type");
  check(
    doc.getElementById("q").value === "",
    "text to file " + JSON.stringify(doc.getElementById("q").value)
  );

  doc.body.innerHTML = keepWrap(
    '<textarea name="note" data-ux-keep-value></textarea>'
  );
  doc.querySelector("textarea").value = "hello note";
  await applyKeepMorph(
    win,
    keepWrap('<input name="note" type="text" data-ux-keep-value value="">')
  );
  check(
    doc.querySelector("input").value === "",
    "textarea to text " + JSON.stringify(doc.querySelector("input").value)
  );

  var kinds =
    '<input name="email" type="email" data-ux-keep-value value="">' +
    '<input name="search" type="search" data-ux-keep-value value="">' +
    '<input name="tel" type="tel" data-ux-keep-value value="">' +
    '<input name="url" type="url" data-ux-keep-value value="">';
  doc.body.innerHTML = keepWrap(kinds);
  doc.querySelector('[name="email"]').value = "a@b.c";
  doc.querySelector('[name="search"]').value = "find";
  doc.querySelector('[name="tel"]').value = "555";
  doc.querySelector('[name="url"]').value = "https://e";
  await applyKeepMorph(win, keepWrap(kinds));
  check(doc.querySelector('[name="email"]').value === "a@b.c", "email kept");
  check(doc.querySelector('[name="search"]').value === "find", "search kept");
  check(doc.querySelector('[name="tel"]').value === "555", "tel kept");
  check(doc.querySelector('[name="url"]').value === "https://e", "url kept");

  doc.body.innerHTML = keepWrap(
    '<input id="pan" name="pan" type="text" data-ux-keep-value value="">' +
      '<input id="nick" name="nick" type="text" data-ux-keep-value value="">'
  );
  doc.getElementById("pan").value = "4111-SECRET";
  doc.getElementById("nick").value = "sam";
  await applyKeepMorph(
    win,
    keepWrap(
      '<input id="nick" name="pan" type="text" data-ux-keep-value value="">' +
        '<input id="pan" name="nick" type="text" data-ux-keep-value value="">'
    )
  );
  check(
    doc.querySelector('[name="nick"]').value !== "4111-SECRET",
    "4111-SECRET landed in nick"
  );
  check(
    doc.querySelector('[name="nick"]').value === "sam",
    "nick " + doc.querySelector('[name="nick"]').value
  );
  check(
    doc.querySelector('[name="pan"]').value === "4111-SECRET",
    "pan " + doc.querySelector('[name="pan"]').value
  );

  var forms =
    '<form id="f1"><input name="user" type="text" data-ux-keep-value value=""></form>' +
    '<form id="f2"><input name="user" type="text" data-ux-keep-value value=""></form>';
  doc.body.innerHTML = keepWrap(forms);
  doc.querySelector("#f1 input").value = "alice";
  doc.querySelector("#f2 input").value = "bob";
  await applyKeepMorph(win, keepWrap(forms));
  check(
    doc.querySelector("#f1 input").value === "alice",
    "f1 " + doc.querySelector("#f1 input").value
  );
  check(
    doc.querySelector("#f2 input").value === "bob",
    "alice crossed into f2 " + doc.querySelector("#f2 input").value
  );

  var owners =
    '<form id="f1"></form><form id="f2"></form>' +
    '<input form="f1" name="user" type="text" data-ux-keep-value value="">' +
    '<input form="f2" name="user" type="text" data-ux-keep-value value="">';
  doc.body.innerHTML = keepWrap(owners);
  doc.querySelectorAll('[name="user"]')[0].value = "alice";
  doc.querySelectorAll('[name="user"]')[1].value = "bob";
  await applyKeepMorph(win, keepWrap(owners));
  check(
    doc.querySelector('[form="f1"]').value === "alice",
    "form= f1 " + doc.querySelector('[form="f1"]').value
  );
  check(
    doc.querySelector('[form="f2"]').value === "bob",
    "form= f2 " + doc.querySelector('[form="f2"]').value
  );

  var clash =
    '<form id="f1"></form>' +
    '<input id="a" form="f1" name="user" type="text" data-ux-keep-value value="">' +
    '<input id="b" form="f1" name="user" type="text" data-ux-keep-value value="">';
  doc.body.innerHTML = keepWrap(clash);
  doc.getElementById("a").value = "alice";
  doc.getElementById("b").value = "bob";
  await applyKeepMorph(win, keepWrap(clash));
  check(doc.getElementById("a").value === "", "clashing form= a " + doc.getElementById("a").value);
  check(doc.getElementById("b").value === "", "clashing form= b " + doc.getElementById("b").value);

  var nested =
    '<form id="outer">' +
    '<input id="out" name="title" type="text" data-ux-keep-value value="">' +
    '<div class="nested"><input id="inn" name="title" type="text" data-ux-keep-value value=""></div>' +
    "</form>";
  doc.body.innerHTML = keepWrap(nested);
  doc.getElementById("out").value = "outer-title";
  doc.getElementById("inn").value = "inner-title";
  await applyKeepMorph(win, keepWrap(nested));
  check(doc.getElementById("out").value === "", "nested outer " + doc.getElementById("out").value);
  check(doc.getElementById("inn").value === "", "nested inner " + doc.getElementById("inn").value);

  doc.body.innerHTML = keepWrap(
    '<input id="dup" name="alpha" type="text" data-ux-keep-value value="">' +
      '<input id="dup" name="beta" type="text" data-ux-keep-value value="">'
  );
  doc.querySelector('[name="alpha"]').value = "one";
  doc.querySelector('[name="beta"]').value = "two";
  await applyKeepMorph(
    win,
    keepWrap(
      '<input id="dup" name="alpha" type="text" data-ux-keep-value value="">' +
        '<input id="dup" name="beta" type="text" data-ux-keep-value value="">'
    )
  );
  check(
    doc.querySelector('[name="alpha"]').value === "one",
    "dup id alpha " + doc.querySelector('[name="alpha"]').value
  );
  check(
    doc.querySelector('[name="beta"]').value === "two",
    "dup id beta " + doc.querySelector('[name="beta"]').value
  );

  doc.body.innerHTML = keepWrap('<input id="only" type="text" data-ux-keep-value value="">');
  doc.getElementById("only").value = "nameless";
  await applyKeepMorph(win, keepWrap('<input id="only" type="text" data-ux-keep-value value="">'));
  check(
    doc.getElementById("only").value === "",
    "id without name " + doc.getElementById("only").value
  );

  doc.body.innerHTML = keepWrap('<input name="q" type="text" data-ux-keep-value value="">');
  doc.querySelector('[name="q"]').value = "only";
  await applyKeepMorph(
    win,
    keepWrap(
      '<input name="q" type="text" data-ux-keep-value value="">' +
        '<input name="q" type="text" data-ux-keep-value value="">'
    )
  );
  var dupNew = doc.querySelectorAll('[name="q"]');
  check(dupNew[0].value === "", "duplicate new first " + dupNew[0].value);
  check(dupNew[1].value === "", "duplicate new second " + dupNew[1].value);

  var namedForms =
    '<form id="same"><input name="user" type="text" data-ux-keep-value value=""></form>' +
    '<form name="same"><input name="user" type="text" data-ux-keep-value value=""></form>';
  doc.body.innerHTML = keepWrap(namedForms);
  doc.querySelector('form[id="same"] input').value = "alice";
  doc.querySelector('form[name="same"] input').value = "bob";
  await applyKeepMorph(win, keepWrap(namedForms));
  check(
    doc.querySelector('form[id="same"] input').value === "alice",
    "form id vs name id-side " + doc.querySelector('form[id="same"] input').value
  );
  check(
    doc.querySelector('form[name="same"] input').value === "bob",
    "form id vs name name-side " + doc.querySelector('form[name="same"] input').value
  );

  doc.body.innerHTML = keepWrap(
    '<form id="f1"><input name="user" type="text" data-ux-keep-value value=""></form>' +
      '<input name="user" type="text" data-ux-keep-value value="">'
  );
  doc.querySelector("#f1 input").value = "alice";
  doc.querySelectorAll('[name="user"]')[1].value = "outside";
  await applyKeepMorph(
    win,
    keepWrap(
      '<form id="f1"><input name="user" type="text" data-ux-keep-value value=""></form>' +
        '<input name="user" type="text" data-ux-keep-value value="">'
    )
  );
  check(
    doc.querySelector("#f1 input").value === "alice",
    "form vs none form " + doc.querySelector("#f1 input").value
  );
  check(
    doc.querySelectorAll('[name="user"]')[1].value === "outside",
    "form vs none outside " + doc.querySelectorAll('[name="user"]')[1].value
  );
}

function installRejectingValue(win) {
  var proto = win.HTMLInputElement.prototype;
  var desc = Object.getOwnPropertyDescriptor(proto, "value");
  Object.defineProperty(proto, "value", {
    configurable: true,
    enumerable: desc.enumerable,
    get: function () {
      return desc.get.call(this);
    },
    set: function (v) {
      if (this.getAttribute("name") === "bad" && v) throw new Error("value setter rejected");
      desc.set.call(this, v);
    },
  });
  return function () {
    Object.defineProperty(proto, "value", desc);
  };
}

async function runErrorCases(win, doc, check) {
  var html =
    '<input name="bad" type="text" data-ux-keep-value value="">' +
    '<input id="safe" name="safe" type="text" data-ux-keep-value value="">';
  doc.body.innerHTML = keepWrap(html);
  doc.querySelector('[name="bad"]').value = "boom";
  var safe = doc.getElementById("safe");
  safe.value = "still-here";
  safe.focus();
  safe.setSelectionRange(1, 4);
  var restoreSetter = installRejectingValue(win);
  try {
    await applyKeepMorph(win, keepWrap(html));
    safe = doc.getElementById("safe");
    check(safe.value === "still-here", "throw sibling " + JSON.stringify(safe.value));
    check(doc.activeElement === safe, "throw focus " + (doc.activeElement && doc.activeElement.id));
    check(
      safe.selectionStart === 1 && safe.selectionEnd === 4,
      "throw selection " + safe.selectionStart + "," + safe.selectionEnd
    );
  } finally {
    restoreSetter();
  }
}
