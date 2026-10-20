// Journal navigation is presentation state only; no browser storage or network.
var journalState = {overview: true, query: "", period: "default", selected: null,
                    limit: 30, routine: false, expanded: true, listScroll: 0, mode: "history", concern: null};
function journal() {
  var j = data.journal, s = journalState, all = j.events;
  var box = h("main", "journal");
  function disclosure(title, child) {
    return h("details", "journal-disclosure", "", h("summary", "", title), child);
  }
  function para(label, value) { return h("p", "", label + ": " + (value || "not recorded")); }
  var last = j.checkpoints[j.checkpoints.length - 1];
  var sessions = all.filter(function (e) { return e.kind === "focus"; });
  var latestSession = sessions[sessions.length - 1];
  var baseline = last ? "Since checkpoint saved " + last.saved_at : latestSession ?
    "Latest recorded session, started " + latestSession.occurred_at : "Available history (no saved checkpoint or session)";
  function periodEvents() {
    if (s.period === "all") return all;
    if (last) return all.filter(function (e) { return last.event_ids.indexOf(e.id) < 0; });
    if (latestSession) return all.filter(function (e) {
      return !e.occurred_at || e.occurred_at >= latestSession.occurred_at;
    });
    return all;
  }
  function concern(e) {
    if (e.limitations.some(function (l) { return l.indexOf("Conflicting") >= 0; })) return "Conflicting or changed source copies";
    if (e.kind === "launch") return "Missing completion evidence";
    if (e.kind === "attempt") {
      if (e.detail.submission) return "Submission without recorded job completion";
      if (e.detail.exit_status !== 0) return e.summary === "failed attempt" ? "Failed attempts remain in history" : "Unknown attempt completion";
      if (e.detail.launch_match !== "matched") return "Launch attribution gaps";
    }
    return null;
  }
  var scope = periodEvents(), groups = {};
  scope.forEach(function (e) {
    var title = concern(e);
    if (title) (groups[title] || (groups[title] = [])).push(e);
    if (e.kind === "verification") {
      (e.detail.projection.findings || []).forEach(function (f) {
        if (f[0] === "gap" || f[0] === "block") {
          var key = f[0] + ": " + f[1];
          var found = groups[key] || (groups[key] = []);
          if (!found.some(function (other) { return other.id === e.id; })) found.push(e);
        }
      });
    }
  });
  var concerns = Object.keys(groups).sort(function (a, b) {
    function rank(t) { return t.indexOf("block:") === 0 ? 0 : /Conflicting|completion|Submission/.test(t) ? 1 : 2; }
    return rank(a) - rank(b) || a.localeCompare(b);
  });
  var serious = Object.keys(j.coverage).filter(function (k) {
    return ["partial", "absent", "malformed", "interrupted", "unsupported"].indexOf(j.coverage[k]) >= 0;
  });
  // Critical source and completion gaps stay visible even when the chosen period has no events.
  var conflicts = all.filter(function (e) { return e.limitations.some(function (l) { return l.indexOf("Conflicting") >= 0; }); }).length;
  var incomplete = all.filter(function (e) { return e.kind === "launch" || e.detail.submission; }).length;
  box.appendChild(h("h1", "title", j.analysis_path.split("/").pop()));
  box.appendChild(h("p", "lead", j.objective.text || "Recorded objective not available"));
  var periodLabel = s.period === "all" ? "All available history" : baseline;
  box.appendChild(h("p", "sub journal-context", periodLabel + " · Report generated " + data.generated_at));
  var controls = h("div", "journal-controls");
  var select = h("select");
  attr(select, "aria-label", "Historical period");
  [["default", baseline], ["all", "All available history"]].forEach(function (v) {
    var option = h("option", "", v[1]); option.value = v[0]; select.appendChild(option);
  });
  select.value = s.period;
  select.addEventListener("change", function () { s.period = select.value; s.limit = 30; renderBody(); });
  controls.appendChild(select);
  box.appendChild(controls);
  var coverage = h("div", "journal-coverage");
  coverage.appendChild(h("p", "", "Coverage: " + (serious.length ? serious.length + " source group(s) absent or incomplete" :
    "inspected sources available; history completeness not established") +
    (conflicts ? " · " + conflicts + " record(s) have conflicting or changed variants" : "") + (j.coverage.handoffs === "interrupted" ? " · publication interrupted" : "") + " · " + incomplete + " record(s) without their own completion evidence · Context is a saved snapshot; refresh to inspect later changes."));
  var covDetail = h("div");
  covDetail.appendChild(para("Refreshed", j.refreshed_at));
  Object.keys(j.coverage).sort().forEach(function (k) { covDetail.appendChild(para(k, j.coverage[k])); });
  covDetail.appendChild(para("Loaded records", all.length + "; collection omissions " + j.collection.omitted));
  j.limitations.forEach(function (l) { covDetail.appendChild(h("p", "", l)); });
  j.checkpoints.forEach(function (c) {
    covDetail.appendChild(disclosure("Coverage observed at checkpoint " + c.saved_at,
      h("pre", "", JSON.stringify(c.source_coverage, null, 2))));
  });
  coverage.appendChild(disclosure("Inspect source coverage and freshness", covDetail));
  box.appendChild(coverage);
  if (s.overview) {
    var verification = all.filter(function (e) { return e.kind === "verification"; }).sort(function (a, b) {
      return (a.observed_at || "").localeCompare(b.observed_at || "");
    });
    var latest = verification[verification.length - 1], projection = latest && latest.detail.projection;
    var tied = latest ? verification.filter(function (e) { return e.observed_at === latest.observed_at; }) : [];
    function outcomes(key) {
      return Array.from(new Set(tied.map(function (e) {
        var p = e.detail.projection; return key === "qualification" ? (p.qualification || {}).overall || "not available" : p.conformity;
      }))).join("; ");
    }
    var assessment = latest ? " · saved observation " + (latest.observed_at || "time not recorded") : "";
    box.appendChild(para("Latest recorded conformity", projection ? outcomes("conformity") + assessment : "not available"));
    box.appendChild(para("Latest recorded qualification", projection && projection.qualification ?
      outcomes("qualification") + assessment : "not available"));
    if (tied.length > 1) box.appendChild(h("p", "fine", latest.observed_at ? "Multiple saved observations share this time; their order is not established." : "Multiple saved observations have no recorded observation time; their order is not established."));
    if (latest) box.appendChild(h("p", "fine", "Assessment computation time was not separately recorded. Saved time is not output production time."));
    var priorities = h("div", "journal-priorities");
    priorities.appendChild(h("h2", "", "Priority concerns"));
    if (!concerns.length) priorities.appendChild(h("p", "", "No priority concerns found in the inspected records"));
    concerns.slice(0, 3).forEach(function (title) {
      var es = groups[title];
      var label = title.replace(/[0-9a-f]{16,}/g, "[identifier in evidence]");
      if (label.length > 110) label = label.slice(0, 107) + "…";
      var b = btn(label + " · " + es.length + " observation(s). Inspect the recorded evidence.", "journal-concern", function () {
        s.selected = es[0].id; s.concern = title; s.mode = "concerns"; s.overview = false; s.expanded = true; renderBody();
      });
      priorities.appendChild(b);
    });
    box.appendChild(priorities);
    box.appendChild(btn("Show all " + concerns.length + " concerns", "btn", function () {
      s.overview = false; s.mode = "concerns"; s.routine = false; renderBody();
    }));
    box.appendChild(btn("Explore history · " + scope.length + " records", "btn", function () {
      s.overview = false; s.mode = "history"; renderBody();
    }));
    box.appendChild(h("p", "fine", "Routine records are collapsed. Search and JSON export include all " + all.length + " loaded records."));
    return box;
  }
  box.appendChild(btn("Back to overview", "btn", function () { s.overview = true; renderBody(); }));
  var expandControl = btn(s.expanded ? "Collapse detail" : "Expand detail", "btn", function () {
    s.expanded = !s.expanded; renderBody();
  });
  attr(expandControl, "aria-expanded", String(s.expanded)); box.appendChild(expandControl);
  var search = h("input", "search"); search.type = "search"; search.value = s.query;
  attr(search, "aria-label", "Search all loaded journal records, including collapsed history");
  search.placeholder = "Search all loaded history";
  // Only redraw results, keeping the focused search input in place.
  box.appendChild(search);
  var resultMount = h("div"); box.appendChild(resultMount);
  function results() {
    clear(resultMount);
    var q = s.query.toLowerCase();
    var filtered = (q ? all : scope).filter(function (e) { return !q || JSON.stringify(e).toLowerCase().indexOf(q) >= 0; });
    var routineCount = filtered.filter(function (e) { return !concern(e) && e.kind !== "verification"; }).length;
    var routineControl = btn((s.routine ? "Collapse" : "Show") + " routine records (" + routineCount + ")", "btn", function () {
      s.routine = !s.routine; s.mode = "history"; results();
    });
    attr(routineControl, "aria-expanded", String(s.routine)); resultMount.appendChild(routineControl);
    var visible = filtered.filter(function (e) { return q || s.routine || concern(e) || e.kind === "verification" || e.id === s.selected; });
    resultMount.appendChild(h("p", "fine", (q ? "Search covers all loaded periods. " : "") +
      "Showing " + Math.min(s.limit, visible.length) + " of " + visible.length + " matching records; " +
      (filtered.length - visible.length) + " routine records collapsed; " + j.collection.omitted + " collection omissions."));
    var flow = h("div", "journal-flow"), list = h("div", "journal-list");
    attr(list, "aria-label", "Historical records");
    if (!q && s.mode === "concerns") {
      resultMount.appendChild(h("p", "fine", "All " + concerns.length + " distinct concern(s); repeated observations grouped."));
      concerns.forEach(function (title) {
        var b = btn(title + " · " + groups[title].length + " observation(s)", "journal-concern", function () {
          s.selected = groups[title][0].id; s.concern = title; s.expanded = true; results();
        });
        list.appendChild(b);
      });
    }
    (q || s.mode !== "concerns" ? visible.slice(0, s.limit) : []).forEach(function (e) {
      var b = btn(e.summary + " · " + (e.occurred_at || "occurrence time unknown"), "journal-event", function () {
        s.listScroll = list.scrollTop || 0; s.selected = e.id; s.concern = null; s.expanded = true; results();
      });
      attr(b, "aria-pressed", s.selected === e.id ? "true" : "false"); list.appendChild(b);
    });
    if ((q || s.mode !== "concerns") && visible.length > s.limit) list.appendChild(btn("Show next " + Math.min(30, visible.length - s.limit) + " records", "btn", function () {
      s.listScroll = list.scrollTop || 0; s.limit += 30; results();
    }));
    list.addEventListener("scroll", function () { s.listScroll = list.scrollTop; });
    flow.appendChild(list);
    var selected = all.filter(function (e) { return e.id === s.selected; })[0];
    var detailBox = h("section", "journal-detail");
    attr(detailBox, "aria-label", "Selected record");
    if (!selected) detailBox.appendChild(h("p", "", "Select a concern or event to inspect its evidence."));
    else if (!s.expanded) detailBox.appendChild(h("p", "", selected.summary + " · detail collapsed"));
    else {
      var e = selected;
      detailBox.appendChild(h("h2", "", e.summary));
      detailBox.appendChild(para("Observation", s.concern || e.summary));
      detailBox.appendChild(para("Recorded outcome", e.kind === "verification" ? e.detail.projection.conformity :
        e.detail.submission ? "submission; completion unknown" : e.detail.exit_status === undefined ? "see recorded evidence" : String(e.detail.exit_status)));
      detailBox.appendChild(para("Context", e.references.plan ? "Recorded plan " + e.references.plan : (e.references.plans || []).length > 1 ? "Multiple recorded plans; see evidence" : "Plan attribution not established"));
      if (e.references.attempt) detailBox.appendChild(para("Attempt", String(e.references.attempt).slice(0, 8) + " (full reference in evidence)"));
      if (e.references.instance) detailBox.appendChild(para("Approval instance", String(e.references.instance).slice(0, 8) + " (full reference in evidence)"));
      var checkpoint = j.checkpoints.find(function (c) { return (e.sources || []).indexOf(c.path) >= 0; });
      if (checkpoint) detailBox.appendChild(para("Preserved observation", "Checkpoint saved " + checkpoint.saved_at));
      detailBox.appendChild(para("Source availability", e.original_evidence));
      detailBox.appendChild(para("Potential implication", "This record may limit what can be established from the evidence; scientific impact is not assessed."));
      detailBox.appendChild(para("Unknowns", e.unknown));
      detailBox.appendChild(h("p", "fine", "Primary inspection: open Evidence and provenance below."));
      if (s.concern && groups[s.concern] && groups[s.concern].length > 1) {
        var related = h("div");
        groups[s.concern].forEach(function (other) {
          related.appendChild(btn(other.summary + " · " + (other.occurred_at || "occurrence time unknown"), "btn", function () {
            s.selected = other.id; results();
          }));
        });
        detailBox.appendChild(disclosure("Related observations and variants (" + groups[s.concern].length + ")", related));
      }
      var evidenceBox = h("div");
      evidenceBox.appendChild(para("Occurrence", e.occurred_at));
      evidenceBox.appendChild(para("Time basis", e.timestamp_basis));
      evidenceBox.appendChild(para("Earliest available saved observation", e.observed_at));
      evidenceBox.appendChild(para("Original evidence", e.original_evidence));
      (e.sources || []).forEach(function (p) {
        evidenceBox.appendChild(para("Source (repository relative; copy to inspect)", p));
        evidenceBox.appendChild(copyButton("Copy source path", p, "btn"));
      });
      evidenceBox.appendChild(h("pre", "", JSON.stringify(e.detail, null, 2)));
      detailBox.appendChild(disclosure("Evidence and provenance (" + (e.sources || []).length + " references)", evidenceBox));
      var limitationBox = h("div");
      e.limitations.concat(j.limitations).forEach(function (l) { limitationBox.appendChild(h("p", "", l)); });
      detailBox.appendChild(disclosure("Coverage limitations (" + (e.limitations.length + j.limitations.length) + ")", limitationBox));
      detailBox.appendChild(disclosure("Technical metadata (identities and independent axes)", h("pre", "", JSON.stringify({
        id: e.id, source_identity: e.source_identity, source_digest: e.source_digest, references: e.references,
        attribution: e.attribution, difference: e.difference, authorization: e.authorization_relation
      }, null, 2))));
      if (j.note_observations.length) {
        var noteBox = h("div");
        j.note_observations.forEach(function (n) { noteBox.appendChild(para("Researcher note (reference only)",
          n.reference + " · " + n.current_status + (n.changed ? " · changed since saved reference" : ""))); });
        detailBox.appendChild(disclosure("Note references (" + j.note_observations.length + ")", noteBox));
      }
    }
    flow.appendChild(detailBox); resultMount.appendChild(flow); list.scrollTop = s.listScroll;
  }
  search.addEventListener("input", function () { s.query = search.value; s.limit = 30; results(); });
  results();
  return box;
}
