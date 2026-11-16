/* Client: manage applicants for a project.
   GET /applications/my (client role → applications on own projects), GET /projects, PUT /applications/{id}/status */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data;
  var $ = function (i) { return document.getElementById(i); };
  var projects = [], apps = [], projectId = UI.qs("project") || "", tab = "all", sortBy = "recent", runners = [];

  function load() {
    UI.showLoading($("list"), "list", 3);
    Promise.all([Api.projects.list({ mine: "true", limit: 100 }), Api.applications.mine({ limit: 500 })]).then(function (r) {
      projects = Api.asList(r[0]).items;
      apps = Api.asList(r[1]).items.filter(function (a) { return a.status !== "withdrawn"; });
      if (!projectId && projects.length) projectId = projects[0].id;
      $("projectSel").innerHTML = '<option value="">All projects</option>' + projects.map(function (p) { return '<option value="' + UI.esc(p.id) + '">' + UI.esc(p.title) + "</option>"; }).join("");
      $("projectSel").value = projectId;
      render();
    }).catch(function (e) { $("tabs").innerHTML = ""; UI.showError($("list"), e, load); });
  }

  function render() {
    var scoped = apps.filter(function (a) { return !projectId || Data.appProject(a).id === projectId; });
    var by = Data.byStatus(scoped), q = $("q").value.trim().toLowerCase();
    var T = [["all", "All"], ["pending", "Pending"], ["shortlisted", "Shortlisted"], ["accepted", "Hired"], ["rejected", "Declined"]];
    $("tabs").innerHTML = T.map(function (t) { return '<button role="tab" aria-selected="' + (tab === t[0]) + '" data-tab="' + t[0] + '">' + t[1] + '<span class="count">' + (t[0] === "all" ? scoped.length : by[t[0]]) + "</span></button>"; }).join("");
    $("tabs").querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { tab = b.dataset.tab; render(); }); });
    var list = scoped.filter(function (a) { var f = Data.appFreelancer(a); return (tab === "all" || a.status === tab) && (!q || (f.name + " " + f.headline + " " + ((f.raw.skills || []).join(" "))).toLowerCase().indexOf(q) > -1); });
    list.sort(function (a, b) { return sortBy === "bid" ? (a.bid_amount || 1e15) - (b.bid_amount || 1e15) : new Date(b.created_at || 0) - new Date(a.created_at || 0); });
    var host = $("list"); runners = [];
    $("analyseAll").disabled = !list.length;
    if (!projects.length) return UI.showEmpty(host, { icon: "briefcase", title: "Post a project to receive applicants", text: "Applicants for your projects will appear here.", href: "post-project.html", action: "Post a project" });
    if (!list.length) return UI.showEmpty(host, { icon: "users", title: scoped.length ? "No applicants in this view" : "No applicants yet", text: scoped.length ? "Try a different status or search term." : "Proposals will appear here as soon as freelancers apply." });
    host.removeAttribute("aria-busy");
    host.innerHTML = list.map(function (a, i) {
      var f = Data.appFreelancer(a), p = Data.appProject(a), fr = f.raw;
      var common = Data.overlap(fr.skills, (projects.filter(function (x) { return x.id === p.id; })[0] || {}).skills);
      return '<div class="applicant"><a href="profile.html?id=' + UI.esc(f.id) + '">' + UI.avatar(f.name, "", fr.avatar_url) + '</a><div style="min-width:0"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><a class="title" style="font-weight:600;font-size:1rem" href="profile.html?id=' + UI.esc(f.id) + '">' + UI.esc(f.name) + "</a>" + UI.statusBadge(a.status) + '</div><div class="small text-2">' + UI.esc(f.headline) + '</div><div class="small muted" style="margin-top:4px;display:flex;gap:14px;flex-wrap:wrap">' +
        (fr.avg_rating ? "<span>" + UI.stars(fr.avg_rating) + " " + Number(fr.avg_rating).toFixed(1) + "</span>" : "") + (fr.years_experience != null ? "<span>" + fr.years_experience + " yrs experience</span>" : "") + (!projectId ? "<span>for " + UI.esc(p.title) + "</span>" : "") + "<span>Applied " + UI.relTime(a.created_at) + "</span></div>" +
        (fr.skills && fr.skills.length ? '<div style="margin-top:10px">' + UI.skillTags(fr.skills.slice(0, 6), common) + "</div>" : "") +
        (a.cover_letter ? '<div class="cover" data-cover="' + i + '">' + UI.esc(a.cover_letter) + '</div><button class="btn btn-ghost btn-sm" style="margin-top:4px" data-expand="' + i + '">Read full proposal</button>' : "") +
        '<div class="applicant-match" data-slot="' + i + '"></div></div><div class="applicant-side"><div style="text-align:right">' + (a.bid_amount != null ? '<div class="job-budget num" style="font-size:1.25rem">' + UI.fmtMoney(a.bid_amount, a.currency) + "</div>" : "") + (a.delivery_days ? '<div class="small muted">in ' + a.delivery_days + " days</div>" : "") + "</div>" + actions(a, i) + "</div></div>";
    }).join("");
    list.forEach(function (a, i) { var f = Data.appFreelancer(a); var run = UI.matchChip(host.querySelector('[data-slot="' + i + '"]'), f.id, Data.appProject(a).id, f.name); if (run) runners.push(run); });
    host.querySelectorAll("[data-expand]").forEach(function (b) { b.addEventListener("click", function () { var c = host.querySelector('[data-cover="' + b.dataset.expand + '"]'); var o = c.classList.toggle("open"); b.textContent = o ? "Show less" : "Read full proposal"; }); });
    host.querySelectorAll("[data-act]").forEach(function (b) { b.addEventListener("click", function () { act(list[+b.dataset.i], b.dataset.act, b); }); });
  }

  function actions(a, i) {
    var b = function (act, label, cls, ic) { return '<button class="btn ' + cls + ' btn-sm" data-act="' + act + '" data-i="' + i + '">' + UI.icon(ic, 14) + label + "</button>"; };
    if (a.status === "withdrawn") return "";
    if (a.status === "pending") return b("accepted", "Hire", "btn-primary", "user-check") + b("shortlisted", "Shortlist", "btn-secondary", "list-checks") + b("rejected", "Decline", "btn-danger", "user-x");
    if (a.status === "shortlisted") return b("accepted", "Hire", "btn-primary", "user-check") + b("rejected", "Decline", "btn-danger", "user-x");
    if (a.status === "accepted") return '<a class="btn btn-secondary btn-sm" href="hiring.html">' + UI.icon("handshake", 14) + "Hiring &amp; tracking</a>";
    return "";
  }
  function act(a, status, btn) {
    if (!a || a.status === "withdrawn" || (a.status !== "pending" && a.status !== "shortlisted")) return;
    var f = Data.appFreelancer(a), verb = { accepted: "Hire", rejected: "Decline", shortlisted: "Shortlist" }[status];
    var go = function () {
      UI.busy(btn, Api.applications.updateStatus(a.id, status).then(function () { a.status = status; UI.toast(f.name + " — " + { accepted: "hired", rejected: "declined", shortlisted: "shortlisted" }[status] + ".", "success"); render(); })).catch(function (e) { UI.toast(e.isNetwork ? "Can't reach the server. Status was not changed." : e.message, "error"); });
    };
    if (status === "shortlisted") return go();
    UI.confirm({ title: verb + " " + f.name + "?", body: status === "accepted" ? "This starts the engagement and notifies the freelancer." : "The freelancer will be told their application was not selected.", confirm: verb, danger: status === "rejected" }).then(function (ok) { if (ok) go(); });
  }

  $("projectSel").addEventListener("change", function () { projectId = this.value; tab = "all"; history.replaceState(null, "", projectId ? "?project=" + encodeURIComponent(projectId) : "applicants.html"); render(); });
  $("q").addEventListener("input", function () { if (apps.length) render(); });
  $("sortSel").addEventListener("change", function () { sortBy = this.value; render(); });
  $("analyseAll").addEventListener("click", function () { runners.forEach(function (r) { r(); }); });
  load();
})();
