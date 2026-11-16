/* Freelancer dashboard: composes data from GET /freelancers/{id}, /projects, /applications/my */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data, user = UI.Auth.user();
  var $ = function (id) { return document.getElementById(id); };
  var profile = null;

  $("hello").textContent = Data.greeting() + ", " + Data.firstName(user.name);
  UI.showLoading($("statRow"), "stats", 4);
  UI.showLoading($("recs"), "list", 3);
  UI.showLoading($("activity"), "list", 2);

  function renderProfile(p) {
    var c = Data.completion(p);
    $("pcScore").textContent = c.score + "%";
    $("pcBar").style.width = c.score + "%";
    var missing = c.checks.filter(function (x) { return !x.ok; });
    $("pcList").innerHTML = missing.length ? missing.slice(0, 4).map(function (m) {
      return '<li><a href="' + (m.link || "profile.html") + '">' + UI.icon("circle-alert", 15) + m.label + "</a></li>";
    }).join("") : '<li class="muted">' + UI.icon("badge-check", 15) + " Your profile is complete.</li>";
    $("pcRating").innerHTML = p.avg_rating ? UI.stars(p.avg_rating) + ' <span class="small text-2 num">' + Number(p.avg_rating).toFixed(1) + (p.reviews_count ? " · " + p.reviews_count + " reviews" : "") + "</span>" : '<span class="small muted">No ratings yet</span>';
  }

  function renderStats(apps, total) {
    var by = Data.byStatus(apps);
    var cards = [
      ["briefcase", "Open projects", window.__openTotal != null ? window.__openTotal : "—", "available to apply for"],
      ["file-text", "Applications", total, by.pending + " awaiting a response"],
      ["user-check", "Shortlisted or hired", by.shortlisted + by.accepted, by.accepted + " active engagement" + (by.accepted === 1 ? "" : "s")],
      ["folder-check", "Completed works", by.completed, "delivered to clients"]
    ];
    $("statRow").innerHTML = cards.map(function (s) {
      return '<div class="panel stat"><div class="k">' + UI.icon(s[0], 16) + s[1] + '</div><div class="v">' + s[2] + '</div><div class="s">' + s[3] + "</div></div>";
    }).join("");
    var total2 = apps.length || 1, colors = { pending: "#a8730f", shortlisted: "#2f5f8f", accepted: "#1f7a55", completed: "#0e6b6b", rejected: "#9a4a3f" };
    $("statusBar").innerHTML = apps.length ? Object.keys(colors).map(function (k) { return by[k] ? '<i style="width:' + (by[k] / total2 * 100) + "%;background:" + colors[k] + '" title="' + k + '"></i>' : ""; }).join("") : "";
    $("statusLegend").innerHTML = apps.length ? Object.keys(colors).map(function (k) { return '<span style="--c:' + colors[k] + '">' + (k === "accepted" ? "Hired" : k[0].toUpperCase() + k.slice(1)) + " " + by[k] + "</span>"; }).join("") : '<span class="muted" style="--c:transparent">No applications yet</span>';
  }

  function renderActivity(apps) {
    var list = apps.slice().sort(function (a, b) { return new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0); }).slice(0, 5);
    if (!list.length) return UI.showEmpty($("activity"), { icon: "send", title: "No applications yet", text: "Applications you send will show up here with live status updates.", href: "projects.html", action: "Find a project" });
    $("activity").removeAttribute("aria-busy");
    $("activity").innerHTML = '<ul class="list">' + list.map(function (a) {
      var p = Data.appProject(a);
      return '<li><div class="grow"><a class="title" href="project-details.html?id=' + UI.esc(p.id) + '">' + UI.esc(p.title) + '</a><span class="small muted">' + (p.client ? UI.esc(p.client) + " · " : "") + "Updated " + UI.relTime(a.updated_at || a.created_at) + "</span></div>" + UI.statusBadge(a.status) + "</li>";
    }).join("") + "</ul>";
  }

  function renderRecs(projects, apps) {
    var applied = apps.map(function (a) { return Data.appProject(a).id; });
    var mine = (profile && profile.skills) || [];
    var list = projects.filter(function (p) { return applied.indexOf(p.id) < 0; }).map(function (p) { return { p: p, n: Data.overlap(mine, p.skills).length }; })
      .sort(function (a, b) { return b.n - a.n; }).slice(0, 4);
    if (!list.length) return UI.showEmpty($("recs"), { icon: "compass", title: "No open projects right now", text: "New projects appear here as clients post them.", href: "projects.html", action: "Open marketplace" });
    $("recs").removeAttribute("aria-busy");
    $("recs").innerHTML = '<ul class="list">' + list.map(function (x, i) {
      var b = UI.budget(x.p);
      return '<li style="align-items:flex-start"><div class="grow"><a class="title" style="white-space:normal" href="project-details.html?id=' + UI.esc(x.p.id) + '">' + UI.esc(x.p.title) + '</a><div class="small muted" style="margin:2px 0 8px">' + UI.esc(b.text) + " · " + b.sub + (x.p.deadline ? " · Due " + UI.fmtDate(x.p.deadline) : "") + "</div>" + UI.skillTags((x.p.skills || []).slice(0, 4), mine) + '</div><div style="text-align:right;display:grid;gap:8px;justify-items:end"><span data-slot="' + i + '"></span><a class="btn btn-secondary btn-sm" href="project-details.html?id=' + UI.esc(x.p.id) + '#apply">Apply</a></div></li>';
    }).join("") + "</ul>";
    list.forEach(function (x, i) { UI.matchChip($("recs").querySelector('[data-slot="' + i + '"]'), user.id, x.p.id, x.p.title); });
  }

  var state = { projects: null, apps: null };
  function load() {
    UI.showLoading($("recs"), "list", 3); UI.showLoading($("activity"), "list", 2);
    Promise.allSettled([Api.freelancers.get(user.id), Api.projects.list({ status: "open", limit: 30 }), Api.applications.mine({ limit: 100 })]).then(function (r) {
      if (r[0].status === "fulfilled") { profile = r[0].value; renderProfile(profile); $("hello").textContent = Data.greeting() + ", " + Data.firstName(profile.name || user.name); }
      else { $("pcScore").textContent = "—"; $("pcList").innerHTML = '<li class="muted">Couldn\'t load your profile.</li>'; }
      var apps = [], total = 0;
      if (r[2].status === "fulfilled") { var l = Api.asList(r[2].value); apps = l.items; total = l.total; renderStats(apps, total); renderActivity(apps); }
      else { UI.showError($("statRow"), r[2].reason, load); $("statRow").style.display = "block"; UI.showError($("activity"), r[2].reason, load); }
      if (r[1].status === "fulfilled") { var pl = Api.asList(r[1].value); window.__openTotal = pl.total; if (r[2].status === "fulfilled") { renderStats(apps, total); renderRecs(pl.items, apps); } else renderRecs(pl.items, []); }
      else UI.showError($("recs"), r[1].reason, load);
      var done = apps.filter(function (a) { return a.status === "completed"; }).slice(0, 3);
      $("doneList").innerHTML = done.length ? '<ul class="list">' + done.map(function (a) { var p = Data.appProject(a); return '<li><div class="grow"><span class="title">' + UI.esc(p.title) + '</span><span class="small muted">' + (a.rating ? "Rated " + Number(a.rating).toFixed(1) + " / 5" : "Awaiting client rating") + "</span></div>" + UI.icon("badge-check", 18) + "</li>"; }).join("") + "</ul>" : '<p class="small muted" style="padding:16px 20px">Completed projects will be listed here.</p>';
      var sub = apps.length ? "You have " + Data.byStatus(apps).pending + " application" + (Data.byStatus(apps).pending === 1 ? "" : "s") + " waiting on a client." : "Complete your profile, then apply to your first project.";
      $("heroSub").textContent = r[2].status === "fulfilled" ? sub : "We couldn't reach the server, so some figures are unavailable.";
    });
  }
  load();
})();
