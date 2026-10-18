(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("data").textContent);
  var state = {view: "review", filter: "attention", query: "", sel: null};
  var app = document.getElementById("app");
  var byEvidence = {};
  data.evidence.forEach(function (e) { byEvidence[e.id] = e; });

  function h(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined && text !== null) el.textContent = String(text);
    for (var i = 3; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }
  function btn(label, cls, fn) { var b = h("button", cls, label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function toast(text) {
    var t = document.getElementById("toast") || document.body.appendChild(h("div")); t.id = "toast";
    t.textContent = text; t.style.display = "block"; clearTimeout(toast.id); toast.id = setTimeout(function () { t.style.display = "none"; }, 2200);
  }
  function copy(text) {  // copies only; nothing here can run anything
    function fallback() {
      var a = h("textarea"); a.value = text; document.body.appendChild(a); a.select();
      try { document.execCommand("copy"); toast("Copied"); } catch (e) { toast("Copy failed: select the text manually"); }
      document.body.removeChild(a);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { toast("Copied"); }, fallback);
    else fallback();
  }
  function tag(item) { return h("span", "tag " + item.bucket, {attention: "Needs attention", authorized: "Authorized change", routine: "Routine"}[item.bucket]); }
  function visible() {
    var q = state.query.toLowerCase();
    return data.items.filter(function (i) {
      if (state.filter !== "all" && i.bucket !== state.filter) return false;
      return !q || (i.title + " " + i.file + " " + i.summary + " " + i.observed).toLowerCase().indexOf(q) >= 0;
    });
  }
  function field(dl, label, value) { if (value) { dl.appendChild(h("dt", "", label)); dl.appendChild(h("dd", "", value)); } }

  function detail(item) {
    var box = h("div", "card");
    if (!item) { box.appendChild(h("div", "empty", "Select a change.")); return box; }
    box.appendChild(h("div", "", "", tag(item), h("span", "mute", item.kind + " · " + item.id)));
    box.appendChild(h("h2", "", item.title));
    box.appendChild(h("p", "", item.summary));
    var dl = h("dl");
    [["Observed", item.observed], ["Potential", item.potential], ["Unknown", item.unknown], ["Baseline", item.baseline],
     ["Current", item.current], ["Authorization", item.authorization], ["Context", item.context],
     ["Axes", ["difference", "focus_relation", "semantic_relation", "authorization_relation", "historical", "consequence", "attribution", "currency"]
        .map(function (k) { return k.replace("_", " ") + ": " + item[k]; }).join(" · ")]].forEach(function (p) { field(dl, p[0], p[1]); });
    box.appendChild(dl);
    if (item.limitations.length) box.appendChild(h("p", "mute", "Limits: " + item.limitations.join("; ")));
    if (item.next.length) {
      box.appendChild(h("h2", "", "What you could do (nothing runs from here)"));
      item.next.forEach(function (n) {
        var row = h("div", "row", "", h("span", "", n));
        (n.match(/`[^`]+`/g) || []).forEach(function (c) { var cmd = c.slice(1, -1); row.appendChild(btn("Copy " + cmd, "", function () { copy(cmd); })); });
        box.appendChild(row);
      });
    }
    box.appendChild(h("h2", "", "Evidence"));
    item.evidence.forEach(function (id) {
      var e = byEvidence[id];
      box.appendChild(btn(id + " · " + (e ? e.source : "?"), "", function () { state.view = "evidence"; state.sel = id; draw(); }));
    });
    return box;
  }
  function diffBox(item) {
    var box = h("div", "diff");
    item.diff.forEach(function (l) { box.appendChild(h("div", l[0], l[1])); });
    return box;
  }

  function review() {
    var list = visible(), wrap = h("div", "grid"), col = h("div", "list");
    if (!list.length) col.appendChild(h("div", "empty", "Nothing in this view. That is not evidence of no change: see Coverage."));
    list.forEach(function (i) {
      var b = btn("", "entry" + (state.sel === i.id ? " sel" : ""), function () { state.sel = i.id; draw(); });
      b.appendChild(tag(i)); b.appendChild(h("span", "", i.title)); b.appendChild(h("small", "", i.file));
      col.appendChild(b);
    });
    wrap.appendChild(col);
    wrap.appendChild(detail(data.items.filter(function (i) { return i.id === state.sel; })[0] || list[0]));
    return wrap;
  }
  function diffs() {
    var box = h("div"), any = false;
    data.items.forEach(function (i) {
      if (!i.diff.length) return; any = true;
      box.appendChild(h("h2", "", i.title)); box.appendChild(h("div", "mute", i.baseline)); box.appendChild(diffBox(i));
    });
    if (!any) box.appendChild(h("div", "empty", "No line diffs: baselines were not kept, or nothing changed. Diffs are bounded and secret-like strings are redacted."));
    return box;
  }
  function table(head, rows, mark) {
    var t = h("table"), tr = h("tr");
    head.forEach(function (x) { tr.appendChild(h("th", "", x)); }); t.appendChild(tr);
    rows.forEach(function (r) { var row = h("tr"); r.forEach(function (c) { row.appendChild(h("td", "", c)); }); if (mark && mark === r[0]) row.style.outline = "2px solid var(--acc)"; t.appendChild(row); });
    return t;
  }
  function timeline() {
    if (!data.timeline.length) return h("div", "empty", "No events recorded.");
    return h("div", "", "", h("p", "mute", "Order is not causation, consent or authorship."),
             table(["When", "Kind", "Event"], data.timeline.map(function (e) { return [e.when, e.kind, e.text]; })));
  }
  function evidence() {
    return table(["Id", "Source", "Reference", "Detail"], data.evidence.map(function (e) { return [e.id, e.source, e.ref, e.detail]; }), state.sel);
  }
  function header() {
    var b = data.baselines, c = data.coverage, top = h("div", "row top");
    top.appendChild(h("h1", "", "Track changes · " + data.analysis_path));
    var tools = h("div", "row");
    tools.appendChild(btn("Copy review brief", "", function () { copy(data.brief_md || ""); }));
    tools.appendChild(btn("Light / dark", "", function () { var r = document.documentElement; r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark"; }));
    top.appendChild(tools);
    var meta = h("div", "meta");
    [["Objective", (data.objective.text || "not stated") + (data.objective.source ? " (" + data.objective.source + ")" : "")],
     ["Original plan", b.original_plan || "none"], ["Current plan", b.current_plan || "none"],
     ["Focus", data.focus.active_at_snapshot ? "open" : "none"], ["Snapshot", data.generated_at]].forEach(function (p) {
      meta.appendChild(h("span", "", "", h("span", "mute", p[0] + " "), document.createTextNode(p[1])));
    });
    var note = h("div", "note", "Read-only evidence. This does not approve, freeze, run or validate anything. Not observed: " + c.not_observed.join(", ") + ".");
    var lim = c.limitations.length ? h("div", "note", "Coverage: " + c.limitations.join(" · ")) : null;
    var frag = h("div"); frag.appendChild(top); frag.appendChild(meta); frag.appendChild(note); if (lim) frag.appendChild(lim);
    return frag;
  }
  function controls() {
    var bar = h("div", "row tabs");
    [["review", "Review"], ["diff", "Diff"], ["timeline", "Timeline"], ["evidence", "Evidence"]].forEach(function (v) {
      bar.appendChild(btn(v[1], state.view === v[0] ? "on" : "", function () { state.view = v[0]; draw(); }));
    });
    if (state.view === "review") {
      [["attention", "Needs attention (" + data.counts.attention + ")"], ["all", "All"], ["authorized", "Authorized (" + data.counts.authorized + ")"], ["routine", "Routine (" + data.counts.routine + ")"]].forEach(function (f) {
        bar.appendChild(btn(f[1], state.filter === f[0] ? "on" : "", function () { state.filter = f[0]; draw(); }));
      });
      var q = h("input"); q.type = "search"; q.placeholder = "Search changes"; q.value = state.query;
      q.addEventListener("input", function () { state.query = q.value; var pos = q.selectionStart; draw(); var n = document.querySelector("input"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } });
      bar.appendChild(q);
    }
    return bar;
  }
  function draw() {
    while (app.firstChild) app.removeChild(app.firstChild);
    document.title = "Track changes · " + data.analysis_path;
    app.appendChild(header()); app.appendChild(controls());
    app.appendChild({review: review, diff: diffs, timeline: timeline, evidence: evidence}[state.view]());
  }
  draw();
})();
