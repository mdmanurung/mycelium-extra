(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("data").textContent);
  var state = {view: data.journal ? "journal" : "review", filter: "attention", query: "", sel: null};
  var app = document.getElementById("app");
  var BUCKET = {attention: "Needs attention", authorized: "Authorized change", routine: "Routine"};
  var byEvidence = {};
  data.evidence.forEach(function (e) { byEvidence[e.id] = e; });

  // Every string reaches the page through textContent, never as markup.
  function h(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined && text !== null) el.textContent = String(text);
    for (var i = 3; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }
  // `backticked` text becomes a code span; still textContent only, never markup.
  function rich(el, text) {
    String(text).split("`").forEach(function (part, i) { el.appendChild(i % 2 ? h("code", "", part) : document.createTextNode(part)); });
    return el;
  }
  function attr(el, name, value) { el.setAttribute(name, value); return el; }
  function btn(label, cls, fn) { var b = h("button", cls, label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }

  // Copies only; nothing on this page can run a command. The button says what happened.
  function copy(text, button) {
    var label = button.textContent;
    function settle(ok) {
      button.textContent = ok ? "Copied" : "Copy failed: select the text by hand";
      attr(button, "data-state", ok ? "done" : "failed");
      setTimeout(function () { button.textContent = label; button.removeAttribute("data-state"); }, 1800);
    }
    function fallback() {
      var a = h("textarea"); a.value = text; document.body.appendChild(a); a.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(a);
      settle(ok);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { settle(true); }, fallback);
    else fallback();
  }
  function copyButton(label, text, cls) {
    var b = btn(label, cls || "btn", function () { copy(text, b); });
    return b;
  }

  function dot(bucket) { return h("span", "dot " + bucket); }
  function visible() {
    var q = state.query.toLowerCase();
    return data.items.filter(function (i) {
      if (state.filter !== "all" && i.bucket !== state.filter) return false;
      return !q || (i.title + " " + i.file + " " + i.summary + " " + i.observed).toLowerCase().indexOf(q) >= 0;
    });
  }
  function field(dl, label, value, cls) {
    if (!value) return;
    dl.appendChild(h("dt", "", label));
    dl.appendChild(rich(h("dd", cls || ""), value));
  }

  function detail(item) {
    var box = h("div", "detail");
    if (!item) { box.appendChild(h("div", "empty", "Select a change on the left.")); return box; }
    box.appendChild(h("div", "status", "", dot(item.bucket), h("span", "", BUCKET[item.bucket]),
                      h("span", "mono", item.kind + " · " + item.id)));
    box.appendChild(h("h2", "", item.title));
    box.appendChild(rich(h("p", "lead"), item.summary));
    var dl = h("dl", "fields");
    field(dl, "Observed", item.observed);
    field(dl, "Potential", item.potential);
    field(dl, "Unknown", item.unknown);
    field(dl, "Baseline", item.baseline);
    field(dl, "Current", item.current);
    field(dl, "Authorization", item.authorization);
    field(dl, "Context", item.context);
    field(dl, "Axes", ["difference", "focus_relation", "semantic_relation", "authorization_relation", "historical", "consequence", "attribution", "currency"]
      .map(function (k) { return k.replace("_", " ") + " " + item[k]; }).join(" · "), "axes");
    box.appendChild(dl);
    if (item.limitations.length) box.appendChild(h("p", "fine", "Limits: " + item.limitations.join("; ")));
    if (item.next.length) {
      var steps = h("div", "section");
      steps.appendChild(h("h3", "", "Possible next steps"));
      steps.appendChild(h("p", "hint", "Nothing runs from this page; the buttons copy a command."));
      item.next.forEach(function (n) {
        var row = h("div", "step", "", rich(h("span"), n));
        (n.match(/`[^`]+`/g) || []).forEach(function (c) { var cmd = c.slice(1, -1); row.appendChild(copyButton("Copy " + cmd, cmd)); });
        steps.appendChild(row);
      });
      box.appendChild(steps);
    }
    var links = h("div", "section");
    links.appendChild(h("h3", "", "Evidence"));
    var row = h("div", "links");
    item.evidence.forEach(function (id) {
      var e = byEvidence[id];
      row.appendChild(btn(id + (e ? " · " + e.source : ""), "btn", function () { state.view = "evidence"; state.sel = id; draw(); }));
    });
    if (item.diff.length) row.appendChild(btn("Open diff", "btn", function () { state.view = "diff"; draw(); }));
    if (!item.evidence.length && !item.diff.length) row.appendChild(h("span", "mute", "No linked records."));
    links.appendChild(row);
    box.appendChild(links);
    return box;
  }

  function review() {
    var list = visible(), wrap = h("div", "split"), col = h("div", "list");
    if (!list.length) {
      col.appendChild(h("div", "empty", "Nothing in this filter. That is not evidence that nothing changed: see the coverage limits above."));
    }
    var shown = data.items.filter(function (i) { return i.id === state.sel; })[0];
    if (!shown || list.indexOf(shown) < 0) shown = list[0];
    list.forEach(function (i) {
      var b = btn("", "row", function () { state.sel = i.id; renderBody(); });
      if (shown && shown.id === i.id) attr(b, "aria-current", "true");
      b.appendChild(h("span", "t", "", dot(i.bucket), h("span", "", i.title)));
      b.appendChild(h("span", "f", i.file));
      attr(b, "title", i.title);
      col.appendChild(b);
    });
    wrap.appendChild(col);
    wrap.appendChild(detail(shown));
    return wrap;
  }
  function diffs() {
    var box = h("div", "block"), any = false;
    data.items.forEach(function (i) {
      if (!i.diff.length) return;
      any = true;
      box.appendChild(h("h2", "", i.title));
      box.appendChild(h("div", "sub", i.baseline));
      var d = h("div", "diff");
      i.diff.forEach(function (l) { d.appendChild(h("div", l[0], l[1])); });
      box.appendChild(d);
    });
    if (!any) box.appendChild(h("div", "empty", "No line diffs: no baseline was kept, or nothing changed. Diffs are bounded, and secret-like strings are redacted."));
    return box;
  }
  function table(head, rows, pick) {
    var t = h("table"), tr = h("tr");
    head.forEach(function (x) { tr.appendChild(h("th", "", x)); });
    t.appendChild(tr);
    rows.forEach(function (r) {
      var row = h("tr", pick && pick === r[0] ? "pick" : "");
      r.forEach(function (c) { row.appendChild(h("td", "", c)); });
      t.appendChild(row);
    });
    return t;
  }
  function timeline() {
    if (!data.timeline.length) return h("div", "empty", "No events were recorded.");
    return h("div", "block", "", h("p", "fine", "Order is not causation, consent or authorship."),
             table(["When", "Kind", "Event"], data.timeline.map(function (e) { return [e.when, e.kind, e.text]; })));
  }
  function evidence() {
    return h("div", "block", "", table(["Id", "Source", "Reference", "Detail"],
      data.evidence.map(function (e) { return [e.id, e.source, e.ref, e.detail]; }), state.sel));
  }

  function header() {
    var b = data.baselines, c = data.coverage, frag = h("div");
    var tools = h("div", "tools");
    tools.appendChild(copyButton("Copy review brief", data.brief_md || ""));
    tools.appendChild(btn("Light / dark", "btn", function () {
      var r = document.documentElement;
      var dark = r.dataset.theme ? r.dataset.theme === "dark" : (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
      r.dataset.theme = dark ? "light" : "dark";
    }));
    frag.appendChild(h("div", "head", "", h("div", "", "", h("h1", "title", data.analysis_path),
                                            h("p", "sub", "Track changes · snapshot " + data.generated_at)), tools));
    var meta = h("dl", "meta");
    [["Objective", (data.objective.text || "not stated") + (data.objective.source ? " (" + data.objective.source + ")" : ""), true],
     [b.original_selection === "earliest_available_for_display" ? "Comparison start (earliest available)" : "Original plan", b.original_plan || "none"], ["Current plan", b.current_plan || "none"],
     ["Focus", data.focus.active_at_snapshot ? "open" : "none"]].forEach(function (p) {
      var cell = h("div", p[2] ? "wide" : "");
      cell.appendChild(h("dt", "", p[0]));
      cell.appendChild(h("dd", p[0].indexOf("plan") >= 0 ? "mono" : "", p[1]));
      meta.appendChild(cell);
    });
    frag.appendChild(meta);
    frag.appendChild(h("p", "fine", "Read-only evidence. It does not approve, freeze, run or validate anything. Not observed: " + c.not_observed.join(", ") + "."));
    if (c.limitations.length) {
      var d = h("details", "limits"), ul = h("ul");
      d.appendChild(h("summary", "", "Coverage limits (" + c.limitations.length + ")"));
      c.limitations.forEach(function (l) { ul.appendChild(h("li", "", l)); });
      d.appendChild(ul);
      frag.appendChild(d);
    }
    return frag;
  }

  __JOURNAL__
  var VIEWS = [["review", "Review", function () { return data.items.length; }],
               ["diff", "Diff", function () { return data.items.filter(function (i) { return i.diff.length; }).length; }],
               [data.journal ? "journal" : "timeline", data.journal ? "Journal" : "Timeline", function () { return data.journal ? data.journal.events.length : data.timeline.length; }],
               ["evidence", "Evidence", function () { return data.evidence.length; }]];

  // level 1: the four views
  function views() {
    var bar = attr(h("div", "views"), "role", "tablist");
    VIEWS.forEach(function (v) {
      var t = h("button", "view", v[1], h("span", "n", v[2]()));
      t.type = "button";
      attr(t, "role", "tab"); attr(t, "aria-selected", state.view === v[0] ? "true" : "false");
      t.addEventListener("click", function () { state.view = v[0]; draw(); });
      bar.appendChild(t);
    });
    return bar;
  }
  // level 2: filters of the Review view, drawn directly under the view strip, only for Review
  function filters() {
    var bar = h("div", "filters"), seg = attr(h("div", "seg"), "role", "group");
    attr(seg, "aria-label", "Filter changes");
    [["attention", "Needs attention", data.counts.attention], ["all", "All", data.items.length],
     ["authorized", "Authorized", data.counts.authorized], ["routine", "Routine", data.counts.routine]].forEach(function (f) {
      var c = h("button", "chip", f[1], h("span", "n", f[2]));
      c.type = "button"; attr(c, "aria-pressed", state.filter === f[0] ? "true" : "false");
      c.addEventListener("click", function () { state.filter = f[0]; draw(); });
      seg.appendChild(c);
    });
    var q = h("input", "search"); q.type = "search"; q.placeholder = "Search changes"; q.value = state.query;
    attr(q, "aria-label", "Search changes");
    q.addEventListener("input", function () { state.query = q.value; renderBody(); });  // only the body redraws, so typing keeps focus
    bar.appendChild(seg); bar.appendChild(q);
    return bar;
  }

  var mount = h("div");
  function renderBody() {
    clear(mount);
    mount.appendChild({review: review, diff: diffs, timeline: timeline, journal: journal, evidence: evidence}[state.view]());
  }
  function draw() {
    clear(app);
    document.title = "Track changes · " + data.analysis_path;
    if (state.view !== "journal") app.appendChild(header());
    app.appendChild(views());
    if (state.view === "review") app.appendChild(filters());
    app.appendChild(mount);
    renderBody();
  }
  draw();
})();
