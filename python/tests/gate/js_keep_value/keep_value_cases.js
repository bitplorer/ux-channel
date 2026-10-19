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
    await runLeakCases(win, doc, check);
    await runComponentCases(win, doc, check, warns);
    await runScopeCases(win, doc, check, warns);

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

async function runLeakCases(win, doc, check) {
  doc.body.innerHTML = keepWrap(
    '<form name="a"><input name="email" type="email" data-ux-keep-value value=""></form>'
  );
  doc.querySelector('form[name="a"] input').value = "from-form-a";
  await applyKeepMorph(
    win,
    keepWrap('<form name="b"><input name="email" type="email" data-ux-keep-value value=""></form>')
  );
  check(
    doc.querySelector("input").value === "",
    "form name a to b " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = keepWrap(
    '<form><input name="email" type="email" data-ux-keep-value value=""></form>'
  );
  doc.querySelector("form input").value = "from-unnamed-form";
  await applyKeepMorph(
    win,
    keepWrap('<input name="email" type="email" data-ux-keep-value value="">')
  );
  check(
    doc.querySelector("input").value === "",
    "unnamed form to none " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = keepWrap(
    '<form id="f1"><input name="x" type="text" data-ux-keep-value value=""></form>'
  );
  doc.querySelector("input").value = "f1-x-secret";
  await applyKeepMorph(
    win,
    keepWrap('<form id="f"><input name="1x" type="text" data-ux-keep-value value=""></form>')
  );
  check(
    doc.querySelector("input").value === "",
    "separator f1/x to f/1x " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = keepWrap(
    '<input name="code" type="text" data-ux-keep-value value="">' +
      '<input name="code" type="text" data-ux-keep-value value="">'
  );
  var oldCodes = doc.querySelectorAll('[name="code"]');
  oldCodes[0].value = "first";
  oldCodes[1].value = "second";
  await applyKeepMorph(
    win,
    keepWrap('<input name="code" type="text" data-ux-keep-value value="">')
  );
  check(
    doc.querySelector('[name="code"]').value === "",
    "old duplicates " + JSON.stringify(doc.querySelector('[name="code"]').value)
  );

  doc.body.innerHTML = keepWrap(
    '<input name="qty" type="text" data-ux-keep-value value="">'
  );
  doc.querySelector('[name="qty"]').value = "12";
  await applyKeepMorph(
    win,
    keepWrap('<input name="qty" type="number" data-ux-keep-value value="4">')
  );
  check(
    doc.querySelector('[name="qty"]').value === "4",
    "text to number " + JSON.stringify(doc.querySelector('[name="qty"]').value)
  );

  var alienOld =
    '<input name="anchor" type="text" data-ux-keep-value value="">' +
    '<input name="obj" type="text" data-ux-keep-value value="">' +
    '<input name="emb" type="text" data-ux-keep-value value="">' +
    '<input name="prm" type="text" data-ux-keep-value value="">';
  var alienNew =
    '<a name="anchor" type="text" data-ux-keep-value></a>' +
    '<object name="obj" type="text" data-ux-keep-value></object>' +
    '<embed name="emb" type="text" data-ux-keep-value>' +
    '<param name="prm" type="text" value="" data-ux-keep-value>';
  doc.body.innerHTML = keepWrap(alienOld);
  doc.querySelector('[name="anchor"]').value = "leak-a";
  doc.querySelector('[name="obj"]').value = "leak-o";
  doc.querySelector('[name="emb"]').value = "leak-e";
  doc.querySelector('[name="prm"]').value = "leak-p";
  await applyKeepMorph(win, keepWrap(alienNew));
  var anchor = doc.querySelector("a");
  var objectEl = doc.querySelector("object");
  var embedEl = doc.querySelector("embed");
  var paramEl = doc.querySelector("param");
  check(anchor.value !== "leak-a", "anchor value " + JSON.stringify(anchor.value));
  check(objectEl.value !== "leak-o", "object value " + JSON.stringify(objectEl.value));
  check(embedEl.value !== "leak-e", "embed value " + JSON.stringify(embedEl.value));
  check(paramEl.value !== "leak-p", "param value " + JSON.stringify(paramEl.value));
  check(paramEl.getAttribute("value") === "", "param attribute " + JSON.stringify(paramEl.getAttribute("value")));
  check(doc.getElementById("region").innerHTML.indexOf("leak-") === -1, "alien markup written");
}

async function runComponentCases(win, doc, check, warns) {
  var swapped =
    '<div data-channel-id="component-a">' +
    '<input name="note" type="text" data-ux-keep-value value="">' +
    "</div>";
  doc.body.innerHTML = keepWrap(swapped);
  doc.querySelector('[name="note"]').value = "A-private";
  await applyKeepMorph(
    win,
    keepWrap(
      '<div data-channel-id="component-b">' +
        '<input name="note" type="text" data-ux-keep-value value="">' +
        "</div>"
    )
  );
  check(
    doc.querySelector('[name="note"]').value === "",
    "A-private into B " + JSON.stringify(doc.querySelector('[name="note"]').value)
  );

  var same =
    '<div data-channel-id="component-a">' +
    '<input name="note" type="text" data-ux-keep-value value="">' +
    "</div>";
  doc.body.innerHTML = keepWrap(same);
  doc.querySelector('[name="note"]').value = "stays-here";
  await applyKeepMorph(win, keepWrap(same));
  check(
    doc.querySelector('[name="note"]').value === "stays-here",
    "same component root " + JSON.stringify(doc.querySelector('[name="note"]').value)
  );

  warns.length = 0;
  doc.body.innerHTML = '<div id="region"><input name="note" type="text" data-ux-keep-value value=""></div>';
  doc.querySelector('[name="note"]').value = "loose";
  await applyKeepMorph(
    win,
    '<div id="region"><input name="note" type="text" data-ux-keep-value value=""></div>'
  );
  var loose = doc.querySelector('[name="note"]');
  check(loose.value === "", "no component root " + JSON.stringify(loose.value));
  var orphanWarns = warns.filter(function (line) {
    return line.indexOf("data-ux-keep-value") !== -1;
  });
  check(orphanWarns.length === 1, "no component root warnings " + orphanWarns.length);
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

function scopeHtml(inner) {
  return '<div id="region">' + inner + "</div>";
}

function keepWarnCount(warns) {
  return warns.filter(function (item) {
    return String(item).indexOf("data-ux-keep-value") !== -1;
  }).length;
}

async function runScopeCases(win, doc, check, warns) {
  var email = '<input name="email" type="email" data-ux-keep-value value="">';
  var unnamed = function (id) {
    return (
      '<div data-channel-id="' + id + '"><form>' + email + "</form></div>"
    );
  };
  doc.body.innerHTML = scopeHtml(unnamed("a"));
  doc.querySelector("input").value = "A-form-private";
  await applyKeepMorph(win, scopeHtml(unnamed("b")));
  check(
    doc.querySelector("input").value === "",
    "unnamed form A to B " + JSON.stringify(doc.querySelector("input").value)
  );

  var named = function (id) {
    return (
      '<div data-channel-id="' + id + '"><form id="f">' + email + "</form></div>"
    );
  };
  doc.body.innerHTML = scopeHtml(named("a"));
  doc.querySelector("input").value = "named-a";
  await applyKeepMorph(win, scopeHtml(named("b")));
  check(
    doc.querySelector("input").value === "",
    "named form A to B " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(unnamed("a"));
  doc.querySelector("input").value = "stays-unnamed";
  await applyKeepMorph(win, scopeHtml(unnamed("a")));
  check(
    doc.querySelector("input").value === "stays-unnamed",
    "same component unnamed " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(named("a"));
  doc.querySelector("input").value = "stays-named";
  await applyKeepMorph(win, scopeHtml(named("a")));
  check(
    doc.querySelector("input").value === "stays-named",
    "same component named " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(
    '<div data-channel-id="1f">' + email + "</div>"
  );
  doc.querySelector("input").value = "comp-1f";
  await applyKeepMorph(win, scopeHtml("<form id=\"f\">" + email + "</form>"));
  check(
    doc.querySelector("input").value === "",
    "component 1f vs form f " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml('<div data-channel-id="f">' + email + "</div>");
  doc.querySelector("input").value = "comp-f";
  await applyKeepMorph(win, scopeHtml("<form id=\"f\">" + email + "</form>"));
  check(
    doc.querySelector("input").value === "",
    "component f vs form f " + JSON.stringify(doc.querySelector("input").value)
  );

  var wrapped =
    '<div data-channel-id="a"><div><label>' +
    '<input name="q" type="text" data-ux-keep-value value="">' +
    "</label></div></div>";
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(wrapped);
  doc.querySelector("input").value = "wrapped";
  await applyKeepMorph(win, scopeHtml(wrapped));
  check(
    doc.querySelector("input").value === "wrapped",
    "wrapped field " + JSON.stringify(doc.querySelector("input").value)
  );
  check(keepWarnCount(warns) === 0, "wrapped warnings " + keepWarnCount(warns));

  var emptyInner =
    '<div data-channel-id="a"><div data-channel-id="">' +
    '<input name="q" type="text" data-ux-keep-value value="">' +
    "</div></div>";
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(emptyInner);
  doc.querySelector("input").value = "outer-a";
  await applyKeepMorph(win, scopeHtml(emptyInner));
  check(
    doc.querySelector("input").value === "outer-a",
    "empty channel id " + JSON.stringify(doc.querySelector("input").value)
  );
  check(keepWarnCount(warns) === 0, "empty channel warnings " + keepWarnCount(warns));

  var own =
    '<input name="q" type="text" data-channel-id="self" data-ux-keep-value value="">';
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(own);
  doc.querySelector("input").value = "own-id";
  await applyKeepMorph(win, scopeHtml(own));
  check(
    doc.querySelector("input").value === "",
    "own data-channel-id " + JSON.stringify(doc.querySelector("input").value)
  );
  check(keepWarnCount(warns) === 1, "own data-channel-id warnings " + keepWarnCount(warns));

  var orphans =
    '<input name="o1" type="text" data-ux-keep-value value="">' +
    '<input name="o2" type="text" data-ux-keep-value value="">';
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(orphans);
  doc.querySelector('[name="o1"]').value = "one";
  doc.querySelector('[name="o2"]').value = "two";
  await applyKeepMorph(win, scopeHtml(orphans));
  check(doc.querySelector('[name="o1"]').value === "", "orphan one kept");
  check(doc.querySelector('[name="o2"]').value === "", "orphan two kept");
  check(keepWarnCount(warns) === 2, "two orphan warnings " + keepWarnCount(warns));

  var namedOnly = '<form id="fid"><input name="byid" type="email" data-ux-keep-value value=""></form>';
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(namedOnly);
  doc.querySelector("input").value = "by-id";
  await applyKeepMorph(win, scopeHtml(namedOnly));
  check(doc.querySelector("input").value === "by-id", "named form no component");
  check(keepWarnCount(warns) === 0, "named form warnings " + keepWarnCount(warns));

  var byName = '<form name="fname"><input name="byname" type="email" data-ux-keep-value value=""></form>';
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(byName);
  doc.querySelector("input").value = "by-name";
  await applyKeepMorph(win, scopeHtml(byName));
  check(doc.querySelector("input").value === "by-name", "form name no component");
  check(keepWarnCount(warns) === 0, "form name warnings " + keepWarnCount(warns));

  var inside =
    '<div data-channel-id="comp"><form>' +
    '<input name="inside" type="email" data-ux-keep-value value="">' +
    "</form></div>";
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(inside);
  doc.querySelector("input").value = "inside-form";
  await applyKeepMorph(win, scopeHtml(inside));
  check(doc.querySelector("input").value === "inside-form", "unnamed form in component");
  check(keepWarnCount(warns) === 0, "unnamed in component warnings " + keepWarnCount(warns));

  var loose = "<form>" + email + "</form>";
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(loose);
  doc.querySelector("input").value = "loose-form";
  await applyKeepMorph(win, scopeHtml(loose));
  check(
    doc.querySelector("input").value === "",
    "unnamed form no component " + JSON.stringify(doc.querySelector("input").value)
  );
  check(keepWarnCount(warns) === 1, "unnamed form no component warnings " + keepWarnCount(warns));

  var compField = function (id, inner) {
    return '<div data-channel-id="' + id + '">' + inner + "</div>";
  };
  var mail = '<input name="email" type="email" data-ux-keep-value value="">';

  doc.body.innerHTML = scopeHtml(compField("a", '<form id="none">' + mail + "</form>"));
  doc.querySelector("input").value = "form-none";
  await applyKeepMorph(win, scopeHtml(compField("a", mail)));
  check(
    doc.querySelector("input").value === "",
    "form id none to no form " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(compField("a", '<form id="unnamed">' + mail + "</form>"));
  doc.querySelector("input").value = "form-unnamed";
  await applyKeepMorph(win, scopeHtml(compField("a", "<form>" + mail + "</form>")));
  check(
    doc.querySelector("input").value === "",
    "form id unnamed to unnamed " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(compField("a", '<form id="name:x">' + mail + "</form>"));
  doc.querySelector("input").value = "id-namex";
  await applyKeepMorph(win, scopeHtml(compField("a", '<form name="x">' + mail + "</form>")));
  check(
    doc.querySelector("input").value === "",
    "form id name:x to name x " + JSON.stringify(doc.querySelector("input").value)
  );

  doc.body.innerHTML = scopeHtml(compField("a", '<form name="id:f">' + mail + "</form>"));
  doc.querySelector("input").value = "name-idf";
  await applyKeepMorph(win, scopeHtml(compField("a", '<form id="f">' + mail + "</form>")));
  check(
    doc.querySelector("input").value === "",
    "form name id:f to id f " + JSON.stringify(doc.querySelector("input").value)
  );

  var card = function (channel) {
    return (
      '<div id="card" data-channel-id="' + channel + '">' +
      '<input name="email" type="email" data-ux-keep-value value="">' +
      "</div>"
    );
  };
  doc.body.innerHTML = scopeHtml(card("a"));
  doc.querySelector("input").value = "A-card";
  await applyKeepMorph(win, scopeHtml(card("b")));
  check(
    doc.querySelector("input").value === "",
    "component element id " + JSON.stringify(doc.querySelector("input").value)
  );

  var bothKinds =
    '<div data-channel-id="a">' +
    '<input name="x" type="text" data-ux-keep-value value="">' +
    '<textarea name="x" data-ux-keep-value></textarea>' +
    "</div>";
  doc.body.innerHTML = scopeHtml(bothKinds);
  doc.querySelector("input").value = "t";
  doc.querySelector("textarea").value = "ta";
  await applyKeepMorph(win, scopeHtml(bothKinds));
  check(
    doc.querySelector("input").value === "t",
    "text beside textarea " + JSON.stringify(doc.querySelector("input").value)
  );
  check(
    doc.querySelector("textarea").value === "ta",
    "textarea beside text " + JSON.stringify(doc.querySelector("textarea").value)
  );

  var nameless =
    '<div data-channel-id="a"><form id="f">' +
    '<input id="only" type="text" data-ux-keep-value value="">' +
    "</form></div>";
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(nameless);
  doc.querySelector("input").value = "nameless";
  await applyKeepMorph(win, scopeHtml(nameless));
  check(
    doc.querySelector("input").value === "",
    "no name kept " + JSON.stringify(doc.querySelector("input").value)
  );
  check(keepWarnCount(warns) === 1, "no name warnings " + keepWarnCount(warns));

  var twoNameless =
    '<input id="one" type="text" data-ux-keep-value value="">' +
    '<input id="two" type="text" data-ux-keep-value value="">';
  warns.length = 0;
  doc.body.innerHTML = scopeHtml(twoNameless);
  await applyKeepMorph(win, scopeHtml(twoNameless));
  check(keepWarnCount(warns) === 2, "two no-name warnings " + keepWarnCount(warns));
}
